// 가짜 응답 데이터: OCR 흐름(O-1 ~ O-5)과 분석 흐름(R-1 ~ R-5). 모양은 API 명세서 v1.5 초안 그대로
// 약 이름과 경고는 화면 확인용 예시예요. 실제 판정은 서버가 DUR 데이터로 함
// EXPO_PUBLIC_MOCK_SCENARIO로 예외 화면을 불러올 수 있음: quality | notdoc | ocrfail | guidefail | pillbag | duplicate | duplicate

import { PICKABLE_DISEASES } from '@/features/rag/diseases';

const SCENARIO = process.env.EXPO_PUBLIC_MOCK_SCENARIO ?? '';

type Cand = { ediCode: string | null; itemSeq: string | null; itemName: string; score: number };
type Item = {
  id: number;
  rawName: string;
  itemName: string | null;
  matchStatus: string;
  ediCode: string | null;
  itemSeq: string | null;
  candidates: Cand[];
  dosePerTime: number | null;
  timesPerDay: number | null;
  totalDays: number | null;
  timing: string | null;
  suggestedBy: 'similar' | 'llm' | null;
  guidance: string[];
  checkFields: string[];
};
type Rx = {
  id: number;
  docType: 'prescription' | 'pill_bag';
  issuedDate: string;
  hospitalName: string;
  diseaseCodes: string[];
  notices: string[];
  items: Item[];
};

const done = (id: number, raw: string, name: string, edi: string, times: number, days: number, timing: string): Item => ({
  id, rawName: raw, itemName: name, matchStatus: 'auto', ediCode: edi, itemSeq: null, candidates: [],
  dosePerTime: 1, timesPerDay: times, totalDays: days, timing,
  suggestedBy: null,
  guidance: SCENARIO === 'pillbag' ? ['아침 식후 30분에 드세요', '졸음이 올 수 있어요'] : [],
  checkFields: [],
});

const freshRx = (): Rx[] => [
  {
    id: 101, docType: SCENARIO === 'pillbag' ? 'pill_bag' : 'prescription', issuedDate: '2026-09-20', hospitalName: '○○내과',
    diseaseCodes: SCENARIO === 'pillbag' ? [] : ['I10', 'E11', 'E78'],
    notices: SCENARIO === 'pillbag' ? ['약 이름 줄 수와 복용 칸 줄 수가 달라 칸 순서를 추정했어요. 약과 복용법이 맞는지 확인해 주세요.'] : [],
    items: [
      done(1001, '노바스크정 5mg', '노바스크정5밀리그람', '073400360', 1, 30, '아침 식후'),
      {
        id: 1002, rawName: '메트____정', itemName: null, matchStatus: 'needs_confirm', ediCode: null, itemSeq: null,
        candidates: [
          { ediCode: '641600390', itemSeq: null, itemName: '메트포르민정500밀리그램', score: 0.92 },
          { ediCode: '664602800', itemSeq: null, itemName: '메트로니다졸정250밀리그램', score: 0.78 },
          { ediCode: '651200020', itemSeq: null, itemName: '메티마졸정5밀리그램', score: 0.61 },
        ],
        dosePerTime: 1, timesPerDay: 2, totalDays: 30, timing: '아침 저녁 식후',
        suggestedBy: 'similar', guidance: [], checkFields: [],
      },
      done(1003, '심바스타틴정 20mg', '심바스타틴정20밀리그램', '623006210', 1, 30, '저녁 식후'),
      done(1004, '아스피린정 100mg', '아스피린정100밀리그램', '642104440', 1, 30, '아침 식후'),
    ],
  },
  {
    id: 102, docType: 'prescription', issuedDate: '2026-09-26', hospitalName: '△△의원', diseaseCodes: ['J20'], notices: [],
    items: [
      done(1005, '암로디핀정 5mg', '암로디핀정5밀리그램', '649805060', 1, 7, '아침 식후'),
      done(1006, '클래리스로마이신정 250mg', '클래리스로마이신정250밀리그램', '649404570', 2, 7, '아침 저녁 식후'),
      done(1007, '디아제팜정 2mg', '디아제팜정2밀리그램', '651900530', 1, 7, '자기 전'),
      {
        id: 1008, rawName: '○○연질캡슐', itemName: null, matchStatus: 'unmatched', ediCode: null, itemSeq: null,
        candidates: [], dosePerTime: 1, timesPerDay: 3, totalDays: 7, timing: '식후',
        suggestedBy: null, guidance: [], checkFields: ['총 일수'],
      },
    ],
  },
];

