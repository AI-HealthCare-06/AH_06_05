"""답 만들기와 정리 (#99 PR 2-1, 설계 메모 7-12 ⑦과 답변 글 규칙). 근거 안에서만 답하고, 글 규칙은 코드로 한 번 더 지킨다.

- 근거가 없으면(검색 결과 none) AI를 부르지 않고 고정 문구
- 검색 판정이 부분(partial)이면 AI가 normal이라고 해도 부분 답
- 의료진 상담(refer)은 끝에 상담 안내 고정 문구를 코드로 붙임 (늘 같은 문구가 붙게, 10/20 수인 결정).
  근거가 없으면 AI를 부르지 않고 상담 안내 문구만 (상담 대상이 "약사에게"로 바뀌지 않게, 10/20 수인 결정)
- 다시 만들기(말투, "정보가 없다", 약 빠뜨림, 사용자 상황)는 PR 2-2 (25초 안에 OpenAI를 한 번 더 부를 여유가 없음)
- 출력 가드레일: 정리한 마지막 글에서 근거와 고정 정보에 없는 숫자, 허가정보에 없는 빠뜨린 약 안내, 양이나 복용을 바꾸라는 말과
  먹지 말라는 말, 먹는 때를 거르고, 걸리면 근거 없음 고정 문구로 바꿈 (10/25 수인 결정: 정리 뒤, 고정 문구). AI를 다시 부르지 않음
"""

import json
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.services.chatbot.context import FixedInfo, dialogue, fixed_info_text
from app.services.chatbot.llm import ChatClient, Usage
from app.services.chatbot.prompts import ANSWER_SCHEMA, ANSWER_SYSTEM
from app.services.chatbot.safety_rules import normalize
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

# 약을 빠뜨린 말 (질문과 허가정보에 같이 씀). "잊", "까먹"은 약을 먹는 말 뒤, "놓쳤"은 먹는 시간 뒤만
# ("약을 잊지 않으려면", "잊을까 봐", "버스를 놓쳤어요"는 아님, 10/25, 10/26 점검). 먹었는지 모르는 질문도 두 번 먹을 수 있어 같이 봄 (10/25 수인 결정)
_TAKING = r"(?:약을?|복용을?|복용하는\s*(?:걸|거|것을?)|먹는\s*(?:걸|거|것을?)|먹기를?)"
_MISSED_DOSE = re.compile(
    r"(깜빡|빠뜨|빼먹|건너뛰|안\s*먹었|못\s*먹었|못\s*챙겼|(?:안|못)\s*챙겨\s*먹|(?:먹는|복용)\s*시간을?\s*놓쳤"
    rf"|먹었는지\s*(?:기억|모르)|{_TAKING}\s*(?:잊(?!지\s*(?:않|말)|을까|어버릴까)|까먹))"
)
# 답이 빠뜨린 상황을 다시 말하는 말. 되물음 다음 차례("노바스크요")처럼 질문에 빠뜨린 말이 없어도 답에서 거르게 (10/25 실제 답).
# 이미 빠뜨린 일을 말하는 꼴만 봄 ("깜빡하지 않도록", "안 챙겨 드시면 … 오를 수 있으니"는 아님). 끼니 이야기와 섞이지 않게
# "거른"은 넣지 않고 "놓친"은 약, 복용, 시간 뒤만 ("식사를 놓친 경우"는 아님, 10/25 점검)
_MISSED_TALK = re.compile(
    r"(잊은|잊었|잊으셨|잊어버렸|잊어버리셨|깜빡하셨|깜빡했|깜빡한|깜빡\s*잊|빠뜨린|빠뜨렸|빠뜨리셨|빼먹은|빼먹었|빼먹으셨"
    r"|(?:약을?|복용을?|시간을?)\s*(?:놓친|놓치셨|놓쳤)|(?:안|못)\s*챙겨\s*(?:먹었|먹은|드셨|드신(?!다))|못\s*챙기셨|못\s*챙겼|안\s*드셨|못\s*드셨"
    r"|생각났을\s*때|생각나시면|생각나면|생각날\s*때|생각난\s*즉시)"
)
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")

logger = logging.getLogger(__name__)


def _fold_ss(text: str) -> str:
    """받침 ㅆ을 ㅅ으로 ("챙겻", "놓쳣"처럼 받침을 잘못 쓴 글도 같게). 규칙과 질문에 똑같이 씀"""
    return "".join(
        chr(ord(c) - 1) if 0 <= ord(c) - 0xAC00 < 11172 and (ord(c) - 0xAC00) % 28 == 20 else c for c in text
    )


