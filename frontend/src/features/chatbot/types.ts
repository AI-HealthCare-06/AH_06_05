// 챗봇 API 모양 (API 명세서 v1.5 초안 5장 H-1 ~ H-8, 설계 메모 3-3 항목). 1단계에 쓰는 칸만
export type AnswerType = 'normal' | 'clarify' | 'partial' | 'no_evidence' | 'refer' | 'emergency' | 'crisis';

export type ChatContext = { type: 'warning' | 'drug'; id: number };

// 챗봇 창을 열 때 넘기는 값 (설계 메모 3-4 항목). from은 기록용이고 창 모양은 바꾸지 않음
export type ChatParams = {
  from: 'fab' | 'CM-03' | 'RG-02' | 'RG-03' | 'RG-04';
  analysisId?: number;
  context?: ChatContext;
};

// 서버 긴급, 자해 감지 결과 (원문 없음)
export type SafetyInfo = { types: ('emergency' | 'crisis')[]; overdose: boolean; rule: string };

// H-2 대화 한 줄
export type Message = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  status: 'generating' | 'done';
  answerType?: AnswerType;
  replyTo?: number;
  sources?: { title: string; basedOn?: string }[];
  contextCard?: { analysisId: number; context?: ChatContext };
  safetyCard?: { analysisId: number; warningIds: number[] };
  safety?: SafetyInfo;
  createdAt: string;
};

export type TodayResponse = { sessionId: number | null; hasHistory: boolean; safetyModeUntil: string | null };