const DRUGS = [
  ['641600390', '메트포르민정500밀리그램', '대원제약'],
  ['073400360', '노바스크정5밀리그람', '한국화이자제약'],
  ['649805060', '암로디핀정5밀리그램', '한미약품'],
  ['672300240', '타이레놀8시간이알서방정', '한국존슨앤드존슨판매'],
  ['623006210', '심바스타틴정20밀리그램', '한미약품'],
  ['642104440', '아스피린정100밀리그램', '바이엘코리아'],
  ['664602800', '메트로니다졸정250밀리그램', '대한약품'],
  ['651900530', '디아제팜정2밀리그램', '삼진제약'],
] as const;

let rxs = freshRx();
let jobStartedAt = 0;
let analysisStartedAt = 0;
let analysisRetries = 0;

const elapsed = (from: number) => Date.now() - from;
const ok = (body: unknown) => ({ status: 200, body });

// O-1
export function startJob() {
  rxs = freshRx();
  analysisRetries = 0;
  jobStartedAt = Date.now();
  return { status: 202, body: { jobId: 9001, status: 'queued' } };
}

// O-5
export function getJob() {
  const t = elapsed(jobStartedAt);
  if (t < 700) return ok({ jobId: 9001, status: 'queued', prescriptionIds: [], failedFiles: [], duplicatedFiles: [] });
  if (t < 1800) return ok({ jobId: 9001, status: 'running', prescriptionIds: [], failedFiles: [], duplicatedFiles: [] });
  if (SCENARIO === 'quality') return ok({ jobId: 9001, status: 'done', prescriptionIds: [], failedFiles: [{ fileIndex: 1, code: 'IMAGE_QUALITY_LOW' }], duplicatedFiles: [] });
  if (SCENARIO === 'notdoc') return ok({ jobId: 9001, status: 'done', prescriptionIds: [], failedFiles: [{ fileIndex: 1, code: 'NOT_A_DOCUMENT' }], duplicatedFiles: [] });
  if (SCENARIO === 'ocrfail') return ok({ jobId: 9001, status: 'failed', prescriptionIds: [], failedFiles: [{ fileIndex: 1, code: 'OCR_FAILED' }], duplicatedFiles: [] });
  return ok({ jobId: 9001, status: 'done', prescriptionIds: rxs.map((r) => r.id), failedFiles: [], duplicatedFiles: SCENARIO === 'duplicate' ? [{ fileIndex: 2, prescriptionId: 101 }] : [] });
}

// O-2
export function getRx(id: number) {
  const rx = rxs.find((r) => r.id === id);
  return rx ? ok(rx) : { status: 404, body: { error: { code: 'NOT_FOUND', message: '찾을 수 없어요.' } } };
}

// O-3
export function patchRxItem(rxId: number, itemId: number, body: Record<string, unknown>) {
  const item = rxs.find((r) => r.id === rxId)?.items.find((i) => i.id === itemId);
  if (!item) return { status: 404, body: { error: { code: 'NOT_FOUND', message: '찾을 수 없어요.' } } };
  if (body.exclude === true) {
    Object.assign(item, { matchStatus: 'excluded', ediCode: null, itemSeq: null });
  } else {
    const edi = typeof body.ediCode === 'string' ? body.ediCode : null;
    const found = [...item.candidates.map((c) => [c.ediCode, c.itemName]), ...DRUGS.map((d) => [d[0], d[1]])].find((c) => c[0] === edi);
    Object.assign(item, { matchStatus: 'user_confirmed', ediCode: edi, itemName: found ? found[1] : item.rawName });
  }
  return { status: 204, body: null };
}

