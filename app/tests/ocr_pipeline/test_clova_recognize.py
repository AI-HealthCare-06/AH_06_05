"""clova.recognize — 여러 쪽 PDF에서 칸마다 성공 · 실패가 달라도 읽힌 쪽은 살린다 (CLOVA는 가짜 응답으로 대신함)"""

import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services.ocr import clova

OK = {"inferResult": "SUCCESS", "fields": [{"inferText": "가", "inferConfidence": 0.99}]}
FAIL = {"inferResult": "ERROR", "message": "fail"}


def _recognize_with(images: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "V2", "images": images})

    real = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        return real(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    return fake_client


async def _recognize(images: list[dict]):
    with (
        patch.object(clova, "uses_sample", lambda: False),
        patch.object(clova.config, "CLOVA_OCR_INVOKE_URL", "http://clova.test"),
        patch.object(clova.config, "CLOVA_OCR_SECRET_KEY", "x"),
        patch.object(clova.httpx, "AsyncClient", _recognize_with(images)),
    ):
        return await clova.recognize(b"%PDF-1.4 x", "pdf", "a.pdf")


def _run(images: list[dict]):
    # 시험 전체가 쓰는 이벤트 루프를 건드리지 않게 새 루프를 따로 만들어 쓰고 닫는다 (async 함수 시험으로 쓰면
    # 뒤의 로그인 · 내 정보 시험이 "현재 이벤트 루프 없음"으로 깨진다)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_recognize(images))
    finally:
        loop.close()


def test_all_pages_ok():
    data = _run([OK, OK, OK])
    assert [i["inferResult"] for i in data["images"]] == ["SUCCESS"] * 3


def test_first_page_failed_but_later_pages_are_kept():
    data = _run([FAIL, OK])
    assert data["images"][0]["fields"] == []  # 실패한 쪽은 글자 칸이 비어 read()가 다시 찍기로 처리
    assert data["images"][1]["fields"] and data["images"][1]["inferResult"] == "SUCCESS"


def test_later_page_failed_keeps_first_page():
    data = _run([OK, FAIL])
    assert data["images"][0]["fields"] and data["images"][1]["fields"] == []


def test_ten_pages_with_some_failures():
    images = [OK if i % 3 else FAIL for i in range(10)]
    data = _run(images)
    assert len(data["images"]) == 10
    assert sum(1 for i in data["images"] if i["fields"]) == 6


def test_every_page_failed_raises():
    with pytest.raises(clova.ClovaError):
        _run([FAIL, FAIL])
