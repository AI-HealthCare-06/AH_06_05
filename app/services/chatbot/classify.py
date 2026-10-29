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
# 앱 추천 칩. 분류가 범위 밖으로 보내 막다른 답이 나옴 (10/26 채연 서버 시험, 10/27 실제 분류 3번 중 3번)
_FOOD_AVOID = re.compile(r"((같이|함께)\s*먹으면\s*안\s*되는|피해야\s*할)\s*음식")
# 약 이름 없이 먹어도, 마셔도 되는지 물음 ("자몽주스 마셔도 돼요?", "자몽 먹으면 안 되나요?"). 분류가 이유에는 약과의 상호작용이라 쓰고 갈래는
# 범위 밖으로 고름 (10/29 실제 분류 4번 중 4번, #145 채연 리뷰). 음식 이름 목록 대신 묻는 꼴만 봄 (10/29 수인 결정)
_MAY_EAT = re.compile(r"(먹어도|마셔도|드셔도|먹으면|마시면|드시면)\s*(안\s*)?(돼|되|괜찮)")
# 분석 칩처럼 분석 전체에서 가장 조심할 것을 물을 때만. "이번 분석에 나온 노바스크 복용법"처럼 약 하나를 물으면 분류대로 (#135 채연 리뷰)
_THIS_ANALYSIS = re.compile(r"이번\s*분석.*(가장|제일).*(조심|주의)")


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
    if any(k not in result for k in CLASSIFY_SCHEMA["required"]):
        raise LLMError("missing_field")  # 칸이 빠지면 KeyError 대신 답변 오류(E6)로
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
    if _FOOD_AVOID.search(question) and cls["category"] == "out_of_scope":
        cls["category"] = "medication"  # 음식과 약 (설계 메모 7-12 ③)
    # 먹는 약 전체로 근거를 찾음. 먹는 약이 없으면 찾을 근거가 없어 그대로. 추천을 바라면 범위 밖 그대로 (골든셋 O3)
    if _MAY_EAT.search(question) and cls["category"] == "out_of_scope" and info.drugs and "추천" not in question:
        cls["category"] = "medication"
    if _THIS_ANALYSIS.search(question) and cls["category"] in ("out_of_scope", "medication"):
        # 경고가 있으면 ⑤ 점검 결과, 없으면 pipeline의 분석 안내
        cls["category"], cls["about_user_drugs"] = "medication", True
    # 임신, 수유 중 복용은 분류가 흔들려도 의사 판단으로 보냄 (R2를 범위 밖으로 본 문제)
    if _PREGNANCY.search(question) and cls["category"] != "refer":
        cls["category"], cls["refer_kind"] = "refer", "next_visit"
    return cls


def asks_this_analysis(question: str) -> bool:
    """분석 칩("이번 분석에서 가장 조심할 건 뭔가요?")처럼 이번 분석에서 가장 조심할 것을 묻는지"""
    return bool(_THIS_ANALYSIS.search(question))
