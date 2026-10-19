// 분석 API 호출 (R-1 ~ R-9)
import { api } from '@/shared/api/client';

import type { AnalysisList, AnalysisProgress, AnalysisResult, WarningDetail } from './types';

export const startAnalysis = (prescriptionIds: number[]) =>
  api<{ analysisId: number; status: 'queued' }>('POST', '/analyses', { prescriptionIds });

// 2초 간격 폴링
export const getAnalysisStatus = (id: number) => api<AnalysisProgress>('GET', `/analyses/${id}/status`);

export const retryAnalysis = (id: number) => api<{ analysisId: number; status: 'queued' }>('POST', `/analyses/${id}/retry`);

export const getAnalysis = (id: number) => api<AnalysisResult>('GET', `/analyses/${id}`);

export const getWarning = (analysisId: number, warningId: number) =>
  api<WarningDetail>('GET', `/analyses/${analysisId}/warnings/${warningId}`);

// 질병분류기호가 없을 때 사용자가 직접 고른 질환 (RG-05-E1)
export const putDiseases = (analysisId: number, diseaseCodes: string[]) =>
  api<AnalysisResult['lifestyle']>('PUT', `/analyses/${analysisId}/diseases`, { diseaseCodes });

// R-7 지난 기록 목록 (홈은 size=1로 최근 1건). 다음 쪽은 앞 응답의 nextCursor를 그대로 넘김
export const listAnalyses = (cursor?: string | null, size = 20) =>
  api<AnalysisList>('GET', `/analyses?size=${size}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`);

// R-8 기록 삭제 (204). 분석이 아직 진행 중이면 409 ANALYSIS_RUNNING
export const deleteAnalysis = (id: number) => api<void>('DELETE', `/analyses/${id}`);

// R-9 안내문 피드백. rating 1 도움됐어요, -1 도움이 안 됐어요. 다시 보내면 앞의 것을 덮어씀
export const sendGuideFeedback = (guideId: number, rating: 1 | -1, comment?: string) =>
  api<{ feedbackId: number }>('POST', `/guides/${guideId}/feedback`, comment ? { rating, comment } : { rating });
