"""약 이름 맞추기 — OCR이 읽은 이름을 약제급여목록(drug_products)에서 찾기

점수: 질문 이름의 글자 조각(2글자) 중 몇 %가 후보 이름에 있나 (overlap, 짧게 읽힌 이름에 유리) + 동점이면 jaccard.
결과를 "찾음 / 비슷한 약이 여럿 / 찾지 못함" 세 가지로 나누는 기준은 저장해 둔 CLOVA 결과로 정함:
- 제대로 맞은 이름: 0.90 이상 (글자 하나를 잘못 읽어도 0.90 안팎)
- 흐린 사진에서 엉뚱하게 읽힌 이름: 0.40 ~ 0.42
"""

import heapq
import re
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.core import config
from app.services.drug_names import base_name, maker_pattern, strip_maker, unify

NOT_FOUND_BELOW = 0.60  # 이 점수 아래면 찾지 못한 것으로 본다
MIN_LEN = 4  # 약 이름이 이보다 짧게 읽히면(예: "병원") 찾지 않는다
BRAND_MIN = 0.70  # 이름 앞부분(숫자 앞)의 글자 조각이 후보와 이 비율 이상 겹쳐야 한다 (10/13 시험으로 0.50 → 0.70)
SIBLING_CHOICES = 5  # 형제 약 확인에서 보여 주는 후보 수 (읽은 이름의 약 + 형제들). 형제가 많은 이름은 3개로는 진짜 약이 빠짐 (측정: 83% → 94%)
MIN_SIBLING_LEN = 3  # 이보다 짧은 상표 이름은 형제로 보지 않음 (너무 짧으면 거의 모든 이름이 형제가 됨)
AMBIGUOUS_GAP = 0.03  # 1등과 2등 점수 차가 이보다 작고 서로 다른 약이면 사용자에게 고르게 한다

# 2차 "비슷한 이름 추천" (pg_trgm 방식 자모 3개 조각 유사도): 규칙이 못 찾은 이름만, 사용자가 고르는 후보로만 내놓는다 (자동 확정 안 함)
# 기준은 오타 시뮬레이션 + 음성 대조로 정함 (docs/design/ocr_fuzzy_match.md)
# 기본 기준(0.70)은 config.OCR_SIMILAR_MIN — 실제 오독 2건(0.71)을 잡고 오타 시뮬레이션에서 78%를 후보에 올리는 선, 0이면 이 추천을 끈다

FOUND, AMBIGUOUS, NOT_FOUND = "found", "ambiguous", "not_found"


def grams(s: str, n: int = 2) -> frozenset[str]:
    return frozenset(s[i : i + n] for i in range(len(s) - n + 1)) if len(s) >= n else frozenset({s})


def trigrams(s: str) -> frozenset[str]:
    """PostgreSQL pg_trgm과 같은 방식의 3글자 조각 — 단, 한글은 자음·모음(자모)으로 풀어서 자른다.
    낱말(글자·숫자 덩어리)마다 앞에 공백 2개 · 뒤에 1개를 붙여 3글자씩 자른다.
    자모로 풀면 글자 하나가 비슷한 글자로 잘못 읽혀도(엘→멜) 조각 대부분이 남는다. 음절 그대로 자르면 실제 CLOVA 오독 2건이 0.38 · 0.55로 낮게 나와 놓친다"""
    out: set[str] = set()
    for w in re.findall(r"\w+", unicodedata.normalize("NFD", s.lower())):
        p = f"  {w} "
        out.update(sys.intern(p[i : i + 3]) for i in range(len(p) - 2))
    return frozenset(out)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """pg_trgm similarity()와 같은 값: 두 조각 모음의 겹침 ÷ 합침 (길이가 다른 이름끼리는 낮게 나옴)"""
    return len(a & b) / len(a | b) if a | b else 0.0


def overlap(a: frozenset[str], b: frozenset[str]) -> float:
    jaccard = len(a & b) / len(a | b) if a | b else 0.0
    return (len(a & b) / len(a) if a else 0.0) + 0.01 * jaccard


def _brand(name: str) -> str:
    """숫자와 괄호 앞까지의 이름 (이디졸캡슐100밀리그램(이트라코나졸) → 이디졸캡슐)"""
    return re.split(r"[\d(]", base_name(name))[0]


def _strength_numbers(name: str) -> list[str]:
    """이름에서 괄호(성분) 앞까지의 숫자들 (노바스크정5밀리그램(암로디핀) → ["5"] · 엔피포지정5/160 → ["5", "160"])"""
    return re.findall(r"\d+(?:\.\d+)?", re.split(r"[(\[]", unify(name))[0])


