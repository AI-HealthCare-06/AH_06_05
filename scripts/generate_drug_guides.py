"""약 안내문을 배치로 한꺼번에 만들어 drug_guides에 저장한다 (실행: python scripts/generate_drug_guides.py [--all])

기본은 아직 없는 약만 만든다. --all이면 표 기준으로 다시 만들고, 내용이 바뀐 약은 사람이 확인한 것도 draft로 되돌려 다시 확인받는다
(내용이 같으면 확인 상태 그대로). 규칙 표(medication.CLASS_*)를 고친 뒤에는 --all로 돌린다.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.services.guide import store  # noqa: E402


async def main(only_missing: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        print(await store.generate_all(only_missing=only_missing))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main(only_missing="--all" not in sys.argv))