# 빠뜨린 질문은 1층과 같게 띄어쓰기, 문장부호, 흔한 오타를 맞춘 뒤 받침을 접어서 봄 (고령 사용자 입력, 10/25 점검)
# 질문에만 보는 말 (10/26 수인 결정)
# - "거르", "걸렀", "거른": 허가정보 "식사를 거르면"을 빠뜨린 약 안내로 보지 않게
# - 약이 없는 "잊어버렸", "잊고", "잊었" ("아침 거 잊어버렸어요", main 규칙이 잡던 것). 질문은 띄어쓰기를 지운 뒤라
#   "이름을", "법을", "번호를" 바로 뒤는 뺌 ("약 이름을 잊었어요"). "잊어버릴까 봐"는 아님
_FORGOT = r"(?<!이름을)(?<!이름)(?<!법을)(?<!법)(?<!번호를)(?<!번호)잊(?:어버렸|어버리고|어먹었|어먹고|고|었)"
_MISSED_QUESTION = re.compile(_fold_ss(_MISSED_DOSE.pattern + "|거르|걸렀|거른|" + _FORGOT))


def _missed_question(question: str) -> bool:
    return bool(_MISSED_QUESTION.search(_fold_ss(normalize(question))))


# 출력 가드레일 규칙. 숫자는 아라비아 숫자와 "두 알", "세 번" 같은 세는 말을 같이 봄
_DIGITS = re.compile(r"\d+(?:\.\d+)?")
_COUNT_WORDS = {"한": "1", "두": "2", "세": "3", "네": "4", "다섯": "5", "여섯": "6", "일곱": "7", "여덟": "8"}
_WORD = "(한|두|세|네|다섯|여섯|일곱|여덟)"
# 세는 말은 먹는 양("두 알")과 "하루 세 번"만 숫자로 봄 ("한 번 더 물어봐 주세요"를 거르지 않게, 10/25 점검)
_COUNT = re.compile(rf"(?:하루|1일|매일)\s*{_WORD}\s*(?:번|회)|{_WORD}\s*(?:알|정|캡슐|포|배)")
_LIST_NO = re.compile(r"(?:^|(?<=\s))\d{1,2}[.)](?=\s)")  # "1. ", "2) " 같은 목록 번호는 숫자로 보지 않음
# 양이나 복용을 바꾸라는 말. "끊지 마세요"처럼 하지 말라는 말은 글자가 이어지지 않아 걸리지 않음.
# 바로 앞 몇 글자에 약이 있을 때만 봄 ("술을 줄이세요", "담배를 끊으세요"는 거르지 않게, 10/25 점검)
_CHANGE = re.compile(
    r"(끊|중단하|멈추|멈춰|그만\s*드|늘리|늘려|줄이|줄여|올리|올려|낮추|낮춰|바꾸|바꿔|건너뛰|거르|몰아서|한꺼번에)"
    r"[가-힣]{0,2}(?:세요|셔도|해도|도\s*(?:돼|괜찮))"
)
# 약을 먹지 말라는 말 ("중단하지 마세요"는 아님). 함께 먹지 말라는 경고도 AI가 만들지 않으므로 거름 (NFR-032, 10/26 수인 결정)
_STOP = re.compile(r"(복용하지|드시지|먹지|복용을\s*하지)\s*(?:마|말)")
# 약을 멈춰도 된다는 말 ("안 드셔도 돼요", "드시지 않아도", "그만 드셔야"). 같은 문장 앞쪽에 약이 있으면 거름.
# 해로운 쪽이라 8글자 창보다 넓게 봄 ("노바스크는 이제 안 먹어도 돼요") (#126 채연 리뷰, 10/26 수인 결정)
_STOP_OK = re.compile(
    r"(?:안|못)\s*(?:드셔도|드시셔도|먹어도|복용하셔도|복용해도)|(?:드시지|먹지|복용하지)\s*않(?:아도|으셔도|는\s*게\s*좋)"
    r"|그만\s*(?:드셔야|드셔도|먹어야|먹어도|드시는\s*게)"
)
# 약을 쉬라는 말은 "약을 (며칠) 쉬어도", "노바스크를 하루 쉬셔도"처럼 약 바로 뒤만 ("약 드시고 쉬세요"는 아님). 사이의 기간 말 목록은 제안
_REST_TAIL = r"[을를은는]?\s*(?:하루|이틀|사흘|며칠|잠시|잠깐|당분간|한동안|일주일)?\s*쉬(?:어도|셔도|세요|시면)"

