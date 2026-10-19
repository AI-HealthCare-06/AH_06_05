"""2층 가드레일 (#99, 설계 메모 7-12). 위험만 보는 전용 호출이고 답은 none, emergency, crisis 중 하나.

질문 분류 안에서 같이 판단하면 위험 17개 중 10개를 놓쳐서 따로 부른다 (10/12). 모델은 gpt-4o-mini (#81 비교 결과).
1층에 걸려도 문맥 파악이 푼 질문, 1층에 걸리지 않은 질문 모두 이 단계를 거친다.
"""

from app.services.chatbot.llm import ChatClient, LLMError, Usage
from app.services.chatbot.prompts import GUARD_SCHEMA, GUARD_SYSTEM

RISKS = ("none", "emergency", "crisis")


async def guard(question: str, client: ChatClient, usage: Usage) -> str:
    result = await client.complete_json(
        GUARD_SYSTEM, [{"role": "user", "content": question}], GUARD_SCHEMA, "guard", usage
    )
    risk = result.get("risk")
    if risk not in RISKS:
        raise LLMError("bad_risk")
    return str(risk)
