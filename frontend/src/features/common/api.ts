// 공통 회원 API (A-1, U-1, U-2). 화면은 이 함수들만 부름
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
