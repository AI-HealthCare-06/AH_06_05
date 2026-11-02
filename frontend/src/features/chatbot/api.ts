// 챗봇 API (명세서 v1.5 초안 H-1 ~ H-8)
import { api } from '@/shared/api/client';

import type { ChatContext, Message, SessionItem, TodayResponse } from './types';

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
  api<{ firstMessage?: Message }>('POST', `/chat/sessions/${sessionId}/context`, { analysisId, context, clientRequestId });

export const getChatDays = (month: string) =>
  api<{ dates: string[] }>('GET', `/chat/sessions?month=${month}`).then((r) => r.dates);

export const getSessionsOn = (date: string) =>
  api<{ items: SessionItem[] }>('GET', `/chat/sessions?date=${date}`).then((r) => r.items);

export const renameSession = (sessionId: number, title: string) =>
  api<{ sessionId: number; title: string }>('PATCH', `/chat/sessions/${sessionId}`, { title });

// 지운 뒤 열려 있는 챗봇 창이 오늘 대화를 다시 찾게 함 (설계 메모 4-13)
let removals = 0;
export const removalCount = () => removals;

export const deleteSession = (sessionId: number) =>
  api<void>('DELETE', `/chat/sessions/${sessionId}`).then(() => void removals++);

export const deleteAllSessions = () => api<void>('DELETE', '/chat/sessions').then(() => void removals++);
