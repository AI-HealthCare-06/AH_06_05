// 공통 회원 API (A-1, U-1 ~ U-5). 화면은 이 함수들만 부름
import { api } from '@/shared/api/client';

import type { Health, HealthUpdate, Smoking, Drinking } from './health';

export type Sex = 'M' | 'F';
export type Me = { id: number; email: string; birthYear: number; sex: Sex; createdAt: string; health: Health };

export type SignupRequest = {
  email: string;
  password: string;
  birthYear: number;
  sex: Sex;
  health: { smoking: Smoking; drinking: Drinking };
  consents: { terms: boolean; privacy: boolean; sensitiveHealth: boolean };
};

// U-1 내 정보
export const getMe = () => api<Me>('GET', '/users/me');

// U-2 내 정보 수정 (보낸 칸만)
export const updateMe = (body: { birthYear?: number; sex?: Sex; health?: HealthUpdate }) =>
  api<Me>('PATCH', '/users/me', body);

// U-4 동의 내역. 철회했으면 withdrawnAt이 있음
export type ConsentType = 'terms' | 'privacy' | 'sensitiveHealth';
export type ConsentItem = { type: ConsentType; agreed: boolean; agreedAt: string | null; withdrawnAt: string | null };
export const getConsents = () => api<{ items: ConsentItem[] }>('GET', '/users/me/consents');

// U-5 동의 철회 (건강 정보 동의만). 처방전, 분석, 챗봇 대화, 건강 정보가 지워짐
export const withdrawConsent = () => api<void>('DELETE', '/users/me/consents/sensitiveHealth');

// U-3 회원 탈퇴. 기록을 모두 지우고 이 계정으로는 더 이상 로그인할 수 없음
export const withdrawMe = () => api<void>('DELETE', '/users/me', { confirmed: true });
