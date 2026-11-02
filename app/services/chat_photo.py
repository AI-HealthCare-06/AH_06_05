"""챗봇 사진 첨부 (CB-04, H-9, 11/2). 사진 한 장을 기존 OCR(CLOVA)로 읽어 세 가지로 가름. 새 AI 호출은 없음.

- 처방전, 약봉투: OCR이 표를 읽으면 챗봇에서 분석하지 않고 분석하기로 안내 (Figma CB-04 "OCR 경로와 겹침 방지")
- 약 상자, 약 한 개: 읽힌 글에서 약 이름을 맞춰 후보로 되물음. 약 이름을 잘못 읽고 그대로 답하면 엉뚱한 약 안내가 되므로 늘 확인을 받음
- 못 읽음: 약 이름을 글자로 적어 달라고 안내
사진과 읽은 글자는 저장하지 않고 이 요청 안에서만 씀 (원본 사진과 OCR 원문은 저장하지 않음, AGENTS.md).
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.models.masters import DrugProduct
from app.services.drug_names import display_name
from app.services.ocr import clova
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NameMatcher
from app.services.ocr.pipeline import read
from app.services.ocr.pouch import _line_texts
from app.services.prescriptions import Blob, get_codes, get_matcher

logger = logging.getLogger(__name__)

PRESCRIPTION, DRUG, UNREADABLE = "prescription", "drug", "unreadable"
CANDIDATE_MAX = 3
CANDIDATE_GAP = 0.15  # 1등과 이 점수 안쪽의 후보만 보여 줌 (시작값)
_HANGUL = re.compile(r"[가-힣]")

PHOTO_TEXT = "사진 1장을 보냈어요."  # 사용자 줄 글: 읽은 글자는 저장하지 않음
PRESCRIPTION_REPLY = "처방전(약봉투) 사진 같아요. 여러 약을 함께 점검하려면 분석하기에서 올려 주세요."
DRUG_ONE = "사진 속 약이 아래 약이 맞나요? 맞으면 약을 눌러 주세요. 아니면 약 이름을 글자로 적어 주세요."
DRUG_MANY = "사진 속 약이 아래 중 하나인가요? 맞는 약을 눌러 주세요. 없으면 약 이름을 글자로 적어 주세요."
UNREADABLE_REPLY = "사진에서 약 이름을 읽지 못했어요. 약 이름을 글자로 적어 주시면 답해 드릴게요."


@dataclass
class PhotoResult:
    kind: str
    items: list[dict[str, Any]] = field(default_factory=list)  # 약 후보 (O-4 모양)


def best_decision(lines: list[str], matcher: NameMatcher) -> Any | None:
    """줄마다 이름 맞추기를 해서 가장 점수가 높은 결정. 한글이 두 글자 미만인 줄(숫자, 영문 로고)은 건너뜀"""
    best = None
    for line in lines:
        if len(_HANGUL.findall(line)) < 2:
            continue
        dec = matcher.decide(line, top_n=CANDIDATE_MAX, siblings=False)
        if dec.status in (FOUND, AMBIGUOUS) and (best is None or dec.score > best.score):
            best = dec
    return best


async def _items(dec: Any) -> list[dict[str, Any]]:
    near = [c for c in dec.candidates if dec.score - c.score <= CANDIDATE_GAP][:CANDIDATE_MAX]
    drugs = {d.edi_code: d for d in await DrugProduct.filter(edi_code__in=[c.edi_code for c in near])}
    return [
        {
            "itemSeq": d.item_seq,
            "ediCode": d.edi_code,
            "itemName": display_name(d.item_name),
            "entpName": d.entp_name,
            "etcOtc": d.etc_otc,
            "score": float(c.score),
        }
        for c in near
        if (d := drugs.get(c.edi_code)) is not None
    ]


async def identify(blob: Blob) -> PhotoResult:
    """사진 한 장(PDF는 첫 쪽)을 읽어 종류를 가름. CLOVA 호출이 실패하면 ClovaError를 그대로 올림"""
    data = await clova.recognize(blob.content, blob.fmt, blob.name)
    matcher, codes = await get_matcher(), await get_codes()
    images = data.get("images") or [{}]
    page = {**data, "images": [images[0]]}
    if (await asyncio.to_thread(read, page, matcher, codes)).status == "ok":
        return PhotoResult(PRESCRIPTION)
    fields = images[0].get("fields") or []
    lines = await asyncio.to_thread(_line_texts, fields) if fields else []
    dec = await asyncio.to_thread(best_decision, lines, matcher)
    items = await _items(dec) if dec else []
    return PhotoResult(DRUG, items) if items else PhotoResult(UNREADABLE)


def answer_fields(result: PhotoResult) -> dict[str, Any]:
    """답 줄에 넣을 칸. 약 후보가 하나여도 확인을 받으므로 늘 clarify"""
    if result.kind == PRESCRIPTION:
        return {"answer_type": "normal", "content": PRESCRIPTION_REPLY, "image_result": PRESCRIPTION}
    if result.kind == DRUG:
        one = len(result.items) == 1
        return {
            "answer_type": "clarify",
            "content": DRUG_ONE if one else DRUG_MANY,
            "chips": [i["itemName"] for i in result.items],
            "drug_match": {"status": "matched" if one else "candidates", "items": result.items},
            "image_result": DRUG,
        }
    return {"answer_type": "no_evidence", "content": UNREADABLE_REPLY, "image_result": UNREADABLE}
