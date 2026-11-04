"""H-1 ~ H-8 챗봇 API (#100). 답 만들기는 가짜로 바꿔 흐름만 확인 (CI에서 OpenAI를 부르지 않음).

1층과 문맥 파악은 실제 규칙으로 돌림 (AI 없음, 명세서 H-3 "저장 전에 봄").
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from starlette import status

from app.core import config
from app.models.analysis import Analysis, AnalysisStatus, AnalysisWarning, DrugGuide, ReviewStatus
from app.models.chat import ChatMessage, ChatSession, MessageRole, MessageStatus
from app.models.masters import DrugProduct
from app.models.ocr import PrescriptionItem
from app.models.users import ConsentType, UserConsent
from app.services import chat_photo, chats, safety
from app.services.chatbot import jev
from app.services.chatbot.answer import DISTRESS, OUT_OF_SCOPE
from app.services.chatbot.context import FixedInfo
from app.services.chatbot.llm import Usage
from app.services.chatbot.pipeline import Reply, Route
from app.services.drug_names import base_name
from app.services.ocr import clova
from app.services.ocr.matcher import NameMatcher
from app.tests.analysis_apis.test_analysis_apis import PRODUCTS, AnalysisCase

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
        self,
        question: str,
        info: FixedInfo,
        history: list[dict[str, str]],
        emergency_dismissed: bool = False,
        recent: list[str] | None = None,
    ) -> Reply:
        self.calls.append(
            {"question": question, "info": info, "history": history, "dismissed": emergency_dismissed, "recent": recent}
        )
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

    async def test_session_history_by_month_and_date(self):
        """H-4: ?month=는 기록 있는 날짜, ?date=는 그날 대화. 날짜는 대화를 시작한 때(한국 시간). 제목이 없으면 첫 질문 앞부분"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f20@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "가슴이 조이고 숨이 차요", crid="q-e")  # 1층: 원문 없음
            long_q = "혈압약을 아침에 먹는 게 좋은지 저녁에 먹는 게 좋은지 궁금해서 여쭤봐요 정말로요"
            await self.ask(client, headers, sid, long_q, crid="q-1")
            old = await self.session(client, headers, crid="s-2")
            await self.ask(client, headers, old, "가슴이 조이고 숨이 차요", crid="q-o")  # 원문이 없어 제목은 "대화"
            nothing = await self.session(client, headers, crid="s-3")  # 줄이 없는 대화는 목록에 없음
            await ChatSession.filter(id=nothing).update(created_at=datetime(2026, 9, 3, 9, tzinfo=config.TIMEZONE))
            at = datetime(2026, 9, 16, 23, 30, tzinfo=config.TIMEZONE)
            await ChatSession.filter(id=old).update(created_at=at)
            today = datetime.now(config.TIMEZONE).date()

            res = await client.get(f"{API}?month={today:%Y-%m}", headers=headers)
            assert res.status_code == 200 and res.json() == {"dates": [today.isoformat()]}
            assert (await client.get(f"{API}?month=2026-09", headers=headers)).json() == {"dates": ["2026-09-16"]}

            items = (await client.get(f"{API}?date={today}", headers=headers)).json()["items"]
            assert [i["sessionId"] for i in items] == [sid]
            assert items[0]["title"] == long_q[:30] and items[0]["preview"] == long_q[:60]
            assert items[0]["createdAt"] and items[0]["updatedAt"]
            empty = (await client.get(f"{API}?date=2026-09-16", headers=headers)).json()["items"][0]
            assert empty["sessionId"] == old and empty["title"] == "대화" and empty["preview"] == ""

            for bad in ("", "?date=2026-13-40", "?month=2026", f"?date={today}&month=2026-09"):
                assert (await client.get(f"{API}{bad}", headers=headers)).status_code == 400, bad

    async def test_session_title_update(self):
        """H-5: 앞뒤 공백을 지운 뒤 1~30자. 남의 대화는 404"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f21@example.com")
            h2, _ = await self.auth(client, "f22@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 언제 먹어요?")
            res = await client.patch(f"{API}/{sid}", json={"title": " 혈압약 복용 시간 "}, headers=headers)
            assert res.status_code == 200 and res.json() == {"sessionId": sid, "title": "혈압약 복용 시간"}
            today = datetime.now(config.TIMEZONE).date()
            items = (await client.get(f"{API}?date={today}", headers=headers)).json()["items"]
            assert items[0]["title"] == "혈압약 복용 시간"
            for title in ("   ", "가" * 31):
                res = await client.patch(f"{API}/{sid}", json={"title": title}, headers=headers)
                assert res.status_code == 400 and res.json()["error"]["code"] == "VALIDATION_ERROR"
            assert (await client.patch(f"{API}/{sid}", json={"title": "남"}, headers=h2)).status_code == 404

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

    async def test_no_evidence_reason_is_logged_without_question(self):
        """근거 없음은 검색 이유를 로그에 남겨 서버에서 원인을 찾게 함 (10/25 서버 확인). 질문 글과 약 이름은 남기지 않음"""
        self.fake.reply = Reply(
            "no_evidence",
            "근거를 찾지 못했어요.",
            Route(kind="medication"),
            evidence_reason="insufficient",
            evidence_verdicts="a=INSUFFICIENT b=PARTIAL/indirect c=NONE",
        )
        with self.assertLogs(chats.logger, "WARNING") as logs:
            async with self.client() as client:
                headers, _ = await self.auth(client, "a11@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        line = "\n".join(logs.output)
        assert "reason=insufficient" in line and "kind=medication" in line and "drugs=0" in line
        # 답 유형 칸 이름은 answer_type, 어느 판정에서 막혔는지도 남김 (#124 채연 리뷰)
        assert "answer_type=no_evidence" in line and " answer=" not in line
        assert "verdicts=a=INSUFFICIENT b=PARTIAL/indirect c=NONE" in line
        assert "혈압약" not in line

    async def test_answer_with_evidence_leaves_no_reason_log(self):
        """근거가 있는 답(이유 없음)은 근거 없음 로그를 남기지 않음 (#124 채연 리뷰)"""
        self.fake.reply = normal_reply()
        with self.assertNoLogs(chats.logger, "WARNING"):
            async with self.client() as client:
                headers, _ = await self.auth(client, "a12@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")

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

    async def test_layer1_only_session_title_stays_default(self):
        """1층이 잡은 질문만 있는 대화는 긴급 답을 목록 제목으로 쓰지 않음 (첫 답 제목은 질문 없이 카드에서 연 대화만)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "a6t@example.com")
            sid = await self.session(client, headers)
            assert (await self.ask(client, headers, sid, EMERGENCY_TEXT)).status_code == 202
            today = datetime.now(config.TIMEZONE).date()
            items = (await client.get(f"{API}?date={today}", headers=headers)).json()["items"]
        assert {i["sessionId"]: i["title"] for i in items}[sid] == "대화"

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

    async def test_amount_question_in_safety_mode_gets_crisis_card(self):
        """안전 모드(그 대화 안, 자정까지)에서 약의 양 질문은 원문 없이 E5로, AI를 부르지 않음 (설계 메모 4-6, #116)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "a13@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, CRISIS_TEXT)
            await self.ask(client, headers, sid, "노바스크 한 번에 몇 알 먹어요?", crid="q-2")
            items = await self.items(client, headers, sid)
        assert self.fake.calls == []
        assert [i["answerType"] for i in items if i["role"] == "assistant"] == ["crisis", "crisis"]
        assert items[-2]["content"] == "" and items[-1]["safety"]["types"] == ["crisis"]
        assert items[-1]["safety"]["rule"] == "safety_mode_amount"

    async def test_safety_mode_follows_user_to_past_chat(self):
        """지난 대화를 열어(CB-03) 물어도 오늘 안전 모드가 그대로. 양 질문은 원문 없이 E5로 (제안, 11/2)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "a14@example.com")
            old = await self.session(client, headers, crid="s-old")
            await ChatSession.filter(id=old).update(created_at=datetime.now(config.TIMEZONE) - timedelta(days=3))
            sid = await self.session(client, headers, crid="s-new")
            await self.ask(client, headers, sid, CRISIS_TEXT)
            await self.ask(client, headers, old, "노바스크 한 번에 몇 알 먹어요?", crid="q-2")
            items = await self.items(client, headers, old)
        assert self.fake.calls == []
        assert items[-1]["safety"]["rule"] == "safety_mode_amount"

    async def test_deleting_chats_keeps_safety_mode(self):
        """대화를 지워도(H-6, 전체 삭제) 자정까지 안전 모드가 남고, 글은 모두 지워지며 목록에 보이지 않음 (설계 메모 4-6)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "a15@example.com")
            for how in ("one", "all"):
                sid = await self.session(client, headers, crid=f"s-{how}")
                await self.ask(client, headers, sid, CRISIS_TEXT, crid=f"q-{how}")
                url = f"{API}/{sid}" if how == "one" else API
                assert (await client.delete(url, headers=headers)).status_code == 204
                today = (await client.get(f"{API}/today", headers=headers)).json()
                assert datetime.fromisoformat(today["safetyModeUntil"]) == next_midnight()
                assert await ChatMessage.filter(session_id=sid).count() == 0
                day = datetime.now(config.TIMEZONE).date().isoformat()
                listed = (await client.get(f"{API}?date={day}", headers=headers)).json()["items"]
                assert listed == []

    async def test_delete_all_sessions_only_mine(self):
        """전체 삭제 (MY-S1): 내 대화만 지움"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "a16@example.com")
            other, _ = await self.auth(client, "a17@example.com")
            mine = await self.session(client, headers, crid="s-1")
            theirs = await self.session(client, other, crid="s-2")
            assert (await client.delete(API, headers=headers)).status_code == 204
            assert (await client.get(f"{API}/{mine}/messages", headers=headers)).status_code == 404
            assert (await client.get(f"{API}/{theirs}/messages", headers=other)).status_code == 200

    async def test_amount_question_without_safety_mode_goes_to_answer(self):
        """안전 모드가 아니면 같은 질문도 보통 흐름으로. 안전 모드여도 때를 묻는 질문은 보통 흐름"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "a14@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "노바스크 한 번에 몇 알 먹어요?")
            await self.ask(client, headers, sid, CRISIS_TEXT, crid="q-2")
            await self.ask(client, headers, sid, "약 언제 먹어요?", crid="q-3")
        assert len(self.fake.calls) == 2


