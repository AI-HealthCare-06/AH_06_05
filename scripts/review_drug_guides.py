"""약 안내문 사람 확인
실행: python scripts/review_drug_guides.py list | approve KEY --by 이름 | reject KEY --by 이름   (규칙 표 안내문, 묶음 단위)
      python scripts/review_drug_guides.py drugs | approve-drug 코드... --by 이름 | reject-drug 코드... --by 이름   (허가정보 문장, 약 단위)

멘토링 4회차: 안내문은 미리 만들어 두되 사람이 확인해야 한다. 분석 때는 approved만 쓰인다.
규칙 표로 만든 안내문은 약효분류마다 내용이 같아서, 같은 내용을 묶음(KEY)으로 보여 주고 묶음 단위로 확인한다.
허가정보 문장(AI가 쓰고 규칙으로 걸러 낸 것)은 약마다 문장이 달라서 묶지 않고 약 하나씩 확인한다. 확인 기준은
"문장이 근거 원문과 어긋나지 않는가"이고 의학적 판단은 아니다. `drugs`가 문장과 근거 원문을 나란히 보여 준다.
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
    if args.cmd == "drugs":
        for g in await store.seed_guides():
            c = g["content"]
            who = f" ({g['reviewedBy']})" if g["reviewedBy"] else ""
            print(f"[{g['ediCode']}] {g['name']}  상태 {g['status']}{who}")
            print(f"    종류={c.get('category')}  쓰임={c.get('purpose')}  출처={c.get('source')}")
            for i, t in enumerate(c.get("cautions") or [], 1):
                print(f"    주의 {i}: {t}")
                for e in g["evidence"]:
                    if e["use"] == f"caution{i}":
                        print(f"        근거 {e['field']}: {e['text']}")
        return
    if args.cmd in ("approve-drug", "reject-drug"):
        status = ReviewStatus.APPROVED if args.cmd == "approve-drug" else ReviewStatus.REJECTED
        n = await store.review_drugs(args.codes, status, args.by)
        print(f"{n}개 {status.value} 처리" if n else "그런 약이 없어요 (drugs로 확인)")
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
    sub.add_parser("drugs")
    for name in ("approve-drug", "reject-drug"):
        p = sub.add_parser(name)
        p.add_argument("codes", nargs="+", help="약 코드(edi_code) 여러 개")
        p.add_argument("--by", required=True, help="확인한 사람 이름")
    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("key")
        p.add_argument("--by", required=True, help="확인한 사람 이름")
    asyncio.run(main(ap.parse_args()))
