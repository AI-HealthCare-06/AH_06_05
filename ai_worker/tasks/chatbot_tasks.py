"""챗봇 답 만들기 작업 (H-3 질문 뒤, #118). 실제 처리는 app/services/chats.py의 generate 한 곳에 있고 여기서는 부르기만 한다.

흐름: 질문 API가 답 줄(만드는 중)을 만들고 이 작업을 대기열에 넣는다 → 워커가 답을 만들어 그 줄에 저장한다 → 앱은 H-2로 확인한다.
다시 시도하지 않는다 (ai_worker/main.py에서 max_tries=1). 실패하면 generate가 답 줄을 지워 앱이 E6을 보인다.
"""

from typing import Any

from app.services import chats


async def chat_answer(ctx: dict[str, Any], message_id: int, emergency_dismissed: bool = False) -> None:
    await chats.generate(message_id, emergency_dismissed)
