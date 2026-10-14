"""약 안내문 사람 확인 (실행: python scripts/review_drug_guides.py list | approve KEY --by 이름 | reject KEY --by 이름)

멘토링 4회차: 안내문은 미리 만들어 두되 사람이 확인해야 한다. 분석 때는 approved만 쓰인다.
규칙 표로 만든 안내문은 약효분류마다 내용이 같아서, 같은 내용을 묶음(KEY)으로 보여 주고 묶음 단위로 확인한다.
HTTP로 열지 않는다 (관리자 권한이 아직 없어서 — 서버 안에서 팀원이 직접 실행).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.analysis import ReviewStatus  # noqa: E402
from app.services.guide import store  # noqa: E402


async def run(args: argparse.Namespace) -> None:
    if args.cmd == "list":
        for g in await store.groups():
            c = g["content"]
            print(f"[{g['key']}] {g['count']}개  상태 {g['status']}")
            print(
                f"    종류={c.get('category')}  쓰임={c.get('purpose')}  주의={c.get('caution')}  출처={c.get('source')}"
            )
            print(f"    예: {' / '.join(g['examples'])}")
        return
    status = ReviewStatus.APPROVED if args.cmd == "approve" else ReviewStatus.REJECTED
    n = await store.review_group(args.key, status, args.by)
    print(f"{n}개 {status.value} 처리" if n else "그런 KEY가 없어요 (list로 확인)")


async def main(args: argparse.Namespace) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        await run(args)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("key")
        p.add_argument("--by", required=True, help="확인한 사람 이름")
    asyncio.run(main(ap.parse_args()))
