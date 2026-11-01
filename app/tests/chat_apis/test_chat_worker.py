"""챗봇 답 만들기를 arq 워커로 보내는 흐름 (#118): 꺼짐 기본값, 맡기기, 못 맡길 때 서버 안 처리, 워커가 하는 일"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.models.chat import ChatMessage, MessageRole, MessageStatus
from app.services.chatbot import queue as chat_queue
from app.services.ocr import queue
from app.tests.chat_apis.test_chat_apis import ChatCase

REPO = Path(__file__).resolve().parents[3]
QUESTION = "메트포르민은 밥 먹고 먹어야 하나요?"


class TestAskHandsToWorker(ChatCase):
    async def answer_row(self, sid: int) -> ChatMessage:
        return await ChatMessage.get(session_id=sid, role=MessageRole.ASSISTANT)

    async def test_off_by_default_answers_in_server(self):
        pool = AsyncMock()
        with patch.object(queue, "_get_pool", pool):
            async with self.client() as client:
                headers, _ = await self.auth(client, "w1@example.com")
                sid = await self.session(client, headers)
                res = await self.ask(client, headers, sid, QUESTION)
        assert res.status_code == status.HTTP_202_ACCEPTED
        pool.assert_not_awaited()
        assert (await self.answer_row(sid)).status == MessageStatus.DONE
        assert len(self.fake.calls) == 1

    async def test_on_leaves_the_answer_to_the_worker(self):
        with (
            patch.object(config, "CHAT_WORKER", True),
            patch.object(chat_queue, "enqueue_answer", AsyncMock(return_value=True)) as q,
        ):
            async with self.client() as client:
                headers, _ = await self.auth(client, "w2@example.com")
                sid = await self.session(client, headers)
                res = await self.ask(client, headers, sid, QUESTION, emergencyDismissed=True)
        answer = await self.answer_row(sid)
        assert res.json() == {"messageId": answer.id}
        q.assert_awaited_once_with(answer.id, True)
        assert answer.status == MessageStatus.GENERATING  # 서버 안에서는 만들지 않음
        assert self.fake.calls == []

    async def test_queue_failure_answers_in_server(self):
        with (
            patch.object(config, "CHAT_WORKER", True),
            patch.object(chat_queue, "enqueue_answer", AsyncMock(return_value=False)),
        ):
            async with self.client() as client:
                headers, _ = await self.auth(client, "w3@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, QUESTION)
        assert (await self.answer_row(sid)).status == MessageStatus.DONE
        assert len(self.fake.calls) == 1

    async def test_first_layer_answer_is_not_queued(self):
        """1층이 잡은 질문은 긴급 답을 바로 저장하므로 워커에 넣지 않음"""
        with (
            patch.object(config, "CHAT_WORKER", True),
            patch.object(chat_queue, "enqueue_answer", AsyncMock(return_value=True)) as q,
        ):
            async with self.client() as client:
                headers, _ = await self.auth(client, "w4@example.com")
                sid = await self.session(client, headers)
                await self.ask(client, headers, sid, "약 먹고 나서 가슴이 조여요")
        q.assert_not_awaited()


class TestChatQueue(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        patcher = patch.object(config, "CHAT_WORKER", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_off_does_not_touch_redis(self):
        with patch.object(config, "CHAT_WORKER", False), patch.object(queue, "_get_pool", AsyncMock()) as get:
            assert await chat_queue.enqueue_answer(7, False) is False
        get.assert_not_awaited()

    async def test_enqueues_with_fixed_job_id(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()), exists=AsyncMock(return_value=1))
        with patch.object(queue, "_get_pool", AsyncMock(return_value=pool)):
            assert await chat_queue.enqueue_answer(7, True) is True
        pool.enqueue_job.assert_awaited_once_with("chat_answer", 7, True, _job_id="chat-7", _expires=30)

    async def test_already_queued_counts_as_handed_over(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=None), exists=AsyncMock(return_value=1))
        with patch.object(queue, "_get_pool", AsyncMock(return_value=pool)):
            assert await chat_queue.enqueue_answer(7, False) is True

    async def test_dead_worker_means_not_enqueued(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(), exists=AsyncMock(return_value=0))
        with (
            patch.object(queue, "_get_pool", AsyncMock(return_value=pool)),
            self.assertLogs(chat_queue.logger, "WARNING"),
        ):
            assert await chat_queue.enqueue_answer(7, False) is False
        pool.exists.assert_awaited_once_with("arq:queue:health-check")
        pool.enqueue_job.assert_not_awaited()

    async def test_redis_down_returns_false_without_raising(self):
        with (
            patch.object(queue, "_get_pool", AsyncMock(side_effect=ConnectionError("no redis"))),
            patch.object(queue, "reset_pool", AsyncMock()) as reset,
            self.assertLogs(chat_queue.logger, "WARNING"),
        ):
            assert await chat_queue.enqueue_answer(7, False) is False
        reset.assert_awaited_once()


class TestWorkerEntry(TestCase):
    """ai_worker/ 쪽 얇은 껍데기 (처리 자체는 chats.generate)"""

    async def test_chat_answer_calls_generate(self):
        spec = importlib.util.spec_from_file_location(
            "chatbot_tasks", REPO / "ai_worker" / "tasks" / "chatbot_tasks.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with patch.object(mod.chats, "generate", AsyncMock()) as gen:
            await mod.chat_answer({"job_try": 1}, 5, True)
        gen.assert_awaited_once_with(5, True)
