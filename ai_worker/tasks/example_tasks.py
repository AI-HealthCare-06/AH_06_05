"""
arq 작업 함수 예제.

실제 OCR·안내문 생성 같은 오래 걸리는 작업은 각 피처 담당자가
이 파일 옆에 새 모듈로 추가하고, main.py의 WorkerSettings.functions에
등록하면 됩니다. 여기 있는 example_echo_task는 틀(패턴)만 보여주는
샘플이라, 실제 로직이 추가되면 지워도 됩니다.
"""

import asyncio
import time
from typing import Any


async def example_echo_task(ctx: dict[str, Any], payload: str) -> dict[str, Any]:
    """샘플 작업: 외부 API 호출을 흉내 내는 대기 + 간단한 텍스트 처리.

    10/2 비동기 워커(arq) 선정을 위한 메모리 측정에 사용한 것과 같은 함수입니다.
    """
    start = time.monotonic()
    await asyncio.sleep(0.3)
    return {"payload": payload, "elapsed": time.monotonic() - start}
