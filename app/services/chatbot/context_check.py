"""1층 문맥 파악 (10/14 회의): 1층 규칙에 걸렸지만 앞뒤 말로 정상이 분명하면 막지 않음.

- AI 없음. 1층 안에서 규칙 다음에 씀
- "막지 않음"까지만 하고 안전으로 확정하지 않음. 풀린 질문도 2층 가드레일은 늘 거침
- 놓치지 않는 쪽 우선: 본인 바람("싶다")이나 죽음을 뜻하는 말이 있거나, 다른 응급 증상 규칙이 함께 걸리면 풀지 않음
"""

from __future__ import annotations

import re

from app.services.chatbot import safety_rules

# 본인 바람("싶다")이나 죽음, 위험한 양을 뜻하는 말. 있으면 어떤 이유로도 풀지 않음
_NEVER = re.compile(
    r"(싶|십지|십어|시퍼|죽어|죽나|죽을|죽는|치사|영원히|안깨|위험|큰일|치명|한통|한병|통째|몇알|몇통|어떻게되|어떻게돼)"
)

# 지금 증상을 뜻하는 말. 있으면 "걱정" 이유로 풀지 않음
_SYMPTOM = re.compile(r"(어지|아파|아프|숨|가슴|떨리|떨려|식은땀|지금|정신|힘이없|휘청)")

# 지금 일이라는 표현. 있으면 "예전에" 이유로 풀지 않음
_NOW = re.compile(
    r"(지금또|지금도|다시|또(조|아|답|막|차)|아까|갑자기|오늘|방금|계속(아파|아프|조여|답답|차|어지|저려))"
)  # "약은 계속 먹어야"는 지금 증상이 아님

# 일이나 치료를 끝내고 싶다는 말은 "싶"이 있어도 위험이 아님. 이 부분을 지운 뒤 _NEVER를 봄
_TASK_FINISH = re.compile(
    r"(치료|공부|일|숙제|복용|약먹는거|운동|청소|이사|검사|입원)(을|를|도|이|가)?\S{0,4}(끝내고싶|끝났으면좋겠|끝나면좋겠|빨리끝나)"
)

