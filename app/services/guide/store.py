"""미리 만들어 둔 약 안내문(drug_guides) — 배치로 한꺼번에 만들고, 분석 때는 조회만 한다 (멘토링 4회차)

AI를 쓰지 않는다: 약효분류 표(medication.CLASS_*)로 종류 · 쓰임을 만들고, 주의할 점은 허가정보를 넣기 전까지 null.
나중에 AI로 문장을 만들더라도 같은 표 · 같은 확인 상태(review_status)를 쓴다.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.models.analysis import DrugGuide, ReviewStatus
from app.models.masters import DrugProduct
from app.services.guide import medication

PROMPT_VER = "rule-v1"  # 규칙(표)으로 만든 판. AI 문장으로 바꾸면 올림
BATCH_SIZE = 1000


def content_of(drug: DrugProduct) -> dict[str, Any]:
    return medication.static_part(drug)


async def lookup(edi_codes: list[str]) -> dict[str, dict[str, Any]]:
    """분석 때 쓸 안내문 — 사람이 확인한(approved) 것만 돌려준다 (멘토링 4회차: 사람 확인 필수).
    저장이 없거나 draft · rejected인 약은 결과에 없고, 그런 약은 '약사에게 확인' 문구가 나간다"""
    if not edi_codes:
        return {}
    rows = await DrugGuide.filter(edi_code__in=edi_codes, review_status=ReviewStatus.APPROVED)
    return {r.edi_code: r.content for r in rows}


async def generate_all(*, only_missing: bool = True) -> dict[str, int]:
    """급여목록 전 품목의 안내문을 만들어 저장.
    - 없는 약은 draft로 새로 만든다
    - only_missing=False면 기존 것도 표 기준으로 다시 만든다. 내용이 바뀐 약은 사람이 확인한 것(approved · rejected)이라도
      draft로 되돌려 다시 확인받는다 (옛 내용이 확인된 채로 남지 않게). 내용이 같으면 확인 상태를 그대로 둔다
    돌려주는 값: created(새로 만듦) · updated(draft 내용 갱신) · reset(확인이 풀림) · skipped(그대로)"""
    existing = {
        g.edi_code: g async for g in DrugGuide.all().only("edi_code", "content", "evidence_ids", "review_status")
    }
    created = updated = reset = skipped = 0
    batch: list[DrugGuide] = []
    async for d in DrugProduct.all().order_by("edi_code"):
        code, content, evidence = d.edi_code, content_of(d), medication.evidence_of(d)
        old = existing.get(code)
        if old is None:
            batch.append(
                DrugGuide(edi_code=code, content=content, evidence_ids=evidence, prompt_ver=PROMPT_VER, model_name=None)
            )
            if len(batch) >= BATCH_SIZE:
                await DrugGuide.bulk_create(batch)
                created += len(batch)
                batch = []
            continue
        if only_missing:
            skipped += 1
            continue
        if group_key(old.content) == group_key(content):
            if (old.evidence_ids or []) == evidence:
                skipped += 1
            else:  # 보이는 내용은 같고 근거 목록만 바뀜 → 확인 상태는 그대로 두고 근거만 갱신
                await DrugGuide.filter(edi_code=code).update(evidence_ids=evidence, updated_at=_now())
                updated += 1
            continue
        reviewed = old.review_status != ReviewStatus.DRAFT
        await DrugGuide.filter(edi_code=code).update(
            content=content,
            evidence_ids=evidence,
            prompt_ver=PROMPT_VER,
            review_status=ReviewStatus.DRAFT,
            reviewed_by=None,
            reviewed_at=None,
            updated_at=_now(),
        )
        reset, updated = (reset + 1, updated) if reviewed else (reset, updated + 1)
    if batch:
        await DrugGuide.bulk_create(batch)
        created += len(batch)
    return {"created": created, "updated": updated, "reset": reset, "skipped": skipped}


async def review(edi_code: str, status: ReviewStatus, reviewer: str) -> bool:
    """약 1개의 확인 결과를 남김"""
    n = await DrugGuide.filter(edi_code=edi_code).update(review_status=status, reviewed_by=reviewer, reviewed_at=_now())
    return n > 0


def group_key(content: Any) -> str:
    """같은 내용끼리 묶는 번호 — 규칙 표로 만든 안내문은 약효분류마다 같아서 22,045개를 몇 묶음으로 확인할 수 있음"""
    raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:8]  # noqa: S324 - 보안용이 아니라 묶음 이름


EXAMPLES = 5


async def groups() -> list[dict[str, Any]]:
    """확인할 묶음 목록: 내용, 약 수, 상태별 수, 예시 약 이름 (많은 순).
    예시는 앞쪽만 뽑으면 한쪽에 치우쳐 잘못 묶인 약을 놓치므로 묶음 전체에서 고르게 뽑는다"""
    names = {d.edi_code: d.item_name async for d in DrugProduct.all().only("edi_code", "item_name")}
    out: dict[str, dict[str, Any]] = {}
    members: dict[str, list[str]] = {}
    async for g in DrugGuide.all().order_by("edi_code"):
        key = group_key(g.content)
        grp = out.setdefault(key, {"key": key, "content": g.content, "count": 0, "status": {}, "examples": []})
        grp["count"] += 1
        grp["status"][g.review_status.value] = grp["status"].get(g.review_status.value, 0) + 1
        if g.edi_code in names:
            members.setdefault(key, []).append(names[g.edi_code])
    for key, grp in out.items():
        m = members.get(key, [])
        step = max(len(m) // EXAMPLES, 1)
        grp["examples"] = m[::step][:EXAMPLES]
    return sorted(out.values(), key=lambda x: -x["count"])


async def review_group(key: str, status: ReviewStatus, reviewer: str) -> int:
    """묶음 전체를 한 번에 확인 처리. 처리한 약 수를 돌려줌 (없는 묶음이면 0)"""
    codes = [g.edi_code async for g in DrugGuide.all().only("edi_code", "content") if group_key(g.content) == key]
    for i in range(0, len(codes), BATCH_SIZE):
        await DrugGuide.filter(edi_code__in=codes[i : i + BATCH_SIZE]).update(
            review_status=status, reviewed_by=reviewer, reviewed_at=_now()
        )
    return len(codes)


def _now() -> datetime:
    return datetime.now(UTC)
