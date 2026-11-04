"""P-1 ~ P-4 실천 API (REQ-110 ~ 112, 115). 포인트(P-6)와 달성 현황(P-5)은 뒤로 미룸"""

from datetime import date, datetime, timedelta

from starlette import status

from app.core import config
from app.models.analysis import AnalysisDisease
from app.models.habits import HabitGoal, HabitRecord, HabitStatus
from app.models.masters import Disease
from app.tests.analysis_apis.test_analysis_apis import AnalysisCase

REC = "/api/v1/recommendations"
GOALS = "/api/v1/habit-goals"


def today() -> date:
    return datetime.now(config.TIMEZONE).date()


class HabitCase(AnalysisCase):
    async def analysis(self, client, headers, user, diseases=("I10",)) -> int:
        rx = await self.prescription(user, ["641900040"], diseases)
        res = await self.start(client, headers, rx)
        assert res.status_code == status.HTTP_202_ACCEPTED, res.text
        return res.json()["analysisId"]

    @staticmethod
    async def recs(client, headers, aid: int) -> dict:
        res = await client.get(REC, params={"analysisId": aid}, headers=headers)
        assert res.status_code == status.HTTP_200_OK, res.text
        return res.json()

    @staticmethod
    async def goals(client, headers, ids: list[int]):
        return await client.post(GOALS, json={"recommendationIds": ids}, headers=headers)

    @staticmethod
    async def today_view(client, headers) -> dict:
        res = await client.get(f"{GOALS}/today", headers=headers)
        assert res.status_code == status.HTTP_200_OK, res.text
        return res.json()

    @staticmethod
    async def record(client, headers, goal_id: int, **body):
        return await client.post(f"{GOALS}/{goal_id}/records", json={"date": str(today()), **body}, headers=headers)


