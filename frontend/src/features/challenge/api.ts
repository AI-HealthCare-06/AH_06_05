// 실천 API 호출 (P-1 ~ P-4)
import { api } from '@/shared/api/client';

import type { RecordResult, RecommendationList, Today } from './types';

// 오늘 날짜만 받음 (기기 날짜, 한국 시간 기준 YYYY-MM-DD)
export function todayString(d = new Date()) {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const getRecommendations = (analysisId: number) =>
  api<RecommendationList>('GET', `/recommendations?analysisId=${analysisId}`);

export const createGoals = (recommendationIds: number[]) =>
  api<{ goalIds: number[] }>('POST', '/habit-goals', { recommendationIds });

export const getToday = () => api<Today>('GET', '/habit-goals/today');

// 체크형: completed false면 완료 취소
export const recordCheck = (goalId: number, completed: boolean) =>
  api<RecordResult>('POST', `/habit-goals/${goalId}/records`, { date: todayString(), completed });

// 수량형: 그날 한 총량 (0~600). 같은 요청을 다시 보내도 두 번 더해지지 않음
export const recordValue = (goalId: number, value: number) =>
  api<RecordResult>('POST', `/habit-goals/${goalId}/records`, { date: todayString(), value });
