"""피처 4 실천 (API 명세서 6장 P-1 ~ P-4, REQ-110 ~ 112, 115). 포인트(P-6)와 달성 현황(P-5)은 뒤로 미룸"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.errors import AppError
from app.models.analysis import Analysis, AnalysisDisease, AnalysisPrescription, AnalysisStatus
from app.models.habits import GoalType, HabitGoal, HabitRecord, HabitStatus, Recommendation
from app.models.ocr import MatchStatus, PrescriptionItem
from app.models.users import User, UserHealthProfile
from app.services import challenges

USABLE = (MatchStatus.AUTO, MatchStatus.USER_CONFIRMED)  # analyses.USABLE과 같음 (확인이 끝난 약만)


def _today() -> date:
    return datetime.now(config.TIMEZONE).date()


def _num(v: Decimal | None) -> int | float | None:
    if v is None:
        return None
    return int(v) if v == v.to_integral_value() else float(v)


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    """값이 없는 칸은 응답에서 뺌 (명세서 예시처럼)"""
    return {k: v for k, v in d.items() if v is not None}


# ── P-1 생활습관 추천 ─────────────────────────────────────────────────────────────────────────
async def recommendations(user: User, analysis_id: int) -> dict[str, Any]:
    """분석의 질환과 약으로 다시 계산해 저장함 (질환 직접 선택 R-6 뒤에도 맞게). 같은 챌린지는 번호를 그대로 둠"""
    a = await Analysis.get_or_none(id=analysis_id, user=user)
    if a is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    if a.status != AnalysisStatus.DONE:
        raise AppError(status.HTTP_409_CONFLICT, "ANALYSIS_NOT_READY", "아직 분석 중이에요.")
    codes = [
        str(c) for c in await AnalysisDisease.filter(analysis=a).order_by("id").values_list("disease_id", flat=True)
    ]
    rx_ids = await AnalysisPrescription.filter(analysis=a).values_list("prescription_id", flat=True)
    items = await PrescriptionItem.filter(prescription_id__in=list(rx_ids), match_status__in=USABLE).prefetch_related(
        "drug"
    )
    names = [i.drug.item_name for i in items if i.drug]
    profile = await UserHealthProfile.get_or_none(user=user)
    picked = challenges.recommend(codes, names, profile.drinking.value if profile else None)

    async with in_transaction():
        await Recommendation.filter(analysis=a).exclude(challenge_key__in=[p["key"] for p in picked]).delete()
        rows = []
        for rank, p in enumerate(picked, start=1):
            fields = {k: p[k] for k in ("title", "desc", "reason_label", "caution_label", "goal_type", "unit")}
            row, _ = await Recommendation.update_or_create(
                analysis=a,
                challenge_key=p["key"],
                defaults={**fields, "target_value": p["target_value"], "fact_refs": p["fact_refs"], "rank": rank},
            )
            rows.append(row)
    return {"items": [_rec_view(r) for r in rows], "hasDiseases": bool(codes)}


def _rec_view(r: Recommendation) -> dict[str, Any]:
    return _drop_none(
        {
            "id": r.id,
            "title": r.title,
            "desc": r.desc,
            "reasonLabel": r.reason_label,
            "cautionLabel": r.caution_label,
            "goalType": r.goal_type.value,
            "targetValue": _num(r.target_value),
            "unit": r.unit,
        }
    )


# ── P-2 목표 만들기 ─────────────────────────────────────────────────────────────────────────
async def create_goals(user: User, recommendation_ids: list[int]) -> list[int]:
    """1 ~ 3개. 다시 고르면 같은 목표(제목과 종류가 같음)는 그대로 두어 오늘 기록이 남고, 뺀 것만 끝내고, 새로 고른 것만 만듦
    (#43 목표 교체, 10/30 수인). 허혈성심질환이 생겨 걷기 모양이 바뀌면 다른 목표로 봄. 주간 다시 고르기 REQ-116은 뒤로"""
    if len(set(recommendation_ids)) != len(recommendation_ids):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "VALIDATION_ERROR",
            "같은 추천을 두 번 고를 수 없어요.",
            field="recommendationIds",
        )
    recs = {r.id: r for r in await Recommendation.filter(id__in=recommendation_ids, analysis__user_id=user.id)}
    if len(recs) != len(recommendation_ids):
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    if len({(r.title, r.goal_type) for r in recs.values()}) != len(recs):  # 다른 분석의 같은 챌린지
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "VALIDATION_ERROR",
            "같은 목표를 두 번 고를 수 없어요.",
            field="recommendationIds",
        )
    today = _today()
    async with in_transaction():
        active = {(g.title, g.goal_type): g for g in await HabitGoal.filter(user=user, status=HabitStatus.ACTIVE)}
        goals = []
        for i in recommendation_ids:
            r = recs[i]
            if g := active.pop((r.title, r.goal_type), None):
                g.recommendation = r  # 새 분석의 추천 이유로 바꿈
                await g.save(update_fields=["recommendation_id"])
            else:
                g = await HabitGoal.create(
                    user=user,
                    recommendation=r,
                    title=r.title,
                    goal_type=r.goal_type,
                    target_value=r.target_value,
                    unit=r.unit,
                    start_date=today,
                )
            goals.append(g)
        if active:
            await HabitGoal.filter(id__in=[g.id for g in active.values()]).update(
                status=HabitStatus.ENDED, end_date=today
            )
    return [g.id for g in goals]