# 먹는 때는 시키는 말에만 ("먹으면 졸릴 수 있어요" 같은 설명은 보지 않음, 10/25 점검)
_TAKE = re.compile(r"(드세요|드시면\s*(?:돼|됩|좋)|드셔도|드시는\s*게\s*좋|복용하세요|복용하시면|먹으세요|드십시오)")
_TIMING = re.compile(r"(아침|점심|저녁|자기\s*전|취침|식전|식후|식사\s*중|공복)")
# "약속", "약국", "약간"의 "약"은 약으로 보지 않음. 붙여 쓴 "약하나", "아예약을"은 약으로 보게 좁게 뺌.
# "예약"도 약으로 봄 (틀려도 근거 없음이라 안전한 쪽, 10/26 수인 결정)
_MED_WORDS = re.compile(r"((?<![계절요공규언])약(?![속국간])|복용|용량|캡슐)")
_MED_OBJECT = re.compile(r"(약|복용|용량|양|알|캡슐)")
_OBJECT_WINDOW = 8
_SAFETY_NUMBERS = {"119", "109"}  # 응급, 자살예방 상담 번호는 근거가 없어도 안내함 (설계 메모 4-6, 6-1)


@dataclass
class Draft:
    answer_type: str
    content: str
    sources: list[str] = field(default_factory=list)
    blocked: str | None = None  # 출력 가드레일에 걸린 종류 (number, missed, change, timing)


