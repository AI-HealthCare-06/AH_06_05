"""O-1 ~ O-5 — 업로드 · 작업 상태 · 인식 결과 · 수정 · 약 이름 검색 (CLOVA는 저장해 둔 가짜 처방전 결과로 대신함)"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.masters import Disease, DrugProduct
from app.models.ocr import MatchStatus, OcrJob, Prescription, PrescriptionItem, PrescriptionItemCandidate
from app.models.users import ConsentType, User, UserConsent
from app.services import prescriptions as svc
from app.services.ocr import clova, llm_fix
from app.tests.helpers import signup

JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PRODUCTS = [
    ("641900040", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "한국화이자제약(주)"),
    ("644300010", "다이아벡스정500밀리그램(메트포르민염산염)_(0.5g/1정)", "한국비엠에스제약(주)"),
    ("645600020", "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)_(10.85mg/1정)", "한국화이자제약(주)"),
    ("648800030", "아스피린프로텍트정100밀리그람_(0.1g/1정)", "바이엘코리아(주)"),
]


def jpeg_of_size(w: int, h: int, tail: bytes = b"") -> bytes:
    """머리말에 크기만 들어 있는 JPEG (OCR은 가짜로 바꿔 쓰므로 그림 내용은 필요 없음)"""
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = (
        b"\xff\xc0\x00\x11\x08"
        + h.to_bytes(2, "big")
        + w.to_bytes(2, "big")
        + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    )
    return b"\xff\xd8" + app0 + sof + b"\xff\xda\x00\x0c" + b"0" * 40 + tail


def with_days(sample: dict, old: str, new: str) -> dict:
    """처방전 결과에서 첫 번째로 나오는 숫자 칸 하나만 바꿈 (숫자 한 글자만 다른 처방전)"""
    out = json.loads(json.dumps(sample))
    for f in out["images"][0]["fields"]:
        if f["inferText"] == old:
            f["inferText"] = new
            return out
    raise AssertionError(f"{old} 칸을 못 찾음")


async def seed_masters() -> None:
    for edi, name, company in PRODUCTS:
        await DrugProduct.create(edi_code=edi, item_name=name, entp_name=company, etc_otc="전문", route="내복")
    for code, name in (("I10", "본태성 고혈압"), ("E11", "2형 당뇨병"), ("L10", "천포창")):
        await Disease.create(code=code, name_kr=name)
    svc.reset_caches()


class OcrApiCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await seed_masters()

    async def asyncTearDown(self):
        svc.reset_caches()
        await super().asyncTearDown()

    @staticmethod
    def client() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @staticmethod
    async def auth(client: AsyncClient, email: str, **overrides) -> dict[str, str]:
        tokens = await signup(client, email, **overrides)
        return {"Authorization": f"Bearer {tokens['accessToken']}"}

    @staticmethod
    async def upload(client: AsyncClient, headers: dict[str, str], n: int = 1):
        files = [("files", (f"p{i}.jpg", JPG + bytes([i]), "image/jpeg")) for i in range(n)]
        return await client.post("/api/v1/prescriptions", files=files, headers=headers)


class TestUploadAndJob(OcrApiCase):
    async def test_upload_reads_prescription_and_saves_items(self):
        async with self.client() as client:
            headers = await self.auth(client, "o1@example.com")
            res = await self.upload(client, headers)
            assert res.status_code == status.HTTP_202_ACCEPTED
            assert res.json()["status"] == "queued"
            job = (await client.get(f"/api/v1/ocr-jobs/{res.json()['jobId']}", headers=headers)).json()
            assert job["status"] == "done" and job["failedFiles"] == [] and len(job["prescriptionIds"]) == 1
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()

        assert rx["docType"] == "prescription" and rx["issuedDate"] == "2026-10-01"
        assert rx["hospitalName"].startswith("가나다내과의원")
        # 110은 I10 · L10 중 무엇인지 모르고 글자 확실도도 낮아서 조용히 고치지 않고 비워 둠 → 사용자가 고름 (RG-05-E1)
        assert rx["diseaseCodes"] == []
        assert [i["matchStatus"] for i in rx["items"]] == ["auto"] * 4
        first = rx["items"][0]
        assert first["ediCode"] == "641900040" and first["itemName"] == "노바스크정5밀리그람(암로디핀베실산염)"
        assert (first["dosePerTime"], first["timesPerDay"], first["totalDays"]) == (1, 1, 30)
        assert first["timing"] == "식후 30분 복용" and first["candidates"] == [] and first["checkFields"] == []
        assert rx["items"][1]["timesPerDay"] == 2

    async def test_two_photos_make_two_prescriptions_in_order(self):
        second = with_days(json.loads(clova.SAMPLE.read_text(encoding="utf-8")), "30", "28")  # 일수만 다른 처방전
        calls = iter([json.loads(clova.SAMPLE.read_text(encoding="utf-8")), second])

        async def fake(content, fmt, name):
            return next(calls)

        async with self.client() as client:
            headers = await self.auth(client, "o2@example.com")
            with patch.object(clova, "recognize", fake):
                job_id = (await self.upload(client, headers, n=2)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["status"] == "done" and len(job["prescriptionIds"]) == 2
        assert job["prescriptionIds"] == sorted(job["prescriptionIds"])

    async def test_validation_errors_are_400_with_file_index(self):
        async with self.client() as client:
            headers = await self.auth(client, "o3@example.com")
            many = await self.upload(client, headers, n=6)
            assert many.status_code == 400 and many.json()["error"]["code"] == "TOO_MANY_FILES"
            text = await client.post(
                "/api/v1/prescriptions",
                files=[("files", ("a.jpg", JPG, "image/jpeg")), ("files", ("b.txt", b"hello", "text/plain"))],
                headers=headers,
            )
            assert text.status_code == 400
            err = text.json()["error"]
            assert err["code"] == "FILE_TYPE_NOT_SUPPORTED" and err["detail"] == {"fileIndex": 2}
            with patch.object(svc, "MAX_BYTES", 50):
                big = await self.upload(client, headers)
            assert big.status_code == 400 and big.json()["error"]["code"] == "FILE_TOO_LARGE"
            none = await client.post("/api/v1/prescriptions", headers=headers)
            assert none.status_code == 400 and none.json()["error"]["code"] == "VALIDATION_ERROR"
        assert await OcrJob.all().count() == 0  # 검사에서 막히면 작업을 만들지 않음

    async def test_auth_and_consent(self):
        async with self.client() as client:
            assert (await self.upload(client, {})).status_code == 401
            headers = await self.auth(client, "o4@example.com")
            # 민감정보 동의를 철회하면 업로드 불가
            user = await User.get(login_id="o4@example.com")
            await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(
                agreed=False, withdrawn_at=datetime.now(UTC)
            )
            res = await self.upload(client, headers)
        assert res.status_code == 403 and res.json()["error"]["code"] == "CONSENT_REQUIRED"

    async def test_other_users_data_is_404(self):
        async with self.client() as client:
            mine = await self.auth(client, "o5@example.com")
            other = await self.auth(client, "o6@example.com")
            job_id = (await self.upload(client, mine)).json()["jobId"]
            rx_id = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=mine)).json()["prescriptionIds"][0]
            assert (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=other)).status_code == 404
            assert (await client.get(f"/api/v1/prescriptions/{rx_id}", headers=other)).status_code == 404
            item_id = (await client.get(f"/api/v1/prescriptions/{rx_id}", headers=mine)).json()["items"][0]["id"]
            res = await client.patch(
                f"/api/v1/prescriptions/{rx_id}/items/{item_id}", json={"exclude": True}, headers=other
            )
        assert res.status_code == 404
        assert (await PrescriptionItem.get(id=item_id)).match_status == MatchStatus.AUTO

    async def read_with(self, client, headers, photos, results):
        """photos: [bytes] → 올리고, 가짜 OCR이 불린 횟수와 작업 결과를 돌려줌"""
        calls = []
        it = iter(results)

        async def fake(content, fmt, name):
            calls.append(content)
            return next(it)

        files = [("files", (f"p{i}.jpg", b, "image/jpeg")) for i, b in enumerate(photos)]
        with patch.object(clova, "recognize", fake):
            res = await client.post("/api/v1/prescriptions", files=files, headers=headers)
        job = (await client.get(f"/api/v1/ocr-jobs/{res.json()['jobId']}", headers=headers)).json()
        return len(calls), job

    async def test_tiny_photo_is_not_sent_to_ocr(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc1@example.com")
            n, job = await self.read_with(client, headers, [jpeg_of_size(291, 400)], [sample])
        assert n == 0 and job["prescriptionIds"] == []
        assert job["failedFiles"] == [{"fileIndex": 1, "code": "IMAGE_QUALITY_LOW"}] and job["status"] == "done"

    async def test_blurry_photo_is_not_sent_to_ocr_and_sharp_one_is(self):
        from app.tests.ocr_pipeline.test_precheck import _page

        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc5@example.com")
            n, job = await self.read_with(client, headers, [_page(), _page(blur=4)], [sample])
        assert n == 1 and len(job["prescriptionIds"]) == 1
        assert job["failedFiles"] == [{"fileIndex": 2, "code": "IMAGE_QUALITY_LOW"}] and job["status"] == "done"

    async def test_normal_size_and_unknown_header_still_go_to_ocr(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc2@example.com")
            n, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            assert n == 1 and len(job["prescriptionIds"]) == 1
            # 머리말을 읽을 수 없는 사진은 걸러 내지 않고 OCR에 맡김 (정상 사진을 잘못 막는 것이 더 나쁨)
            n, job = await self.read_with(client, headers, [JPG], [sample])
            assert n == 1 and len(job["prescriptionIds"]) == 1

    async def test_exactly_same_file_is_read_once(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        photo = jpeg_of_size(1200, 1600)
        async with self.client() as client:
            headers = await self.auth(client, "pc3@example.com")
            n, job = await self.read_with(client, headers, [photo, photo], [sample, sample])
        assert n == 1 and len(job["prescriptionIds"]) == 1 and job["failedFiles"] == [] and job["status"] == "done"
        assert job["duplicatedFiles"] == [{"fileIndex": 2, "prescriptionId": job["prescriptionIds"][0]}]

    async def test_reupload_on_another_day_reuses_existing_record(self):
        """수인님 결정(10/14): 이미 올린 처방전이면 새로 저장하지 않고 기존 기록을 쓰게 안내"""
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc7@example.com")
            _, first = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            _, second = await self.read_with(client, headers, [jpeg_of_size(1200, 1600, b"later")], [sample])
            other = await self.auth(client, "pc8@example.com")  # 다른 사용자의 기록은 같은 처방전이어도 건드리지 않음
            _, third = await self.read_with(client, other, [jpeg_of_size(1200, 1600, b"o")], [sample])
        rx_id = first["prescriptionIds"][0]
        assert first["duplicatedFiles"] == []
        assert second["prescriptionIds"] == [rx_id]  # 새 기록 없이 기존 처방전 ID
        assert second["duplicatedFiles"] == [{"fileIndex": 1, "prescriptionId": rx_id}]
        assert second["failedFiles"] == [] and second["status"] == "done"
        assert await Prescription.filter(user__login_id="pc7@example.com").count() == 1
        assert third["prescriptionIds"] != [rx_id] and third["duplicatedFiles"] == []
        assert await Prescription.filter(user__login_id="pc8@example.com").count() == 1

    async def test_changed_prescription_is_not_treated_as_duplicate(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        changed = with_days(sample, "30", "28")  # 일수만 다른 다른 처방전
        async with self.client() as client:
            headers = await self.auth(client, "pc9@example.com")
            _, first = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            _, second = await self.read_with(client, headers, [jpeg_of_size(1200, 1600, b"d")], [changed])
        assert second["duplicatedFiles"] == [] and second["prescriptionIds"] != first["prescriptionIds"]

    async def test_mixed_upload_keeps_photo_order_with_existing_and_new(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        new = with_days(sample, "30", "28")
        async with self.client() as client:
            headers = await self.auth(client, "pc10@example.com")
            _, first = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            _, job = await self.read_with(
                client, headers, [jpeg_of_size(1200, 1600, b"n"), jpeg_of_size(1200, 1600, b"m")], [new, sample]
            )
        old_id = first["prescriptionIds"][0]
        assert job["duplicatedFiles"] == [{"fileIndex": 2, "prescriptionId": old_id}]
        assert len(job["prescriptionIds"]) == 2 and job["prescriptionIds"][1] == old_id  # 사진 1(새 기록), 사진 2(기존)

    async def test_missing_letter_in_name_becomes_candidates_for_user_to_choose(self):
        """규칙이 못 찾은 이름(글자가 빠짐)을 비슷한 이름 추천으로 후보에 올린다 — 자동 확정은 아님"""
        data = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        for f in data["images"][0]["fields"]:
            if f["inferText"].startswith("노바스크정5밀리그램"):
                f["inferText"] = "노바스정5밀리그램(암로디핀베실산염)"
        async with self.client() as client:
            headers = await self.auth(client, "pc15@example.com")
            _, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [data])
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
        first = rx["items"][0]
        assert first["matchStatus"] == "needs_confirm" and first["ediCode"] is None and first["itemName"] is None
        assert len(first["candidates"]) >= 2 and first["candidates"][0]["itemName"].startswith("노바스크정5밀리그")
        assert first["suggestedBy"] == "similar"  # 화면이 "비슷한 이름을 추천했어요"를 보여 줄 수 있게
        assert all(it["suggestedBy"] is None for it in rx["items"][1:])
        assert (await PrescriptionItem.get(raw_name__startswith="노바스정")).match_score is None  # 추천은 점수를 비움
        # 사용자가 후보를 고르면 더 이상 "추천" 안내를 띄우지 않는다
        async with self.client() as client:
            pick = first["candidates"][0]["ediCode"]
            url = f"/api/v1/prescriptions/{rx['id']}/items/{first['id']}"
            assert (await client.patch(url, json={"ediCode": pick}, headers=headers)).status_code == 204
            after = (await client.get(f"/api/v1/prescriptions/{rx['id']}", headers=headers)).json()["items"][0]
        assert after["matchStatus"] == "user_confirmed" and after["suggestedBy"] is None

    async def test_name_with_a_different_ingredient_sibling_is_left_for_the_user_to_choose(self):
        """읽힌 이름이 목록에 있어도 글자 하나 차이의 다른 성분 약(노바스크엠정)이 있으면 자동 확정하지 않고 고르게 한다"""
        await DrugProduct.filter(edi_code="641900040").update(ingr_code="A1")
        await DrugProduct.create(
            edi_code="641900099",
            item_name="노바스크엠정5밀리그람(암로디핀베실산염/로사르탄칼륨)_(1정)",
            entp_name="한국화이자제약(주)",
            ingr_code="A2",
            etc_otc="전문",
            route="내복",
        )
        svc.reset_caches()
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc17@example.com")
            _, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
        first = rx["items"][0]
        assert first["matchStatus"] == "needs_confirm" and first["ediCode"] is None
        assert [c["ediCode"] for c in first["candidates"]][:2] == ["641900040", "641900099"]  # 읽은 이름의 약이 1번
        assert first["suggestedBy"] is None  # 오타 보정 추천이 아니라 형제 약 확인
        assert all(it["matchStatus"] == "auto" for it in rx["items"][1:])  # 다른 줄은 그대로 자동 확정
        # 사용자가 이름을 직접 쳐서 찾는 검색은 그대로 — 정확히 같은 이름이면 그 약 하나로 확정한다 (형제 약 확인은 사진 읽기에만 적용)
        async with self.client() as client:
            found = (
                await client.get(
                    "/api/v1/drugs/search", params={"q": "노바스크정5밀리그람(암로디핀베실산염)"}, headers=headers
                )
            ).json()
        assert found["status"] == "matched" and [i["ediCode"] for i in found["items"]] == ["641900040"]

    async def test_matching_runs_off_the_event_loop_and_index_is_prebuilt(self):
        """이름 맞추기는 CPU를 쓰므로 서버(이벤트 루프)를 멈추지 않게 별도 스레드에서 돌리고, 추천용 색인은 미리 만들어 둔다"""
        import threading

        main_thread = threading.get_ident()
        seen: list[int] = []
        real_read = svc.read

        def spy(*args, **kwargs):
            seen.append(threading.get_ident())
            return real_read(*args, **kwargs)

        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc16@example.com")
            with patch.object(svc, "read", spy):
                await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
        assert seen and all(t != main_thread for t in seen)
        assert (await svc.get_matcher())._tidx is not None

    async def test_saved_key_matches_read_time_key_for_every_kind_of_row(self):
        """content_key를 채우는 규칙(저장된 기록 기준)이 읽은 직후의 규칙과 같아야 이전 기록도 찾아진다"""
        garbled = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        for f in garbled["images"][0]["fields"]:
            if f["inferText"].startswith("노바스크정5밀리그램"):
                f["inferText"] = "누바스큐쟁5밀리그램(암로디핀베실산염)"  # 못 찾는 줄(읽은 이름으로 비교)이 섞인 처방전
        async with self.client() as client:
            headers = await self.auth(client, "pc12@example.com")
            _, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [garbled])
        rx = await Prescription.get(id=job["prescriptionIds"][0])
        assert rx.content_key is not None and await svc.saved_content_key(rx) == rx.content_key
        # 사용자가 못 찾은 줄에 약을 골라 준 뒤(user_confirmed, 약 번호가 생김)에도 같은 열쇠여야 한다 (읽은 이름으로 계산)
        sure = await PrescriptionItem.filter(prescription=rx, match_status=MatchStatus.AUTO).first()
        unmatched = await PrescriptionItem.filter(prescription=rx, match_status=MatchStatus.UNMATCHED).first()
        assert sure and unmatched
        await PrescriptionItem.filter(id=unmatched.id).update(
            match_status=MatchStatus.USER_CONFIRMED,
            drug_id=sure.drug_id,  # type: ignore[attr-defined]
        )
        assert await svc.saved_content_key(rx) == rx.content_key

    async def test_backfill_gives_old_records_a_key_so_reupload_is_found(self):
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "backfill_content_key", Path(__file__).resolve().parents[3] / "scripts" / "backfill_content_key.py"
        )
        assert spec and spec.loader
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)

        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc13@example.com")
            _, first = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            rx_id = first["prescriptionIds"][0]
            await Prescription.filter(id=rx_id).update(content_key=None)  # 열쇠 도입 전에 저장한 기록처럼
            _, before = await self.read_with(client, headers, [jpeg_of_size(1200, 1600, b"1")], [sample])
            assert before["duplicatedFiles"] == []  # 열쇠가 없으면 못 찾아서 새로 저장됨
            extra = [i for i in before["prescriptionIds"] if i != rx_id]
            await Prescription.filter(id__in=extra).delete()  # 새로 저장된 사본을 지우고 옛 기록만 남김
            await script.run(apply=False)
            assert (await Prescription.get(id=rx_id)).content_key is None  # 기본(--apply 없이)은 저장하지 않음
            await script.run(apply=True)
            assert (await Prescription.get(id=rx_id)).content_key is not None
            _, again = await self.read_with(client, headers, [jpeg_of_size(1200, 1600, b"2")], [sample])
        assert again["duplicatedFiles"] == [{"fileIndex": 1, "prescriptionId": rx_id}]

    async def test_spacing_difference_in_unread_name_is_still_same_prescription(self):
        def garbled(name: str) -> dict:
            d = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
            for f in d["images"][0]["fields"]:
                if f["inferText"].startswith("노바스크정5밀리그램"):
                    f["inferText"] = name
            return d

        async with self.client() as client:
            headers = await self.auth(client, "pc14@example.com")
            _, first = await self.read_with(
                client, headers, [jpeg_of_size(1200, 1600)], [garbled("누바스큐쟁5밀리그램")]
            )
            _, second = await self.read_with(
                client, headers, [jpeg_of_size(1200, 1600, b"s")], [garbled("누바스큐쟁 5밀리 그램")]
            )
        assert second["duplicatedFiles"] == [{"fileIndex": 1, "prescriptionId": first["prescriptionIds"][0]}]

    async def test_raw_text_is_not_stored(self):
        # 10/15 결정: 인식 원문은 저장하지 않는다. 원문이 아닌 읽은 결과(병원 · 약 · 숫자)는 그대로 저장
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc11@example.com")
            _, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
        rx = await Prescription.get(id=job["prescriptionIds"][0])
        assert rx.ocr_raw_text is None
        assert rx.hospital_name and "가나다내과의원" in rx.hospital_name
        assert await PrescriptionItem.filter(prescription_id=rx.id).count() == 4

    async def test_same_prescription_shot_twice_is_saved_once(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc4@example.com")
            n, job = await self.read_with(
                client, headers, [jpeg_of_size(1200, 1600, b"a"), jpeg_of_size(1200, 1600, b"b")], [sample, sample]
            )
        assert n == 2 and len(job["prescriptionIds"]) == 1 and job["failedFiles"] == []
        assert job["duplicatedFiles"] == [{"fileIndex": 2, "prescriptionId": job["prescriptionIds"][0]}]

    async def test_prescriptions_differing_by_one_number_are_both_kept(self):
        # 이미지가 거의 같아도 일수가 30일 → 28일로 다르면 다른 처방전이다 (재처방 등). 잘못 합치면 처방전이 사라짐
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        async with self.client() as client:
            headers = await self.auth(client, "pc5@example.com")
            n, job = await self.read_with(
                client,
                headers,
                [jpeg_of_size(1200, 1600, b"a"), jpeg_of_size(1200, 1600, b"b")],
                [sample, with_days(sample, "30", "28")],
            )
        assert n == 2 and len(job["prescriptionIds"]) == 2

    async def test_llm_suggestion_for_garbled_name_goes_to_user_confirmation(self):
        garbled = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        for f in garbled["images"][0]["fields"]:
            if f["inferText"].startswith("노바스크정5밀리그램"):
                f["inferText"] = "누바스큐쟁5밀리그램(암로디핀베실산염)"  # 글자가 깨져 규칙이 못 찾음

        class Fake:
            calls = 0

            async def complete(self, system, user):
                Fake.calls += 1
                return json.dumps(
                    {"items": [{"i": 0, "fixed": "노바스크정5밀리그램(암로디핀베실산염)"}]}, ensure_ascii=False
                )

        async with self.client() as client:
            headers = await self.auth(client, "pc6@example.com")
            n, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [garbled])  # 꺼짐(기본)
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
            assert rx["items"][0]["matchStatus"] == "unmatched" and Fake.calls == 0  # 켜지 않으면 LLM을 부르지 않음
            headers = await self.auth(
                client, "pc6b@example.com"
            )  # 같은 사용자가 같은 처방전을 또 올리면 기존 기록을 쓰므로 다른 사용자로
            with patch.object(llm_fix, "make_client", lambda: Fake()):
                n, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600, b"x")], [garbled])
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
        first = rx["items"][0]
        assert Fake.calls == 1
        assert first["matchStatus"] == "needs_confirm" and first["ediCode"] is None  # 자동 확정이 아님
        assert first["suggestedBy"] == "llm"
        assert (await PrescriptionItem.get(id=first["id"])).match_score is None
        assert first["candidates"][0]["ediCode"] == "641900040"  # 추천이 1번
        assert [i["matchStatus"] for i in rx["items"][1:]] == ["auto"] * 3  # 나머지 줄은 그대로

    async def test_maker_glued_to_the_name_is_removed_using_the_makers_in_the_master(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        for f in sample["images"][0]["fields"]:
            if f["inferText"].startswith("노바스크정5밀리그램"):
                f["inferText"] = (
                    "노바스크정5밀리그램한국화이자제약(주)"  # 이름에 제조사가 붙어 읽힘 (실제 CLOVA 결과 n4에서 본 모양)
                )
        async with self.client() as client:
            headers = await self.auth(client, "pc8@example.com")
            n, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [sample])
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
        assert rx["items"][0]["matchStatus"] == "auto" and rx["items"][0]["ediCode"] == "641900040"

    async def test_llm_failure_does_not_fail_the_job(self):
        garbled = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        for f in garbled["images"][0]["fields"]:
            if f["inferText"].startswith("노바스크정5밀리그램"):
                f["inferText"] = "누바스큐쟁5밀리그램(암로디핀베실산염)"

        class Boom:
            async def complete(self, system, user):
                raise TimeoutError

        async with self.client() as client:
            headers = await self.auth(client, "pc7@example.com")
            with patch.object(llm_fix, "make_client", lambda: Boom()):
                n, job = await self.read_with(client, headers, [jpeg_of_size(1200, 1600)], [garbled])
            rx = (await client.get(f"/api/v1/prescriptions/{job['prescriptionIds'][0]}", headers=headers)).json()
        assert job["status"] == "done" and rx["items"][0]["matchStatus"] == "unmatched"

    async def test_unreadable_photo_is_reported_per_file(self):
        blurry = {"images": [{"inferResult": "SUCCESS", "fields": [{"inferText": "흐림", "inferConfidence": 0.3}]}]}

        async def fake(content, fmt, name):
            return blurry

        async with self.client() as client:
            headers = await self.auth(client, "o7@example.com")
            with patch.object(clova, "recognize", fake):
                job_id = (await self.upload(client, headers)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["status"] == "done" and job["prescriptionIds"] == []
        assert job["failedFiles"] == [{"fileIndex": 1, "code": "IMAGE_QUALITY_LOW"}]

    async def test_clear_text_without_table_is_not_a_document(self):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        sample["images"][0]["fields"] = [f for f in sample["images"][0]["fields"] if "일수" not in f["inferText"]]

        async def fake(content, fmt, name):
            return sample

        async with self.client() as client:
            headers = await self.auth(client, "o8@example.com")
            with patch.object(clova, "recognize", fake):
                job_id = (await self.upload(client, headers)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["failedFiles"] == [{"fileIndex": 1, "code": "NOT_A_DOCUMENT"}]

    async def test_clova_failure_marks_job_failed(self):
        async def boom(content, fmt, name):
            raise clova.ClovaError("HTTPStatusError")

        async with self.client() as client:
            headers = await self.auth(client, "o9@example.com")
            with patch.object(clova, "recognize", boom):
                job_id = (await self.upload(client, headers, n=2)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["status"] == "failed" and job["prescriptionIds"] == []
        assert [f["code"] for f in job["failedFiles"]] == ["OCR_FAILED", "OCR_FAILED"]

    async def test_one_bad_photo_keeps_the_good_one(self):
        good = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        calls = iter([good, RuntimeError])

        async def fake(content, fmt, name):
            v = next(calls)
            if v is RuntimeError:
                raise clova.ClovaError("Timeout")
            return v

        async with self.client() as client:
            headers = await self.auth(client, "o10@example.com")
            with patch.object(clova, "recognize", fake):
                job_id = (await self.upload(client, headers, n=2)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["status"] == "done" and len(job["prescriptionIds"]) == 1
        assert job["failedFiles"] == [{"fileIndex": 2, "code": "OCR_FAILED"}]


class TestUnexpectedError(OcrApiCase):
    async def test_unexpected_error_never_leaves_job_running(self):
        async def weird(content, fmt, name):
            raise ValueError("예상 못 한 오류")

        async with self.client() as client:
            headers = await self.auth(client, "o11@example.com")
            with patch.object(clova, "recognize", weird):
                job_id = (await self.upload(client, headers)).json()["jobId"]
            job = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()
        assert job["status"] == "failed"


class TestItemsAndSearch(OcrApiCase):
    async def prescription(self, client, headers) -> dict:
        job_id = (await self.upload(client, headers)).json()["jobId"]
        rx_id = (await client.get(f"/api/v1/ocr-jobs/{job_id}", headers=headers)).json()["prescriptionIds"][0]
        return (await client.get(f"/api/v1/prescriptions/{rx_id}", headers=headers)).json()

    async def test_patch_exclude_pick_and_numbers(self):
        async with self.client() as client:
            headers = await self.auth(client, "p1@example.com")
            rx = await self.prescription(client, headers)
            base = f"/api/v1/prescriptions/{rx['id']}/items"
            a, b = rx["items"][0], rx["items"][1]
            assert (await client.patch(f"{base}/{a['id']}", json={"exclude": True}, headers=headers)).status_code == 204
            pick = {"ediCode": "645600020", "dosePerTime": 2, "timesPerDay": 3, "totalDays": 7}
            assert (await client.patch(f"{base}/{b['id']}", json=pick, headers=headers)).status_code == 204
            after = (await client.get(f"/api/v1/prescriptions/{rx['id']}", headers=headers)).json()["items"]
        assert after[0]["matchStatus"] == "excluded" and after[0]["ediCode"] is None and after[0]["itemName"] is None
        assert after[1]["matchStatus"] == "user_confirmed" and after[1]["ediCode"] == "645600020"
        assert after[1]["itemName"].startswith("리피토정") and after[1]["dosePerTime"] == 2
        assert (after[1]["timesPerDay"], after[1]["totalDays"]) == (3, 7)

    async def test_patch_validation_and_item_seq(self):
        await DrugProduct.create(edi_code="672300240", item_seq="199903123", item_name="타이레놀정500밀리그램")
        svc.reset_caches()
        async with self.client() as client:
            headers = await self.auth(client, "p2@example.com")
            rx = await self.prescription(client, headers)
            url = f"/api/v1/prescriptions/{rx['id']}/items/{rx['items'][0]['id']}"
            unknown = await client.patch(url, json={"ediCode": "999999999"}, headers=headers)
            assert unknown.status_code == 400 and unknown.json()["error"]["field"] == "ediCode"
            assert (await client.patch(url, json={"timesPerDay": 0}, headers=headers)).status_code == 400
            assert (await client.patch(url, json={"itemSeq": "199903123"}, headers=headers)).status_code == 204
            item = (await client.get(f"/api/v1/prescriptions/{rx['id']}", headers=headers)).json()["items"][0]
        assert item["ediCode"] == "672300240" and item["matchStatus"] == "user_confirmed"

    async def test_needs_confirm_item_lists_candidates_and_blocks_until_picked(self):
        async with self.client() as client:
            headers = await self.auth(client, "p3@example.com")
            rx = await self.prescription(client, headers)
            item = await PrescriptionItem.get(id=rx["items"][0]["id"])
            item.match_status = MatchStatus.NEEDS_CONFIRM
            item.drug_id = None
            await item.save()
            await PrescriptionItemCandidate.filter(item=item).delete()  # 자동 확정 때 저장된 후보를 비움
            await PrescriptionItemCandidate.create(item=item, rank=1, drug_id="641900040", score=0.82)
            await PrescriptionItemCandidate.create(item=item, rank=2, drug_id="645600020", score=0.79)
            got = (await client.get(f"/api/v1/prescriptions/{rx['id']}", headers=headers)).json()["items"][0]
        assert got["matchStatus"] == "needs_confirm" and got["ediCode"] is None and got["itemName"] is None
        assert [c["ediCode"] for c in got["candidates"]] == ["641900040", "645600020"]
        assert got["candidates"][0]["itemName"] == "노바스크정5밀리그람(암로디핀베실산염)"

    async def test_search_matched_candidates_not_found(self):
        async with self.client() as client:
            headers = await self.auth(client, "p4@example.com")
            exact = (
                await client.get(
                    "/api/v1/drugs/search", params={"q": "리피토정10 mg(아토르바스타틴칼슘삼수화물)"}, headers=headers
                )
            ).json()
            typo = (
                await client.get("/api/v1/drugs/search", params={"q": "리피토정 10밀리그램"}, headers=headers)
            ).json()
            none = (
                await client.get("/api/v1/drugs/search", params={"q": "전혀없는이름의약품"}, headers=headers)
            ).json()
            bad = await client.get("/api/v1/drugs/search", params={"q": ""}, headers=headers)
            noauth = await client.get("/api/v1/drugs/search", params={"q": "리피토정"})
        assert exact["status"] == "matched" and len(exact["items"]) == 1
        assert exact["items"][0]["ediCode"] == "645600020" and exact["items"][0]["entpName"] == "한국화이자제약(주)"
        assert typo["status"] == "candidates" and typo["items"][0]["ediCode"] == "645600020"
        assert none == {"status": "not_found", "items": []}
        assert bad.status_code == 400 and noauth.status_code == 401
