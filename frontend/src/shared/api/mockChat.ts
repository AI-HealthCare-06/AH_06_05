// 챗봇 가짜 응답 (명세서 v1.5 초안 H-1 ~ H-8 모양 그대로). 서버 규칙 중 화면 확인에 필요한 것만 흉내 냄
// - "가슴"이 들어간 질문: 1층 긴급(원문 없이 저장), "죽고"가 들어간 질문: 도움 연결, "많이 먹"이 들어간 질문: 과다 복용 긴급
// - "오류"가 들어간 질문: 답을 만들다 실패해 답 줄이 사라짐 (E6). 다시 시도하면 답함
// - "끊김"이 들어간 질문: 처음 한 번은 질문을 저장하지 않고 500 (서버에 닿지 못한 E6). 다시 시도하면 받음
// - 그 밖의 질문: 3초 뒤 답 완성 (그동안 generating)
type Row = Record<string, unknown> & { id: number; role: 'user' | 'assistant'; status: 'generating' | 'done' };
type Session = { id: number; crid: string; createdAt: number; rows: Row[]; safetyUntil: string | null };

const ANSWER_MS = 3000;
const KST_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
const sessions: Session[] = [];
const crids = new Map<string, number>(); // clientRequestId → 질문 줄 번호
const failOnce = new Set<number>(); // 한 번 실패시킬 질문 줄
const readyAt = new Map<number, number>(); // 답 줄 → 완성 시각
const cutOnce = new Set<string>(); // 한 번 500을 돌려준 clientRequestId
let seq = 9100;

const iso = (ms = Date.now()) => new Date(ms + KST_MS).toISOString().replace('Z', '+09:00');
const kstDay = (ms: number) => Math.floor((ms + KST_MS) / DAY_MS);
const reply = (status: number, body: unknown) => ({ status, body });
const notFound = () => reply(404, { error: { code: 'NOT_FOUND', message: '찾을 수 없어요.' } });

function answerFor(q: string): Record<string, unknown> {
  if (q.includes('혈압')) {
    return { answerType: 'normal', content: '혈압약은 매일 같은 시간에 드시는 게 좋아요.', sources: [{ title: '식약처 의약품 허가정보' }] };
  }
  return { answerType: 'no_evidence', content: '등록된 자료에서 이 질문에 대한 근거를 찾지 못했어요. 확인되지 않은 정보는 안내하지 않아요. 약사에게 확인해 주세요.', sources: [] };
}

function settle(s: Session) {
  const now = Date.now();
  for (const r of s.rows) {
    if (r.status !== 'generating') continue;
    const at = readyAt.get(r.id) ?? 0;
    if (now < at) continue;
    const q = s.rows.find((x) => x.id === r.replyTo);
    if (q && failOnce.has(q.id)) {
      failOnce.delete(q.id);
      s.rows = s.rows.filter((x) => x.id !== r.id); // 실패하면 답 줄을 지움
      continue;
    }
    Object.assign(r, { status: 'done', ...answerFor(String(q?.content ?? '')) });
  }
}

function view(r: Row) {
  return Object.fromEntries(Object.entries(r).filter(([, v]) => v !== undefined));
}

export function routeChat(method: string, p: string, body: Record<string, unknown>): { status: number; body: unknown } | null {
  let m: RegExpMatchArray | null;
  if (method === 'GET' && p === '/chat/sessions/today') {
    const today = [...sessions].reverse().find((s) => kstDay(s.createdAt) === kstDay(Date.now()));
    return reply(200, { sessionId: today?.id ?? null, hasHistory: sessions.length > 0, safetyModeUntil: today?.safetyUntil ?? null });
  }
  if (method === 'POST' && p === '/chat/sessions') {
    const crid = String(body.clientRequestId);
    const found = sessions.find((s) => s.crid === crid);
    if (found) return reply(201, { sessionId: found.id });
    const s: Session = { id: ++seq, crid, createdAt: Date.now(), rows: [], safetyUntil: null };
    sessions.push(s);
    return reply(201, { sessionId: s.id });
  }
  const s = (m = p.match(/^\/chat\/sessions\/(\d+)/)) ? sessions.find((x) => x.id === Number(m![1])) : undefined;
  if (!m) return null;
  if (!s) return notFound();
  if (method === 'GET' && p.endsWith('/messages')) {
    settle(s);
    return reply(200, { items: s.rows.map(view) });
  }
  if (method === 'POST' && p.endsWith('/context')) {
    const crid = `card:${String(body.clientRequestId)}`;
    if (!crids.has(crid)) {
      const id = ++seq;
      crids.set(crid, id);
      const card = { analysisId: body.analysisId, ...(body.context ? { context: body.context } : {}) };
      s.rows.push({ id, role: 'assistant', content: '', status: 'done', contextCard: card, createdAt: iso() });
    }
    return reply(201, {});
  }
  if (method === 'POST' && p.endsWith('/messages')) {
    const content = String(body.content ?? '').trim();
    if (content.length < 1 || content.length > 500) {
      return reply(400, { error: { code: 'VALIDATION_ERROR', message: '입력한 내용을 다시 확인해 주세요.', field: 'content' } });
    }
    const crid = String(body.clientRequestId);
    if (content.includes('끊김') && !cutOnce.has(crid)) {
      cutOnce.add(crid);
      return reply(500, { error: { code: 'INTERNAL_ERROR', message: '잠시 문제가 생겼어요. 잠시 후 다시 시도해 주세요.' } });
    }
    const qid = crids.get(crid);
    if (qid !== undefined) {
      const last = [...s.rows].reverse().find((r) => r.replyTo === qid);
      if (last) return reply(202, { messageId: last.id });
      const a: Row = { id: ++seq, role: 'assistant', status: 'generating', replyTo: qid, createdAt: iso() };
      readyAt.set(a.id, Date.now() + ANSWER_MS);
      s.rows.push(a);
      return reply(202, { messageId: a.id });
    }
    const dismissed = body.emergencyDismissed === true;
    const crisis = content.includes('죽고');
    const overdose = !dismissed && content.includes('많이 먹');
    const emergency = !dismissed && (content.includes('가슴') || overdose);
    const q: Row = { id: ++seq, role: 'user', status: 'done', content: emergency || crisis ? '' : content, createdAt: iso() };
    crids.set(crid, q.id);
    s.rows.push(q);
    if (emergency || crisis) {
      const types = [...(emergency ? ['emergency'] : []), ...(crisis ? ['crisis'] : [])];
      const a: Row = {
        id: ++seq, role: 'assistant', status: 'done', content: '', answerType: types[0], replyTo: q.id, sources: [],
        safety: { types, overdose, rule: overdose ? 'overdose' : emergency ? 'chest' : 'self_harm' }, createdAt: iso(),
      };
      s.rows.push(a);
      if (crisis) s.safetyUntil = iso((kstDay(Date.now()) + 1) * DAY_MS - KST_MS);
      return reply(202, { messageId: a.id });
    }
    if (content.includes('오류')) failOnce.add(q.id);
    const a: Row = { id: ++seq, role: 'assistant', status: 'generating', replyTo: q.id, createdAt: iso() };
    readyAt.set(a.id, Date.now() + ANSWER_MS);
    s.rows.push(a);
    return reply(202, { messageId: a.id });
  }
  if (method === 'DELETE' && /^\/chat\/sessions\/\d+$/.test(p)) {
    sessions.splice(sessions.indexOf(s), 1);
    return reply(204, null);
  }
  return null;
}