# (이름, 풀어도 되는 1층 규칙, 정상이 분명한 문장 모양). 정규식은 공백과 문장부호를 없앤 문장에 씀
CONTEXT_RULES: list[tuple[str, set[str], str]] = [
    # 상담전화, 번호를 묻는 정보 질문
    ("contact_info", {"self_harm"}, r"(상담전화|전화번호|번호|연락처)(가|를|좀)?(뭐|알려|어디|몇번)"),
    # 드라마, 뉴스 등에서 본 장면을 전함
    ("media_scene", {"self_harm", "consciousness"}, r"(드라마|영화|뉴스|기사|책|장면)\S*(봤|보고|보니|읽)"),
    # 먹었는지 헷갈림 (증상 없음)
    ("uncertain_taken", {"overdose"}, r"(먹었는지|드셨는지|먹은건지)(헷갈|모르겠|기억)"),
    # 피해야 할 약, 음식을 묻는 질문
    ("caution_question", {"dose_question"}, r"(먹으면|먹어도)안되는(약|음식|것|거)"),
    # 두 가지를 같이 먹어도 되는지 묻는 질문
    ("pair_question", {"dose_question"}, r"(이랑|랑|하고)\S*(한번에|같이|한꺼번에)먹으면"),
    # 바쁨, 놀람을 과장한 말
    ("idiom_busy", {"consciousness"}, r"(기절할|까무러칠)(만큼|정도로)(바빴|바쁘|놀랐|웃)"),
    # 운동 강도를 말함
    ("exercise_pace", {"breath"}, r"숨(이)?차게(걷|운동|뛰)"),
    # 쓰러질까 봐 미리 조심함 (지금 증상이 없을 때만, 아래 _SYMPTOM 참고)
    ("worry_future", {"consciousness"}, r"쓰러질(까|지도)\S{0,4}(봐|걱정|몰라)"),
    # 아침마다, 늘 그런 붓기 (숨, 목, 혀, 입술 증상이 없을 때만)
    (
        "habitual_swelling",
        {"allergy"},
        r"^(?!.*(숨|목|혀|입술|목구멍)).*(아침마다|매일|늘|자주|원래|평소|항상)\S{0,6}(얼굴|눈두덩|눈꺼풀)(이|가)?\S{0,4}(부|붓)",
    ),
    # 얼굴이 약간 붓는 느낌 (숨, 목, 혀 증상이 없을 때만. 알레르기 규칙에 다른 부위가 함께 걸리면 풀지 않음)
    (
        "mild_swelling",
        {"allergy"},
        r"^(?!.*(숨|목|혀|입술|목구멍)).*(얼굴|눈두덩|눈꺼풀)(이|가)?(약간|조금|좀|살짝)\S{0,4}(붓|부은|부어)\S{0,4}(기분|느낌|것같|거같)",
    ),
    # 지난 일, 지금은 나은 증상
    (
        "past_resolved",
        {"chest", "breath", "stroke", "consciousness"},
        r"(예전에|전에|옛날에|작년|지난달|지난번|지난주|몇년전)\S{0,10}(아파서|아팠|있었|차서|찼|저렸|쓰러졌|쓰러져|입원|앓았)|쓰러졌던|(과거에|한번)\S{0,6}(쓰러져|쓰러졌|앓았)|(지금은|금방|이제는|요즘은|요새는)(괜찮|나았|안아|건강|멀쩡)|예전일|(했었|었었)는데\S{0,6}지금은",
    ),
    # 일이나 치료를 끝내고 싶음
    ("task_finish", {"self_harm"}, _TASK_FINISH.pattern),
    # 처방받은 약을 다 먹으면 되는지, 많이 먹으면 안 되는지 묻는 질문
    (
        "course_question",
        {"dose_question"},
        r"(이약|약|한팩|한봉지)(을)?다먹으면(되는거|되나|되죠|돼|끝이|끝인)|다먹으면\S{0,4}(사야|타야|받아야|처방|병원)|먹으면안(되나|되죠|되지|돼요|되요)|먹어도(괜찮|되나|돼|되는)",
    ),
    # 약을 다 먹은 뒤나 많이 먹을 때의 영향을 묻는 정보 질문
    (
        "followup_question",
        {"dose_question"},
        r"(먹으면|먹어도)\S{0,8}(병원|간이|간에|신장|콩팥|위가|살찌|하루치|처방|다시|부작용|나빠지|가야|약국)",
    ),
    # 약 때문에 변 색이 바뀌는지 묻는 질문
    (
        "side_effect_question",
        {"bleeding"},
        r"(철분|비스무트|변비약|약|영양제)\S{0,8}(먹으면|먹고|때문)\S{0,8}(변|대변)",
    ),
    # 남은 약을 모아 버리거나 정리함
    ("disposal", {"dose_question"}, r"(유통기한|버리|폐의약품|정리|수거|반납|버려)"),
]


def looks_normal(text: str, rule: safety_rules.SafetyResult) -> str | None:
    """1층에 걸린 문장이 앞뒤 말로 정상이 분명하면 그 이유 이름을, 아니면 None을 돌려줌."""
    if not rule.hit:
        return None
    s = safety_rules.normalize(text)
    if _NEVER.search(_TASK_FINISH.sub("", s)):
        return None
    hit_rules = set(rule.rules)
    now = bool(_NOW.search(s))
    for name, allowed, pattern in CONTEXT_RULES:
        if name == "worry_future" and _SYMPTOM.search(s):
            continue  # "어지러워서 쓰러질까 봐"는 지금 증상
        if name == "past_resolved" and now:
            continue  # "예전에도 아팠는데 지금 또"는 지금 일
        # 걸린 규칙이 모두 이 이유로 풀 수 있는 것일 때만 풂 (다른 응급 증상이 함께 걸리면 풀지 않음)
        if hit_rules <= allowed and re.search(pattern, s):
            return name
    return None
