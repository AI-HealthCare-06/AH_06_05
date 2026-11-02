// 챗봇 API (명세서 v1.5 초안 H-1 ~ H-8)
import { Platform } from 'react-native';

import { api } from '@/shared/api/client';

import type { Picked } from './attach';
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

// H-9 사진 첨부: 사진 한 장을 올리면 서버가 읽어 사용자 줄과 답 줄을 만들고, 앱은 H-2로 받음
export async function sendPhotoFile(sessionId: number, file: Picked, clientRequestId: string) {
  const form = new FormData();
  if (Platform.OS === 'web') form.append('file', await (await fetch(file.uri)).blob(), file.name);
  else form.append('file', { uri: file.uri, name: file.name, type: file.type } as unknown as Blob);
  form.append('clientRequestId', clientRequestId);
  return api<{ messageId: number }>('POST', `/chat/sessions/${sessionId}/attachments`, form).then((r) => r.messageId);
}
