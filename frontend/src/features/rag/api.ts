// 분석 API 호출 (R-1 ~ R-6)
import { api } from '@/shared/api/client';

import type { AnalysisProgress, AnalysisResult, WarningDetail } from './types';

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
