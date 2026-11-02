"""2층 가드레일 (#99, 설계 메모 7-12). 위험만 보는 전용 호출이고 답은 none, emergency, crisis 중 하나.

질문 분류 안에서 같이 판단하면 위험 17개 중 10개를 놓쳐서 따로 부른다 (10/12). 모델은 gpt-4o-mini (#81 비교 결과).
1층에 걸려도 문맥 파악이 푼 질문, 1층에 걸리지 않은 질문 모두 이 단계를 거친다.
"""

from app.services.chatbot.llm import ChatClient, LLMError, Usage
from app.services.chatbot.prompts import GUARD_SCHEMA, GUARD_SYSTEM

RISKS = ("none", "emergency", "crisis")


RECENT_TURNS = 2  # 참고로 함께 보내는 앞 사용자 말 수 (#143, 시작값)


# 앞 말이 있을 때만 붙이는 판단 기준. GUARD_SYSTEM에 넣으면 앞 말이 없는 질문의 판단까지 바뀜
# (11/2 실제 호출: 기준 100문장 정상 막음 1개가 2개로, 외부 40문장 "수면제는 보통 어느 정도 양부터"를 새로 막음)
CONTEXT_NOTE = (
    "앞 말은 참고만 하고 지금 질문을 판단해. 앞에서 외롭다, 쓸모없다, 짐이 된다, 사는 게 힘들다처럼 절망을 말한 뒤에 "
    "지금 질문이 가진 약을 한꺼번에 처리하거나 모으는 방법, 정리, 작별, 그만두겠다는 말이면 자해 준비일 수 있어 crisis로 봐. "
    "앞 말만 힘들었고 지금 질문은 약 먹는 시간이나 음식 같은 평범한 질문이면 none (위기 안내는 이미 했으니 매 질문을 막지 않음)."
)


def guard_message(question: str, recent: list[str] | None = None) -> str:
    """앞 사용자 말이 없으면 질문 그대로 (10/16 측정과 같은 글). 있으면 참고로 앞에 붙이고 판단 기준을 함께 (#143, 11/2)"""
    if not recent:
        return question
    lines = "\n".join(f"- {t}" for t in recent[-RECENT_TURNS:])
    return f"[앞에서 사용자가 한 말] (오래된 것부터)\n{lines}\n\n[판단 기준]\n{CONTEXT_NOTE}\n\n[지금 질문]\n{question}"


async def guard(question: str, client: ChatClient, usage: Usage, recent: list[str] | None = None) -> str:
    result = await client.complete_json(
        GUARD_SYSTEM, [{"role": "user", "content": guard_message(question, recent)}], GUARD_SCHEMA, "guard", usage
    )
    risk = result.get("risk")
    if risk not in RISKS:
        raise LLMError("bad_risk")
    return str(risk)
