"""R-7 ~ R-9 — 지난 기록 목록 · 기록 삭제 · 안내문 피드백"""

import base64
import json
from unittest.mock import patch

from starlette import status

from app.core import config
from app.models.analysis import Analysis, AnalysisStatus, AnalysisWarning, Guide, GuideFeedback
from app.models.ocr import Prescription, PrescriptionItem
from app.services import safety
from app.services.analyses import _now
from app.tests.analysis_apis.test_analysis_apis import AnalysisCase


class TestHistoryList(AnalysisCase):
    async def test_empty_list(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "h1@example.com")
            res = await client.get("/api/v1/analyses", headers=headers)
        assert res.status_code == status.HTTP_200_OK and res.json() == {"items": [], "nextCursor": None}

    async def test_newest_first_with_labels_and_fields(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h2@example.com")
            risky = await self.prescription(user, ["645600020", "648800030"], ("I10",), "○○내과")
            clean = await self.prescription(user, ["641900040"], ("E11",), "△△의원")
            first = (await self.start(client, headers, risky)).json()["analysisId"]
            second = (await self.start(client, headers, clean)).json()["analysisId"]
            items = (await client.get("/api/v1/analyses", headers=headers)).json()["items"]
        assert [i["analysisId"] for i in items] == [second, first]
        assert items[0]["resultLabel"] == "걸린 항목 없음" and items[0]["hospitals"] == ["△△의원"]
        assert items[0]["drugCount"] == 1 and items[0]["status"] == "done" and items[0]["diseaseNames"]
        assert items[1]["resultLabel"] == "확인 필요 1건" and items[1]["drugCount"] == 2
        assert items[1]["hospitals"] == ["○○내과"] and items[1]["createdAt"]

    async def test_paging_with_cursor_and_bad_cursor(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h3@example.com")
            ids = []
            for _ in range(3):
                rx = await self.prescription(user, ["641900040"])
                ids.append((await self.start(client, headers, rx)).json()["analysisId"])
            page1 = (await client.get("/api/v1/analyses?size=2", headers=headers)).json()
            assert [i["analysisId"] for i in page1["items"]] == [ids[2], ids[1]] and page1["nextCursor"]
            page2 = (await client.get(f"/api/v1/analyses?size=2&cursor={page1['nextCursor']}", headers=headers)).json()
            assert [i["analysisId"] for i in page2["items"]] == [ids[0]] and page2["nextCursor"] is None
            one = (await client.get("/api/v1/analyses?size=1", headers=headers)).json()
            assert len(one["items"]) == 1 and one["items"][0]["analysisId"] == ids[2]  # 홈의 최근 1건
            for bad in (
                "%%%",
                base64.urlsafe_b64encode(b"[1]").decode(),
                base64.urlsafe_b64encode(b'{"x":1}').decode(),
            ):
                res = await client.get(f"/api/v1/analyses?cursor={bad}", headers=headers)
                assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"
            assert (await client.get("/api/v1/analyses?size=0", headers=headers)).status_code == 400
            assert (await client.get("/api/v1/analyses?size=51", headers=headers)).status_code == 400

    async def test_cursor_matches_spec_shape(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h4@example.com")
            for _ in range(2):
                rx = await self.prescription(user, ["641900040"])
                await self.start(client, headers, rx)
            cursor = (await client.get("/api/v1/analyses?size=1", headers=headers)).json()["nextCursor"]
        assert "id" in json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))

    async def test_only_my_records_and_failed_and_running_labels(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h5@example.com")
            other_headers, other = await self.auth(client, "h6@example.com")
            await self.start(client, other_headers, await self.prescription(other, ["641900040"]))
            rx = await self.prescription(user, ["645600020", "648800030"])
            with patch.object(config, "SAFETY_DB_PATH", ""):
                safety.reset_checker()
                failed = (await self.start(client, headers, rx)).json()["analysisId"]
            running = await Analysis.create(user=user, status=AnalysisStatus.RUNNING, started_at=_now())
            items = (await client.get("/api/v1/analyses", headers=headers)).json()["items"]
        by_id = {i["analysisId"]: i for i in items}
        assert set(by_id) == {failed, running.id}
        assert by_id[failed]["status"] == "failed" and by_id[failed]["resultLabel"] == "분석 실패"
        assert "hospitals" not in by_id[failed]
        assert by_id[running.id]["status"] == "running" and by_id[running.id]["resultLabel"] == "분석 중"

    async def test_requires_login(self):
        async with self.client() as client:
            assert (await client.get("/api/v1/analyses")).status_code == 401


class TestDelete(AnalysisCase):
    async def test_delete_removes_result_and_only_prescriptions_used_here(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d1@example.com")
            shared = await self.prescription(user, ["641900040"])
            only_a = await self.prescription(user, ["645600020", "648800030"], ("I10",))
            a = (await self.start(client, headers, shared, only_a)).json()["analysisId"]
            b = (await self.start(client, headers, shared)).json()["analysisId"]
            unrelated = await self.prescription(user, ["644300010"])
            guide_ids = await Guide.filter(analysis_id=a).values_list("id", flat=True)
            assert guide_ids and await AnalysisWarning.filter(analysis_id=a).exists()

            res = await client.delete(f"/api/v1/analyses/{a}", headers=headers)
            assert res.status_code == status.HTTP_204_NO_CONTENT
            assert (await client.get(f"/api/v1/analyses/{a}", headers=headers)).status_code == 404
            assert not await Analysis.filter(id=a).exists()
            assert not await AnalysisWarning.filter(analysis_id=a).exists()
            assert not await Guide.filter(id__in=list(guide_ids)).exists()
            assert not await Prescription.filter(id=only_a.id).exists()
            assert not await PrescriptionItem.filter(prescription_id=only_a.id).exists()
            assert await Prescription.filter(id=shared.id).exists()  # 다른 분석에도 쓰임
            assert await Prescription.filter(id=unrelated.id).exists()  # 분석에 안 쓰인 처방전은 그대로
            assert (await client.get(f"/api/v1/analyses/{b}", headers=headers)).status_code == 200
            ids = [i["analysisId"] for i in (await client.get("/api/v1/analyses", headers=headers)).json()["items"]]
            assert ids == [b]

    async def test_delete_removes_feedback_too(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d2@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"], ("I10",)))).json()[
                "analysisId"
            ]
            guide_id = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()["medication"]["guideId"]
            assert (
                await client.post(f"/api/v1/guides/{guide_id}/feedback", json={"rating": 1}, headers=headers)
            ).status_code == 201
            assert await GuideFeedback.filter(guide_id=guide_id).exists()
            await client.delete(f"/api/v1/analyses/{aid}", headers=headers)
            assert not await GuideFeedback.filter(guide_id=guide_id).exists()

    async def test_others_and_missing_are_404_and_running_is_409(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d3@example.com")
            other_headers, other = await self.auth(client, "d4@example.com")
            theirs = (await self.start(client, other_headers, await self.prescription(other, ["641900040"]))).json()[
                "analysisId"
            ]
            assert (await client.delete(f"/api/v1/analyses/{theirs}", headers=headers)).status_code == 404
            assert await Analysis.filter(id=theirs).exists()
            assert (await client.delete("/api/v1/analyses/999999", headers=headers)).status_code == 404
            running = await Analysis.create(user=user, status=AnalysisStatus.RUNNING, started_at=_now())
            res = await client.delete(f"/api/v1/analyses/{running.id}", headers=headers)
            assert res.status_code == 409 and res.json()["error"]["code"] == "ANALYSIS_RUNNING"
            assert await Analysis.filter(id=running.id).exists()


class TestFeedback(AnalysisCase):
    async def _guide_id(self, client, headers, user, email_unused=None):
        rx = await self.prescription(user, ["641900040"], ("I10",))
        aid = (await self.start(client, headers, rx)).json()["analysisId"]
        return (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()["medication"]["guideId"]

    async def test_feedback_is_accepted_only_once(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "g1@example.com")
            gid = await self._guide_id(client, headers, user)
            res = await client.post(
                f"/api/v1/guides/{gid}/feedback",
                json={"rating": -1, "comment": "  글씨가 더 컸으면 좋겠어요  "},
                headers=headers,
            )
            assert res.status_code == status.HTTP_201_CREATED and res.json()["feedbackId"]
            row = await GuideFeedback.get(guide_id=gid)
            assert row.rating == -1 and row.comment == "글씨가 더 컸으면 좋겠어요" and row.user_id == user.id  # type: ignore[attr-defined]
            res2 = await client.post(
                f"/api/v1/guides/{gid}/feedback", json={"rating": 1, "comment": " "}, headers=headers
            )
            assert res2.status_code == status.HTTP_409_CONFLICT
            assert res2.json()["error"]["code"] == "FEEDBACK_ALREADY_SENT"  # 한 번 보냈으면 다시 받지 않음
            assert await GuideFeedback.filter(guide_id=gid).count() == 1
            row = await GuideFeedback.get(guide_id=gid)
            assert row.rating == -1 and row.comment == "글씨가 더 컸으면 좋겠어요"  # 처음 보낸 의견이 그대로

    async def test_result_tells_if_this_user_already_sent_feedback(self):
        """분석 결과에 내가 보낸 의견이 들어 있어, 앱이 다시 열어도 보내기를 막을 수 있다"""
        async with self.client() as client:
            headers, user = await self.auth(client, "g6@example.com")
            rx = await self.prescription(user, ["641900040"], ("I10",))
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            before = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            gid = before["medication"]["guideId"]
            await client.post(
                f"/api/v1/guides/{gid}/feedback", json={"rating": -1, "comment": " 글씨가 작아요 "}, headers=headers
            )
            after = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
            resend = await client.post(f"/api/v1/guides/{gid}/feedback", json={"rating": 1}, headers=headers)
            again = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
        assert resend.status_code == status.HTTP_409_CONFLICT
        assert before["medication"]["feedback"] is None and before["lifestyle"]["feedback"] is None
        assert after["medication"]["feedback"] == {"rating": -1, "comment": "글씨가 작아요"}
        assert after["lifestyle"]["feedback"] is None  # 다른 안내문 것은 따로
        assert again["medication"]["feedback"] == {
            "rating": -1,
            "comment": "글씨가 작아요",
        }  # 다시 보내도 처음 것이 남음

    async def test_same_prescription_again_is_blocked_but_other_set_is_allowed(self):
        """같은 처방전(중복 사진 포함)으로 다시 분석해도 못 보내고, 처방전 묶음이 다르면(A+B) 보낼 수 있다"""
        async with self.client() as client:
            headers, user = await self.auth(client, "g9@example.com")
            rx_a = await self.prescription(user, ["641900040"], ("I10",))
            rx_b = await self.prescription(user, ["645600020"], ("E11",), "△△의원")

            async def analyse(*rxs):
                aid = (await self.start(client, headers, *rxs)).json()["analysisId"]
                return aid, (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()

            async def send(gid):
                return await client.post(f"/api/v1/guides/{gid}/feedback", json={"rating": 1}, headers=headers)

            _, a1 = await analyse(rx_a)
            assert (await send(a1["medication"]["guideId"])).status_code == status.HTTP_201_CREATED
            _, a2 = await analyse(rx_a)  # 같은 처방전으로 다시 분석 (중복 사진을 올린 경우도 같은 처방전)
            assert a2["medication"]["guideId"] != a1["medication"]["guideId"]
            assert a2["medication"]["feedback"] == {"rating": 1, "comment": None}  # 앱이 처음부터 막힌 채로 보여 줌
            again = await send(a2["medication"]["guideId"])
            assert (
                again.status_code == status.HTTP_409_CONFLICT
                and again.json()["error"]["code"] == "FEEDBACK_ALREADY_SENT"
            )
            _, ab = await analyse(rx_a, rx_b)  # 처방전 묶음이 다름
            assert ab["medication"]["feedback"] is None
            assert (await send(ab["medication"]["guideId"])).status_code == status.HTTP_201_CREATED
            _, ab2 = await analyse(rx_b, rx_a)  # 순서가 달라도 같은 묶음
            assert ab2["medication"]["feedback"] == {"rating": 1, "comment": None}
            _, b_only = await analyse(rx_b)  # A+B로 보냈어도 B만은 다른 묶음
            assert b_only["medication"]["feedback"] is None
            assert await GuideFeedback.filter(user=user).count() == 2

    async def test_other_users_feedback_is_not_shown(self):
        """같은 안내문이 아니어도 남의 의견은 내 결과에 보이지 않는다 (사람마다 따로)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "g7@example.com")
            other_headers, other = await self.auth(client, "g8@example.com")
            rx = await self.prescription(user, ["641900040"], ("I10",))
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            gid = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()["medication"]["guideId"]
            await GuideFeedback.create(guide_id=gid, user=other, rating=1, comment="남의 의견")
            mine = (await client.get(f"/api/v1/analyses/{aid}", headers=headers)).json()
        assert mine["medication"]["feedback"] is None

    async def test_validation_and_ownership(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "g2@example.com")
            other_headers, _ = await self.auth(client, "g3@example.com")
            gid = await self._guide_id(client, headers, user)
            for body in ({"rating": 0}, {"rating": 2}, {}, {"rating": 1, "comment": "가" * 501}):
                res = await client.post(f"/api/v1/guides/{gid}/feedback", json=body, headers=headers)
                assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"
            res = await client.post(f"/api/v1/guides/{gid}/feedback", json={"rating": 1}, headers=other_headers)
            assert res.status_code == 404  # 남의 안내문
            assert (
                await client.post("/api/v1/guides/999999/feedback", json={"rating": 1}, headers=headers)
            ).status_code == 404
            assert (await client.post(f"/api/v1/guides/{gid}/feedback", json={"rating": 1})).status_code == 401
