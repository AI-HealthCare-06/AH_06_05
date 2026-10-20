"""근거 모으기 (#99 PR 2-1). 채연의 근거 검색 rag.search 하나만 부른다 (생활습관 근거도 팩트표 조각으로 같이 옴, 10/20).

- 약 코드: 분류가 고른 대상 약이 먹는 약이면 그 약만, 아니면 먹는 약 전부
- 질환: FixedInfo.disease_ids (처방전 질환과 내 정보 질환을 합친 팩트표 질환 id, #101). 약도 질환도 없으면
  rag.search가 OpenAI를 부르지 않고 no_code로 끝낸다
- 시간: 챗봇 작업 제한 25초 안에 답 만들기 한 번(15초)이 들어가게, 남은 시간으로 검색 예산을 정함 (10/20 수인 결정)
"""

from collections.abc import Awaitable, Callable
from typing import Any

from app.services.chatbot.context import FixedInfo
from app.services.chatbot.llm import TIMEOUT_SEC
from app.services.rag.pipeline import SearchResult

JOB_LIMIT_SEC = 25.0  # 설계 메모 0-1 항목 7
Search = Callable[..., Awaitable[SearchResult]]


def drug_codes(info: FixedInfo, target: str | None) -> list[str]:
    picked = [d for d in info.drugs if target and (d.name[:3] in target or target[:3] in d.name)]
    return [d.code for d in (picked or info.drugs) if d.code]


def budget(elapsed: float) -> float:
    """남은 시간에서 답 만들기 몫을 뺀 근거 검색 예산. 0 이하면 검색하지 않음"""
    return JOB_LIMIT_SEC - elapsed - TIMEOUT_SEC


async def gather(question: str, cls: dict[str, Any], info: FixedInfo, search: Search, elapsed: float) -> SearchResult:
    left = budget(elapsed)
    if left <= 0:
        return SearchResult(reason="timeout")
    return await search(question, drug_codes(info, cls.get("target_drug")), list(info.disease_ids), budget_sec=left)
