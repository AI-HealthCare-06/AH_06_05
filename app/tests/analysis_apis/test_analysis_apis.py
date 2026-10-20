"""R-1 ~ R-6 — 분석 시작 · 진행 상태 · 다시 시도 · 결과 · 경고 자세히 · 질환 직접 선택
안전성 점검 DB는 시험용으로 작게 만든 sqlite를 씀 (표 모양은 실제 safety.sqlite와 같음)."""

import json
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.main import app
from app.models.analysis import Analysis, AnalysisStatus, AnalysisStep, DrugGuide, ReviewStatus
from app.models.masters import Disease, DrugProduct
from app.models.ocr import DocType, MatchStatus, Prescription, PrescriptionDisease, PrescriptionItem
from app.models.users import ConsentType, User, UserConsent
from app.services import analyses as svc
from app.services import safety
from app.services.drug_names import base_name
from app.services.guide import lifestyle, store
from app.tests.helpers import signup

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE drug_products (edi_code TEXT PRIMARY KEY, product_name TEXT, ingr_code TEXT, ingr_name TEXT,
    ingr_count INTEGER, route TEXT, company TEXT, rx_type TEXT);
CREATE TABLE dur_interaction (code_a TEXT, code_b TEXT, valid_from TEXT, valid_to TEXT, reason TEXT, message TEXT,
    sex TEXT, spc_age INTEGER, spc_age_cond TEXT, check_range TEXT, excep_days INTEGER, notice_date TEXT, notice_no TEXT);
CREATE TABLE dur_interaction_exception (code_a TEXT, code_b TEXT, edi_code TEXT, valid_from TEXT, valid_to TEXT);
CREATE TABLE dur_age_limit (ingr_code TEXT, valid_from TEXT, valid_to TEXT, age INTEGER, unit TEXT, op TEXT,
    cond_text TEXT, reason TEXT, notice_date TEXT, notice_no TEXT);
CREATE TABLE dur_age_limit_exception (ingr_code TEXT, edi_code TEXT);
CREATE TABLE dur_elderly (ingr_code TEXT, valid_from TEXT, valid_to TEXT, age INTEGER, reason TEXT);
CREATE TABLE dur_dose_limit (ingr_code TEXT, sno INTEGER, valid_from TEXT, valid_to TEXT, ingr_name TEXT,
    unit_amount REAL, daily_max REAL, daily_max_text TEXT, age INTEGER, age_unit TEXT, age_op TEXT,
    sex TEXT, group_code TEXT, detail TEXT);
