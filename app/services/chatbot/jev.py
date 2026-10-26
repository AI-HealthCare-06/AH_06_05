"""1층에 더하는 Jev(TypeSafe) 판단 (10/26 수인 결정). 1층 규칙에 안 걸린 질문만, 질문을 저장하기 전에 한 번 봄.

- 켜는 설정 SAFETY_JEV (기본 꺼짐): 질문(건강 정보)이 TypeSafe로 가므로 개인정보 고지가 정해지면 켬
- "해당 없음" 확률이 SAFETY_JEV_MAX_NONE보다 낮을 때만 막음 (시작값 0.3). 10/26 열지 않은 채점 묶음(seed 19, 20)에서
  규칙만은 위험 112개 중 51개를 놓쳤고, 이 기준을 더하면 20개로 줄며 정상 106개 중 막은 수는 3개에서 5개가 됨
- 1층은 AI 없이도 돌아야 하므로 SAFETY_JEV_TIMEOUT_SEC 안에 답이 없거나 오류면 규칙 결과만 씀 (재시도 없음)
- 지시문과 보기는 10/26 측정 때와 같은 글 (저장소 밖 chatbot_sandbox/jev_guard.py). 바꾸면 다시 잼
"""

import asyncio
import logging

from app.core import config

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "고령 사용자가 복약 안내 챗봇에 보낸 질문 `question`이 지금 위험한 상황인지 고른다. "
    "오타와 띄어쓰기가 틀려도 뜻으로 판단한다. 놓치는 것이 더 위험하므로 애매하면 위험한 쪽을 고른다."
)
CRITERIA = {
    "emergency": "지금 몸에 응급 증상이 있다 (가슴, 숨, 의식, 마비, 심한 출혈, 붓는 알레르기, 저혈당으로 정신이 흐림). "
    "또는 약을 이미 많이 먹었거나 잘못 먹었다 (아이가 어른 약을 먹은 것 포함)",
    "crisis": "죽고 싶다, 사라지고 싶다, 짐이 된다, 끝내고 싶다처럼 자해나 자살 생각을 돌려 말한다. "
    "또는 약을 모으거나, 많이 먹으면 어떻게 되는지, 깨지 않고 자려면 얼마나 먹는지처럼 위험한 양을 묻는다",
    "none": "위의 둘이 아니다. 상담전화 번호나 약 먹는 시간 같은 정보 질문, 지난 일이나 남의 이야기, "
    "약 추천이나 지시를 무시하라는 요청은 none",
}


async def _typesafe(question: str) -> tuple[str, float]:
    """Jev가 고른 보기와 "해당 없음" 확률"""
    from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy

    async with AsyncTypeSafeClient(
        api_key=config.TYPESAFE_API_KEY, retry=RetryPolicy(max_retries=0), timeout=config.SAFETY_JEV_TIMEOUT_SEC
    ) as client:
        resp = await client.system_one(
            state={"question": question},
            questions={"risk": Choice(instructions=INSTRUCTIONS, criteria=CRITERIA)},
        )
    answer = resp.answers["risk"]
    probs = answer.probabilities
    p_none = probs.get("none", 0.0) if isinstance(probs, dict) else getattr(probs, "none", 0.0)
    return answer.choice, float(p_none)


async def check(question: str, emergency_dismissed: bool = False) -> str | None:
    """막을 갈래(emergency, crisis) 또는 None. 꺼져 있거나 늦거나 실패하면 None"""
    if not config.SAFETY_JEV or not config.TYPESAFE_API_KEY:
        return None
    try:
        choice, p_none = await asyncio.wait_for(_typesafe(question), timeout=config.SAFETY_JEV_TIMEOUT_SEC)
    except Exception as e:  # 시간 초과, 연결, 인증 오류 모두 규칙 결과만 씀
        logger.warning("Jev가 답하지 않아 1층 규칙만 씀 (%s)", type(e).__name__)  # 질문 글은 남기지 않음
        return None
    if choice not in ("emergency", "crisis") or p_none >= config.SAFETY_JEV_MAX_NONE:
        return None
    if choice == "emergency" and emergency_dismissed:
        return None  # [지금은 증상이 없어요] 뒤에는 자해만 봄 (규칙과 같게, 명세서 H-3)
    return choice
