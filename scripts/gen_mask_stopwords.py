"""이름 모양이지만 이름이 아닌 낱말 목록 만들기 (실행: python scripts/gen_mask_stopwords.py [--write])

원문 마스킹(app/services/ocr/mask.py)은 "성씨 + 2글자" 낱말을 이름으로 보고 가린다. 그런데 약 이름 · 제조사 · 질병명에는
주사액 · 서방정 · 고혈압처럼 이름 모양인 낱말이 있어서, 급여목록과 상병마스터에서 그런 낱말을 뽑아 mask_stopwords.txt로 둔다.
기본은 개수만 보여 주고, --write를 주면 파일을 새로 쓴다. 약 목록이 바뀌면 다시 실행한다.
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.masters import Disease, DrugProduct  # noqa: E402
from app.services.ocr import mask as mask_module  # noqa: E402

OUT = Path(mask_module.__file__).with_name("mask_stopwords.txt")
HANGUL = re.compile(r"[가-힣]+")


def shaped(word: str) -> bool:
    if len(word) == 3:
        return word[0] in mask_module.SURNAMES
    return len(word) == 4 and word[:2] in mask_module.SURNAMES_2


async def collect() -> list[str]:
    texts: list[str] = []
    texts += [name for (name,) in await DrugProduct.all().values_list("item_name")]
    texts += [maker for (maker,) in await DrugProduct.filter(entp_name__not_isnull=True).values_list("entp_name")]
    texts += [name for (name,) in await Disease.all().values_list("name_kr")]
    return sorted({w for t in texts for w in HANGUL.findall(t) if shaped(w)})


async def main(write: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        words = await collect()
    finally:
        await Tortoise.close_connections()
    print(f"이름 모양 낱말 {len(words)}개 (약 이름 · 제조사 · 질병명)")
    if write:
        OUT.write_text("\n".join(words) + "\n", encoding="utf-8")
        print(f"{OUT} 에 저장했어요")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="파일에 저장 (없으면 개수만 보여 줌)")
    asyncio.run(main(ap.parse_args().write))
