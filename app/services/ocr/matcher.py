"""약 이름 맞추기 — OCR이 읽은 이름을 약제급여목록(drug_products)에서 찾기

점수: 질문 이름의 글자 조각(2글자) 중 몇 %가 후보 이름에 있나 (overlap, 짧게 읽힌 이름에 유리) + 동점이면 jaccard.
결과를 "찾음 / 비슷한 약이 여럿 / 찾지 못함" 세 가지로 나누는 기준은 저장해 둔 CLOVA 결과로 정함:
- 제대로 맞은 이름: 0.90 이상 (글자 하나를 잘못 읽어도 0.90 안팎)
- 흐린 사진에서 엉뚱하게 읽힌 이름: 0.40 ~ 0.42
"""

import heapq
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from app.services.drug_names import base_name, maker_pattern, strip_maker, unify

NOT_FOUND_BELOW = 0.60  # 이 점수 아래면 찾지 못한 것으로 본다
MIN_LEN = 4  # 약 이름이 이보다 짧게 읽히면(예: "병원") 찾지 않는다
BRAND_MIN = 0.70  # 이름 앞부분(숫자 앞)의 글자 조각이 후보와 이 비율 이상 겹쳐야 한다 (10/13 시험으로 0.50 → 0.70)
AMBIGUOUS_GAP = 0.03  # 1등과 2등 점수 차가 이보다 작고 서로 다른 약이면 사용자에게 고르게 한다

FOUND, AMBIGUOUS, NOT_FOUND = "found", "ambiguous", "not_found"


def grams(s: str, n: int = 2) -> frozenset[str]:
    return frozenset(s[i : i + n] for i in range(len(s) - n + 1)) if len(s) >= n else frozenset({s})


def overlap(a: frozenset[str], b: frozenset[str]) -> float:
    jaccard = len(a & b) / len(a | b) if a | b else 0.0
    return (len(a & b) / len(a) if a else 0.0) + 0.01 * jaccard


def _brand(name: str) -> str:
    """숫자와 괄호 앞까지의 이름 (이디졸캡슐100밀리그램(이트라코나졸) → 이디졸캡슐)"""
    return re.split(r"[\d(]", base_name(name))[0]


def _brand_overlap(a: str, b: str) -> float:
    ga, gb = grams(unify(_brand(a))), grams(unify(_brand(b)))
    return len(ga & gb) / len(ga) if ga else 0.0


@dataclass(frozen=True)
class Candidate:
    edi_code: str
    item_name: str
    score: float


@dataclass(frozen=True)
class Decision:
    status: str  # found | ambiguous | not_found
    score: float
    candidates: list[Candidate]
    exact: bool = False  # 이름이 제품명과 글자 그대로 같음
    same_name: bool = False  # mg · 밀리그람 같은 표기를 통일하면 제품명과 같음 (약 이름 검색의 "확실" 기준)


class NameMatcher:
    def __init__(self, products: list[tuple[str, str]], makers: Iterable[str] = ()) -> None:
        """products: [(edi_code, 제품명)], makers: 급여목록의 제조사 이름들 (처방전에서 이름에 붙어 읽힌 제조사를 떼는 데 씀)"""
        self._idx = [(edi, nm, grams(unify(base_name(nm)))) for edi, nm in products]
        self._maker = maker_pattern(makers)

    def without_maker(self, name: str) -> str:
        """OCR이 읽은 약 이름에서 제조사 꼬리를 뗌"""
        return strip_maker(unicodedata.normalize("NFKC", name), self._maker)

    def __len__(self) -> int:
        return len(self._idx)

    def decide(self, read_name: str, top_n: int = 3) -> Decision:
        qb = base_name(self.without_maker(read_name))  # 제조사 꼬리를 먼저 뗌
        if len(qb) < MIN_LEN or not self._idx:
            return Decision(NOT_FOUND, 0.0, [])
        qg = grams(unify(qb))
        top = heapq.nlargest(top_n, ((overlap(qg, g), edi, nm) for edi, nm, g in self._idx))
        cands = [Candidate(edi, nm, round(sc, 3)) for sc, edi, nm in top]
        best = top[0][0]
        if best < NOT_FOUND_BELOW or _brand_overlap(qb, top[0][2]) < BRAND_MIN:
            return Decision(NOT_FOUND, round(best, 3), cands)
        # 1등과 점수가 거의 같은데 이름이 다른 약(규격만 다른 같은 약은 제외)이면 고르게 한다
        # (이름이 제품명과 글자 그대로 같으면 그 약으로 본다)
        exact = base_name(top[0][2]) == qb
        close = (
            []
            if exact
            else [c for c in top[1:] if best - c[0] < AMBIGUOUS_GAP and base_name(c[2]) != base_name(top[0][2])]
        )
        if close:
            return Decision(AMBIGUOUS, round(best, 3), cands)
        return Decision(FOUND, round(best, 3), cands, exact=exact, same_name=unify(base_name(top[0][2])) == unify(qb))
