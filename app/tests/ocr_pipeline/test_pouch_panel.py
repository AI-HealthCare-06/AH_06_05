"""약봉투 오른쪽 "약품명" 칸 이름으로 영수증 칸 이름 바로잡기 시험 (DB · 네트워크 없음)

10/16 실물 약봉투(영수증 칸 + 복약안내 칸이 있는 푸른 봉투)에서 잰 좌표를 줄여 만든 합성 글자 위치다. 개인정보 칸은 넣지 않았다.
영수증 칸 이름은 약국 프로그램이 10자쯤에서 잘랐고 CLOVA가 한 글자씩 잘못 읽었다: 펜크티정375밀리그램(아 / 에이탈정(아세클로페낙) / 가스:므틴정5밀리그람(모
"""

from app.services.ocr.matcher import AMBIGUOUS, FOUND, NameMatcher
from app.services.ocr.pipeline import PANEL_FLAG, read
from app.services.ocr.pouch_panel import panel_words, refine

PRODUCTS = [
    ("100000001", "펜크라정375밀리그램(아목시실린수화물,클라불란산칼륨희석물)"),
    ("100000002", "에어탈정(아세클로페낙)"),
    ("100000003", "가스모틴정5밀리그램(모사프리드시트르산염수화물)"),
    ("100000004", "헥사메딘액0.12%(클로르헥시딘글루콘산염액)"),
]


def fld(text: str, x: float, y: float, w: float, h: float, conf: float = 0.97) -> dict:
    return {
        "inferText": text,
        "inferConfidence": conf,
        "boundingPoly": {
            "vertices": [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
        },
    }


def receipt() -> list[dict]:
    """왼쪽 영수증 칸: 머리글(약품명 투약량 횟수 일수) + 약 네 줄 (이름은 잘리고 잘못 읽힘)"""
    out = [
        fld("약품명", 190, 1027, 75, 24),
        fld("투약량", 395, 1030, 58, 24),
        fld("횟수", 495, 1030, 33, 24),
        fld("일수", 562, 1032, 36, 24),
    ]
    rows = [
        (1071, "펜크티정375밀리그램(아", ("1", "2", "3"), 0.42),
        (1101, "에이탈정(아세클로페낙)", ("1", "2", "3"), 0.69),
        (1131, "가스:므틴정5밀리그람(모", ("1", "2", "3"), 0.88),
        (1162, "헥사메딘액0.12%(클로르", ("1", "1", "1"), 0.82),
    ]
    for y, name, nums, conf in rows:
        out.append(fld(name, 78, y - 12, 300, 26, conf))
        for x, v in zip((457, 525, 595), nums, strict=True):
            out.append(fld(v, x, y - 8, 12, 20))
    return out


def panel(names: list[str] | None = None) -> list[dict]:
    """오른쪽 복약안내 칸: 머리글(약품사진 약품명 복약안내 주의사항) + 약 이름(크게)과 모양 설명"""
    names = names or ["펜크라정375mg", "에어탈정", "가스모틴정5mg", "헥사메딘액0.12%"]
    out = [
        fld("약품사진", 680, 335, 110, 36),
        fld("약품명", 962, 355, 90, 36),
        fld("복약안내", 1260, 355, 110, 36),
        fld("주의사항", 1795, 335, 110, 36),
    ]
    for y, n in zip((423, 524, 629, 731), names, strict=True):
        out.append(fld(n, 846, y, 207, 42, 0.99))
        out.append(fld("흰색", 841, y + 40, 47, 28, 0.93))
        out.append(fld("필름코팅정", 868, y + 66, 116, 29, 0.98))
        out.append(fld("[페니실린계", 1060, y - 10, 140, 30))  # 다음 칸(분류)은 이름 칸이 아니다
    return out


def data(*parts: list[dict]) -> dict:
    return {"images": [{"fields": [f for p in parts for f in p]}]}


def test_panel_words_reads_only_the_column_under_the_right_header():
    words = {w for w, _ in panel_words(data(receipt(), panel())["images"][0]["fields"])}
    assert {"펜크라정375mg", "에어탈정", "가스모틴정5mg", "헥사메딘액0.12%"} <= words
    assert "[페니실린계" not in words  # 오른쪽 분류 칸
    assert "펜크티정375밀리그램(아" not in words  # 영수증 칸 (그 머리글 "약품명"은 약품사진 · 복약안내와 한 줄이 아님)
    assert panel_words(data(receipt())["images"][0]["fields"]) == []  # 약품명 칸이 없는 약봉투는 건드리지 않음


def test_refine_matches_by_brand_and_strength_and_refuses_when_unsure():
    w = panel_words(data(receipt(), panel())["images"][0]["fields"])
    assert refine("펜크티정375밀리그램(아", w) == "펜크라정375mg"
    assert refine("에이탈정(아세클로페낙)", w) == "에어탈정"
    assert refine("가스:므틴정5밀리그람(모", w) == "가스모틴정5mg"
    assert refine("펜크라정500밀리그램(아", w) is None  # 함량이 다르면 다른 약
    assert refine("전혀다른약정10밀리그램", w) is None
    assert refine("펜크티정375밀리그램(아", [("펜크라정375mg", 0.5)]) is None  # 약품명 칸 글자가 흐리면 바꾸지 않음


def test_pipeline_replaces_cut_receipt_names_with_panel_names():
    res = read(data(receipt(), panel()), NameMatcher(PRODUCTS), {})
    assert res.status == "ok" and res.doc_type == "pill_bag"
    assert [r.read_name for r in res.rows] == ["펜크라정375mg", "에어탈정", "가스모틴정5mg", "헥사메딘액0.12%"]
    for r, edi in zip(res.rows, ("100000001", "100000002", "100000003", "100000004"), strict=True):
        assert r.decision.candidates and r.decision.candidates[0].edi_code == edi
        assert "약 이름 글자가 흐리게 읽혔어요" not in r.flags  # 바로잡았으니 흐린 글자 표시는 뺀다
    # 앞의 세 줄은 이름이 달라서 바로잡았다는 표시가 붙는다. 헥사메딘은 영수증 칸 이름으로도 같은 약을 찾았으니 이름만 바꾸고 표시는 없다
    assert [PANEL_FLAG in r.flags for r in res.rows] == [True, True, True, False]
    assert res.rows[1].decision.status in (FOUND, AMBIGUOUS)


def test_pipeline_leaves_good_receipt_names_alone():
    fields = receipt()
    for f in fields:  # 영수증 칸 이름을 제대로 읽은 경우: 바꾸지 않는다
        f["inferText"] = {
            "펜크티정375밀리그램(아": "펜크라정375밀리그램(아목시실린수화물,클라불란산칼륨희석물)",
            "에이탈정(아세클로페낙)": "에어탈정(아세클로페낙)",
            "가스:므틴정5밀리그람(모": "가스모틴정5밀리그램(모사프리드시트르산염수화물)",
            "헥사메딘액0.12%(클로르": "헥사메딘액0.12%(클로르헥시딘글루콘산염액)",
        }.get(f["inferText"], f["inferText"])
        if f["inferConfidence"] < 0.9:
            f["inferConfidence"] = 0.95
    res = read(data(fields, panel()), NameMatcher(PRODUCTS), {})
    assert [r.read_name.split("(")[0] for r in res.rows] == [
        "펜크라정375밀리그램",
        "에어탈정",
        "가스모틴정5밀리그램",
        "헥사메딘액0.12%",
    ]
    assert all(PANEL_FLAG not in r.flags for r in res.rows)
