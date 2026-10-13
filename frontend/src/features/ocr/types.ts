// OCR 응답 모양 (API 명세서 v1.5 초안 3장 O-1 ~ O-5)
export type MatchStatus = 'auto' | 'needs_confirm' | 'user_confirmed' | 'unmatched' | 'excluded';

export type Candidate = {
  ediCode: string | null;
  itemSeq: string | null;
  itemName: string;
  score: number;
};

export type PrescriptionItem = {
  id: number;
  rawName: string;
  itemName: string | null; // 약이 정해진 항목의 화면 표시 이름 (명세서 O-2에는 아직 없음, 서버에 요청할 것)
  matchStatus: MatchStatus;
  ediCode: string | null;
  itemSeq: string | null;
  candidates: Candidate[];
  dosePerTime: number | null;
  timesPerDay: number | null;
  totalDays: number | null;
  timing: string | null;
};

export type Prescription = {
  id: number;
  docType: 'prescription' | 'pill_bag';
  issuedDate: string | null;
  hospitalName: string | null;
  diseaseCodes: string[];
  items: PrescriptionItem[];
};

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';
export type FailedFileCode = 'IMAGE_QUALITY_LOW' | 'NOT_A_DOCUMENT' | 'OCR_FAILED';

export type OcrJob = {
  jobId: number;
  status: JobStatus;
  prescriptionIds: number[];
  failedFiles: { fileIndex: number; code: FailedFileCode }[];
};

export type DrugSearch = {
  status: 'matched' | 'candidates' | 'not_found';
  items: {
    itemSeq: string | null;
    ediCode: string | null;
    itemName: string;
    entpName: string;
    etcOtc: string;
    score: number;
  }[];
};

// 약을 고르거나 빼는 수정 (O-3)
export type ItemPatch =
  | { ediCode: string | null; itemSeq?: string | null }
  | { itemSeq: string; ediCode?: null }
  | { exclude: true; ediCode: null; itemSeq: null };
