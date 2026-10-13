// 분석 응답 모양 (API 명세서 v1.5 초안 4장 R-1 ~ R-6)
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
      caution: string | null;
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