class TestQuestionNumbersMasked(ChatCase):
    async def test_id_numbers_are_hidden_before_saving_and_answering(self):
        """주민번호, 전화번호는 저장과 OpenAI로 가기 전에 가림. 1층은 원문을 봄 (#100 입력 정책, 10/31 수인 결정)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "m1@example.com")
            sid = await self.session(client, headers)
            text = "제 번호 010-1234-5678이고 주민번호 500101-1234567인데 혈압약은 언제 먹어요?"
            await self.ask(client, headers, sid, text)
            items = await self.items(client, headers, sid)
        want = "제 번호 [전화번호]이고 주민번호 [주민번호]인데 혈압약은 언제 먹어요?"
        assert items[0]["content"] == want
        assert self.fake.calls[0]["question"] == want

    async def test_guard_gets_recent_user_turns_including_out_of_scope(self):
        """2층에 앞 사용자 말 2개를 참고로 줌. 범위 밖으로 걸러진 말도 넣고(괴로움이 범위 밖으로 간 경우), 1층이 잡아 원문이 없는 말은 빠짐 (#143)"""
        self.fake.reply = Reply("normal", "범위 밖 응대", Route(kind="out_of_scope"))
        async with self.client() as client:
            headers, _ = await self.auth(client, "g1@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "요즘 사는 게 너무 힘들어요", crid="q-1")
            await self.ask(client, headers, sid, "가슴이 조이고 숨이 차요", crid="q-2")  # 1층: 원문 없음
            await self.ask(client, headers, sid, "오늘 날씨 좋네요", crid="q-3")
            await self.ask(client, headers, sid, "남은 약은 어떻게 하면 돼요?", crid="q-4")
        assert self.fake.calls[-1]["recent"] == ["요즘 사는 게 너무 힘들어요", "오늘 날씨 좋네요"]
        assert self.fake.calls[-1]["history"] == []  # 답 기억에는 범위 밖 말을 넣지 않음 (그대로)

    async def test_jev_is_skipped_without_the_risk_check_consent(self):
        """위험 판단 AI 전달에 동의하지 않은 사람의 질문은 TypeSafe로 가지 않음: Jev를 부르지 않고 보통 흐름 (11/2 수인 결정, 제안)"""
        asked: list[str] = []

        async def judge(question: str) -> tuple[str, float]:
            asked.append(question)
            return "crisis", 0.05

        on = {"SAFETY_JEV": True, "TYPESAFE_API_KEY": "test-key"}
        with patch.multiple(config, **on), patch.object(jev, "_typesafe", judge):
            async with self.client() as client:
                headers, _ = await self.auth(client, "a19@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "요즘 사는 게 다 귀찮네요")
        assert asked == [] and len(self.fake.calls) == 1  # TypeSafe로 보내지 않고 답 만들기로 감

    async def test_jev_gets_masked_text_only(self):
        """TypeSafe로 가는 글에도 전화번호, 이메일은 가려서 (OpenAI로 보낼 때와 같게, 동의 문구에 적은 약속)"""
        asked: list[str] = []

        async def judge(question: str) -> tuple[str, float]:
            asked.append(question)
            return "none", 0.99

        on = {"SAFETY_JEV": True, "TYPESAFE_API_KEY": "test-key"}
        with patch.multiple(config, **on), patch.object(jev, "_typesafe", judge):
            async with self.client() as client:
                headers, user = await self.auth(client, "a20@example.com")
                await UserConsent.create(
                    user=user, consent_type=ConsentType.RISK_CHECK, agreed=True, agreed_at=datetime.now(config.TIMEZONE)
                )
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "010-1234-5678 번호로 연락 온 약 광고인데 혈압약 먹어도 돼요?")
        assert len(asked) == 1 and "010-1234-5678" not in asked[0] and "혈압약" in asked[0]

    async def test_jev_block_saves_no_raw_text(self):
        """1층 규칙에 안 걸려도 Jev가 확신하면 저장 전에 막음: 원문 없이 저장, AI를 부르지 않음 (10/26 수인 결정)"""

        async def judge(question: str) -> tuple[str, float]:
            return "crisis", 0.05

        on = {"SAFETY_JEV": True, "TYPESAFE_API_KEY": "test-key"}
        with patch.multiple(config, **on), patch.object(jev, "_typesafe", judge):
            async with self.client() as client:
                headers, user = await self.auth(client, "a9@example.com")
                await UserConsent.create(
                    user=user, consent_type=ConsentType.RISK_CHECK, agreed=True, agreed_at=datetime.now(config.TIMEZONE)
                )  # 위험 판단 AI 전달 동의가 있는 사람만 Jev를 거침
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "요즘 사는 게 다 귀찮네요")
                q, a = await self.items(client, headers, sid)
        assert self.fake.calls == []
        assert q["content"] == "" and a["answerType"] == "crisis" and a["safety"]["rule"] == "jev"
        assert not await ChatMessage.filter(content__contains="귀찮").exists()


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
            await DrugProduct.filter(edi_code="641900040").update(class_code="214")  # 약효분류도 고정 정보로 감 (11/3)
            second = (await self.start(client, headers, rx)).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=first)
            body = {"analysisId": second, "clientRequestId": "ctx"}
            assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        info = self.fake.calls[0]["info"]
        assert [d.code for d in info.drugs] == ["641900040"]  # 가장 최근에 붙은 맥락 카드의 분석
        assert info.drugs[0].name.startswith("노바스크정") and info.drugs[0].purpose == "혈압 관리에 쓰는 약이에요"
        assert info.drugs[0].class_code == "214"
        assert info.disease_ids == ["HTN"] and info.age is not None

    async def test_card_drug_is_the_focus_drug(self):
        """ "이 약 물어보기"로 붙인 맥락 카드의 약을 고정 정보에 남김 ("이 약"을 그 약으로 풀게, 11/2 서버 E2E).
        카드 뒤에 다른 약을 물었거나, 경고 카드거나, 그 분석의 약이 아니면 남기지 않음"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f11@example.com")
            rx = await self.prescription(user, ["641900040", "644300010"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            ids = await PrescriptionItem.filter(prescription=rx).order_by("id").values_list("id", flat=True)
            sid = await self.session(client, headers, analysisId=aid)
            body = {"analysisId": aid, "context": {"type": "drug", "id": ids[1]}, "clientRequestId": "ctx-d"}
            assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            await self.ask(client, headers, sid, "이 약은 언제 먹어요?", crid="q-1")
            first = self.fake.calls[-1]["info"]
            await self.ask(client, headers, sid, "노바스크는요?", crid="q-2")
            await self.ask(client, headers, sid, "이 약 부작용은요?", crid="q-3")
            after_other = self.fake.calls[-1]["info"]
            body = {"analysisId": aid, "context": {"type": "warning", "id": 1}, "clientRequestId": "ctx-w"}
            await client.post(f"{API}/{sid}/context", json=body, headers=headers)
            await self.ask(client, headers, sid, "이 약은요?", crid="q-4")
            warning = self.fake.calls[-1]["info"]
            body = {"analysisId": aid, "context": {"type": "drug", "id": 999999}, "clientRequestId": "ctx-x"}
            await client.post(f"{API}/{sid}/context", json=body, headers=headers)
            await self.ask(client, headers, sid, "이 약은요?", crid="q-5")
            missing = self.fake.calls[-1]["info"]
        assert first.focus_drug is not None and first.focus_drug.startswith("다이아벡스")
        assert after_other.focus_drug is None
        assert warning.focus_drug is None and missing.focus_drug is None
        assert warning.focus_warning == 1 and first.focus_warning is None and missing.focus_warning is None

    async def test_daily_question_limit(self):
        """하루 질문 상한은 1층을 지난 질문만 셈. 긴급 질문과 같은 질문 다시 보내기는 막지 않음. 0이면 끔 (#116)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f12@example.com")
            sid = await self.session(client, headers)
            with patch.object(config, "CHAT_DAILY_QUESTION_LIMIT", 2):
                assert (await self.ask(client, headers, sid, "약은 언제 먹어요?", crid="q-1")).status_code == 202
                assert (await self.ask(client, headers, sid, "가슴이 조이고 숨이 차요", crid="q-e")).status_code == 202
                assert (await self.ask(client, headers, sid, "운동해도 돼요?", crid="q-2")).status_code == 202
                res = await self.ask(client, headers, sid, "술 마셔도 돼요?", crid="q-3")
                assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                err = res.json()["error"]
                assert err["code"] == "DAILY_LIMIT_EXCEEDED" and err["detail"] == {"limit": 2, "used": 2}
                # 상한에 닿아도 긴급과 다시 보내기는 그대로
                assert (await self.ask(client, headers, sid, "가슴이 조이고 숨이 차요", crid="q-e2")).status_code == 202
                assert (await self.ask(client, headers, sid, "운동해도 돼요?", crid="q-2")).status_code == 202
            with patch.object(config, "CHAT_DAILY_QUESTION_LIMIT", 0):
                assert (await self.ask(client, headers, sid, "술 마셔도 돼요?", crid="q-3")).status_code == 202

    async def test_home_chat_uses_latest_done_analysis(self):
        """홈에서 연 대화(analysisId도 맥락 카드도 없음)는 가장 최근 완료 분석을 쓰고 대화에 적음 (#159).
        적어 두면 그 분석을 지울 때 이 대화도 같이 지워짐 (R-8, #100)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f8@example.com")
            await self.start(client, headers, await self.prescription(user, ["644300010"]))
            rx = await self.prescription(user, ["641900040"], ("I10",))
            second = (await self.start(client, headers, rx)).json()["analysisId"]
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        info = self.fake.calls[0]["info"]
        assert info.analysis_id == second and [d.code for d in info.drugs] == ["641900040"]
        assert info.disease_ids == ["HTN"]
        assert (await ChatSession.get(id=sid)).analysis_id == second

    async def test_home_chat_skips_unfinished_and_others_analysis(self):
        """끝나지 않은 분석과 다른 사람 분석은 쓰지 않음. 쓸 분석이 없으면 일반 질문 모드 (명세서 H-1)"""
        async with self.client() as client:
            other, other_user = await self.auth(client, "f9@example.com")
            await self.start(client, other, await self.prescription(other_user, ["641900040"]))
            headers, user = await self.auth(client, "f10@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()["analysisId"]
            await Analysis.filter(id=aid).update(status=AnalysisStatus.FAILED)
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        info = self.fake.calls[0]["info"]
        assert info.analysis_id is None and info.drugs == [] and info.age is not None
        assert (await ChatSession.get(id=sid)).analysis_id is None

    async def test_home_chat_without_consent_records_nothing(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f11@example.com")
            await self.start(client, headers, await self.prescription(user, ["641900040"]))
            await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(
                agreed=False, withdrawn_at=datetime.now(config.TIMEZONE)
            )
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        assert self.fake.calls[0]["info"].drugs == []
        assert (await ChatSession.get(id=sid)).analysis_id is None

    async def test_deleting_latest_analysis_deletes_home_chat(self):
        async with self.client() as client:
            headers, user = await self.auth(client, "f12@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            assert (await client.delete(f"/api/v1/analyses/{aid}", headers=headers)).status_code == 204
        assert not await ChatSession.exists(id=sid)

    @staticmethod
    async def finished(aid: int, minutes_ago: int) -> None:
        await Analysis.filter(id=aid).update(finished_at=datetime.now(config.TIMEZONE) - timedelta(minutes=minutes_ago))

    async def test_home_chat_moves_to_analysis_finished_after_it(self):
        """같은 날 A로 묻고 B를 분석한 뒤 같은 대화에서 물으면 B로 답하고 대화에 B를 적음 (#162 채연 리뷰).
        답 줄마다 쓴 분석을 적어 두어 A를 지워도 이 대화가 지워짐"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f13@example.com")
            a = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()["analysisId"]
            await self.finished(a, 60)
            sid = await self.session(client, headers)
            await ChatSession.filter(id=sid).update(created_at=datetime.now(config.TIMEZONE) - timedelta(minutes=30))
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            b = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            await self.ask(client, headers, sid, "혈압약은 저녁에 먹어도 되나요?", crid="q-2")
            items = await self.items(client, headers, sid)
        assert [c["info"].analysis_id for c in self.fake.calls] == [a, b]
        assert (await ChatSession.get(id=sid)).analysis_id == b
        answers = await ChatMessage.filter(session_id=sid, role=MessageRole.ASSISTANT).order_by("id")
        assert [m.analysis_id for m in answers] == [a, b]
        assert all("analysisId" not in i for i in items)  # 앱으로 내려보내지 않음

    async def test_chat_opened_from_old_record_keeps_it(self):
        """결과 화면에서 예전 기록 A로 연 대화는, B가 그 전에 끝났으면 A를 그대로 씀"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f14@example.com")
            a = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()["analysisId"]
            b = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            await self.finished(a, 120)
            await self.finished(b, 60)
            sid = await self.session(client, headers, analysisId=a)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        assert self.fake.calls[0]["info"].analysis_id == a
        assert (await ChatSession.get(id=sid)).analysis_id == a

    async def test_analysis_finished_after_card_wins(self):
        """맥락 카드 A를 붙인 뒤 B가 끝나면 B를 씀. 그 뒤 카드 A를 다시 붙이면 A로 돌아감"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f15@example.com")
            a = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()["analysisId"]
            await self.finished(a, 60)
            sid = await self.session(client, headers)
            body = {"analysisId": a, "clientRequestId": "ctx-1"}
            assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            await ChatMessage.filter(session_id=sid).update(
                created_at=datetime.now(config.TIMEZONE) - timedelta(minutes=30)
            )
            b = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            body = {"analysisId": a, "clientRequestId": "ctx-2"}
            assert (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).status_code == 201
            await self.ask(client, headers, sid, "혈압약은 저녁에 먹어도 되나요?", crid="q-2")
        assert [c["info"].analysis_id for c in self.fake.calls] == [b, a]

    async def test_latest_is_by_finish_time_not_number(self):
        """실패한 분석을 다시 시도하면 번호는 작아도 나중에 끝남. 끝난 때가 늦은 분석을 씀"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f16@example.com")
            a = (await self.start(client, headers, await self.prescription(user, ["644300010"]))).json()["analysisId"]
            b = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            await self.finished(b, 60)
            await self.finished(a, 10)
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
        assert self.fake.calls[0]["info"].analysis_id == a

    async def test_deleting_either_analysis_deletes_the_moved_chat(self):
        """A에서 B로 바뀐 대화는 A를 지워도(답 줄에 적힌 분석), B를 지워도(대화에 적힌 분석) 지워짐 (R-8)"""
        for target in ("a", "b"):
            async with self.client() as client:
                headers, user = await self.auth(client, f"f17{target}@example.com")
                rx_a = await self.prescription(user, ["644300010"])
                a = (await self.start(client, headers, rx_a)).json()["analysisId"]
                await self.finished(a, 60)
                sid = await self.session(client, headers, crid=f"s-{target}")
                await ChatSession.filter(id=sid).update(
                    created_at=datetime.now(config.TIMEZONE) - timedelta(minutes=30)
                )
                await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
                b = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()[
                    "analysisId"
                ]
                await self.ask(client, headers, sid, "혈압약은 저녁에 먹어도 되나요?", crid="q-2")
                assert (await ChatSession.get(id=sid)).analysis_id == b
                aid = a if target == "a" else b
                assert (await client.delete(f"/api/v1/analyses/{aid}", headers=headers)).status_code == 204
            assert not await ChatSession.exists(id=sid), target

    async def test_card_session_title_uses_first_answer(self):
        """질문 없이 약 카드에서 연 대화는 목록 제목이 첫 답 첫 줄. 카드만 있으면 "분석 결과 대화" (11/4 E2E: 모두 "대화"였음)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f31@example.com")
            await DrugGuide.create(
                edi_code="641900040",
                content={"purpose": "혈압 관리에 쓰는 약이에요"},
                review_status=ReviewStatus.APPROVED,
            )
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            item = (await PrescriptionItem.filter(prescription=rx).first()).id
            drug_sid = await self.session(client, headers, analysisId=aid)
            body = {"analysisId": aid, "context": {"type": "drug", "id": item}, "clientRequestId": "ctx-t1"}
            first = (await client.post(f"{API}/{drug_sid}/context", json=body, headers=headers)).json()["firstMessage"]
            card_sid = await self.session(client, headers, analysisId=aid, crid="s-card")
            only_card = {"analysisId": aid, "clientRequestId": "ctx-t2"}
            assert (await client.post(f"{API}/{card_sid}/context", json=only_card, headers=headers)).status_code == 201
            today = datetime.now(config.TIMEZONE).date()
            items = (await client.get(f"{API}?date={today}", headers=headers)).json()["items"]
        titles = {i["sessionId"]: i["title"] for i in items}
        assert titles[drug_sid] == first["content"].split("\n")[0][:30]
        assert titles[card_sid] == "분석 결과 대화"

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

    async def test_first_message_for_drug_card(self):
        """H-7: 약 카드는 쓰임과 먹는 법으로 첫 답. AI 없이 만들고, 같은 요청을 다시 보내면 줄을 새로 만들지 않음 (#116)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f30@example.com")
            await DrugGuide.create(
                edi_code="641900040",
                content={"purpose": "혈압 관리에 쓰는 약이에요"},
                review_status=ReviewStatus.APPROVED,
            )
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            item = (await PrescriptionItem.filter(prescription=rx).first()).id
            sid = await self.session(client, headers, analysisId=aid)
            body = {"analysisId": aid, "context": {"type": "drug", "id": item}, "clientRequestId": "ctx-1"}
            res = await client.post(f"{API}/{sid}/context", json=body, headers=headers)
            assert res.status_code == 201
            first = res.json()["firstMessage"]
            assert "혈압 관리에 쓰는 약이에요" in first["content"] and first["answerType"] == "normal"
            assert first["sources"] == [{"title": "심평원 약제급여목록 약효분류", "basedOn": "2026-09-01"}]
            again = await client.post(f"{API}/{sid}/context", json=body, headers=headers)
            assert again.json()["firstMessage"]["id"] == first["id"]
            items = await self.items(client, headers, sid)
        assert [i["id"] for i in items if i.get("answerType")] == [first["id"]]
        assert self.fake.calls == []  # 답 AI를 부르지 않음

    async def test_first_message_source_follows_the_guide_source(self):
        """시연 약은 "무엇에 쓰나요"가 허가정보에서 나옴: 안내문의 source를 출처로 (복약 안내 카드와 같게). 없을 때만 약효분류와 기준일 (#193 채연 리뷰)"""
        permit = "식약처 의약품 허가정보 (품목기준코드 199603456, 허가일 2018-05-02)"
        async with self.client() as client:
            headers, user = await self.auth(client, "f37@example.com")
            await DrugGuide.create(
                edi_code="641900040",
                content={"purpose": "혈압 관리에 쓰는 약이에요", "source": permit},
                review_status=ReviewStatus.APPROVED,
            )
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            item = (await PrescriptionItem.filter(prescription=rx).first()).id
            sid = await self.session(client, headers, analysisId=aid)
            body = {"analysisId": aid, "context": {"type": "drug", "id": item}, "clientRequestId": "ctx-s1"}
            first = (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).json()["firstMessage"]
        assert first["sources"] == [{"title": permit}]

    async def test_first_message_for_warning_card_uses_template(self):
        """H-7: 경고 카드는 점검 문장(템플릿) 그대로 + 상담 안내. 경고 문구를 AI가 만들지 않음 (NFR-032, 설계 메모 4-4)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f31@example.com")
            rx = await self.prescription(user, ["641900040", "644300010"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            a, b = await PrescriptionItem.filter(prescription=rx).order_by("id")
            w = await AnalysisWarning.create(
                analysis_id=aid, warning_type="contra", severity="high", item_a=a, item_b=b,
                summary="함께 먹으면 안 되는 약이에요", source="병용금기 고시", notice_date=date(2025, 3, 31),
            )  # fmt: skip
            sid = await self.session(client, headers, analysisId=aid)
            body = {"analysisId": aid, "context": {"type": "warning", "id": w.id}, "clientRequestId": "ctx-1"}
            first = (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).json()["firstMessage"]
        assert "함께 먹으면 안 되는 약이에요" in first["content"]
        assert first["content"].endswith("처방한 의사나 약사에게 꼭 알려 주세요.")
        assert first["sources"] == [{"title": "병용금기 고시", "basedOn": "2025-03-31"}]  # 고시일

    async def test_first_message_for_warning_card_adds_reason_as_written(self):
        """H-7: DUR 사유가 있으면 경고 자세히 화면처럼 "원문:"으로 그대로 붙임. "-"처럼 내용이 없으면 뺌 (설계 메모 4-4)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f32@example.com")
            rx = await self.prescription(user, ["641900040", "644300010"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            a, b = await PrescriptionItem.filter(prescription=rx).order_by("id")
            common = {"analysis_id": aid, "warning_type": "contra", "severity": "high", "item_a": a, "item_b": b}
            w1 = await AnalysisWarning.create(
                **common, summary="문장", source="고시", reason="근육병증의 위험 증가 가능"
            )
            w2 = await AnalysisWarning.create(**common, summary="문장", source="고시", reason=" - ")
            sid = await self.session(client, headers, analysisId=aid)
            texts = []
            for i, w in enumerate((w1, w2)):
                body = {"analysisId": aid, "context": {"type": "warning", "id": w.id}, "clientRequestId": f"ctx-r{i}"}
                res = await client.post(f"{API}/{sid}/context", json=body, headers=headers)
                texts.append(res.json()["firstMessage"]["content"])
        assert "원문: 근육병증의 위험 증가 가능" in texts[0]
        assert "원문" not in texts[1]

    async def test_no_first_message_without_target(self):
        """분석 요약 카드, 그 분석에 없는 번호에는 첫 답이 없음. 남의 경고가 새지 않음"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f32@example.com")
            aid = (await self.start(client, headers, await self.prescription(user, ["641900040"]))).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=aid)
            plain = {"analysisId": aid, "clientRequestId": "ctx-1"}
            assert "firstMessage" not in (await client.post(f"{API}/{sid}/context", json=plain, headers=headers)).json()
            for kind in ("drug", "warning"):
                body = {"analysisId": aid, "context": {"type": kind, "id": 999999}, "clientRequestId": f"ctx-{kind}"}
                assert (
                    "firstMessage" not in (await client.post(f"{API}/{sid}/context", json=body, headers=headers)).json()
                )

    async def test_pair_warnings_of_the_analysis_are_passed(self):
        """⑤에 쓰는 약 두 개짜리 경고. 이름은 분석 화면과 같은 처방 이름 그대로 (10/26 수인 결정)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f6@example.com")
            rx = await self.prescription(user, ["645600020", "648800030"])  # 시험용 병용금기
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            sid = await self.session(client, headers, analysisId=aid)
            await self.ask(client, headers, sid, "같이 먹으면 안 되는 약 있어?")
        info = self.fake.calls[0]["info"]
        assert info.analysis_id == aid and len(info.pair_warnings) == 1
        w = info.pair_warnings[0]
        assert set(w.names) == {base_name(PRODUCTS[2][1]), "아스피린프로텍트정100밀리그람"}  # 수출명은 뗌
        assert w.summary == "함께 드시면 안 되는 약이에요"

    async def test_single_drug_warnings_are_passed_separately(self):
        """노인주의처럼 약 하나짜리 경고는 other_warnings로. ⑤의 약 두 개짜리(pair_warnings)와 섞지 않음 (11/2 멘토 피드백)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f33@example.com")
            rx = await self.prescription(user, ["641900040"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            (a,) = await PrescriptionItem.filter(prescription=rx)
            await AnalysisWarning.create(
                analysis_id=aid, warning_type="elderly", severity="caution", item_a=a,
                summary="어르신이 조심해야 하는 약이에요", source="심평원 DUR 노인주의",
            )  # fmt: skip
            sid = await self.session(client, headers, analysisId=aid)
            await self.ask(client, headers, sid, "이번 분석에서 가장 조심할 건 뭔가요?")
        info = self.fake.calls[0]["info"]  # 답은 가짜라 고정 정보만 봄. 답 글은 test_answer에서
        assert info.pair_warnings == [] and len(info.other_warnings) == 1
        assert info.other_warnings[0].names == (base_name(PRODUCTS[0][1]),)
        assert info.other_warnings[0].summary == "어르신이 조심해야 하는 약이에요"

    async def test_polypharmacy_warning_has_no_drug_name(self):
        """여러 약 복용 경고는 약 하나가 아니라 여러 약에 대한 것이라 이름 없이 (#195 채연 리뷰 3)"""
        async with self.client() as client:
            headers, user = await self.auth(client, "f38@example.com")
            rx = await self.prescription(user, ["641900040", "644300010"])
            aid = (await self.start(client, headers, rx)).json()["analysisId"]
            (a, _b) = await PrescriptionItem.filter(prescription=rx).order_by("id")
            await AnalysisWarning.create(
                analysis_id=aid, warning_type="polypharmacy", severity="info", item_a=a,
                summary="약을 5가지 함께 드시고 있어요", source="점검 기준",
            )  # fmt: skip
            sid = await self.session(client, headers, analysisId=aid)
            await self.ask(client, headers, sid, "이번 분석에서 가장 조심할 건 뭔가요?")
        info = self.fake.calls[0]["info"]
        assert [w.names for w in info.other_warnings] == [()]

    async def test_safety_card_is_saved_and_returned(self):
        """점검 결과로 답하면 answerType은 normal, safetyCard는 H-2에 그대로 (명세서 v1.5 초안 H-2)"""
        card = {"analysisId": 7, "warningIds": [31, 32]}
        self.fake.reply = Reply("normal", "분석에서 확인된, 같이 먹을 때 주의할 점이에요.", Route(kind="medication"))
        self.fake.reply.safety_card = card
        async with self.client() as client:
            headers, _ = await self.auth(client, "f7@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "같이 먹으면 안 되는 약 있어?")
            items = await self.items(client, headers, sid)
        assert items[-1]["answerType"] == "normal" and items[-1]["safetyCard"] == card
        assert "safetyCard" not in items[0]  # 카드가 없는 줄은 칸을 생략

    async def test_clarify_chips_are_saved_and_returned(self):
        """되물음의 예상 답 칩은 H-2 답 줄의 chips로. 칩이 없는 줄은 칸을 생략 (명세서 H-2 제안, 11/2)"""
        self.fake.reply = Reply(
            "clarify", "어느 약을 말씀하시나요?", Route(kind="clarify"), chips=["아침 약이요", "저녁 약이요"]
        )
        async with self.client() as client:
            headers, _ = await self.auth(client, "f34@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "그거 언제 먹어요?")
            items = await self.items(client, headers, sid)
        assert items[-1]["answerType"] == "clarify" and items[-1]["chips"] == ["아침 약이요", "저녁 약이요"]
        assert "chips" not in items[0]

    async def test_distress_answer_has_no_feedback_flag(self):
        """범위 밖 괴로움의 도움 연결 답은 noFeedback으로 표시해 앱이 피드백 버튼을 숨김 (#144 채연 리뷰, #117, 제안)"""
        self.fake.reply = Reply("normal", DISTRESS, Route(kind="out_of_scope"))
        async with self.client() as client:
            headers, _ = await self.auth(client, "f35@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "약 먹는 게 너무 힘들어요")
            items = await self.items(client, headers, sid)
        assert items[-1]["noFeedback"] is True and "noFeedback" not in items[0]

    async def test_drug_match_is_saved_and_returned(self):
        """질문의 약 이름 맞추기 결과는 H-2 답 줄 drugMatch로 (명세서 O-4 챗봇 줄, 제안)"""
        dm = {"status": "candidates", "items": [{"ediCode": "672300240", "itemName": "타이레놀정500밀리그램"}]}
        self.fake.reply = Reply(
            "clarify",
            "말씀하신 약이 아래 중 하나인가요?",
            Route(kind="clarify"),
            chips=["타이레놀정500밀리그램"],
            drug_match=dm,
        )
        async with self.client() as client:
            headers, _ = await self.auth(client, "f36@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "타이레놀 먹어도 돼요?")
            items = await self.items(client, headers, sid)
        assert items[-1]["drugMatch"] == dm and "drugMatch" not in items[0]


class TestPhoto(ChatCase):
    """H-9 사진 첨부 (CB-04)"""

    JPEG = b"\xff\xd8\xff" + b"0" * 64

    @staticmethod
    def ocr_text(*lines: str) -> dict[str, Any]:
        """CLOVA 결과 모양: 줄마다 낱말 하나 (세로로 쌓음)"""
        fields = [
            {
                "inferText": t,
                "inferConfidence": 0.99,
                "boundingPoly": {
                    "vertices": [
                        {"x": 10, "y": 40 * i},
                        {"x": 400, "y": 40 * i},
                        {"x": 400, "y": 40 * i + 30},
                        {"x": 10, "y": 40 * i + 30},
                    ]
                },
            }
            for i, t in enumerate(lines)
        ]
        return {"images": [{"inferResult": "SUCCESS", "fields": fields}]}

    async def photo(self, client, headers, sid: int, crid: str = "p-1", content: bytes | None = None):
        return await client.post(
            f"{API}/{sid}/attachments",
            files={"file": ("a.jpg", content or self.JPEG, "image/jpeg")},
            data={"clientRequestId": crid},
            headers=headers,
        )

    def photo_patches(self, ocr: dict[str, Any] | Exception | None = None):
        """사진 OCR 자리: 급여목록 대신 시험용 약 목록으로 이름을 맞춤. ocr가 None이면 가짜 처방전(키 없음)"""
        matcher = NameMatcher([(e, n) for e, n, *_ in PRODUCTS])
        matcher.prepare()

        async def recognize(content, fmt, name):
            if isinstance(ocr, Exception):
                raise ocr
            return ocr if ocr is not None else json.loads(clova.SAMPLE.read_text(encoding="utf-8"))

        async def get_codes():
            return {}

        return (
            patch.object(chat_photo, "get_matcher", AsyncMock(return_value=matcher)),
            patch.object(chat_photo, "get_codes", get_codes),
            patch.object(clova, "recognize", recognize),
        )

    async def test_photo_of_prescription_points_to_analysis(self):
        """처방전 사진이면 챗봇에서 분석하지 않고 분석하기로 안내. 사용자 줄에는 읽은 글자가 아닌 고정 글 (원문 저장 금지)"""
        p1, p2, p3 = self.photo_patches()
        async with self.client() as client:
            headers, _ = await self.auth(client, "h1@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                res = await self.photo(client, headers, sid)
            items = await self.items(client, headers, sid)
        assert res.status_code == status.HTTP_201_CREATED and res.json()["messageId"] == items[-1]["id"]
        assert items[0]["content"] == chat_photo.PHOTO_TEXT and items[0]["role"] == "user"
        assert items[-1]["answerType"] == "normal" and items[-1]["imageResult"] == "prescription"
        assert items[-1]["action"] == "open_analysis" and "분석하기" in items[-1]["content"]
        assert self.fake.calls == []  # 답 AI를 부르지 않음

    async def test_photo_of_drug_box_asks_to_confirm_the_name(self):
        """약 상자는 읽은 이름을 후보로 되물음 (늘 확인, 후보 하나여도 clarify)"""
        p1, p2, p3 = self.photo_patches(self.ocr_text("전문의약품", "노바스크정5밀리그람", "30정"))
        async with self.client() as client:
            headers, _ = await self.auth(client, "h2@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                await self.photo(client, headers, sid)
            items = await self.items(client, headers, sid)
        a = items[-1]
        assert a["answerType"] == "clarify" and a["imageResult"] == "drug" and "action" not in a
        assert a["chips"][0].startswith("노바스크정5밀리그람") and a["drugMatch"]["status"] in ("matched", "candidates")
        assert a["drugMatch"]["items"][0]["ediCode"] == "641900040"

    async def test_photo_without_readable_name_asks_for_text(self):
        p1, p2, p3 = self.photo_patches(self.ocr_text("TYLENOL", "500mg", "24 CAPLETS"))
        async with self.client() as client:
            headers, _ = await self.auth(client, "h3@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                await self.photo(client, headers, sid)
            items = await self.items(client, headers, sid)
        assert items[-1]["answerType"] == "no_evidence" and items[-1]["imageResult"] == "unreadable"
        assert "글자로 적어" in items[-1]["content"] and "chips" not in items[-1]

    async def test_photo_pdf_is_read_like_a_photo(self):
        """PDF도 사진과 같게 처리 (첫 쪽, 설계 메모 4-9)"""
        p1, p2, p3 = self.photo_patches(self.ocr_text("노바스크정5밀리그람"))
        async with self.client() as client:
            headers, _ = await self.auth(client, "h7@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                res = await self.photo(client, headers, sid, "p-pdf", content=b"%PDF-1.4\n" + b"0" * 40)
            items = await self.items(client, headers, sid)
        assert res.status_code == 201 and items[-1]["imageResult"] == "drug"

    async def test_photo_same_request_id_makes_one_pair_and_stays_out_of_history(self):
        p1, p2, p3 = self.photo_patches()
        async with self.client() as client:
            headers, _ = await self.auth(client, "h4@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                first = (await self.photo(client, headers, sid, "p-9")).json()["messageId"]
                again = (await self.photo(client, headers, sid, "p-9")).json()["messageId"]
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            items = await self.items(client, headers, sid)
        assert first == again and [i["role"] for i in items[:2]] == ["user", "assistant"] and len(items) == 4
        assert self.fake.calls[0]["history"] == []  # 사진 안내는 다음 답의 기억에 넣지 않음

    async def test_photo_counts_toward_the_daily_ocr_limit(self):
        """챗봇 사진도 O-1과 같은 하루 사진 상한에 합산해 챗봇으로 CLOVA를 무제한 부르지 못하게 함. 막히면 OCR을 부르지 않음 (점검, 11/2)"""
        p1, p2, p3 = self.photo_patches()
        with patch.object(config, "OCR_DAILY_FILE_LIMIT", 2):
            async with self.client() as client:
                headers, _ = await self.auth(client, "h6@example.com")
                sid = await self.session(client, headers)
                with p1, p2, p3:
                    codes = [(await self.photo(client, headers, sid, f"p-l{i}")).status_code for i in range(3)]
                    over = await self.photo(client, headers, sid, "p-l3")
        assert codes == [201, 201, 429] and over.json()["error"]["code"] == "DAILY_LIMIT_EXCEEDED"

    async def test_deleting_chats_does_not_reset_the_daily_photo_limit(self):
        """대화를 지워도 하루 사진 상한이 0으로 돌아가지 않음. 지우고 다시 보내 CLOVA를 계속 부르지 못하게 (#199 채연 리뷰)"""
        p1, p2, p3 = self.photo_patches()
        with patch.object(config, "OCR_DAILY_FILE_LIMIT", 2):
            async with self.client() as client:
                headers, _ = await self.auth(client, "h8@example.com")
                sid = await self.session(client, headers)
                with p1, p2, p3:
                    codes = [(await self.photo(client, headers, sid, f"p-d{i}")).status_code for i in range(2)]
                    deleted = await client.delete(f"{API}/{sid}", headers=headers)
                    sid2 = await self.session(client, headers)
                    again = await self.photo(client, headers, sid2, "p-d2")
        assert codes == [201, 201] and deleted.status_code == status.HTTP_204_NO_CONTENT
        assert again.status_code == 429 and again.json()["error"]["detail"] == {"limit": 2, "used": 2}

    async def test_photo_answers_have_no_feedback_buttons(self):
        """사진 첨부 안내는 규칙으로 만든 답이라 피드백 버튼을 두지 않음 (#199 채연 리뷰)"""
        p1, p2, p3 = self.photo_patches()
        async with self.client() as client:
            headers, _ = await self.auth(client, "h9@example.com")
            sid = await self.session(client, headers)
            with p1, p2, p3:
                await self.photo(client, headers, sid, "p-f")
            items = await self.items(client, headers, sid)
        assert items[-1]["noFeedback"] is True and "noFeedback" not in items[0]

    async def test_photo_rejects_bad_file_without_consent_and_ocr_failure(self):
        p1, p2, p3 = self.photo_patches()
        async with self.client() as client:
            headers, user = await self.auth(client, "h5@example.com")
            sid = await self.session(client, headers)
            bad = await self.photo(client, headers, sid, "p-2", content=b"GIF89a" + b"0" * 20)
            assert bad.status_code == 400 and bad.json()["error"]["code"] == "FILE_TYPE_NOT_SUPPORTED"
            big = await self.photo(client, headers, sid, "p-3", content=self.JPEG + b"0" * (10 * 1024 * 1024))
            assert big.status_code == 400 and big.json()["error"]["code"] == "FILE_TOO_LARGE"
            with p1, p2, p3:
                await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(
                    agreed=False, withdrawn_at=datetime.now(config.TIMEZONE)
                )
                no = await self.photo(client, headers, sid, "p-4")
            assert no.status_code == 403 and no.json()["error"]["code"] == "CONSENT_REQUIRED"
            await UserConsent.filter(user=user, consent_type=ConsentType.SENSITIVE_HEALTH).update(
                agreed=True, withdrawn_at=None
            )
            f1, f2, f3 = self.photo_patches(clova.ClovaError("timeout"))
            with f1, f2, f3:
                down = await self.photo(client, headers, sid, "p-5")
            items = await self.items(client, headers, sid)
        assert down.status_code == 502 and down.json()["error"]["code"] == "OCR_FAILED"
        assert items == []  # 실패한 사진은 줄을 만들지 않음 (다시 시도)

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

    async def test_history_skips_out_of_scope_turn(self):
        """범위 밖으로 걸러진 질문과 그 답은 다음 질문의 대화 기억에 넣지 않음. 앞 대화가 노이즈가 됨
        (5회차 멘토링 시연 "마이클 잭슨 누구야" 다음 "내가 먹는 약이 뭐야?", #99)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f8@example.com")
            sid = await self.session(client, headers)
            self.fake.reply = Reply("normal", OUT_OF_SCOPE, Route(kind="out_of_scope"))
            await self.ask(client, headers, sid, "마이클 잭슨이 누구야?")
            self.fake.reply = normal_reply()
            await self.ask(client, headers, sid, "내가 먹는 약이 뭐야?", crid="q-2")
            await self.ask(client, headers, sid, "그럼 아침에 먹어?", crid="q-3")
        assert self.fake.calls[1]["history"] == []
        assert self.fake.calls[2]["history"] == [
            {"role": "user", "content": "내가 먹는 약이 뭐야?"},
            {"role": "assistant", "content": "식사 직후에 드시는 게 좋아요."},
        ]

    async def test_answer_row_keeps_route_kind(self):
        """답 줄에 답을 만든 갈래를 남김. 질문 줄은 비움 (1층이 잡은 긴급 답 포함)"""
        async with self.client() as client:
            headers, _ = await self.auth(client, "f9@example.com")
            sid = await self.session(client, headers)
            await self.ask(client, headers, sid, "혈압약은 아침에 먹나요?")
            await self.ask(client, headers, sid, EMERGENCY_TEXT, crid="q-2")
        rows = await ChatMessage.filter(session_id=sid).order_by("id")
        assert [(m.role.value, m.route_kind) for m in rows] == [
            ("user", None),
            ("assistant", "medication"),
            ("user", None),
            ("assistant", "emergency"),
        ]
