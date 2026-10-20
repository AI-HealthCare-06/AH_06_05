// 분석 응답 모양 (API 명세서 v1.5 초안 4장 R-1 ~ R-9)
export type StepState = 'pending' | 'running' | 'done' | 'failed';
export type AnalysisStatus = 'queued' | 'running' | 'done' | 'failed';

export type AnalysisProgress = {
  analysisId: number;
  status: AnalysisStatus;
  steps: { key: string; label?: string; state: StepState }[];
  drugCount?: number;
  excludedCount?: number;
  estimatedSeconds?: number;
  error?: { code: string; message: string };
  partialResultAvailable?: boolean;
  retryCount?: number;
};

export type Severity = 'danger' | 'caution' | 'info';

export type Warning = {
  id: number;
  type: string;
  severity: Severity;
  title: string;
  drugs: { ediCode: string | null; itemName: string; hospitalName: string | null }[];
  summary: string;
  source: { name: string; noticeDate: string | null };
};

export type Action = { text: string; kind: 'fact' | 'safety_notice'; sourceIds: number[] };

export type AnalysisResult = {
  analysisId: number;
  status: 'done';
  createdAt: string;
  summary: {
    prescriptionCount: number;
    hospitals: string[];
    drugCount: number;
    warningCounts: Record<Severity, number>;
  };
  excludedDrugs: { rawName: string; reason: string }[];
  warnings: Warning[];
  checkedItems: { type: string; label: string; state: string }[];
  medication: {
    guideId: number;
    status: 'done' | 'failed';
    items: {
      itemId: number;
      ediCode: string | null;
      itemName: string;
      category: string | null;
      purpose: string | null;
      howToTake: string | null;
      caution: string | null; // cautions를 줄바꿈으로 이은 문자열 (명세서의 caution)
      cautions: string[]; // 문장별 목록 (명세서에 추가 제안)
      source: string | null;
    }[];
  };
  lifestyle: {
    guideId: number;
    status: 'done' | 'failed';
    diseases: { code: string; name: string; origin: 'prescription' | 'user' }[];
    medicationLinks: { itemId: number; itemName: string; requiresClinician: boolean; actions: Action[] }[];
    sections: {
      diseaseCode: string;
      title: string;
      goal: string | null;
      actions: Action[];
      conflict: { message: string; label: string } | null;
    }[];
    warningSigns: { diseaseCode: string; actions: Action[] }[];
    sources: { id: number; org: string; title: string }[];
  };
  disclaimer: string;
};

export type WarningDetail = {
  id: number;
  severity: Severity;
  title: string;
  drugs: { itemName: string; hospitalName: string | null; category: string | null; ingredient: string | null }[];
  explanation: string;
  reasonOriginal: string;
  source: { name: string; noticeDate: string | null };
  judgedBy: 'database';
  actionAdvice: string;
};

// R-7 지난 기록 목록. 끝난 분석(done)에만 병원, 약 수, 질환이 있고 진행 중 또는 실패는 상태 라벨만 있음
export type AnalysisListItem = {
  analysisId: number;
  createdAt: string;
  status: 'running' | 'done' | 'failed';
  resultLabel: string; // 서버가 만든 화면 라벨 ("확인 필요 N건" 등)
  hospitals?: string[];
  drugCount?: number;
  diseaseNames?: string[];
};

export type AnalysisList = { items: AnalysisListItem[]; nextCursor: string | null };
