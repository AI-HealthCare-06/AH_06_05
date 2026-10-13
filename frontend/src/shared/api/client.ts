// 서버 API 호출 함수 하나 (API 명세서 v1.3 0절 공통 규칙, A-4 "앱에서 하는 순서")
// - 출입증을 헤더에 넣음: Authorization: Bearer {accessToken}
// - 에러는 명세서 모양 {"error": {code, message, field?, detail?}}을 ApiError로 바꿔 던짐
// - 401 TOKEN_EXPIRED면 A-4로 출입증을 다시 받고 같은 요청을 한 번만 다시 보냄
// - A-4도 실패하면 저장한 두 값을 지우고 로그인 화면으로 보내도록 알림 (setAuthLostHandler)
import { copy } from '@/shared/copy';
import { tokens } from '@/shared/storage/tokens';

import { mockFetch } from './mock';

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost/api/v1';
const USE_MOCK = process.env.EXPO_PUBLIC_USE_MOCK === 'true';

export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export class ApiError extends Error {
  readonly status: number; // 0이면 서버에 닿지 못함 (연결 오류, CM-08)
  readonly code: string;
  readonly field?: string;
  readonly detail?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, field?: string, detail?: Record<string, unknown>) {
    super(message); // 명세서상 message는 화면에 그대로 띄울 수 있는 문장
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.field = field;
    this.detail = detail;
  }
}

// expired: 로그인이 끝남 ("다시 로그인해 주세요"를 보여 줌), unauthorized: 처음부터 로그인 안 됨
export type AuthLostReason = 'expired' | 'unauthorized';
let onAuthLost: ((reason: AuthLostReason) => void) | null = null;

export function setAuthLostHandler(handler: ((reason: AuthLostReason) => void) | null) {
  onAuthLost = handler;
}

async function loseAuth(reason: AuthLostReason) {
  await tokens.clear();
  onAuthLost?.(reason);
}

async function send(method: Method, path: string, body: unknown, auth: boolean): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  // 업로드(O-1 처방전 사진)는 FormData 그대로. Content-Type은 fetch가 경계값과 함께 넣음
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  if (auth) {
    const access = await tokens.getAccess();
    if (access) headers.Authorization = `Bearer ${access}`;
  }
  const init: RequestInit = {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  };
  if (USE_MOCK) return mockFetch(method, path, init);
  try {
    return await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(0, 'NETWORK', copy.network.title);
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const data = (await res.json()) as { error?: { code: string; message: string; field?: string; detail?: Record<string, unknown> } };
    if (data.error) {
      const { code, message, field, detail } = data.error;
      return new ApiError(res.status, code, message, field, detail);
    }
  } catch {
    // 본문이 JSON이 아님 (nginx 오류 화면 등)
  }
  return new ApiError(res.status, 'INTERNAL_ERROR', copy.common.serverError);
}

// 여러 요청이 동시에 출입증 만료를 만나도 A-4는 한 번만 부름
let refreshing: Promise<ApiError | null> | null = null;

function refreshAccess(): Promise<ApiError | null> {
  refreshing ??= (async () => {
    const refreshToken = await tokens.getRefresh();
    if (!refreshToken) return new ApiError(401, 'UNAUTHORIZED', copy.login.expired);
    const res = await send('POST', '/auth/token/refresh', { refreshToken }, false);
    if (!res.ok) return toError(res);
    const { accessToken } = (await res.json()) as { accessToken: string };
    await tokens.saveAccess(accessToken);
    return null;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function finish<T>(res: Response, auth: boolean): Promise<T> {
  if (res.ok) return (res.status === 204 ? undefined : await res.json()) as T;
  const err = await toError(res);
  if (auth && res.status === 401) await loseAuth(err.code === 'TOKEN_EXPIRED' ? 'expired' : 'unauthorized');
  throw err;
}

// auth: false는 로그인, 회원가입, 재발급처럼 출입증 없이 부르는 API
export async function api<T>(method: Method, path: string, body?: unknown, opts: { auth?: boolean } = {}): Promise<T> {
  const auth = opts.auth ?? true;
  const res = await send(method, path, body, auth);
  if (!(auth && res.status === 401)) return finish<T>(res, auth);

  const first = await toError(res);
  if (first.code !== 'TOKEN_EXPIRED') {
    await loseAuth('unauthorized');
    throw first;
  }
  const refreshError = await refreshAccess().catch((e: unknown) =>
    e instanceof ApiError ? e : new ApiError(500, 'INTERNAL_ERROR', copy.common.serverError),
  );
  if (refreshError) {
    // A-4도 401일 때만 저장한 두 값을 지움 (명세서 A-4 4번). 연결 끊김이나 서버 오류(500, 503)는
    // 서버가 잠깐 불안정한 것일 수 있어서 로그인은 그대로 두고 에러만 알림
    if (refreshError.status === 401) {
      await loseAuth(refreshError.code === 'UNAUTHORIZED' ? 'unauthorized' : 'expired');
    }
    throw refreshError;
  }
  return finish<T>(await send(method, path, body, true), true); // 한 번만 다시 보냄
}
