"""질문 분류 (#99, 설계 메모 7-12 ③). 갈래(약, 생활습관, 의료진 상담 안내, 되묻기, 범위 밖)와 대상 약.

분류기가 고른 값을 코드로 한 번 더 확인한다 (로컬 실험과 같음):
- "앞 대화에서 찾았다"는 약이 실제 기억(앞 대화, 요약, 지시어 풀이)에 없으면 추측으로 봄
- 지시어 풀이가 찾은 약이 있으면 그 약을 따름
분류 안의 risk는 쓰지 않는다. 위험 판단은 2층 전용 호출만 따름.
"""

import re
from typing import Any

from app.services.chatbot.context import FixedInfo, dialogue, fixed_info_text, target_in_memory
from app.services.chatbot.llm import ChatClient, LLMError, Usage
from app.services.chatbot.prompts import CLASSIFY_SCHEMA, CLASSIFY_SYSTEM

CATEGORIES = ("medication", "lifestyle", "refer", "clarify", "out_of_scope")
_REFERS_BACK = re.compile(r"(그\s*약|그거|그것|아까|방금|처음|번째|물어본|물어봤던|얘기한|말한)")
_PREGNANCY = re.compile(r"(임신|임산부|수유|모유)")


def classify_message(
    question: str,
    info: FixedInfo,
    past: list[dict[str, str]],
    first_turn: int,
    summary: str | None,
    resolved: str | None,
) -> str:
    context = f"[고정 정보]\n{fixed_info_text(info)}"
    if summary:
        context += f"\n\n[앞부분 요약] (앞 대화보다 오래된 대화)\n{summary}"
    hint = (
        f"\n\n[지시어 풀이] 질문의 순서 표현이 가리키는 약 (저장된 전체 대화에서 찾음): {resolved}" if resolved else ""
    )
    return (
        f"{context}\n\n[앞 대화] (오래된 것부터)\n{dialogue(past, first_turn) or '(없음)'}{hint}\n\n[질문]\n{question}"
    )


async def classify(message: str, client: ChatClient, usage: Usage) -> dict[str, Any]:
    result = await client.complete_json(
        CLASSIFY_SYSTEM, [{"role": "user", "content": message}], CLASSIFY_SCHEMA, "classify", usage
    )
    if result.get("category") not in CATEGORIES:
        raise LLMError("bad_category")
    return result


def check_classification(
    cls: dict[str, Any],
    question: str,
    info: FixedInfo,
    past: list[dict[str, str]],
    summary: str | None,
    resolved: str | None,
) -> dict[str, Any]:
    """분류 결과를 코드로 확인해 고친 사본을 돌려줌"""
    cls = dict(cls)
    if cls["target_source"] in ("history", "guess") and not _REFERS_BACK.search(question):
        cls["target_source"] = "question"  # 가리키는 말이 없으면 추측이라고 볼 일이 없음
    if cls["about_user_drugs"] and cls["category"] == "clarify":
        cls["category"] = "medication"  # "이 두 약", "내 약끼리"는 지금 먹는 약 전체를 가리킴
    if cls["target_source"] == "history" and cls["target_drug"]:
        found = target_in_memory(cls["target_drug"], past, summary, info.drugs) or bool(
            resolved and resolved[:3] in cls["target_drug"]
        )
        if not found:
            cls["target_source"] = "guess"
    if resolved and resolved[:3] not in (cls["target_drug"] or ""):
        cls["target_drug"], cls["target_source"] = resolved, "history"  # 코드로 찾은 순서를 따름
    # 임신, 수유 중 복용은 분류가 흔들려도 의사 판단으로 보냄 (R2를 범위 밖으로 본 문제)
    if _PREGNANCY.search(question) and cls["category"] != "refer":
        cls["category"], cls["refer_kind"] = "refer", "next_visit"
    return cls
