// 챗봇 API (명세서 v1.5 초안 H-1 ~ H-8)
import { api } from '@/shared/api/client';

import type { ChatContext, Message, TodayResponse } from './types';

export const findToday = () => api<TodayResponse>('GET', '/chat/sessions/today');

export const startSession = (clientRequestId: string, analysisId?: number, context?: ChatContext) =>
  api<{ sessionId: number }>('POST', '/chat/sessions', { clientRequestId, analysisId, context });

export const getMessages = (sessionId: number) =>
  api<{ items: Message[] }>('GET', `/chat/sessions/${sessionId}/messages`).then((r) => r.items);

export const sendQuestion = (sessionId: number, content: string, clientRequestId: string, emergencyDismissed = false) =>
  api<{ messageId: number }>('POST', `/chat/sessions/${sessionId}/messages`, {
    content,
    clientRequestId,
    ...(emergencyDismissed ? { emergencyDismissed } : {}),
  }).then((r) => r.messageId);

export const addContext = (sessionId: number, analysisId: number, clientRequestId: string, context?: ChatContext) =>
  api<Record<string, never>>('POST', `/chat/sessions/${sessionId}/context`, { analysisId, context, clientRequestId });
