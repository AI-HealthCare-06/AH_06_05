"""미리 만들어 둔 약 안내문(drug_guides) — 배치로 한꺼번에 만들고, 분석 때는 조회만 한다 (멘토링 4회차)

두 가지 안내문이 같은 표(drug_guides)에 들어간다.
- 규칙 표: 약효분류 표(medication.CLASS_*)로 종류 · 쓰임을 만든 것. 주의할 점은 null. model_name이 비어 있다
- 허가정보 문장(seed): 데모 약처럼 AI가 허가정보 문장을 근거로 쓰고 규칙으로 걸러 낸 것. model_name이 있다.
  data/demo_guides.json을 load_seed()로 넣는다. 규칙 표 재생성(generate_all)이 덮어쓰지 않는다
둘 다 같은 확인 상태(review_status)를 쓰고, 분석 때는 approved만 보여 준다.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.analysis import DrugGuide, ReviewStatus
from app.models.masters import DrugProduct
from app.services.guide import medication

PROMPT_VER = "rule-v1"  # 규칙(표)으로 만든 판. AI 문장으로 바꾸면 올림
BATCH_SIZE = 1000
SEED_PATH = Path(__file__).parent / "data" / "demo_guides.json"
PERMIT_SOURCE = "식약처 의약품 허가정보"


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
        g.edi_code: g
        async for g in DrugGuide.all().only("edi_code", "content", "evidence_ids", "review_status", "model_name")
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
        if only_missing or old.model_name:  # 허가정보 문장(seed)은 표로 다시 만들지 않음 — load_seed로만 바꾼다
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
    async for g in DrugGuide.filter(model_name__isnull=True).order_by("edi_code"):
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
    codes = [
        g.edi_code
        async for g in DrugGuide.filter(model_name__isnull=True).only("edi_code", "content")
        if group_key(g.content) == key
    ]
    for i in range(0, len(codes), BATCH_SIZE):
        await DrugGuide.filter(edi_code__in=codes[i : i + BATCH_SIZE]).update(
            review_status=status, reviewed_by=reviewer, reviewed_at=_now()
        )
    return len(codes)


def seed_entries(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["guides"]


def seed_content(entry: dict[str, Any], drug: DrugProduct) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """seed 1건 → (content, evidence_ids).
    caution은 API 명세서 R-4가 문자열 하나라서 문장을 줄바꿈으로 이어 붙이고, 문장별 목록은 cautions에 따로 둔다"""
    texts = [c["text"] for c in entry["cautions"]]
    permit = entry["permit"]
    date = permit["permitDate"]
    content = {
        "category": medication.CLASS_NAME.get((drug.class_code or "")[:3]),
        "purpose": entry["purpose"],
        "caution": "\n".join(texts) or None,
        "cautions": texts,
        "source": f"{PERMIT_SOURCE} (품목기준코드 {permit['itemSeq']}, 허가일 {date[:4]}-{date[4:6]}-{date[6:]})",
    }
    evidence = [
        {
            "kind": "drug_details",
            "key": permit["itemSeq"],
            "label": PERMIT_SOURCE,
            "field": e["id"],
            "use": "purpose",
            "text": e["text"],
        }
        for e in entry["purposeSources"]
    ]
    for i, c in enumerate(entry["cautions"], 1):
        evidence += [
            {
                "kind": "drug_details",
                "key": permit["itemSeq"],
                "label": PERMIT_SOURCE,
                "field": e["id"],
                "use": f"caution{i}",
                "text": e["text"],
            }
            for e in c["sources"]
        ]
    return content, evidence


async def load_seed(path: Path = SEED_PATH) -> dict[str, Any]:
    """허가정보 문장(seed)을 drug_guides에 넣는다. 새 약은 draft, 내용이 바뀐 약은 확인이 풀려 draft로 돌아간다.
    내용이 같으면 확인 상태를 그대로 둔다. 급여목록(drug_products)에 없는 약은 넣지 않고 missing에 담는다"""
    created = updated = reset = skipped = 0
    missing: list[str] = []
    for entry in seed_entries(path):
        code = entry["ediCode"]
        drug = await DrugProduct.get_or_none(edi_code=code)
        if drug is None:
            missing.append(code)
            continue
        content, evidence = seed_content(entry, drug)
        old = await DrugGuide.get_or_none(edi_code=code)
        if old is None:
            await DrugGuide.create(
                edi_code=code,
                content=content,
                evidence_ids=evidence,
                prompt_ver=entry["promptVer"],
                model_name=entry["model"],
            )
            created += 1
        elif old.content == content and old.evidence_ids == evidence and old.model_name == entry["model"]:
            skipped += 1
        else:
            reviewed = old.review_status != ReviewStatus.DRAFT
            await DrugGuide.filter(edi_code=code).update(
                content=content,
                evidence_ids=evidence,
                prompt_ver=entry["promptVer"],
                model_name=entry["model"],
                review_status=ReviewStatus.DRAFT,
                reviewed_by=None,
                reviewed_at=None,
                updated_at=_now(),
            )
            reset, updated = (reset + 1, updated) if reviewed else (reset, updated + 1)
    return {"created": created, "updated": updated, "reset": reset, "skipped": skipped, "missing": missing}


async def seed_guides() -> list[dict[str, Any]]:
    """사람이 약 하나씩 확인할 목록 (허가정보 문장) — 약 이름, 상태, 쓰임, 문장과 근거 번호"""
    rows = [g async for g in DrugGuide.filter(model_name__isnull=False).order_by("edi_code")]
    names = {d.edi_code: d.item_name for d in await DrugProduct.filter(edi_code__in=[g.edi_code for g in rows])}
    return [
        {
            "ediCode": g.edi_code,
            "name": names.get(g.edi_code, ""),
            "status": g.review_status.value,
            "reviewedBy": g.reviewed_by,
            "content": g.content,
            "evidence": g.evidence_ids or [],
        }
        for g in rows
    ]


async def review_drugs(edi_codes: list[str], status: ReviewStatus, reviewer: str) -> int:
    """허가정보 문장(seed) 약을 약마다 확인 처리 — 규칙 표 약(묶음)에는 쓰지 않는다. 처리한 약 수를 돌려줌"""
    return await DrugGuide.filter(edi_code__in=edi_codes, model_name__isnull=False).update(
        review_status=status, reviewed_by=reviewer, reviewed_at=_now()
    )


def _now() -> datetime:
    return datetime.now(UTC)
