// 실천 API 응답 모양 (API 명세서 6장 P-1 ~ P-4)
export type GoalType = 'check' | 'quantity';

// P-1 추천 한 건
export type Recommendation = {
  id: number;
  title: string;
  desc: string;
  reasonLabel: string;
  goalType: GoalType;
  targetValue?: number;
  unit?: string;
  cautionLabel?: string;
};
export type RecommendationList = { items: Recommendation[]; hasDiseases: boolean };

// P-3 오늘의 실천 한 건 (분석을 지웠으면 reasonLabel, cautionLabel이 빠짐)
export type TodayItem = {
  goalId: number;
  title: string;
  desc?: string; // 서버가 내려 주면 카드에 한 줄로 보여 줌 (명세 P-3에는 아직 없음)
  reasonLabel?: string;
  cautionLabel?: string;
  goalType: GoalType;
  targetValue?: number;
  currentValue?: number;
  unit?: string;
  done: boolean;
};
export type Today = { hasGoals: boolean; doneCount: number; totalCount: number; streakDays: number; items: TodayItem[] };

// P-4 응답 (수량형은 currentValue도)
export type RecordResult = { goalId: number; done: boolean; allDone: boolean; currentValue?: number };