CREATE TABLE dup_ingredient (edi_code TEXT, dur_ingr_code TEXT, dur_ingr_name TEXT, PRIMARY KEY (edi_code, dur_ingr_code));
CREATE TABLE dup_efficacy (edi_code TEXT, check_code TEXT, group_name TEXT, PRIMARY KEY (edi_code, check_code));
"""
PRODUCTS = [  # (edi, 이름, 성분코드, 성분명, DUR 약 이름)
    ("641900040", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "C1", "암로디핀"),
    ("644300010", "다이아벡스정500밀리그램(메트포르민염산염)_(0.5g/1정)", "M1", "메트포르민"),
    ("645600020", "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)_(10.85mg/1정)", "T1", "아토르바스타틴"),
    ("648800030", "아스피린프로텍트정100밀리그람_(0.1g/1정)", "S1", "아스피린"),
]
DISEASES = [("I10", "본태성 고혈압"), ("E11", "2형 당뇨병"), ("N18", "만성 신장병")]


def make_safety_db(directory: str) -> str:
    path = Path(directory) / "safety.sqlite"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for edi, name, ingr, ingr_name in PRODUCTS:
        con.execute("INSERT INTO drug_products VALUES (?,?,?,?,1,'내복','회사','전문')", (edi, name, ingr, ingr_name))
    con.execute(  # 아토르바스타틴 + 아스피린은 시험용 병용금기
        "INSERT INTO dur_interaction VALUES ('T1','S1','20000101','99991231','시험용 금기 사유','',NULL,NULL,NULL,NULL,NULL,'20190101','2019-1')"
    )
    con.commit()
    con.close()
    return str(path)


class AnalysisCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = make_safety_db(self._tmp.name)
        self._patch = patch.object(config, "SAFETY_DB_PATH", self.db_path)
        self._patch.start()
        safety.reset_checker()
        for edi, name, _i, _n in PRODUCTS:
            await DrugProduct.create(edi_code=edi, item_name=name, entp_name="회사", etc_otc="전문", route="내복")
        for code, name in DISEASES:
            await Disease.create(code=code, name_kr=name)

    async def asyncTearDown(self):
        self._patch.stop()
        safety.reset_checker()
        self._tmp.cleanup()
        await super().asyncTearDown()

    @staticmethod
    def client() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @staticmethod
    async def auth(client: AsyncClient, email: str) -> tuple[dict[str, str], User]:
        tokens = await signup(client, email)
        user = await User.get(login_id=email)
        return {"Authorization": f"Bearer {tokens['accessToken']}"}, user

    @staticmethod
    async def prescription(
        user: User,
        edis: list[str],
        diseases: tuple[str, ...] = (),
        hospital: str = "○○내과",
        status_: MatchStatus = MatchStatus.AUTO,
    ) -> Prescription:
        rx = await Prescription.create(
            user=user,
            doc_type=DocType.PRESCRIPTION,
            issued_date=date.today() - timedelta(days=1),
            hospital_name=hospital,
        )
        for i, code in enumerate(diseases):
            await PrescriptionDisease.create(prescription=rx, disease_id=code, is_main=i == 0)
        for edi in edis:
            await PrescriptionItem.create(
                prescription=rx, drug_id=edi, raw_name=edi, match_status=status_,
                dose_per_time=1, times_per_day=2, total_days=30, timing="아침 식후",
            )  # fmt: skip
        return rx

    async def start(self, client, headers, *rxs: Prescription):
        return await client.post("/api/v1/analyses", json={"prescriptionIds": [r.id for r in rxs]}, headers=headers)


class TestStartAndResult(AnalysisCase):
    async def test_full_flow_interaction_warning_and_guides(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r1@example.com")
            rx1 = await self.prescription(user, ["645600020"], ("I10",), "○○내과")
            rx2 = await self.prescription(user, ["648800030", "644300010"], (), "△△의원")
            res = await self.start(client, headers, rx1, rx2)
            assert res.status_code == status.HTTP_202_ACCEPTED
            aid = res.json()["analysisId"]
            st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
            assert st["status"] == "done" and [s["state"] for s in st["steps"]] == ["done"] * 3
            assert st["drugCount"] == 3 and st["excludedCount"] == 0

            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            assert r["status"] == "done" and r["summary"]["prescriptionCount"] == 2
            assert r["summary"]["hospitals"] == ["○○내과", "△△의원"] and r["summary"]["drugCount"] == 3
            assert r["summary"]["warningCounts"]["danger"] == 1
            w = r["warnings"][0]
            assert w["type"] == "interaction" and w["severity"] == "danger" and w["title"] == "함께 먹으면 안 되는 약"
            assert {d["itemName"] for d in w["drugs"]} == {base_name(PRODUCTS[2][1]), base_name(PRODUCTS[3][1])}
            assert {d["hospitalName"] for d in w["drugs"]} == {"○○내과", "△△의원"}
            assert len(r["checkedItems"]) == 5 and r["disclaimer"]

            med = r["medication"]
            assert med["status"] == "done" and len(med["items"]) == 3
            first = med["items"][0]
            assert first["howToTake"] == "하루 2번 · 아침 식후 · 1회 1 · 30일" or "하루 2번" in first["howToTake"]
            assert first["caution"] is None and first["itemId"]

            life = r["lifestyle"]
            assert life["status"] == "done"
            assert life["diseases"] == [{"code": "I10", "name": "고혈압", "origin": "prescription"}]
            assert life["sections"] and all(s["diseaseCode"] == "I10" for s in life["sections"])
            ids = {s["id"] for s in life["sources"]}
            assert ids and all(i in ids for s in life["sections"] for a in s["actions"] for i in a["sourceIds"])
            assert life["warningSigns"]

    async def test_health_snapshot_is_kept_when_profile_changes(self):
        """분석 시점 건강 정보를 남김. 내 정보를 고쳐도 지난 분석은 그대로 (ERD analyses.health_snapshot, #101)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "snap@example.com")
            rx = await self.prescription(user, ["645600020"], ("I10",))
            res = await self.start(client, headers, rx)
            aid = res.json()["analysisId"]
            await client.patch("/api/v1/users/me", json={"health": {"smoking": "daily"}}, headers=headers)
        snap = (await Analysis.get(id=aid)).health_snapshot
        assert snap is not None and snap["smoking"] == "never" and snap["drinking"] == "monthly"
        assert snap["diseases"] == [] and snap["upcomingExams"] == []

    async def test_warning_detail_r5(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r5@example.com")
            rx = await self.prescription(user, ["645600020", "648800030"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            wid = r["warnings"][0]["id"]
            d = (await client.get(f"/api/v1/analyses/{aid}/warnings/{wid}", headers=headers)).json()
            assert d["judgedBy"] == "database" and d["reasonOriginal"] == "시험용 금기 사유"
            assert {x["ingredient"] for x in d["drugs"]} == {"아토르바스타틴", "아스피린"}
            assert d["source"]["name"] == "심평원 DUR 병용금기" and d["doseDetail"] is None and d["actionAdvice"]
            assert (await client.get(f"/api/v1/analyses/{aid}/warnings/999999", headers=headers)).status_code == 404

    async def test_no_warning_returns_empty_list_and_checked_items(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r2@example.com")
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            assert r["warnings"] == [] and len(r["checkedItems"]) == 5
            assert r["lifestyle"]["diseases"] == [] and r["lifestyle"]["sections"] == []

    async def test_excluded_item_is_allowed_and_listed(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r3@example.com")
            rx = await self.prescription(user, ["641900040"])
            await PrescriptionItem.create(prescription=rx, raw_name="빼기약", match_status=MatchStatus.EXCLUDED)
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            assert r["excludedDrugs"] == [{"rawName": "빼기약", "reason": "excluded"}]
            assert r["summary"]["drugCount"] == 1
            st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
            assert st["excludedCount"] == 1

    async def test_start_errors(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r4@example.com")
            other_headers, other = await self.auth(client, "r4b@example.com")
            ok = await self.prescription(user, ["641900040"])
            pending = await self.prescription(user, ["641900040"], status_=MatchStatus.NEEDS_CONFIRM)
            unmatched = await self.prescription(user, [], status_=MatchStatus.UNMATCHED)
            await PrescriptionItem.create(prescription=unmatched, raw_name="모름", match_status=MatchStatus.UNMATCHED)
            mine_only_excluded = await self.prescription(user, [])
            await PrescriptionItem.create(
                prescription=mine_only_excluded, raw_name="x", match_status=MatchStatus.EXCLUDED
            )

            res = await self.start(client, headers, ok, pending)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ITEMS_NOT_CONFIRMED"
            res = await self.start(client, headers, unmatched)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ITEMS_NOT_CONFIRMED"
            res = await self.start(client, headers, mine_only_excluded)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ITEMS_NOT_CONFIRMED"
            res = await self.start(client, other_headers, ok)  # 남의 처방전
            assert res.status_code == 404
            res = await client.post("/api/v1/analyses", json={"prescriptionIds": []}, headers=headers)
            assert res.status_code == 400
            res = await client.post("/api/v1/analyses", json={"prescriptionIds": [1, 2, 3, 4, 5, 6]}, headers=headers)
            assert res.status_code == 400
            assert (await client.post("/api/v1/analyses", json={"prescriptionIds": [ok.id]})).status_code == 401

            await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(agreed=False)
            res = await self.start(client, headers, ok)
            assert res.status_code == 403 and res.json()["error"]["code"] == "CONSENT_REQUIRED"

    async def test_other_users_analysis_is_404_and_unfinished_is_409(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "r6@example.com")
            other_headers, _ = await self.auth(client, "r6b@example.com")
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            for path in (f"/analyses/{aid}", f"/analyses/{aid}/status", f"/analyses/{aid}/warnings/1"):
                assert (await client.get("/api/v1" + path, headers=other_headers)).status_code == 404
            assert (await client.post(f"/api/v1/analyses/{aid}/retry", headers=other_headers)).status_code == 404
            assert (
                await client.put(f"/api/v1/analyses/{aid}/diseases", json={"diseaseCodes": []}, headers=other_headers)
            ).status_code == 404
            running = await Analysis.create(
                user=user, status=AnalysisStatus.RUNNING, current_step=AnalysisStep.SAFETY_CHECK, started_at=svc._now()
            )
            res = await client.get(f"/api/v1/analyses/{running.id}", headers=headers)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ANALYSIS_NOT_READY"
            st = (await client.get(f"/api/v1/analyses/{running.id}/status", headers=headers)).json()
            assert [s["state"] for s in st["steps"]] == ["done", "running", "pending"]
            res = await client.put(
                f"/api/v1/analyses/{running.id}/diseases", json={"diseaseCodes": []}, headers=headers
            )
            assert res.status_code == 409


class TestFailureAndRetry(AnalysisCase):
    async def test_safety_failure_then_retry_resumes(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f1@example.com")
            rx = await self.prescription(user, ["645600020", "648800030"])
            with patch.object(config, "SAFETY_DB_PATH", ""):
                safety.reset_checker()
                aid = (await self.start(client, headers, rx)).json()["analysisId"]
                st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
            assert st["status"] == "failed" and st["error"]["code"] == "SAFETY_CHECK_FAILED"
            assert [s["state"] for s in st["steps"]] == ["done", "failed", "pending"]
            assert st["partialResultAvailable"] is False and st["retryCount"] == 0
            assert (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).status_code == 409

            safety.reset_checker()
            res = await client.post(f"/api/v1/analyses/{aid}/retry", headers=headers)
            assert res.status_code == 202 and res.json() == {"analysisId": aid, "status": "queued"}
            st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
            assert st["status"] == "done"
            assert (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()["warnings"]
            res = await client.post(f"/api/v1/analyses/{aid}/retry", headers=headers)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ANALYSIS_NOT_FAILED"

    async def test_guide_failure_keeps_safety_result_and_retry_limit(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f2@example.com")
            rx = await self.prescription(user, ["645600020", "648800030"], ("I10",))
            with patch.object(lifestyle, "build", side_effect=RuntimeError("boom")):
                aid = (await self.start(client, headers, rx)).json()["analysisId"]
                st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
                assert st["status"] == "failed" and st["error"]["code"] == "GUIDE_GENERATION_FAILED"
                assert st["partialResultAvailable"] is True
                assert [s["state"] for s in st["steps"]] == ["done", "done", "failed"]
                r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()  # 안전성 결과만 먼저 보기
                assert r["status"] == "failed" and r["warnings"] and r["lifestyle"]["status"] == "failed"
                assert r["medication"]["status"] == "failed" or r["medication"]["items"] == []
                for n in (1, 2, 3):
                    assert (await client.post(f"/api/v1/analyses/{aid}/retry", headers=headers)).status_code == 202
                    st = (await client.get(f"/api/v1/analyses/{aid}/status", headers=headers)).json()
                    assert st["status"] == "failed" and st["retryCount"] == n
                res = await client.post(f"/api/v1/analyses/{aid}/retry", headers=headers)
                assert res.status_code == 429 and res.json()["error"]["code"] == "RETRY_LIMIT_EXCEEDED"
            await Analysis.filter(id=aid).update(retry_count=0)
            assert (await client.post(f"/api/v1/analyses/{aid}/retry", headers=headers)).status_code == 202
            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            assert r["status"] == "done" and r["lifestyle"]["status"] == "done" and r["medication"]["status"] == "done"

    async def test_timeout_after_60_seconds(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f3@example.com")
            stuck = await Analysis.create(
                user=user, status=AnalysisStatus.RUNNING, current_step=AnalysisStep.SAFETY_CHECK,
                started_at=svc._now() - timedelta(seconds=120),
            )  # fmt: skip
            st = (await client.get(f"/api/v1/analyses/{stuck.id}/status", headers=headers)).json()
            assert st["status"] == "failed" and st["error"]["code"] == "TIMEOUT"
            assert [s["state"] for s in st["steps"]] == ["done", "failed", "pending"]


class TestDiseases(AnalysisCase):
    async def test_put_diseases_builds_user_lifestyle_with_conflict_and_links(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d1@example.com")
            rx = await self.prescription(user, ["641900040", "644300010"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            res = await client.put(
                f"/api/v1/analyses/{aid}/diseases", json={"diseaseCodes": ["I10", "E11", "N18"]}, headers=headers
            )
            assert res.status_code == 200
            life = res.json()
            assert [(d["code"], d["origin"]) for d in life["diseases"]] == [
                ("I10", "user"),
                ("E11", "user"),
                ("N18", "user"),
            ]
            assert any(s["conflict"] and s["conflict"]["label"] == "의료진 상담 필요" for s in life["sections"])
            names = {m["itemName"] for m in life["medicationLinks"]}
            assert {base_name(PRODUCTS[0][1]), base_name(PRODUCTS[1][1])} <= names
            assert all(m["itemId"] for m in life["medicationLinks"])
            # R-4에도 같은 내용이 반영됨
            r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            assert [d["code"] for d in r["lifestyle"]["diseases"]] == ["I10", "E11", "N18"]
            # 다시 비우면 해당 없음
            res = await client.put(f"/api/v1/analyses/{aid}/diseases", json={"diseaseCodes": []}, headers=headers)
            assert res.status_code == 200 and res.json()["diseases"] == [] and res.json()["sections"] == []

    async def test_put_diseases_validation(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d2@example.com")
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            res = await client.put(f"/api/v1/analyses/{aid}/diseases", json={"diseaseCodes": ["ZZZ9"]}, headers=headers)
            assert res.status_code == 400
            res = await client.put(f"/api/v1/analyses/{aid}/diseases", json={}, headers=headers)
            assert res.status_code == 400
            # 마스터에는 있지만 팩트 테이블에 없는 질환 → 안내 없이 빈 목록
            await Disease.create(code="J00", name_kr="급성 비인두염")
            res = await client.put(f"/api/v1/analyses/{aid}/diseases", json={"diseaseCodes": ["j00"]}, headers=headers)
            assert res.status_code == 200 and res.json()["sections"] == [] and res.json()["diseases"] == []


class TestStoredGuides(AnalysisCase):
    """안내문 사전 저장 — 분석 때는 drug_guides를 조회해서 붙인다"""

    async def medication_items(self, client, headers, user):
        rx = await self.prescription(user, ["641900040"], ("I10",))
        aid = (await self.start(client, headers, rx)).json()["analysisId"]
        r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
        return r["medication"]["items"]

    async def test_stored_content_is_used_and_howtotake_stays_per_prescription(self):
        await DrugGuide.create(
            edi_code="641900040",
            content={"category": "혈압약", "purpose": "저장된 쓰임", "caution": "저장된 주의", "source": "시험 출처"},
            review_status=ReviewStatus.APPROVED,
        )
        async with self.client() as client:
            headers, user = await self.auth(client, "g1@example.com")
            it = (await self.medication_items(client, headers, user))[0]
            assert it["purpose"] == "저장된 쓰임" and it["caution"] == "저장된 주의" and it["source"] == "시험 출처"
            assert it["howToTake"].startswith("하루 2번")

    async def test_rejected_gives_pharmacist_text_not_table(self):
        await DrugGuide.create(
            edi_code="641900040", content={"purpose": "쓰면 안 됨"}, review_status=ReviewStatus.REJECTED
        )
        async with self.client() as client:
            headers, user = await self.auth(client, "g2@example.com")
            it = (await self.medication_items(client, headers, user))[0]
            assert it["purpose"] == "처방받은 목적을 약사에게 확인해 주세요" and it["category"] is None
            assert it["caution"] is None

    async def test_draft_and_missing_are_not_shown_until_a_person_approves(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "g3@example.com")
            assert (await store.generate_all())["created"] == len(PRODUCTS)
            it = (await self.medication_items(client, headers, user))[0]  # draft
            assert it["purpose"] == "처방받은 목적을 약사에게 확인해 주세요" and it["category"] is None
            assert it["source"] is None and it["howToTake"]
            await DrugGuide.filter(edi_code="641900040").update(review_status=ReviewStatus.APPROVED)
            await Analysis.all().delete()
            it = (await self.medication_items(client, headers, user))[0]
            assert it["source"] == "심평원 약제급여목록 약효분류"

    async def test_review_group_approves_same_content_together(self):
        await store.generate_all()  # 시험 약은 약효분류가 없어 내용이 모두 같음 → 묶음 1개
        gs = await store.groups()
        assert len(gs) == 1 and gs[0]["count"] == len(PRODUCTS) and gs[0]["status"] == {"draft": len(PRODUCTS)}
        assert len(gs[0]["examples"]) == len(PRODUCTS) and len(set(gs[0]["examples"])) == len(PRODUCTS)
        assert await store.review_group("없는키", ReviewStatus.APPROVED, "채연") == 0
        assert await store.review_group(gs[0]["key"], ReviewStatus.APPROVED, "채연") == len(PRODUCTS)
        g = await DrugGuide.get(edi_code="644300010")
        assert g.review_status == ReviewStatus.APPROVED and g.reviewed_by == "채연" and g.reviewed_at
        assert set(await store.lookup(["644300010", "000000000"])) == {"644300010"}

    async def test_generate_all_creates_missing_and_regenerate_resets_only_changed(self):
        n = len(PRODUCTS)
        assert await store.generate_all() == {"created": n, "updated": 0, "reset": 0, "skipped": 0}
        assert await store.generate_all() == {"created": 0, "updated": 0, "reset": 0, "skipped": n}
        await DrugGuide.filter(edi_code="641900040").update(review_status=ReviewStatus.APPROVED, reviewed_by="채연")
        await DrugGuide.filter(edi_code="644300010").update(review_status=ReviewStatus.REJECTED)
        # 표가 그대로면 다시 만들어도 확인 상태가 유지됨
        assert await store.generate_all(only_missing=False) == {"created": 0, "updated": 0, "reset": 0, "skipped": n}
        assert (await DrugGuide.get(edi_code="641900040")).review_status == ReviewStatus.APPROVED
        # 표가 바뀌면 (draft는 갱신, 확인된 것은 draft로 되돌림)
        await DrugGuide.filter(edi_code__in=["641900040", "644300010"]).update(content={"purpose": "옛 내용"})
        await DrugGuide.filter(edi_code="645600020").update(content={"purpose": "옛 내용"})
        r = await store.generate_all(only_missing=False)
        assert r == {"created": 0, "updated": 1, "reset": 2, "skipped": n - 3}
        g = await DrugGuide.get(edi_code="641900040")
        assert g.review_status == ReviewStatus.DRAFT and g.reviewed_by is None and g.content["purpose"] != "옛 내용"
        assert (await DrugGuide.get(edi_code="644300010")).review_status == ReviewStatus.DRAFT

    async def test_evidence_is_saved_and_refreshed_without_resetting_review(self):
        await DrugProduct.filter(edi_code="641900040").update(class_code="214")
        await store.generate_all()
        g = await DrugGuide.get(edi_code="641900040")
        assert g.evidence_ids == [{"kind": "hira_class", "key": "214", "label": "심평원 약제급여목록 약효분류"}]
        assert (await DrugGuide.get(edi_code="644300010")).evidence_ids == []  # 분류가 표에 없는 약은 근거 없음
        await DrugGuide.filter(edi_code="641900040").update(review_status=ReviewStatus.APPROVED, evidence_ids=None)
        r = await store.generate_all(only_missing=False)  # 내용은 같고 근거만 비어 있음 → 근거만 채우고 승인은 유지
        assert r["updated"] >= 1 and r["reset"] == 0
        g = await DrugGuide.get(edi_code="641900040")
        assert g.review_status == ReviewStatus.APPROVED and g.evidence_ids

    async def test_mixed_purpose_classes_fall_back_to_pharmacist_text(self):
        # 한 분류에 쓰임이 다른 약이 섞인 분류는 쓰임을 단정하지 않는다 (243은 갑상선 호르몬을 줄이는 약도 포함)
        for cls in ("219", "339", "117", "243", "245"):
            await DrugProduct.filter(edi_code="641900040").update(class_code=cls)
            await store.generate_all(only_missing=False)
            g = await DrugGuide.get(edi_code="641900040")
            assert g.content["category"] is None and g.content["purpose"] == "처방받은 목적을 약사에게 확인해 주세요"
            assert g.evidence_ids == []

    async def test_review_marks_status_and_reviewer(self):
        await store.generate_all()
        assert await store.review("644300010", ReviewStatus.APPROVED, "채연")
        g = await DrugGuide.get(edi_code="644300010")
        assert g.review_status == ReviewStatus.APPROVED and g.reviewed_by == "채연" and g.reviewed_at
        assert not await store.review("000000000", ReviewStatus.APPROVED, "채연")


class TestGuideUnits(TestCase):
    def test_disease_lookup_by_three_characters(self):
        assert lifestyle.disease_of("I10")["id"] == "HTN"
        assert lifestyle.disease_of("i15.9")["id"] == "HTN"
        assert lifestyle.disease_of("E119")["id"] == "DM2"
        assert lifestyle.disease_of("Z00") is None

    def test_many_drugs_alone_do_not_add_a_conflict_note(self):
        """약이 5개 이상이라는 이유만으로 질환 겹침 안내가 붙지 않는다 (R-4의 다제약물 참고와 겹치고 세는 기준도 달랐다)"""
        from types import SimpleNamespace

        items = [
            SimpleNamespace(id=n, drug=SimpleNamespace(edi_code=str(n), item_name=f"시험약{n}정")) for n in range(1, 7)
        ]

        def notes(codes: list[str]) -> list[str]:
            return [s["conflict"]["message"] for s in lifestyle.build(codes, items)["sections"] if s["conflict"]]  # type: ignore[arg-type]

        assert notes(["I10", "E11", "E78"]) == []  # 질환 겹침 규칙에 해당 없음 + 약 6개
        both = notes(["I48", "M81"])  # 심방세동 + 골다공증은 그대로 안내
        assert len(both) == 1 and "복용 간격" in both[0]

    def test_every_picker_code_has_facts(self):
        for code in lifestyle.PICKABLE.values():
            assert lifestyle.is_supported(code), code


class TestSeedGuides(AnalysisCase):
    """허가정보 문장(seed) — 데모 약 17개를 drug_guides에 넣고, 약 하나씩 확인한 뒤에만 보여 준다"""

    def seed_file(self, **changes):
        """시험 약(641900040)용 seed 1건짜리 파일 — 실제 seed의 노바스크 항목을 바탕으로 함"""
        entry = next(e for e in store.seed_entries() if e["label"].startswith("노바스크"))
        entry = {**entry, "ediCode": "641900040", **changes}
        path = Path(self._tmp.name) / "seed.json"
        path.write_text(json.dumps({"guides": [entry]}, ensure_ascii=False), encoding="utf-8")
        return path

    async def medication_items(self, client, headers, user):
        rx = await self.prescription(user, ["641900040"], ("I10",))
        aid = (await self.start(client, headers, rx)).json()["analysisId"]
        r = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
        return r["medication"]["items"]

    def test_real_seed_file_is_well_formed(self):
        entries = store.seed_entries()
        assert len(entries) == 17 and len({e["ediCode"] for e in entries}) == 17
        for e in entries:
            assert e["purpose"] and e["purpose"].endswith("약이에요") and e["purposeSources"], e["label"]
            assert 1 <= len(e["cautions"]) <= 3, e["label"]
            for c in e["cautions"]:
                assert c["text"].endswith(".") and c["sources"], (e["label"], c["text"])
                assert all(s["id"] and s["text"] for s in c["sources"]), (e["label"], c["text"])
            assert e["permit"]["itemSeq"] and e["model"] and e["promptVer"]

    def test_real_seed_urgent_wording_has_urgent_source(
        self,
    ):  # "바로 병원 · 즉시"는 근거 원문에 급하다는 말이 있을 때만
        urgent = (
            "즉시",
            "즉각",
            "치명",
            "중증",
            "심각",
            "중대한",
            "급격",
            "급성",
            "아낙필락시스",
            "사망",
            "응급",
        )  # 샌드박스 검증 규칙과 같음
        for e in store.seed_entries():
            for c in e["cautions"]:
                if "바로 병원" in c["text"] or "즉시" in c["text"]:
                    assert any(u in s["text"] for s in c["sources"] for u in urgent), (e["label"], c["text"])

    async def test_seed_is_draft_until_a_person_approves_each_drug(self):
        path = self.seed_file()
        r = await store.load_seed(path)
        assert r == {"created": 1, "updated": 0, "reset": 0, "skipped": 0, "missing": []}
        g = await DrugGuide.get(edi_code="641900040")
        assert g.review_status == ReviewStatus.DRAFT and g.model_name == "gpt-4o-mini" and g.prompt_ver
        assert any(e["kind"] == "drug_details" and e["use"] == "caution1" and e["text"] for e in g.evidence_ids)
        async with self.client() as client:
            headers, user = await self.auth(client, "s1@example.com")
            it = (await self.medication_items(client, headers, user))[0]
            assert it["caution"] is None and it["cautions"] == [] and it["source"] is None  # 확인 전에는 안 나감
            assert await store.review_drugs(["641900040", "000000000"], ReviewStatus.APPROVED, "채연") == 1
            await Analysis.all().delete()
            it = (await self.medication_items(client, headers, user))[0]
            assert it["purpose"] == "고혈압과 심장병에 쓰는 약이에요" and it["howToTake"].startswith("하루 2번")
            assert it["cautions"] == [
                "부종이 생기면 의사에게 알리세요.",
                "자몽이나 자몽주스는 함께 드시는 것을 피하세요.",
            ]
            assert it["caution"] == "\n".join(it["cautions"])  # 명세서의 caution(문자열)은 문장을 줄바꿈으로 이은 것
            assert "허가정보" in it["source"] and "허가일 2006-09-06" in it["source"]

    async def test_load_seed_is_repeatable_and_resets_review_only_when_changed(self):
        path = self.seed_file()
        await store.load_seed(path)
        await store.review_drugs(["641900040"], ReviewStatus.APPROVED, "채연")
        assert (await store.load_seed(path))["skipped"] == 1
        assert (await DrugGuide.get(edi_code="641900040")).review_status == ReviewStatus.APPROVED
        path = self.seed_file(purpose="바뀐 쓰임")
        assert (await store.load_seed(path)) == {"created": 0, "updated": 0, "reset": 1, "skipped": 0, "missing": []}
        g = await DrugGuide.get(edi_code="641900040")
        assert g.review_status == ReviewStatus.DRAFT and g.reviewed_by is None and g.content["purpose"] == "바뀐 쓰임"

    async def test_drug_not_in_master_is_reported_not_inserted(self):
        r = await store.load_seed(self.seed_file(ediCode="999999999"))
        assert r["created"] == 0 and r["missing"] == ["999999999"]
        assert not await DrugGuide.filter(edi_code="999999999").exists()

    async def test_rule_table_regeneration_and_group_review_leave_seed_alone(self):
        await store.load_seed(self.seed_file())
        before = (await DrugGuide.get(edi_code="641900040")).content
        n = len(PRODUCTS)
        r = await store.generate_all(only_missing=False)
        assert r == {"created": n - 1, "updated": 0, "reset": 0, "skipped": 1}
        assert (await DrugGuide.get(edi_code="641900040")).content == before
        gs = await store.groups()  # 묶음 확인에는 규칙 표 약만
        assert sum(g["count"] for g in gs) == n - 1
        for g in gs:
            await store.review_group(g["key"], ReviewStatus.APPROVED, "채연")
        assert (await DrugGuide.get(edi_code="641900040")).review_status == ReviewStatus.DRAFT
        # 반대로 약 단위 확인은 규칙 표 약을 건드리지 않음
        assert await store.review_drugs(["644300010"], ReviewStatus.APPROVED, "채연") == 0
        assert [g["ediCode"] for g in await store.seed_guides()] == ["641900040"]
