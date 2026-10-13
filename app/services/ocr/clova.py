"""CLOVA OCR 호출 (캠프 제공 키). 사진 1장 → 글자 목록(fields)이 든 결과 JSON

키(CLOVA_OCR_INVOKE_URL, CLOVA_OCR_SECRET_KEY)가 없으면 local · dev에서는 저장해 둔 가짜 처방전 결과를 돌려준다
(사진 내용과 상관없음 — 키 없이 화면 · 서버 흐름을 확인하는 용도). prod에서 키가 없으면 오류.
"""

import base64
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.core import config
from app.core.config import Env

SAMPLE = Path(__file__).resolve().parent / "samples" / "fake_prescription.json"
TIMEOUT = 40.0


class ClovaError(Exception):
    """CLOVA 호출 실패 (네트워크 · 키 · 응답 형식) → 해당 사진은 OCR_FAILED"""


def uses_sample() -> bool:
    return not (config.CLOVA_OCR_INVOKE_URL and config.CLOVA_OCR_SECRET_KEY) and config.ENV != Env.PROD


async def recognize(content: bytes, fmt: str, name: str) -> dict[str, Any]:
    """fmt: jpg | png | pdf"""
    if uses_sample():
        return json.loads(SAMPLE.read_text(encoding="utf-8"))
    if not (config.CLOVA_OCR_INVOKE_URL and config.CLOVA_OCR_SECRET_KEY):
        raise ClovaError("CLOVA 키가 없습니다")
    body = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "lang": "ko",
        "images": [{"format": fmt, "name": name, "data": base64.b64encode(content).decode()}],
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                config.CLOVA_OCR_INVOKE_URL,
                json=body,
                headers={"X-OCR-SECRET": config.CLOVA_OCR_SECRET_KEY},
            )
        resp.raise_for_status()
        data = resp.json()
        if data["images"][0].get("inferResult") != "SUCCESS":
            raise ClovaError(f"inferResult={data['images'][0].get('inferResult')}")
        data["images"][0].setdefault("fields", [])
    except ClovaError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
        # 키 · 주소가 로그에 남지 않도록 예외 종류만 적는다
        raise ClovaError(type(e).__name__) from e
    return data
