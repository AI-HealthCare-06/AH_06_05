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
  suggestedBy: 'similar' | 'llm' | null; // needs_confirm일 때 후보가 비슷한 이름인지 AI 추천인지 (명세서에 추가 제안)
  guidance: string[]; // 약봉투에 약국이 인쇄한 복약 안내 (사진에서 읽은 글자 그대로, 없으면 빈 배열)
  checkFields: string[]; // 못 읽었거나 범위 밖이라 다시 확인할 칸 이름 (예: '1회량')
};

export type Prescription = {
  id: number;
  docType: 'prescription' | 'pill_bag';
  issuedDate: string | null;
  hospitalName: string | null;
  diseaseCodes: string[];
  notices: string[]; // 사진을 읽을 때 사용자가 확인해야 할 점 (없으면 빈 배열)
  items: PrescriptionItem[];
};

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';
export type FailedFileCode = 'IMAGE_QUALITY_LOW' | 'NOT_A_DOCUMENT' | 'OCR_FAILED';

export type OcrJob = {
  jobId: number;
  status: JobStatus;
  prescriptionIds: number[];
  failedFiles: { fileIndex: number; code: FailedFileCode }[];
  duplicatedFiles: { fileIndex: number; prescriptionId: number }[]; // 이미 올린 사진이라 새로 읽지 않은 것
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
