"""생활습관 안내의 약 연결용 성분코드 앞 4자리 목록을 만든다 (실행: python scripts/gen_lifestyle_ingr_prefixes.py <safety.sqlite 경로>)

약제급여목록의 주성분명(영문)에 대상 성분이 든 품목의 성분코드(ingr_code) 앞 4자리를 모은다. 이름에 성분이 안 적힌 복합제(엑스포지, 코자플러스 등)도
성분코드로 찾기 위함이다. 약 종류마다 성분이 달라서 종류별로 따로 만든다 (app/services/guide/lifestyle.py의 _ingr_prefixes).
같은 앞 4자리를 쓰는 품목이 모두 대상 성분을 가진 것은 11/2에 확인했다 (충돌 0개). 약제급여목록을 새로 받으면 다시 돌려 확인한다.
"""

import json
import sqlite3
import sys
from pathlib import Path

ACE = ["enalapril", "captopril", "lisinopril", "ramipril", "perindopril", "cilazapril", "alacepril"]
ARB = [
    "losartan",
    "valsartan",
    "telmisartan",
    "candesartan",
    "irbesartan",
    "azilsartan",
    "fimasartan",
    "olmesartan",
    "eprosartan",
]
THIAZIDE_LOOP = [
    "hydrochlorothiazide",
    "furosemide",
    "indapamide",
    "torsemide",
    "torasemide",
    "chlorthalidone",
    "chlortalidone",
    "azosemide",
    "xipamide",
]
SPIRONOLACTONE = ["spironolactone"]
FINERENONE = ["finerenone"]

# 팩트표 약 종류 이름(app/services/guide/data/lifestyle_facts.json의 drug_class) → 주성분명(영문) 낱말
CLASSES = {
    "티아지드·루프 이뇨제 (히드로클로로티아지드, 푸로세미드 등 — 칼륨 보전 이뇨제 제외)": THIAZIDE_LOOP,
    "ACE억제제·ARB (에날라프릴, 로사르탄 등)": ACE + ARB,
    "칼륨 보전 이뇨제 (스피로노락톤)": SPIRONOLACTONE,
    "칼륨 보전 이뇨제·ACE억제제·ARB": ACE + ARB + SPIRONOLACTONE + FINERENONE,
}
OUT = Path(__file__).resolve().parents[1] / "app" / "services" / "guide" / "data" / "lifestyle_ingr_prefixes.json"


def main(db_path: str) -> None:
    rows = sqlite3.connect(db_path).execute("SELECT ingr_code, ingr_name FROM drug_products").fetchall()
    prefixes: dict[str, list[str]] = {}
    for drug_class, words in CLASSES.items():
        found = {(code or "")[:4] for code, name in rows if code and any(w in (name or "").lower() for w in words)}
        bad = {  # 같은 앞 4자리인데 대상 성분이 없는 품목이 섞이면 안 됨
            p
            for p in found
            for code, name in rows
            if (code or "")[:4] == p and not any(w in (name or "").lower() for w in words)
        }
        if bad:
            sys.exit(f"충돌: {drug_class} {sorted(bad)}")
        prefixes[drug_class] = sorted(found)
    meta = "약제급여목록 주성분명(영문)에 대상 성분이 든 품목의 성분코드 앞 4자리. scripts/gen_lifestyle_ingr_prefixes.py로 만듦 (11/2)"
    OUT.write_text(
        json.dumps({"_meta": meta, "prefixes": prefixes}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print({k[:10]: len(v) for k, v in prefixes.items()})


if __name__ == "__main__":
    main(sys.argv[1])