def clean_text(text: str) -> str:
    """글 규칙 후처리: 마크다운 기호, 이모지, 줄표, 가운뎃점을 없앰 (로컬 실험과 같음)"""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*(#+|[-*])\s+", "", text, flags=re.M)
    text = _EMOJI.sub("", text)
    text = text.replace(" — ", ", ").replace("—", ", ").replace(" · ", ", ").replace("·", ", ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _numbers(text: str) -> set[str]:
    text = _LIST_NO.sub(" ", text)
    return set(_DIGITS.findall(text)) | {_COUNT_WORDS[a or b] for a, b in _COUNT.findall(text)}


def _about_drug(before: str, drug_names: list[str]) -> bool:
    return bool(_MED_OBJECT.search(before)) or any(n in before for n in drug_names)


def _rest(sentence: str, drug_names: list[str]) -> list[str]:
    objects = "|".join(["약", "복용", *(re.escape(n) + "[가-힣]{0,6}?" for n in drug_names)])
    return [m.group(0) for m in re.finditer(rf"(?:{objects}){_REST_TAIL}", sentence)]


def _changes_drug(sentence: str, drug_names: list[str], flat: str) -> bool:
    """근거에 없는 바꾸라는 말, 먹지 말라는 말(바로 앞 몇 글자에 약), 멈춰도 된다는 말(같은 문장 앞쪽에 약), 약을 쉬라는 말"""
    found = [(m, m.group(1)) for m in _CHANGE.finditer(sentence)] + [(m, m.group(0)) for m in _STOP.finditer(sentence)]
    for m, word in found:
        before = sentence[max(0, m.start() - _OBJECT_WINDOW) : m.start()]
        if _about_drug(before, drug_names) and re.sub(r"\s+", "", word) not in flat:
            return True
    for m in _STOP_OK.finditer(sentence):
        if _about_drug(sentence[: m.start()], drug_names) and re.sub(r"\s+", "", m.group(0)) not in flat:
            return True
    return any(re.sub(r"\s+", "", w) not in flat for w in _rest(sentence, drug_names))  # 약이 말 안에 있음


def output_guard(content: str, evidence: list[Evidence], info: FixedInfo) -> str | None:
    """근거 글과 고정 정보에 없는 숫자(number), 허가정보에 없는 빠뜨린 약 안내(missed), 양이나 복용을 바꾸라는 말(change),
    먹는 때(timing)가 있으면 그 종류.
    복용 지시는 약 이야기를 하는 문장에서만 봄 (생활습관 "나트륨을 줄이세요"는 거르지 않게). 먹는 때는 바로 앞 문장이 약 이야기여도 봄"""
    allowed = " ".join([fixed_info_text(info), *(f"{e.heading} {e.text}" for e in evidence)])
    flat = re.sub(r"\s+", "", allowed)
    if _numbers(content) - _numbers(allowed) - _SAFETY_NUMBERS:
        return "number"
    # 빠뜨린 약 안내: 답이 그 상황을 말하며 먹으라고 하는데 허가정보에 그 안내가 없으면 (10/25 점검)
    permit = [e.text for e in evidence if e.source == "drug_permit"]
    if _MISSED_TALK.search(content) and _TAKE.search(content):
        if not any(_MISSED_TALK.search(p) or _MISSED_DOSE.search(p) for p in permit):
            return "missed"
    drug_names = [d.name[:3] for d in info.drugs if d.name]
    prev_med = False
    for sentence in re.split(r"(?<=[.!?])\s+|\n", content):
        is_med = bool(_MED_WORDS.search(sentence)) or any(n in sentence for n in drug_names)
        # 먹는 때는 바로 앞 문장이 약 이야기여도 봄 ("노바스크는 혈압약이에요. 자기 전에 드셔도 돼요", 10/25 점검)
        about_med, prev_med = is_med or prev_med, is_med
        if not about_med:
            continue
        if _changes_drug(sentence, drug_names, flat):
            return "change"
        if _TAKE.search(sentence) and any(re.sub(r"\s+", "", t) not in flat for t in _TIMING.findall(sentence)):
            return "timing"
    return None


def _no_evidence(cls: dict[str, Any]) -> Draft:
    tail = REFER.get(cls.get("refer_kind") or "") if cls.get("category") == "refer" else None
    return Draft("refer", tail) if tail else Draft("no_evidence", NO_EVIDENCE)


# 허가 원문의 "이 약"은 그 약 이름으로 바꿔 넘김. 다른 약 근거 속 "이 약"을 AI가 엉뚱한 약으로 옮김 (10/26 채연 Q1).
# 앞 글자가 한글이면 낱말 끝("것이 약효")이라, 뒤가 국, 사, 제("이 약국")면 다른 낱말이라 그대로. 저장된 원문과 출처는 바꾸지 않음
_THIS_DRUG = re.compile(r"(?<![가-힣])이\s?약(?:물)?(?![국사제])")


def _evidence_json(evidence: list[Evidence], info: FixedInfo) -> str:
    names = {d.code: d.name for d in info.drugs if d.code}
    rows = [
        {
            "번호": e.sentence_id,
            "무엇에 대한 글": names.get(e.drug_code or "", e.drug_code) or e.disease_code or "질환이 겹칠 때",
            "제목": e.heading,
            "글": _THIS_DRUG.sub(names[e.drug_code], e.text)
            if e.source == "drug_permit" and e.drug_code in names
            else e.text,
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
    """답을 만들고 정리한 마지막 글에 출력 가드레일을 거침. 걸리면 근거 없음 고정 문구 (상담 갈래는 상담 안내 문구)"""
    draft = await _write(question, cls, info, past, first_turn, found, client, usage)
    if draft.content in (NO_EVIDENCE, *REFER.values()):
        return draft
    blocked = output_guard(draft.content, found.evidence if found else [], info)
    if blocked:
        logger.warning("출력 가드레일에 걸려 근거 없음으로 바꿈 (%s)", blocked)  # 답 글은 건강 정보가 섞여 남기지 않음
        return replace(_no_evidence(cls), blocked=blocked)
    return draft


async def _write(
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
    # 약을 빠뜨린 질문: 근거에 그 안내가 없으면 AI가 무엇이라 하든 근거 없음 (로컬 실험 N5, B2)
    # 허가정보 문장만 봄: 팩트표 "끼니 거르지 않기"를 빠뜨린 약 안내로 보던 것 (10/25 실제 답 확인)
    # 약 이야기일 때만 (질문에 약이나 약 이름, 또는 분류가 약, 상담): "끼니를 거르면"은 팩트표로 답함 (10/25 점검)
    # 범위 밖 응대보다 먼저 봄: 분류가 범위 밖으로 나와도 빠뜨린 약 답이 그대로 나가지 않게 (10/25 점검)
    permit = [e for e in evidence if e.source == "drug_permit"]
    names = [d.name[:3] for d in info.drugs if d.name]
    about_drug = cls.get("category") in ("medication", "refer") or bool(_MED_WORDS.search(question))
    about_drug = about_drug or any(n in question for n in names)
    missed = _missed_question(question) and about_drug and not any(_MISSED_DOSE.search(e.text) for e in permit)
    if cls.get("category") == "out_of_scope" and isinstance(gen.get("content"), str) and gen["content"].strip():
        # 범위 밖은 짧게 응대하는 normal (설계 메모 7-12 ③). 근거가 없으니 AI가 no_evidence라고 해도 응대 글을 씀
        return _no_evidence(cls) if missed else Draft("normal", clean_text(gen["content"]))
    kind = gen.get("answer_type")
    if kind not in ANSWER_SCHEMA["properties"]["answer_type"]["enum"] or not isinstance(gen.get("content"), str):
        kind = "no_evidence"
    known = {e.sentence_id for e in evidence}
    sources = [s for s in gen.get("used_sources") or [] if s in known]
    if missed:
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
