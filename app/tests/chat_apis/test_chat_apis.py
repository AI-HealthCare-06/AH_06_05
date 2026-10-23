"""H-1 ~ H-8 챗봇 API (#100). 답 만들기는 가짜로 바꿔 흐름만 확인 (CI에서 OpenAI를 부르지 않음).

1층과 문맥 파악은 실제 규칙으로 돌림 (AI 없음, 명세서 H-3 "저장 전에 봄").
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from starlette import status

from app.core import config
from app.models.analysis import DrugGuide, ReviewStatus
from app.models.chat import ChatMessage, ChatSession, MessageRole, MessageStatus
from app.models.users import ConsentType, UserConsent
from app.services import chats, safety
from app.services.chatbot.context import FixedInfo
from app.services.chatbot.llm import Usage
from app.services.chatbot.pipeline import Reply, Route
from app.tests.analysis_apis.test_analysis_apis import AnalysisCase

API = "/api/v1/chat/sessions"
EMERGENCY_TEXT = "약 먹고 나서 가슴이 조여요"  # 1층 chest
CRISIS_TEXT = "죽고 싶어요"  # 1층 self_harm


class FakeAnswer:
    """chats.run_pipeline 자리에 넣는 가짜. 받은 값을 남기고 정해 둔 답을 돌려줌"""

    def __init__(self, reply: Reply | Exception | None = None) -> None:
        self.reply = reply
        self.before: Callable[[], Awaitable[None]] | None = None  # 답을 돌려주기 전에 할 일 (느린 답, 도중 삭제)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, question: str, info: FixedInfo, history: list[dict[str, str]], emergency_dismissed: bool = False
    ) -> Reply:
        self.calls.append({"question": question, "info": info, "history": history, "dismissed": emergency_dismissed})
        if self.before:
            await self.before()
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply or normal_reply()


def normal_reply(sources: list[str] | None = None) -> Reply:
    usage = Usage(prompt_tokens=120, completion_tokens=40, calls=3)
    return Reply("normal", "식사 직후에 드시는 게 좋아요.", Route(kind="medication"), sources or [], usage=usage)


class ChatCase(AnalysisCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.fake = FakeAnswer()
        self._chat_patch = patch.object(chats, "run_pipeline", self.fake)
        self._chat_patch.start()

    async def asyncTearDown(self):
        self._chat_patch.stop()
        await super().asyncTearDown()

    @staticmethod
    async def session(client, headers, crid: str = "s-1", **body: Any) -> int:
        res = await client.post(API, json={"clientRequestId": crid, **body}, headers=headers)
        assert res.status_code == status.HTTP_201_CREATED, res.text
        return res.json()["sessionId"]

    @staticmethod
    async def ask(client, headers, sid: int, content: str, crid: str = "q-1", **body: Any):
        return await client.post(
            f"{API}/{sid}/messages", json={"content": content, "clientRequestId": crid, **body}, headers=headers
        )

    @staticmethod
    async def items(client, headers, sid: int) -> list[dict[str, Any]]:
        res = await client.get(f"{API}/{sid}/messages", headers=headers)
        assert res.status_code == status.HTTP_200_OK, res.text
        return res.json()["items"]


def next_midnight() -> datetime:
    now = datetime.now(config.TIMEZONE)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


class TestSessions(ChatCase):
    async def test_start_is_idempotent_and_today_finds_it(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "c1@example.com")
            today = (await client.get(f"{API}/today", headers=headers)).json()
            assert today == {"sessionId": None, "hasHistory": False, "safetyModeUntil": None}
            sid = await self.session(client, headers)
            assert await self.session(client, headers) == sid  # 같은 clientRequestId면 새로 만들지 않음
            today = (await client.get(f"{API}/today", headers=headers)).json()
        assert today == {"sessionId": sid, "hasHistory": True, "safetyModeUntil": None}

    async def test_start_with_analysis_makes_no_card_row(self):
        """H-1 analysisId는 대화에만 적고 맥락 카드 줄은 만들지 않음 (10/22)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "c2@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=aid)
            assert await self.items(client, headers, sid) == []
        assert (await ChatSession.get(id=sid)).analysis_id == aid

    async def test_start_keeps_context(self):
        """H-1 context(RG-03, RG-04에서 열었을 때)는 대화에 적음"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "c8@example.com")
            sid = await self.session(client, headers, context={"type": "warning", "id": 9001})
        s = await ChatSession.get(id=sid)
        assert (s.context_type, s.context_ref) == ("warning", 9001)

    async def test_other_users_data_is_404(self):
        async with self.client() as client:
            h1, u1 = await self.auth(client, "c3@example.com")
            h2, _ = await self.auth(client, "c4@example.com")
            aid = (await self.start(client, h1, await self.prescription(u1, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, h1)
            assert (
                await client.post(API, json={"clientRequestId": "x", "analysisId": aid}, headers=h2)
            ).status_code == 404
            assert (await client.get(f"{API}/{sid}/messages", headers=h2)).status_code == 404
            assert (await self.ask(client, h2, sid, "안녕하세요")).status_code == 404
            assert (await client.delete(f"{API}/{sid}", headers=h2)).status_code == 404
            ctx = {"analysisId": aid, "clientRequestId": "c"}
            assert (await client.post(f"{API}/{sid}/context", json=ctx, headers=h2)).status_code == 404
            own = await self.session(client, h2, crid="s-2")  # 내 대화에 남의 분석 번호
            assert (await client.post(f"{API}/{own}/context", json=ctx, headers=h2)).status_code == 404

    async def test_delete_session(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "c5@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "메트포르민은 밥 먹고 먹어야 하나요?")
            assert (await client.delete(f"{API}/{sid}", headers=headers)).status_code == status.HTTP_204_NO_CONTENT
            assert (await client.get(f"{API}/{sid}/messages", headers=headers)).status_code == 404
        assert await ChatMessage.filter(session_id=sid).count() == 0

    async def test_context_card_once_per_request(self):
        """H-7: 맥락 카드 줄을 남기고, 같은 clientRequestId면 새로 만들지 않음. firstMessage는 아직 없음 (#116)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "c6@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers)
            body = {"analysisId": aid, "context": {"type": "drug", "id": 7001}, "clientRequestId": "ctx-1"}
            for _ in range(2):
                res = await client.post(f"{API}/{sid}/context", json=body, headers=headers)
                assert res.status_code == status.HTTP_201_CREATED and "firstMessage" not in res.json()
            items = await self.items(client, headers, sid)
        assert len(items) == 1
        card = items[0]
        assert card["role"] == "assistant" and card["content"] == "" and card["status"] == "done"
        assert card["contextCard"] == {"analysisId": aid, "context": {"type": "drug", "id": 7001}}
        assert "replyTo" not in card

    async def test_deleting_analysis_deletes_linked_chats(self):
        """R-8: 분석을 지우면 그 분석으로 시작한 대화와 그 분석의 맥락 카드가 붙은 대화를 메시지째 지움 (명세서 R-8, #119 리뷰 10/23).
        다른 분석의 카드만 붙은 대화는 남김"""
        async with self.client() as client:
            headers, user = await self.auth(client, "c7@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            other = (await self.start(client, headers, await self.prescription(user, ["645600020"]))).json()[
                "analysisId"
            ]
            started = await self.session(client, headers, "s-1", analysisId=aid)
            carded = await self.session(client, headers, "s-2")
            kept = await self.session(client, headers, "s-3")
            for sid, target in ((carded, aid), (kept, other)):
                body = {"analysisId": target, "clientRequestId": f"ctx-{sid}"}
                assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            assert (await self.ask(client, headers, carded, "그 약은 언제 먹어요?")).status_code == 202
            assert (await client.delete(f"/api/v1/analyses/{aid}", headers=headers)).status_code == 204
            assert (await client.get(f"{API}/{carded}/messages", headers=headers)).status_code == 404
        assert await ChatSession.filter(id__in=[started, carded]).count() == 0
        assert await ChatMessage.filter(session_id=carded).count() == 0
        assert await ChatSession.filter(id=kept).exists()
        assert await ChatMessage.filter(session_id=kept).count() == 1


def test_sources_map_fact_ids_by_lifestyle_name():
    """팩트표 생활습관 번호 F:<질환>:life:<항목 이름>을 그 항목의 출처로 이음 (조각 파일 번호 모양, #119 채연 리뷰).
    목표 수치, 약 연결, 위험 신호, 질환 겹침은 출처 칸이 없어 붙이지 않음. 없는 항목, 모르는 질환도 뺌. 같은 출처는 한 번만"""
    ids = [
        "F:HTN:life:나트륨 줄이기",
        "F:HTN:life:혈압 자가측정",
        "F:HTN:life:없는 항목",
        "F:NONE:life:금연",
        "F:HTN:target",
        "F:HTN:med:1",
        "F:HTN:warn",
        "F:X:cross:1",
        "D:1:S1",
        "D:2:S3",
    ]
    assert chats._sources(ids) == [
        {"title": "질병관리청 국가건강정보포털"},
        {"title": "대한고혈압학회 진료지침"},
        {"title": "대한고혈압학회 가정혈압 측정 권고"},
        {"title": "식약처 의약품 허가정보"},
    ]


class TestAsk(ChatCase):
    async def test_202_then_answer_appears_in_messages(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a1@example.com")
            sid = await self.session(client, headers)
            self.fake.reply = normal_reply(["D:645600020:S3", "F:HTN:life:나트륨 줄이기"])
            res = await self.ask(client, headers, sid, "  메트포르민은 밥 먹고 먹어야 하나요?  ")
            assert res.status_code == status.HTTP_202_ACCEPTED
            mid = res.json()["messageId"]
            assert set(res.json()) == {"messageId"}
            q, a = await self.items(client, headers, sid)
        assert q["role"] == "user" and q["content"] == "메트포르민은 밥 먹고 먹어야 하나요?" and q["status"] == "done"
        assert a["id"] == mid and a["role"] == "assistant" and a["status"] == "done"
        assert a["answerType"] == "normal" and a["replyTo"] == q["id"] and a["content"]
        # 팩트표 F:<질환>:life:<항목 이름>은 lifestyle_facts.json 그 항목의 출처를 붙임 (#119 채연 리뷰)
        assert a["sources"] == [
            {"title": "식약처 의약품 허가정보"},
            {"title": "질병관리청 국가건강정보포털"},
            {"title": "대한고혈압학회 진료지침"},
        ]
        assert "model" not in a and "latencyMs" not in a
        row = await ChatMessage.get(id=mid)
        assert row.model == config.OPENAI_CHAT_MODEL and (row.prompt_tokens, row.completion_tokens) == (120, 40)
        assert row.latency_ms is not None and row.latency_ms >= 0

    async def test_content_must_be_1_to_500_after_trim(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a2@example.com")
            sid = await self.session(client, headers)
            for bad in ("", "   ", "가" * 501):
                res = await self.ask(client, headers, sid, bad, crid=f"bad-{len(bad)}")
                assert res.status_code == status.HTTP_400_BAD_REQUEST, bad
                assert res.json()["error"]["code"] == "VALIDATION_ERROR" and res.json()["error"]["field"] == "content"
            assert (await self.ask(client, headers, sid, " " + "가" * 500 + " ", crid="ok")).status_code == 202

    async def test_same_request_returns_same_answer(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a3@example.com")
            sid = await self.session(client, headers)
            first = (await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")).json()["messageId"]
            again = (await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")).json()["messageId"]
        assert first == again and len(self.fake.calls) == 1
        assert await ChatMessage.filter(session_id=sid, role=MessageRole.USER).count() == 1

    async def test_failure_deletes_answer_row_and_retry_makes_new(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a4@example.com")
            sid = await self.session(client, headers)
            self.fake.reply = RuntimeError("boom")
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            assert [i["role"] for i in await self.items(client, headers, sid)] == ["user"]
            self.fake.reply = Reply("error", None, Route(kind="error"))  # 2층이나 답 만들기가 응답하지 않음
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            assert [i["role"] for i in await self.items(client, headers, sid)] == ["user"]
            self.fake.reply = normal_reply()
            mid = (await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")).json()["messageId"]
            q, a = await self.items(client, headers, sid)
        assert a["id"] == mid and a["replyTo"] == q["id"] and a["status"] == "done"

    async def test_slow_answer_is_cut_and_row_deleted(self):
        """답 만들기는 25초 안에서 끊음. 30초가 지나 새로 만드는 답과 겹치지 않게 (10/22)"""
        self.fake.before = lambda: asyncio.sleep(1)
        with patch.object(chats, "ANSWER_TIMEOUT_SEC", 0.05):
            async with self.client() as client:
                headers, _ = await self.auth(client, "a9@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
                assert [i["role"] for i in await self.items(client, headers, sid)] == ["user"]

    async def test_answer_not_saved_when_row_deleted_meanwhile(self):
        """만드는 동안 답 줄이 지워졌으면(30초 정리) 저장하지 않음 (10/22)"""

        async def delete_generating() -> None:
            await ChatMessage.filter(status=MessageStatus.GENERATING).delete()

        self.fake.before = delete_generating
        async with self.client() as client:
            headers, _ = await self.auth(client, "a10@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        assert not await ChatMessage.filter(session_id=sid, role=MessageRole.ASSISTANT).exists()

    async def test_generating_row_is_kept_then_replaced_after_30s(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a5@example.com")
            sid = await self.session(client, headers)
            q = await ChatMessage.create(session_id=sid, role=MessageRole.USER, content="질문", client_request_id="q-1")
            old = await ChatMessage.create(
                session_id=sid, role=MessageRole.ASSISTANT, status=MessageStatus.GENERATING, reply_to=q
            )
            same = (await self.ask(client, headers, sid, "질문")).json()["messageId"]
            assert same == old.id and self.fake.calls == []  # 만드는 중이면 같은 messageId
            await ChatMessage.filter(id=old.id).update(created_at=datetime.now(config.TIMEZONE) - timedelta(seconds=31))
            new = (await self.ask(client, headers, sid, "질문")).json()["messageId"]
        assert new != old.id and not await ChatMessage.exists(id=old.id)
        assert (await ChatMessage.get(id=new)).status == MessageStatus.DONE

    async def test_layer1_emergency_saves_no_raw_text(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a6@example.com")
            sid = await self.session(client, headers)
            res = await self.ask(client, headers, sid, EMERGENCY_TEXT)
            assert res.status_code == 202
            q, a = await self.items(client, headers, sid)
        assert self.fake.calls == []  # AI를 부르지 않음
        assert q["content"] == "" and a["answerType"] == "emergency" and a["status"] == "done"
        assert a["safety"]["types"] == ["emergency"] and a["safety"]["overdose"] is False and a["safety"]["rule"]
        assert not await ChatMessage.filter(content__contains="가슴").exists()

    async def test_dismissed_resend_skips_emergency(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a7@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, EMERGENCY_TEXT)
            await self.ask(client, headers, sid, EMERGENCY_TEXT, crid="q-2", emergencyDismissed=True)
            items = await self.items(client, headers, sid)
        assert len(self.fake.calls) == 1 and self.fake.calls[0]["dismissed"] is True
        assert items[-1]["answerType"] == "normal" and items[-2]["content"] == EMERGENCY_TEXT

    async def test_crisis_turns_on_safety_mode_until_midnight(self):
        async with self.client() as client:
            headers, _ = await self.auth(client, "a8@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, CRISIS_TEXT)
            items = await self.items(client, headers, sid)
            today = (await client.get(f"{API}/today", headers=headers)).json()
        assert items[-1]["answerType"] == "crisis" and items[0]["content"] == ""
        assert datetime.fromisoformat(today["safetyModeUntil"]) == next_midnight()


class TestFixedInfo(ChatCase):
    async def test_uses_latest_card_analysis_with_consent(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f1@example.com")
            await DrugGuide.create(
                edi_code="641900040",
                content={"purpose": "혈압 관리에 쓰는 약이에요"},
                review_status=ReviewStatus.APPROVED,
            )
            first = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()[
                "analysisId"
            ]
            rx = await self.prescription(user, ["641900040"], ("I10",))
            second = (await self.start(client, headers, rx)).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=first)
            body = {"analysisId": second, "clientRequestId": "ctx"}
            assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        info = self.fake.calls[0]["info"]
        assert [d.code for d in info.drugs] == ["641900040"]  # 가장 최근에 붙은 맥락 카드의 분석
        assert info.drugs[0].name.startswith("노바스크정") and info.drugs[0].purpose == "혈압 관리에 쓰는 약이에요"
        assert info.disease_ids == ["HTN"] and info.age is not None

    async def test_unapproved_guide_gives_no_purpose(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f2@example.com")
            await DrugGuide.create(edi_code="641900040", content={"purpose": "검토 전 문장"})
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=aid)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        assert self.fake.calls[0]["info"].drugs[0].purpose == ""

    async def test_missing_safety_db_still_answers(self):
        """성분 이름을 읽는 점검 DB가 없어도 답은 만들고 성분만 비움 (10/22)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f5@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=aid)
            with patch.object(config, "SAFETY_DB_PATH", ""):
                safety.reset_checker()
                await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            items = await self.items(client, headers, sid)
        assert self.fake.calls[0]["info"].drugs[0].ingredient == "" and items[-1]["status"] == "done"

    async def test_no_consent_means_general_info_only(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f3@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(
                agreed=False, withdrawn_at=datetime.now(config.TIMEZONE)
            )
            sid = await self.session(client, headers, analysisId=aid)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        info = self.fake.calls[0]["info"]
        assert info.drugs == [] and info.diseases == [] and info.disease_ids == []
        assert info.age is None  # 나이도 넣지 않음 (설계 메모 0-1 항목 5 "일반 정보만", 10/22)

    async def test_history_skips_empty_layer1_question(self):
        """1층이 잡아 원문이 없는 질문과 그 긴급 답은 다음 질문의 대화 기억에 넣지 않음"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f4@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, EMERGENCY_TEXT)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?", crid="q-2")
        assert self.fake.calls[0]["history"] == []