// O-4
export function searchDrugs(q: string, size: number) {
  const t = q.replace(/\s/g, '');
  const hits = DRUGS.filter((d) => t.length >= 2 && d[1].includes(t)).slice(0, size);
  const items = hits.map((d, i) => ({ itemSeq: null, ediCode: d[0], itemName: d[1], entpName: d[2], etcOtc: '전문', score: Number((0.92 - i * 0.05).toFixed(2)) }));
  return ok({ status: items.length === 0 ? 'not_found' : 'candidates', items });
}

// 분석에 들어가는 약 (확인이 끝나고 빼지 않은 것)
const active = () => rxs.flatMap((r) => r.items.filter((i) => i.ediCode && i.matchStatus !== 'excluded').map((i) => ({ ...i, rx: r })));

// R-1, R-3
export function startAnalysisMock(retry = false) {
  if (retry) analysisRetries += 1;
  analysisStartedAt = Date.now();
  return { status: 202, body: { analysisId: 5001, status: 'queued' } };
}

const failsGuide = () => SCENARIO === 'guidefail' && analysisRetries === 0;

// R-2
export function analysisStatus() {
  const t = elapsed(analysisStartedAt);
  const step = (key: string, label: string, state: string) => ({ key, label, state });
  const drugCount = active().length;
  const excludedCount = rxs.flatMap((r) => r.items).filter((i) => i.matchStatus === 'excluded' || i.matchStatus === 'unmatched').length;
  const base = { analysisId: 5001, drugCount, excludedCount, estimatedSeconds: 20, retryCount: analysisRetries };
  const mk = (a: string, b: string, c: string) => [
    step('drug_info', '약 정보 확인', a), step('safety_check', '같이 먹으면 안 되는 약 점검', b), step('guide_generation', '안내문 작성', c),
  ];
  if (t < 1000) return ok({ ...base, status: 'running', steps: mk('running', 'pending', 'pending') });
  if (t < 2200) return ok({ ...base, status: 'running', steps: mk('done', 'running', 'pending') });
  if (t < 3500) return ok({ ...base, status: 'running', steps: mk('done', 'done', 'running') });
  if (failsGuide()) {
    return ok({
      ...base, status: 'failed', steps: mk('done', 'done', 'failed'),
      error: { code: 'GUIDE_GENERATION_FAILED', message: '안내문을 만들지 못했어요.' }, partialResultAvailable: true,
    });
  }
  return ok({ ...base, status: 'done', steps: mk('done', 'done', 'done') });
}

let userCodes: string[] = [];
const DISEASE_NAMES: Record<string, string> = Object.fromEntries(PICKABLE_DISEASES.map((d) => [d.code, d.name]));
const has = (names: string[]) => names.every((n) => active().some((i) => i.itemName?.includes(n)));

function buildWarnings() {
  const h = (n: string) => active().find((i) => i.itemName?.includes(n))?.rx.hospitalName ?? null;
  const d = (n: string, name: string) => ({ ediCode: null, itemName: name, hospitalName: h(n) });
  const w = [];
  if (has(['심바스타틴', '클래리스로마이신'])) {
    w.push({
      id: 9001, type: 'interaction', severity: 'danger', title: '함께 먹으면 안 되는 약',
      drugs: [d('심바스타틴', '심바스타틴정 20mg'), d('클래리스로마이신', '클래리스로마이신정 250mg')],
      summary: '함께 먹으면 근육이 상하는 부작용 위험이 커질 수 있어요.',
      source: { name: '식약처 병용금기 성분 고시', noticeDate: '2019-01-01' },
    });
  }
  if (has(['노바스크', '암로디핀'])) {
    w.push({
      id: 9002, type: 'duplicate_ingredient', severity: 'caution', title: '같은 성분이 겹쳐요',
      drugs: [d('노바스크', '노바스크정 5mg'), d('암로디핀', '암로디핀정 5mg')],
      summary: '두 약에 같은 성분(암로디핀)이 들어 있어요. 같이 먹으면 혈압이 너무 낮아질 수 있어요.',
      source: { name: '식약처 동일성분 중복 점검', noticeDate: null },
    });
  }
  if (active().length >= 5) {
    w.push({
      id: 9003, type: 'polypharmacy', severity: 'info', title: '여러 약을 함께 드시고 있어요',
      drugs: active().slice(0, 3).map((i) => ({ ediCode: i.ediCode, itemName: i.itemName ?? i.rawName, hospitalName: i.rx.hospitalName })),
      summary: `먹는 약이 ${active().length}가지예요. 약사에게 전체 약을 한 번 점검받아 보세요.`,
      source: { name: '다제약물 복용 점검 기준', noticeDate: null },
    });
  }
  return w;
}

