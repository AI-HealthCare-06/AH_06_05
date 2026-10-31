// 실천 가짜 응답 (P-1 ~ P-4). 모양은 API 명세서 6장 그대로
// 추천에서 질환이 없으면(처방전 질환 없음, 질환 직접 고르기 전) hasDiseases:false → 앱은 질환 고르기로
// 기록 저장 실패(RW-03-E1) 확인: 걷기를 99분(1시간 39분)으로 저장하면 처음 한 번만 실패하고, [다시 시도]하면 성공 (로그인 mock의 "1234"와 같은 방식)
import type { GoalType, Recommendation, Today, TodayItem } from '@/features/challenge/types';

const ok = (body: unknown, status = 200) => ({ status, body });
const err = (status: number, code: string, message: string, field?: string) => ({
  status,
  body: { error: { code, message, ...(field ? { field } : {}) } },
});

// 화면 확인용 예시 문구. 1번은 대한고혈압학회 2026 진료지침 권고 21, 2번은 앱 팩트표 데이터의 고혈압 운동 문구(검증 v1.8은 권고 23의 주 150분으로 바꾸라고 했고 팩트표 담당과 확정 전), 3번은 당뇨병 진료지침 2025 제9판 식사요법 권고 11. 실제 문구는 서버가 질환별로 내려 줌
const RECS: Recommendation[] = [
  { id: 1, title: '국물 남기기', desc: '하루 소금 5g(나트륨 2,000mg) 이하', reasonLabel: '고혈압', goalType: 'check' },
  { id: 2, title: '빠르게 걷기 30분', desc: '주 5회 이상, 회당 30분 이상 (중강도)', reasonLabel: '고혈압, 당뇨병', goalType: 'quantity', targetValue: 30, unit: '분' },
  { id: 3, title: '술 마시지 않기', desc: '가급적 금주를 권고해요', reasonLabel: '약과 함께', goalType: 'check' },
];

type Goal = { goalId: number; rec: Recommendation; currentValue: number; done: boolean };
let goals: Goal[] = [];
let nextId = 11;
let failedOnce = false;

export function getRecommendationsMock(hasDiseases: boolean) {
  return ok({ items: hasDiseases ? RECS : [], hasDiseases });
}

export function createGoalsMock(body: Record<string, unknown>) {
  const ids = Array.isArray(body.recommendationIds) ? (body.recommendationIds as number[]) : [];
  if (ids.length < 1 || ids.length > 3 || new Set(ids).size !== ids.length) {
    return err(400, 'VALIDATION_ERROR', '입력한 내용을 다시 확인해 주세요.', 'recommendationIds');
  }
  const picked = ids.map((i) => RECS.find((r) => r.id === i));
  if (picked.some((r) => !r)) return err(404, 'NOT_FOUND', '찾을 수 없어요.');
  // 다시 고르면 같은 목표는 그대로 두고, 뺀 것만 끝냄
  const next = (picked as Recommendation[]).map(
    (rec) => goals.find((g) => g.rec.id === rec.id) ?? { goalId: nextId++, rec, currentValue: 0, done: false },
  );
  goals = next;
  return ok({ goalIds: next.map((g) => g.goalId) }, 201);
}

const toItem = (g: Goal): TodayItem => ({
  goalId: g.goalId,
  title: g.rec.title,
  desc: g.rec.desc,
  reasonLabel: g.rec.reasonLabel,
  goalType: g.rec.goalType as GoalType,
  ...(g.rec.goalType === 'quantity' ? { targetValue: g.rec.targetValue, currentValue: g.currentValue, unit: g.rec.unit } : {}),
  done: g.done,
});

export function todayMock() {
  const body: Today = {
    hasGoals: goals.length > 0,
    doneCount: goals.filter((g) => g.done).length,
    totalCount: goals.length,
    streakDays: goals.some((g) => g.done) ? 3 : 2,
    items: goals.map(toItem),
  };
  return ok(body);
}

export function recordMock(goalId: number, body: Record<string, unknown>) {
  const g = goals.find((x) => x.goalId === goalId);
  if (!g) return err(404, 'NOT_FOUND', '찾을 수 없어요.');
  if (body.value === 99 && !failedOnce) {
    failedOnce = true;
    return err(500, 'INTERNAL_ERROR', '잠시 문제가 생겼어요');
  }
  if (typeof body.value === 'number') {
    if (g.rec.goalType !== 'quantity' || body.value < 0 || body.value > 600) {
      return err(400, 'VALIDATION_ERROR', '입력한 내용을 다시 확인해 주세요.', 'value');
    }
    g.currentValue = body.value;
    g.done = body.value >= (g.rec.targetValue ?? Infinity);
  } else if (typeof body.completed === 'boolean') {
    g.done = body.completed;
  } else {
    return err(400, 'VALIDATION_ERROR', '입력한 내용을 다시 확인해 주세요.');
  }
  const allDone = goals.every((x) => x.done);
  return ok({ goalId, done: g.done, allDone, ...(g.rec.goalType === 'quantity' ? { currentValue: g.currentValue } : {}) });
}