def _different_ingredient(a: set[str | None], b: set[str | None]) -> bool:
    """두 상표의 주성분코드가 하나도 겹치지 않으면 다른 약 (코드를 모르는 약이 끼어 있으면 다르다고 봄)"""
    return None in a or None in b or not (a & b)


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
    strength: bool = False  # 읽은 이름의 함량 숫자가 맞는 약의 숫자와 달라 사용자가 고르게 함 (decide)
    sibling: bool = False  # 이름이 글자 하나 차이인 다른 성분의 약이 있어 사용자가 고르게 함 (아래 NameMatcher.decide)


class NameMatcher:
    def __init__(
        self,
        products: list[tuple[str, str]],
        makers: Iterable[str] = (),
        ingredients: Mapping[str, str | None] | None = None,
    ) -> None:
        """products: [(edi_code, 제품명)], makers: 급여목록의 제조사 이름들 (처방전에서 이름에 붙어 읽힌 제조사를 떼는 데 씀),
        ingredients: {edi_code: 주성분코드} — 주면 "글자 하나 차이인 다른 성분의 약"을 알아본다 (없으면 그 검사를 하지 않음)"""
        self._idx = [(edi, nm, grams(unify(base_name(nm)))) for edi, nm in products]
        self._base = [base_name(nm) for _, nm in products]  # 이름이 글자 그대로 같은 제품을 동점에서 먼저 고르는 데 씀
        self._tidx: list[tuple[str, str, frozenset[str]]] | None = None
        self._ingr = ingredients
        self._sib: dict[str, list[str]] | None = None
        self._by_brand: dict[str, list[int]] = {}
        self._maker = maker_pattern(makers)

    def without_maker(self, name: str) -> str:
        """OCR이 읽은 약 이름에서 제조사 꼬리를 뗌"""
        return strip_maker(unicodedata.normalize("NFKC", name), self._maker)

    def __len__(self) -> int:
        return len(self._idx)

    def prepare(self) -> list[tuple[str, str, frozenset[str]]]:
        """비슷한 이름 추천용 조각 색인 (처음 한 번 0.5초쯤). 서버를 켤 때 미리 만들어 두면 첫 요청이 느려지지 않는다.
        여러 스레드가 동시에 불러도 같은 결과가 나오며 결과는 한 번 만들면 바뀌지 않는다"""
        self._siblings()
        idx = self._tidx
        if idx is None:
            idx = self._tidx = [(edi, nm, trigrams(unify(base_name(nm)))) for edi, nm, _ in self._idx]
        return idx

    def _siblings(self) -> dict[str, list[str]]:
        """{상표 이름: 글자 하나가 더 있거나 빠진 이름의 다른 성분 약 상표들}. 상표 이름 = 숫자·괄호 앞까지 (글리마릴정 ↔ 글리마릴엠정).
        성분은 주성분코드로 비교하고 코드를 모르는 약은 다르다고 본다 (놓치는 것보다 한 번 더 묻는 쪽이 안전).
        한 번 만들면 바뀌지 않아 여러 스레드가 동시에 만들어도 결과가 같다"""
        sib = self._sib
        if sib is not None:
            return sib
        ingr = self._ingr or {}
        by_brand: dict[str, list[int]] = defaultdict(list)
        codes: dict[str, set[str | None]] = defaultdict(set)
        for i, (edi, nm, _) in enumerate(self._idx):
            key = unify(_brand(nm))
            if len(key) >= MIN_SIBLING_LEN:
                by_brand[key].append(i)
                codes[key].add(ingr.get(edi))
        shorter: dict[str, set[str]] = defaultdict(set)  # 글자 하나를 뺀 이름 → 그 이름이 만들어지는 긴 상표들
        for key in by_brand:
            for i in range(len(key)):
                shorter[key[:i] + key[i + 1 :]].add(key)
        out: dict[str, list[str]] = {}
        for key in by_brand:
            near = set(shorter.get(key, ()))  # 글자가 하나 더 있는 형제
            near |= {k for i in range(len(key)) if (k := key[:i] + key[i + 1 :]) in by_brand}  # 하나 빠진 형제
            diff = sorted(k for k in near if _different_ingredient(codes[key], codes[k]))
            if diff:
                out[key] = diff
        self._by_brand = by_brand
        self._sib = out
        return out

    def similar(self, read_name: str, top_n: int = 3) -> Decision | None:
        """규칙이 못 찾은 이름에 대한 "비슷한 이름" 추천. 글자 하나가 바뀌거나 빠진 이름을 글자 3개 조각 유사도(pg_trgm 방식)로 찾는다.
        결과는 항상 사용자가 고르는 AMBIGUOUS (자동 확정 아님). 기준에 못 미치면 None"""
        limit = config.OCR_SIMILAR_MIN
        qb = base_name(self.without_maker(read_name))
        if limit <= 0 or len(qb) < MIN_LEN or not self._idx:
            return None
        q = trigrams(unify(qb))
        top = heapq.nlargest(top_n, ((similarity(q, t), edi, nm) for edi, nm, t in self.prepare()))
        if top[0][0] < limit:
            return None
        return Decision(AMBIGUOUS, round(top[0][0], 3), [Candidate(edi, nm, round(sc, 3)) for sc, edi, nm in top])

    def decide(self, read_name: str, top_n: int = 3, siblings: bool = True) -> Decision:
        """siblings=False면 형제 약 확인을 건너뜀 (이미 사용자가 고르는 경로이거나, 사용자가 직접 이름을 친 검색)"""
        qb = base_name(self.without_maker(read_name))  # 제조사 꼬리를 먼저 뗌
        if not self._idx:
            return Decision(NOT_FOUND, 0.0, [])
        if len(qb) < MIN_LEN:
            return self._short_exact(qb)
        qg = grams(unify(qb))
        # 글자 조각이 같은 다른 이름(브록솔정 ↔ 록솔정: 2글자 조각 집합이 같음)과 동점이면 이름이 글자 그대로 같은 제품이 먼저 (점수에는 영향 없는 1e-9)
        top = heapq.nlargest(
            top_n,
            (
                (overlap(qg, g) + (1e-9 if self._base[i] == qb else 0.0), edi, nm)
                for i, (edi, nm, g) in enumerate(self._idx)
            ),
        )
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
        read_nums = _strength_numbers(qb)
        if read_nums and read_nums != _strength_numbers(top[0][2].split("_(")[0]):
            # 읽은 이름의 함량 숫자가 맞는 약의 숫자와 다르다 (60을 30으로, 5를 50으로 잘못 읽은 경우 · 목록에 없는 함량).
            # 글자는 거의 같아서 점수가 높게 나오지만 다른 함량의 약일 수 있다 → 틀린 함량이 확정되지 않게 사용자가 고른다 (10/15, 급여목록으로 한 자리 바꾸기 시험에서 3%)
            return Decision(AMBIGUOUS, round(best, 3), cands, strength=True)
        if siblings and (sib := self._sibling_choices(top[0][2], qg, top_n)):
            # 읽힌 이름이 목록에 있는 이름이어도, 글자 하나 차이의 다른 성분 약이 있으면 오타인지 다른 약인지 글자만으로는 알 수 없다
            # (예: 로글리코엠정을 로글리코정으로 읽음). 틀린 약이 확정되는 것을 막으려고 사용자가 고르게 한다
            return Decision(AMBIGUOUS, round(best, 3), [cands[0], *sib], sibling=True)
        return Decision(FOUND, round(best, 3), cands, exact=exact, same_name=unify(base_name(top[0][2])) == unify(qb))

    def _short_exact(self, qb: str) -> Decision:
        """짧은 이름(3글자: 울셋정 · 코푸정 · 아트정 등 급여목록에 실제로 있음)은 비슷한 이름을 찾으면 엉뚱한 약이 나오기 쉬워서,
        급여목록 제품명과 글자 그대로 같을 때만 찾는다. 2글자 이하는 찾지 않는다 (병원 · 약국 같은 낱말이 약 이름 칸에 섞여 읽히는 경우)"""
        if len(qb) >= MIN_LEN - 1:
            hits = [i for i, b in enumerate(self._base) if b == qb]
            if hits:
                edi, nm, _ = self._idx[hits[0]]
                return Decision(FOUND, 1.0, [Candidate(edi, nm, 1.0)], exact=True, same_name=True)
        return Decision(NOT_FOUND, 0.0, [])

    def _sibling_choices(self, name: str, qg: frozenset[str], top_n: int) -> list[Candidate]:
        """찾은 약의 형제 상표들에서 질문 이름과 가장 가까운 제품을 하나씩 (읽은 이름의 약 포함 최대 max(top_n, SIBLING_CHOICES)개).
        형제가 없거나 확인을 끄면 빈 목록"""
        if not config.OCR_SIBLING_CONFIRM or self._ingr is None:
            return []
        brands = self._siblings().get(unify(_brand(name)))
        if not brands:
            return []
        picks = [
            max((overlap(qg, self._idx[i][2]), self._idx[i][1], self._idx[i][0]) for i in self._by_brand[b])
            for b in brands
        ]
        picks.sort(reverse=True)
        return [Candidate(edi, nm, round(sc, 3)) for sc, nm, edi in picks[: max(top_n, SIBLING_CHOICES) - 1]]