const act = (text: string, ids: number[], kind = 'fact') => ({ text, kind, sourceIds: ids });

// R-4
export function analysisResult() {
  const ws = buildWarnings();
  const items = active();
  const guideFailed = failsGuide();
  const codes = [...new Set(rxs.filter((r) => r.items.some((i) => items.some((a) => a.id === i.id))).flatMap((r) => r.diseaseCodes))];
  const origin = codes.length > 0 ? 'prescription' : 'user'; // 처방전에 코드가 없으면 사용자가 RG-05-E1에서 고른 질환
  const diseases = (codes.length > 0 ? codes : userCodes).filter((c) => DISEASE_NAMES[c]).map((c) => ({ code: c, name: DISEASE_NAMES[c], origin }));
  const count = (s: string) => ws.filter((w) => w.severity === s).length;
  return ok({
    analysisId: 5001, status: 'done', createdAt: new Date().toISOString(),
    summary: {
      prescriptionCount: rxs.length, hospitals: rxs.map((r) => r.hospitalName), drugCount: items.length,
      warningCounts: { danger: count('danger'), caution: count('caution'), info: count('info') },
    },
    excludedDrugs: rxs.flatMap((r) => r.items).filter((i) => i.matchStatus === 'excluded' || i.matchStatus === 'unmatched').map((i) => ({ rawName: i.rawName, reason: i.matchStatus })),
    warnings: ws,
    checkedItems: [
      { type: 'interaction', label: '함께 먹으면 안 되는 약', state: 'checked' },
      { type: 'duplicate', label: '같은 성분 · 같은 효과 중복', state: 'checked' },
      { type: 'elderly_age', label: '어르신 주의 · 나이 금기', state: 'checked' },
      { type: 'dose_exceed', label: '하루 최대량 초과', state: 'checked' },
      { type: 'polypharmacy', label: '여러 약 함께 복용', state: 'checked' },
    ],
    medication: {
      guideId: 7001, status: guideFailed ? 'failed' : 'done',
      items: guideFailed ? [] : items.map((i) => ({
        itemId: i.id, ediCode: i.ediCode, itemName: i.itemName ?? i.rawName,
        category: '복약 안내 예시', purpose: '(허가정보를 바탕으로 AI가 쉬운 말로 쓰는 자리)',
        howToTake: `하루 ${i.timesPerDay}번, ${i.timing} ${i.dosePerTime}알 · ${i.totalDays}일`,
        caution: '(허가정보에서 가져온 주의 문장 자리)', cautions: ['(허가정보 문장을 쉬운 말로 쓴 첫째 주의)', '(둘째 주의)'], source: '식약처 의약품 허가정보',
      })),
    },
    lifestyle: {
      guideId: 7002, status: guideFailed ? 'failed' : 'done', diseases: guideFailed ? [] : diseases,
      medicationLinks: guideFailed || !has(['암로디핀']) ? [] : [{
        itemId: items.find((i) => i.itemName?.includes('암로디핀'))?.id ?? 0, itemName: '암로디핀정 5mg', requiresClinician: false,
        actions: [act('자몽과 자몽주스는 피하기', [31])],
      }],
      sections: guideFailed || !diseases.some((x) => x.code === 'I10') ? [] : [
        {
          diseaseCode: 'I10', title: '나트륨 줄이기', goal: '1일 나트륨 2,000mg 이하 (소금 약 5g)',
          actions: [act('국물은 남기고 건더기 위주로 먹기', [31]), act('젓갈 · 장아찌 · 김치 양 줄이기', [31])], conflict: null,
        },
        {
          diseaseCode: 'I10', title: '유산소 운동', goal: '주 5회 이상, 회당 30분 이상',
          actions: [act('빠르게 걷기 하루 30분, 주 5일 이상', [31])], conflict: null,
        },
      ],
      warningSigns: [],
      sources: [{ id: 31, org: '질병관리청 국가건강정보포털', title: '고혈압 생활습관 (예시 자리)' }],
    },
    disclaimer: '의학적 진단 · 처방이 아닌 참고용 안내예요',
  });
}