class TestRecommendations(HabitCase):
    async def test_hypertension_analysis_recommends_soup_and_walk(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h1@example.com")
            aid = await self.analysis(client, headers, user)
            body = await self.recs(client, headers, aid)
            assert body["hasDiseases"] is True
            assert [(i["title"], i["reasonLabel"], i["goalType"]) for i in body["items"]] == [
                ("국물 남기기", "고혈압", "check"),
                ("빠르게 걷기 30분", "고혈압", "quantity"),
            ]
            walk = body["items"][1]
            assert walk["targetValue"] == 30 and walk["unit"] == "분" and "cautionLabel" not in walk
            # 다시 불러도 같은 추천 번호 (목표가 추천을 가리킴)
            again = await self.recs(client, headers, aid)
            assert [i["id"] for i in again["items"]] == [i["id"] for i in body["items"]]

    async def test_no_disease_tells_app_to_pick_disease(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h2@example.com")
            aid = await self.analysis(client, headers, user, diseases=())
            body = await self.recs(client, headers, aid)
            assert body == {"items": [], "hasDiseases": False}

    async def test_other_users_analysis_is_404(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "h3@example.com")
            aid = await self.analysis(client, headers, user)
            other, _ = await self.auth(client, "h4@example.com")
            res = await client.get(REC, params={"analysisId": aid}, headers=other)
            assert res.status_code == status.HTTP_404_NOT_FOUND


class TestGoals(HabitCase):
    async def test_pick_one_to_three(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "g1@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            assert (await self.goals(client, headers, [])).status_code == status.HTTP_400_BAD_REQUEST
            assert (await self.goals(client, headers, [ids[0]] * 4)).status_code == status.HTTP_400_BAD_REQUEST
            res = await self.goals(client, headers, ids)
            assert res.status_code == status.HTTP_201_CREATED, res.text
            assert len(res.json()["goalIds"]) == 2

    async def test_other_users_recommendation_is_404(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "g2@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            other, _ = await self.auth(client, "g3@example.com")
            assert (await self.goals(client, other, ids)).status_code == status.HTTP_404_NOT_FOUND
            assert await HabitGoal.all().count() == 0

    async def test_picking_again_keeps_same_goals(self):
        # 다시 고르면 같은 목표는 그대로 두고(오늘 기록이 남음), 뺀 것만 끝내고, 새로 고른 것만 만듦 (#43, 10/30 수인)
        async with self.client() as client:
            headers, user = await self.auth(client, "g4@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            soup, walk = (await self.goals(client, headers, ids)).json()["goalIds"]
            await self.record(client, headers, soup, completed=True)
            assert (await self.goals(client, headers, ids)).json()["goalIds"] == [soup, walk]
            assert (await self.goals(client, headers, ids[:1])).json()["goalIds"] == [soup]
            view = await self.today_view(client, headers)
            assert view["totalCount"] == 1 and view["items"][0]["title"] == "국물 남기기"
            assert view["doneCount"] == 1
            assert await HabitGoal.filter(status=HabitStatus.ENDED).values_list("id", flat=True) == [walk]
            # 다른 분석의 같은 챌린지를 함께 고르면 400
            other = (await self.recs(client, headers, await self.analysis(client, headers, user)))["items"]
            assert (await self.goals(client, headers, [ids[0], other[0]["id"]])).status_code == 400

    async def test_picker_keeps_active_goal_from_older_analysis(self):
        # 고혈압 분석에서 국물 남기기와 걷기를 고른 뒤, 당뇨 분석(걷기만 추천)에서 다시 고를 때 국물 남기기도 보이고 그대로 이어짐
        async with self.client() as client:
            headers, user = await self.auth(client, "g5@example.com")
            old = (await self.recs(client, headers, await self.analysis(client, headers, user)))["items"]
            soup, walk = (await self.goals(client, headers, [i["id"] for i in old])).json()["goalIds"]
            new = await self.recs(client, headers, await self.analysis(client, headers, user, diseases=("E11",)))
            titles = [i["title"] for i in new["items"]]
            assert titles == ["빠르게 걷기 30분", "국물 남기기"], titles
            assert new["items"][1]["id"] == old[0]["id"] and new["items"][1]["reasonLabel"] == "고혈압"
            ids = [i["id"] for i in new["items"]]
            assert (await self.goals(client, headers, ids)).json()["goalIds"] == [walk, soup]
            assert await HabitGoal.filter(status=HabitStatus.ENDED).count() == 0
            # 국물 남기기를 빼면 그때만 끝남
            assert (await self.goals(client, headers, ids[:1])).json()["goalIds"] == [walk]
            assert await HabitGoal.filter(status=HabitStatus.ENDED).values_list("id", flat=True) == [soup]
            # 끝난 목표는 더 내려 주지 않음
            again = await self.recs(client, headers, await self.analysis(client, headers, user, diseases=("E11",)))
            assert [i["title"] for i in again["items"]] == ["빠르게 걷기 30분"]

    async def test_picker_keeps_active_goal_after_diseases_change(self):
        # 질환 직접 선택 등으로 분석의 질환이 바뀌어 추천이 다시 계산돼도, 실천 중인 목표는 다시 고르기에 남음
        async with self.client() as client:
            headers, user = await self.auth(client, "g6@example.com")
            aid = await self.analysis(client, headers, user)
            old = (await self.recs(client, headers, aid))["items"]
            soup, walk = (await self.goals(client, headers, [i["id"] for i in old])).json()["goalIds"]
            await AnalysisDisease.filter(analysis_id=aid).update(disease_id="E11")
            body = await self.recs(client, headers, aid)
            assert [i["title"] for i in body["items"]] == ["빠르게 걷기 30분", "국물 남기기"]
            assert (await self.goals(client, headers, [i["id"] for i in body["items"]])).json()["goalIds"] == [
                walk,
                soup,
            ]
            assert await HabitGoal.filter(status=HabitStatus.ENDED).count() == 0

    async def test_picker_marks_walk_that_changed_shape(self):
        # 당뇨 분석에서 "빠르게 걷기 30분"을 하던 중 허혈성심질환이 있는 분석을 열면 걷기가 "걷기"로 바뀜.
        # 같은 챌린지라서 어떤 목표를 대신하는지(replaces) 알려 줘야 앱이 미리 골라 주고 하던 목표가 사라진 것처럼 안 보임
        async with self.client() as client:
            await Disease.create(code="I25", name_kr="만성 허혈심장병")
            headers, user = await self.auth(client, "g7@example.com")
            old = await self.recs(client, headers, await self.analysis(client, headers, user, diseases=("E11",)))
            assert all("replaces" not in i for i in old["items"])
            (walk,) = (await self.goals(client, headers, [old["items"][0]["id"]])).json()["goalIds"]
            new = await self.recs(client, headers, await self.analysis(client, headers, user, diseases=("I25",)))
            assert [i["title"] for i in new["items"]] == ["걷기"]
            assert new["items"][0]["replaces"] == "빠르게 걷기 30분"
            # 고르면 하던 걷기는 끝나고 새 걷기가 만들어짐 (모양이 바뀌면 다른 목표, 10/30 수인)
            (heart,) = (await self.goals(client, headers, [new["items"][0]["id"]])).json()["goalIds"]
            assert heart != walk
            assert await HabitGoal.filter(status=HabitStatus.ENDED).values_list("id", flat=True) == [walk]
            # 이제 하는 목표와 제목이 같으니 replaces는 없음
            again = await self.recs(client, headers, await self.analysis(client, headers, user, diseases=("I25",)))
            assert [i["title"] for i in again["items"]] == ["걷기"] and "replaces" not in again["items"][0]


class TestToday(HabitCase):
    async def start_goals(self, client, email: str):
        headers, user = await self.auth(client, email)
        aid = await self.analysis(client, headers, user)
        ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
        goal_ids = (await self.goals(client, headers, ids)).json()["goalIds"]
        return headers, user, aid, goal_ids

    async def test_no_goals(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "t1@example.com")
            assert await self.today_view(client, headers) == {
                "hasGoals": False, "doneCount": 0, "totalCount": 0, "streakDays": 0, "items": []
            }  # fmt: skip

    async def test_check_and_quantity_records(self):
        async with self.client() as client:
            headers, _, _, (soup, walk) = await self.start_goals(client, "t2@example.com")
            view = await self.today_view(client, headers)
            assert view["hasGoals"] and view["doneCount"] == 0 and view["totalCount"] == 2
            assert view["items"][0] == {
                "goalId": soup, "title": "국물 남기기", "reasonLabel": "고혈압", "goalType": "check", "done": False
            }  # fmt: skip
            assert view["items"][1]["currentValue"] == 0 and view["items"][1]["targetValue"] == 30

            res = await self.record(client, headers, soup, completed=True)
            assert res.status_code == status.HTTP_200_OK, res.text
            assert res.json() == {"goalId": soup, "done": True, "allDone": False}
            # 같은 날 다시 완료하면 무시하고 200
            assert (await self.record(client, headers, soup, completed=True)).json()["done"] is True
            assert await HabitRecord.filter(goal_id=soup).count() == 1

            assert (await self.record(client, headers, walk, value=10)).json() == {
                "goalId": walk, "done": False, "currentValue": 10, "allDone": False
            }  # fmt: skip
            # value는 그날 한 총량. 저장 실패 배너(RW-03-E1)가 같은 요청을 다시 보내도 두 번 더해지지 않음 (REQ-115)
            assert (await self.record(client, headers, walk, value=10)).json()["currentValue"] == 10
            res = await self.record(client, headers, walk, value=30)
            assert res.json() == {"goalId": walk, "done": True, "currentValue": 30, "allDone": True}
            view = await self.today_view(client, headers)
            assert view["doneCount"] == 2 and view["streakDays"] == 1

    async def test_undo_records(self):
        # 완료 취소 허용 (10/2 회의 결정, #43). 체크형은 completed=false, 수량형은 총량을 줄임
        async with self.client() as client:
            headers, _, _, (soup, walk) = await self.start_goals(client, "t6@example.com")
            await self.record(client, headers, soup, completed=True)
            await self.record(client, headers, walk, value=30)
            res = await self.record(client, headers, soup, completed=False)
            assert res.json() == {"goalId": soup, "done": False, "allDone": False}
            res = await self.record(client, headers, walk, value=20)
            assert res.json() == {"goalId": walk, "done": False, "currentValue": 20, "allDone": False}
            assert (await self.record(client, headers, walk, value=0)).json()["currentValue"] == 0
            view = await self.today_view(client, headers)
            assert view["doneCount"] == 0 and view["streakDays"] == 0

    async def test_bad_records(self):
        async with self.client() as client:
            headers, _, _, (soup, walk) = await self.start_goals(client, "t3@example.com")
            yesterday = str(today() - timedelta(days=1))
            res = await client.post(
                f"{GOALS}/{soup}/records", json={"date": yesterday, "completed": True}, headers=headers
            )
            assert res.status_code == status.HTTP_400_BAD_REQUEST  # 오늘 기록만 (몰아서 체크 막기)
            assert (await self.record(client, headers, soup)).status_code == status.HTTP_400_BAD_REQUEST
            assert (await self.record(client, headers, walk, completed=True)).status_code == 400  # 수량형은 값으로
            assert (await self.record(client, headers, walk, value=601)).status_code == 400
            other, _ = await self.auth(client, "t4@example.com")
            assert (await self.record(client, other, soup, completed=True)).status_code == 404

    async def test_streak_counts_days_with_any_done_goal(self):
        # 연속 실천일: 어떤 목표든 하루 1개 이상 완료, 목표가 바뀌어도 이어짐 (REQ-114)
        async with self.client() as client:
            headers, user, aid, (soup, _walk) = await self.start_goals(client, "t5@example.com")
            for back in (1, 2):
                await HabitRecord.create(goal_id=soup, record_date=today() - timedelta(days=back), completed=True)
            await HabitRecord.create(goal_id=soup, record_date=today() - timedelta(days=4), completed=True)
            assert (await self.today_view(client, headers))["streakDays"] == 2  # 오늘 아직 안 했으면 어제까지
            await self.record(client, headers, soup, completed=True)
            assert (await self.today_view(client, headers))["streakDays"] == 3


class TestDeletes(HabitCase):
    async def test_deleting_analysis_keeps_goals_without_reason(self):
        # R-8: 추천은 지우고 목표와 기록은 남김, 추천 이유(질환 라벨)도 같이 사라짐
        async with self.client() as client:
            headers, user = await self.auth(client, "d1@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            await self.goals(client, headers, ids)
            res = await client.delete(f"/api/v1/analyses/{aid}", headers=headers)
            assert res.status_code == status.HTTP_204_NO_CONTENT, res.text
            view = await self.today_view(client, headers)
            assert view["totalCount"] == 2 and all("reasonLabel" not in i for i in view["items"])

    async def test_consent_withdrawal_ends_goals_and_keeps_records(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d2@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            goal_ids = (await self.goals(client, headers, ids)).json()["goalIds"]
            await self.record(client, headers, goal_ids[0], completed=True)
            res = await client.delete("/api/v1/users/me/consents/sensitiveHealth", headers=headers)
            assert res.status_code == status.HTTP_204_NO_CONTENT, res.text
            assert (await self.today_view(client, headers))["hasGoals"] is False
            assert await HabitGoal.filter(user=user, status=HabitStatus.ENDED).count() == 2
            assert await HabitRecord.filter(goal_id=goal_ids[0]).count() == 1

    async def test_account_withdrawal_deletes_goals(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "d3@example.com")
            aid = await self.analysis(client, headers, user)
            ids = [i["id"] for i in (await self.recs(client, headers, aid))["items"]]
            await self.goals(client, headers, ids)
            res = await client.request("DELETE", "/api/v1/users/me", json={"confirmed": True}, headers=headers)
            assert res.status_code == status.HTTP_204_NO_CONTENT, res.text
            assert await HabitGoal.filter(user_id=user.id).count() == 0