# ── P-3 오늘의 실천 ─────────────────────────────────────────────────────────────────────────
async def _streak(user: User, today: date) -> int:
    """어떤 목표든 하루 1개 이상 완료한 날이 이어진 수. 목표가 바뀌어도 이어지고, 오늘 아직 안 했으면 어제까지 셈 (REQ-114)"""
    days = set(
        await HabitRecord.filter(goal__user_id=user.id, completed=True, record_date__lte=today).values_list(
            "record_date", flat=True
        )
    )
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


async def today_view(user: User) -> dict[str, Any]:
    today = _today()
    goals = (
        await HabitGoal.filter(user=user, status=HabitStatus.ACTIVE).order_by("id").prefetch_related("recommendation")
    )
    records = {r.goal_id: r for r in await HabitRecord.filter(goal_id__in=[g.id for g in goals], record_date=today)}
    items = []
    for g in goals:
        r, rec = records.get(g.id), g.recommendation
        quantity = g.goal_type == GoalType.QUANTITY
        items.append(
            _drop_none(
                {
                    "goalId": g.id,
                    "title": g.title,
                    "reasonLabel": rec.reason_label if rec else None,
                    "cautionLabel": rec.caution_label if rec else None,
                    "goalType": g.goal_type.value,
                    "targetValue": _num(g.target_value) if quantity else None,
                    "currentValue": _num(r.value if r and r.value is not None else Decimal(0)) if quantity else None,
                    "unit": g.unit if quantity else None,
                    "done": bool(r and r.completed),
                }
            )
        )
    return {
        "hasGoals": bool(goals),
        "doneCount": sum(i["done"] for i in items),
        "totalCount": len(items),
        "streakDays": await _streak(user, today),
        "items": items,
    }


# ── P-4 실천 기록 ─────────────────────────────────────────────────────────────────────────
def _bad(message: str, field: str) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", message, field=field)


async def record(user: User, goal_id: int, day: date, completed: bool | None, value: int | None) -> dict[str, Any]:
    """체크형은 completed, 수량형은 그날 한 총량(목표 값에 닿으면 완료). 완료 취소는 허용 (10/2 회의 결정, #43):
    체크형은 completed=false, 수량형은 줄인 총량. 총량이라 저장 실패 뒤 같은 요청을 다시 보내도 두 번 더해지지 않음 (REQ-115).
    같은 날 다시 완료하면 무시하고 그대로 200 (REQ-112). 오늘 기록만 받음 (몰아서 체크 막기)"""
    goal = await HabitGoal.get_or_none(id=goal_id, user=user, status=HabitStatus.ACTIVE)
    if goal is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    today = _today()
    if day != today:
        raise _bad("오늘 기록만 남길 수 있어요.", "date")
    quantity = goal.goal_type == GoalType.QUANTITY
    if quantity and (value is None or completed is not None):
        raise _bad("걷기 같은 목표는 한 만큼의 값을 보내 주세요.", "value")
    if not quantity and (completed is None or value is not None):
        raise _bad("완료 여부를 보내 주세요.", "completed")

    async with in_transaction():
        row, _ = await HabitRecord.get_or_create(goal=goal, record_date=today)
        row = await HabitRecord.select_for_update().get(id=row.id)
        if quantity:
            row.value = Decimal(value or 0)
            row.completed = goal.target_value is not None and row.value >= goal.target_value
        else:
            row.completed = bool(completed)
        await row.save()

    active = await HabitGoal.filter(user=user, status=HabitStatus.ACTIVE).values_list("id", flat=True)
    done = await HabitRecord.filter(goal_id__in=list(active), record_date=today, completed=True).count()
    return _drop_none(
        {
            "goalId": goal.id,
            "done": row.completed,
            "currentValue": _num(row.value) if quantity else None,
            "allDone": done == len(active),
        }
    )


# ── 동의 철회, 탈퇴 (U-5, U-3) ─────────────────────────────────────────────────────────────
async def end_goals(user: User) -> None:
    """U-5: 목표는 끝내고 기록은 남김. 추천(질환 라벨)은 분석과 같이 지워져 목표의 연결이 비워짐"""
    await HabitGoal.filter(user=user, status=HabitStatus.ACTIVE).update(status=HabitStatus.ENDED, end_date=_today())


async def delete_goals(user: User) -> None:
    """U-3: 목표와 기록을 모두 지움 (기록은 DB가 같이 지움)"""
    await HabitGoal.filter(user=user).delete()