// R-6: 고른 질환으로 생활습관 부분만 새로 만들어 돌려줌
export function putDiseases(body: Record<string, unknown>) {
  userCodes = Array.isArray(body.diseaseCodes) ? (body.diseaseCodes as string[]) : [];
  return ok((analysisResult().body as { lifestyle: unknown }).lifestyle);
}

// R-5
export function warningDetail(id: number) {
  const w = buildWarnings().find((x) => x.id === id);
  if (!w) return { status: 404, body: { error: { code: 'NOT_FOUND', message: '찾을 수 없어요.' } } };
  return ok({
    id: w.id, severity: w.severity, title: w.title,
    drugs: w.drugs.map((d) => ({ itemName: d.itemName, hospitalName: d.hospitalName, category: null, ingredient: null })),
    explanation: w.summary, reasonOriginal: '(DUR 금기 사유 원문 자리)', source: w.source, judgedBy: 'database',
    actionAdvice: '약을 임의로 끊지 말고, 처방한 의사나 약사와 먼저 상의하세요.',
  });
}

// R-7 지난 기록 목록 (가짜 3건). cursor는 건너뛸 개수, size는 쪽 크기. 지운 기록은 다시 나오지 않음
// 분석 중인 기록은 서버처럼 60초가 지나면 실패로 닫힘 (그 뒤에는 지울 수 있어서 기록 없음 화면까지 볼 수 있음)
const MOCK_STARTED = Date.now();
const deletedRecords = new Set<number>();

function mockRecords() {
  const stalled = Date.now() - MOCK_STARTED > 60_000;
  return [
    stalled
      ? { analysisId: 5003, createdAt: '2026-10-16T10:00:00+09:00', status: 'failed', resultLabel: '분석 실패' }
      : { analysisId: 5003, createdAt: '2026-10-16T10:00:00+09:00', status: 'running', resultLabel: '분석 중' },
    {
      analysisId: 5002, createdAt: '2026-10-10T09:00:00+09:00', status: 'done', hospitals: ['○○내과'],
      drugCount: 5, diseaseNames: ['고혈압', '당뇨'], resultLabel: '확인 필요 2건',
    },
    { analysisId: 5001, createdAt: '2026-09-20T10:00:00+09:00', status: 'failed', resultLabel: '분석 실패' },
  ].filter((r) => !deletedRecords.has(r.analysisId));
}

export function listAnalysesMock(cursor = 0, size = 20) {
  const all = mockRecords();
  const end = cursor + size;
  return ok({ items: all.slice(cursor, end), nextCursor: end < all.length ? String(end) : null });
}

// R-8: 진행 중이면 409
export function deleteAnalysisMock(id: number) {
  const rec = mockRecords().find((r) => r.analysisId === id);
  if (!rec) return { status: 404, body: { error: { code: 'NOT_FOUND', message: '찾을 수 없어요.' } } };
  if (rec.status === 'running') {
    return { status: 409, body: { error: { code: 'ANALYSIS_RUNNING', message: '분석이 끝난 뒤에 지울 수 있어요.' } } };
  }
  deletedRecords.add(id);
  return { status: 204, body: null };
}
