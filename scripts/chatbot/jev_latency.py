"""서버에서 Jev(TypeSafe) 호출 시간과 실패 비율을 재는 스크립트 (11/2, 켜기 전 확인용).

실행 (서버, 저장소 루트):  docker compose exec fastapi uv run --no-sync python scripts/chatbot/jev_latency.py
- 가짜 문장 50개만 보냄 (실제 사용자 질문 없음). 키 값은 출력하지 않음.
- 운영 설정과 같은 1초 제한(SAFETY_JEV_TIMEOUT_SEC)으로 한 번씩 차례로 호출하고 평균, 95%, 최대, 실패 수를 출력함.
- 기준(시작값): 95%가 0.8초 안이고 실패가 5% 아래면 켜도 됨. 넘으면 SAFETY_JEV_TIMEOUT_SEC나 켜기를 다시 정함.
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core import config  # noqa: E402
from app.services.chatbot import jev  # noqa: E402

SENTENCES = [
    "혈압약은 아침에 먹는 게 좋아요?",
    "약을 줄이고 싶은데 어떻게 말씀드려요?",
    "자몽주스 마셔도 돼요?",
    "약통에 남은 약은 어떻게 버려야 하나요",
    "요즘 너무 피곤한데 혈압약 때문일까요",
    "운동하고 나면 숨이 차는데 쉬면 괜찮아져요",
    "어제 약먹는걸 까먹었는데 오늘은 어쩌죠",
    "당뇨약 먹고 배가 살살 아픈데 흔한가요",
    "건강검진 전에 약을 잠깐 끊어도 되나요",
    "아버지 혈압약을 아침으로 옮겨도 되나요",
]


async def main() -> None:
    if not config.TYPESAFE_API_KEY:
        sys.exit("TYPESAFE_API_KEY가 없어요")
    secs: list[float] = []
    failed = 0
    for i in range(50):
        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(jev._typesafe(SENTENCES[i % len(SENTENCES)]), timeout=config.SAFETY_JEV_TIMEOUT_SEC)
        except Exception as e:  # noqa: BLE001  시간 초과, 연결, 인증 오류 모두 실패로 셈
            failed += 1
            print(f"실패 {i + 1}: {type(e).__name__}")
        secs.append(time.perf_counter() - t0)
    ok = sorted(secs)
    print(
        f"호출 {len(secs)}, 실패 {failed}, 평균 {statistics.mean(secs):.2f}초, 95% {ok[int(len(ok) * 0.95)]:.2f}초, 최대 {ok[-1]:.2f}초"
    )


asyncio.run(main())
