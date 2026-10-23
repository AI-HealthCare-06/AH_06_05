// 가짜 응답 (EXPO_PUBLIC_USE_MOCK=true): 서버 없이 화면을 볼 때. 모양은 API 명세서 v1.3 그대로 (회원 A-1, U-1, U-2는 v1.5 초안)
// 로그인: 비밀번호를 비우거나 "1234"를 넣으면 실패(CM-01-E1), 5번 틀리면 10분 잠김(CM-01-E2). 나머지는 성공
import { DIALYSIS, DISEASE_IDS, DRINKING, EXAM_NAME_MAX, SMOKING } from '@/features/common/health';

import type { Method } from './client';
import * as md from './mockData';
import { routeChat } from './mockChat';

const MAX_FAILURES = 5;
const LOCK_MINUTES = 10;
const USER = { id: 1, birthYear: 1958, sex: 'M' as 'M' | 'F' };
const EMAIL = 'hong@example.com';
// U-1 health (가입 때는 흡연, 음주만 받고 나머지는 비어 있음)
let health: Record<string, unknown> = {
  smoking: 'never',
  drinking: 'monthly',
  diseases: [],
  pregnant: null,
  dialysis: null,
  heightCm: null,
  weightKg: null,
  upcomingExams: [],
};

function me(): Response {
  return json(200, { ...USER, email: EMAIL, createdAt: '2026-10-19T10:00:00+09:00', health });
}

// A-1: 흡연, 음주가 없거나 동의가 빠지면 실패 (에러 모양과 문구는 서버와 같게). "dup@"으로 시작하는 이메일은 이미 가입된 이메일
function signup(body: Record<string, unknown>): Response {
  const h = body.health as { smoking?: string; drinking?: string } | undefined;
  const invalid = (field: string) =>
    json(400, { error: { code: 'VALIDATION_ERROR', message: '입력한 내용을 다시 확인해 주세요.', field } });
  if (!h) return invalid('health');
  if (!h.smoking) return invalid('health.smoking');
  if (!h.drinking) return invalid('health.drinking');
  const c = body.consents as Record<string, boolean> | undefined;
  for (const [k, f] of [['terms', 'consents.terms'], ['privacy', 'consents.privacy'], ['sensitiveHealth', 'consents.sensitiveHealth']]) {
    if (!c?.[k]) return json(400, { error: { code: 'CONSENT_REQUIRED', message: '필수 동의 항목에 모두 동의해 주세요.', field: f } });
  }
  if (typeof body.email === 'string' && body.email.startsWith('dup@')) {
    return json(409, { error: { code: 'EMAIL_DUPLICATED', message: '이미 가입된 이메일이에요.', field: 'email' } });
  }
  USER.birthYear = Number(body.birthYear) || USER.birthYear;
  USER.sex = body.sex === 'F' ? 'F' : 'M';
  health = { ...health, smoking: h.smoking, drinking: h.drinking };
  return json(201, { accessToken: 'mock-access', refreshToken: 'mock-refresh', user: USER });
}

// U-2 health 검사: 서버 app/dtos/users.py와 같은 규칙. 틀린 칸 이름을 돌려줌 (없으면 null)
function invalidHealthField(h: Record<string, unknown>): string | null {
  const allowed: Record<string, readonly unknown[]> = {
    smoking: SMOKING,
    drinking: DRINKING,
    pregnant: ['yes', 'no', null],
    dialysis: [...DIALYSIS, null],
  };
  for (const key of Object.keys(h)) {
    const v = h[key];
    // 서버처럼 null은 "안 보낸 것"(흡연, 음주) 또는 "빈 목록"(질환, 예정 검사)으로 봄
    if (v === null && ['smoking', 'drinking', 'diseases', 'upcomingExams'].includes(key)) continue;
    if (key in allowed) {
      if (!allowed[key].includes(v)) return `health.${key}`;
    } else if (key === 'diseases') {
      if (!Array.isArray(v)) return 'health.diseases';
      const i = v.findIndex((d) => !(DISEASE_IDS as readonly unknown[]).includes(d));
      if (i >= 0) return `health.diseases.${i}`;
    } else if (key === 'heightCm') {
      if (v !== null && !(Number.isInteger(v) && (v as number) > 0)) return 'health.heightCm';
    } else if (key === 'weightKg') {
      if (v !== null && !(typeof v === 'number' && v > 0 && Math.round(v * 10) === v * 10)) return 'health.weightKg';
    } else if (key === 'upcomingExams') {
      if (!Array.isArray(v)) return 'health.upcomingExams';
      for (const [i, e] of v.entries()) {
        const { name, date } = (e ?? {}) as { name?: unknown; date?: unknown };
        if (typeof name !== 'string' || name.length < 1 || name.length > EXAM_NAME_MAX) return `health.upcomingExams.${i}.name`;
        if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return `health.upcomingExams.${i}.date`;
      }
    } else {
      return `health.${key}`; // 없는 칸
    }
  }
  return null;
}

// U-2: 보낸 칸만. 임신은 여성만, 성별을 M으로 바꾸면 비움
function updateMe(body: Record<string, unknown>): Response {
  const sex = body.sex === 'F' || body.sex === 'M' ? body.sex : USER.sex;
  const h = (body.health ?? {}) as Record<string, unknown>;
  const bad = invalidHealthField(h);
  if (bad) return json(400, { error: { code: 'VALIDATION_ERROR', message: '입력한 내용을 다시 확인해 주세요.', field: bad } });
  if (h.pregnant != null && sex !== 'F') {
    return json(400, { error: { code: 'VALIDATION_ERROR', message: '임신 여부는 여성만 입력할 수 있어요.', field: 'health.pregnant' } });
  }
  if (typeof body.birthYear === 'number') USER.birthYear = body.birthYear;
  USER.sex = sex;
  const cleaned = Object.fromEntries(
    Object.entries(h)
      .filter(([k, v]) => !(v === null && (k === 'smoking' || k === 'drinking')))
      .map(([k, v]) => [k, v === null && (k === 'diseases' || k === 'upcomingExams') ? [] : v]),
  );
  health = { ...health, ...cleaned, ...(sex === 'M' ? { pregnant: null } : {}) };
  return me();
}

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
  if (method === 'POST' && path === '/auth/signup') return signup(body);
  if (method === 'GET' && path === '/users/me') return me();
  if (method === 'PATCH' && path === '/users/me') return updateMe(body);
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
  if (method === 'GET' && p === '/analyses') return md.listAnalysesMock(Number(url.searchParams.get('cursor') ?? 0) || 0, Number(url.searchParams.get('size') ?? 20));
  if (method === 'DELETE' && (m = route(/^\/analyses\/(\d+)$/))) return md.deleteAnalysisMock(Number(m[1]));
  if (method === 'POST' && route(/^\/guides\/\d+\/feedback$/)) return { status: 201, body: { feedbackId: 1 } };
  if (method === 'POST' && p === '/analyses') return md.startAnalysisMock();
  if (method === 'POST' && route(/^\/analyses\/\d+\/retry$/)) return md.startAnalysisMock(true);
  if (method === 'GET' && route(/^\/analyses\/\d+\/status$/)) return md.analysisStatus();
  if (method === 'GET' && (m = route(/^\/analyses\/\d+\/warnings\/(\d+)$/))) return md.warningDetail(Number(m[1]));
  if (method === 'PUT' && route(/^\/analyses\/\d+\/diseases$/)) return md.putDiseases((body ?? {}) as Record<string, unknown>);
  if (method === 'GET' && route(/^\/analyses\/\d+$/)) return md.analysisResult();
  return routeChat(method, p, body);
}
