// 가짜 응답 (EXPO_PUBLIC_USE_MOCK=true): 서버 없이 화면을 볼 때. 모양은 API 명세서 v1.3 그대로
// 로그인: 비밀번호를 비우거나 "1234"를 넣으면 실패(CM-01-E1), 5번 틀리면 10분 잠김(CM-01-E2). 나머지는 성공
import type { Method } from './client';
import * as md from './mockData';

const MAX_FAILURES = 5;
const LOCK_MINUTES = 10;
const USER = { id: 1, nickname: '홍길동', birthYear: 1958, sex: 'M' };

let failures = 0;
let lockedUntil = 0;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function error(status: number, code: string, message: string, detail?: Record<string, unknown>): Response {
  return json(status, { error: { code, message, ...(detail ? { detail } : {}) } });
}

function locked(): Response {
  return error(423, 'AUTH_LOCKED', `비밀번호를 ${MAX_FAILURES}번 틀려서 ${LOCK_MINUTES}분 동안 로그인할 수 없어요.`, {
    lockedUntil: new Date(lockedUntil).toISOString(),
  });
}

function login(body: { password?: string }): Response {
  if (Date.now() < lockedUntil) return locked();
  if (!body.password || body.password === '1234') {
    failures += 1;
    if (failures >= MAX_FAILURES) {
      failures = 0;
      lockedUntil = Date.now() + LOCK_MINUTES * 60 * 1000;
      return locked();
    }
    return error(401, 'AUTH_INVALID_CREDENTIALS', '이메일 또는 비밀번호가 맞지 않아요.', {
      remainingAttempts: MAX_FAILURES - failures,
    });
  }
  failures = 0;
  return json(200, { accessToken: 'mock-access', refreshToken: 'mock-refresh', user: USER });
}

export async function mockFetch(method: Method, path: string, init: RequestInit): Promise<Response> {
  await new Promise((r) => setTimeout(r, 300)); // 서버를 부르는 것처럼 잠깐 기다림
  const body = typeof init.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : {};
  if (method === 'POST' && path === '/auth/login') return login({ password: typeof body.password === 'string' ? body.password : undefined });
  if (method === 'POST' && path === '/auth/token/refresh') return json(200, { accessToken: 'mock-access' });
  const r = routeFlow(method, path, body);
  if (r) return r.body === null ? new Response(null, { status: r.status }) : json(r.status, r.body);
  return error(404, 'NOT_FOUND', '가짜 응답이 아직 없는 주소예요.');
}

// OCR, 분석 흐름 (mockData.ts)
function routeFlow(method: Method, path: string, body: Record<string, unknown>): { status: number; body: unknown } | null {
  const url = new URL(path, 'http://mock');
  const p = url.pathname;
  const route = (re: RegExp) => p.match(re);
  let m: RegExpMatchArray | null;
  if (method === 'POST' && p === '/prescriptions') return md.startJob();
  if (method === 'GET' && route(/^\/ocr-jobs\/\d+$/)) return md.getJob();
  if (method === 'GET' && (m = route(/^\/prescriptions\/(\d+)$/))) return md.getRx(Number(m[1]));
  if (method === 'PATCH' && (m = route(/^\/prescriptions\/(\d+)\/items\/(\d+)$/))) return md.patchRxItem(Number(m[1]), Number(m[2]), body);
  if (method === 'GET' && p === '/drugs/search') return md.searchDrugs(url.searchParams.get('q') ?? '', Number(url.searchParams.get('size') ?? 5));
  if (method === 'POST' && p === '/analyses') return md.startAnalysisMock();
  if (method === 'POST' && route(/^\/analyses\/\d+\/retry$/)) return md.startAnalysisMock(true);
  if (method === 'GET' && route(/^\/analyses\/\d+\/status$/)) return md.analysisStatus();
  if (method === 'GET' && (m = route(/^\/analyses\/\d+\/warnings\/(\d+)$/))) return md.warningDetail(Number(m[1]));
  if (method === 'PUT' && route(/^\/analyses\/\d+\/diseases$/)) return md.putDiseases((body ?? {}) as Record<string, unknown>);
  if (method === 'GET' && route(/^\/analyses\/\d+$/)) return md.analysisResult();
  return null;
}
