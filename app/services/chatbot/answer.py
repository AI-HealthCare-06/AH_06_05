"""답 만들기와 정리 (#99 PR 2-1, 설계 메모 7-12 ⑦과 답변 글 규칙). 근거 안에서만 답하고, 글 규칙은 코드로 한 번 더 지킨다.

- 근거가 없으면(검색 결과 none) AI를 부르지 않고 고정 문구
- 검색 판정이 부분(partial)이면 AI가 normal이라고 해도 부분 답
- 의료진 상담(refer)은 끝에 상담 안내 고정 문구를 코드로 붙임 (늘 같은 문구가 붙게, 10/20 수인 결정).
  근거가 없으면 AI를 부르지 않고 상담 안내 문구만 (상담 대상이 "약사에게"로 바뀌지 않게, 10/20 수인 결정)
- 다시 만들기(말투, "정보가 없다", 약 빠뜨림, 사용자 상황)는 PR 2-2 (25초 안에 OpenAI를 한 번 더 부를 여유가 없음)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.chatbot.context import FixedInfo, dialogue, fixed_info_text
from app.services.chatbot.llm import ChatClient, Usage
from app.services.chatbot.prompts import ANSWER_SCHEMA, ANSWER_SYSTEM
from app.services.rag.pipeline import Evidence, SearchResult

# 화면 고정 문구 (설계 메모 6-1 문구표, Figma). 화면 문구라 그대로 씀
NO_EVIDENCE = (
    "등록된 자료에서 이 질문에 대한 근거를 찾지 못했어요. 확인되지 않은 정보는 안내하지 않아요. 약사에게 확인해 주세요."
)
REFER = {
    "pharmacist": "복용 방법이나 함께 먹는 약은 약사에게 확인해 주세요.",
    "next_visit": "다음 진료 때 처방한 의사에게 꼭 물어봐 주세요.",
    "soon": "며칠 안에 진료를 받아 보시길 권해요.",
}

_MISSED_DOSE = re.compile(r"(깜빡|잊어버|잊고|빠뜨|빼먹|거르|건너뛰|안\s*먹었|못\s*먹었)")
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")


@dataclass
class Draft:
    answer_type: str
    content: str
    sources: list[str] = field(default_factory=list)


def clean_text(text: str) -> str:
    """글 규칙 후처리: 마크다운 기호, 이모지, 줄표, 가운뎃점을 없앰 (로컬 실험과 같음)"""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*(#+|[-*])\s+", "", text, flags=re.M)
    text = _EMOJI.sub("", text)
    text = text.replace(" — ", ", ").replace("—", ", ").replace(" · ", ", ").replace("·", ", ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _no_evidence(cls: dict[str, Any]) -> Draft:
    tail = REFER.get(cls.get("refer_kind") or "") if cls.get("category") == "refer" else None
    return Draft("refer", tail) if tail else Draft("no_evidence", NO_EVIDENCE)


def _evidence_json(evidence: list[Evidence], info: FixedInfo) -> str:
    names = {d.code: d.name for d in info.drugs if d.code}
    rows = [
        {
            "번호": e.sentence_id,
            "무엇에 대한 글": names.get(e.drug_code or "", e.drug_code) or e.disease_code or "질환이 겹칠 때",
            "제목": e.heading,
            "글": e.text,
        }
        for e in evidence
    ]
    return json.dumps(rows, ensure_ascii=False)


async def write(
    question: str,
    cls: dict[str, Any],
    info: FixedInfo,
    past: list[dict[str, str]],
    first_turn: int,
    found: SearchResult | None,
    client: ChatClient,
    usage: Usage,
) -> Draft:
    """found가 None이면 근거 없이 답함 (범위 밖). LLMError는 부르는 쪽이 답변 오류(E6)로"""
    if found is not None and found.coverage == "none":
        return _no_evidence(cls)
    evidence = found.evidence if found else []
    message = (
        f"[고정 정보]\n{fixed_info_text(info)}\n\n[앞 대화] (오래된 것부터)\n{dialogue(past, first_turn) or '(없음)'}\n\n"
        f"[질문 분류]\n{json.dumps(cls, ensure_ascii=False)}\n\n[근거]\n{_evidence_json(evidence, info)}\n\n[질문]\n{question}"
    )
    gen = await client.complete_json(
        ANSWER_SYSTEM, [{"role": "user", "content": message}], ANSWER_SCHEMA, "answer", usage
    )
    if cls.get("category") == "out_of_scope" and isinstance(gen.get("content"), str) and gen["content"].strip():
        # 범위 밖은 짧게 응대하는 normal (설계 메모 7-12 ③). 근거가 없으니 AI가 no_evidence라고 해도 응대 글을 씀
        return Draft("normal", clean_text(gen["content"]))
    kind = gen.get("answer_type")
    if kind not in ANSWER_SCHEMA["properties"]["answer_type"]["enum"] or not isinstance(gen.get("content"), str):
        kind = "no_evidence"
    known = {e.sentence_id for e in evidence}
    sources = [s for s in gen.get("used_sources") or [] if s in known]
    # 약을 빠뜨린 질문: 근거에 그 안내가 없으면 AI가 무엇이라 하든 근거 없음 (로컬 실험 N5, B2)
    if _MISSED_DOSE.search(question) and not any(_MISSED_DOSE.search(e.text) for e in evidence):
        kind = "no_evidence"
    if kind == "no_evidence":
        return _no_evidence(cls)
    content = clean_text(gen["content"])
    if cls.get("category") == "refer":
        tail = REFER.get(cls.get("refer_kind") or "", "")
        if tail and tail not in content:
            content = f"{content} {tail}"
        return Draft("refer", content, sources)  # 서버가 판별한 갈래를 따름
    if kind == "refer":
        # 분류가 약이어도 AI가 상담이 필요하다고 보면 이름표를 붙임 (로컬 실험과 같음)
        return Draft("refer", content, sources)
    if kind == "partial" or (found is not None and found.coverage == "partial"):
        return Draft("partial", content, sources)
    return Draft("normal", content, sources)
