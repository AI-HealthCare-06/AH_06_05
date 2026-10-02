// 실제 DUR 점검 — 로컬 공공데이터(심평원 약제급여목록 · DUR m.db · 효능군중복)에서 뽑은 dur.json 사용
// LLM을 거치지 않고 DB 조회로만 판정 (NFR-032)
import raw from './data/dur.json';

type Product = [string, string, string, string, string, string, string]; // edi, 제품명, 주성분코드, 성분명, 업체, 전문/일반, 식약분류
const D = raw as unknown as {
  meta: { source: string };
  products: Product[];
  reasons: string[];
  interactions: Record<string, [number, string]>;
  exceptions: Record<string, string[]>;
  elderly: Record<string, [number, number]>;
  ageLimit: Record<string, [string, string, string, number]>;
  efficacy: Record<string, [string, string]>;
};

export const DUR_SOURCE = D.meta.source;
const byEdi = new Map(D.products.map((p) => [p[0], p]));

export type Drug = { edi: string; name: string; ingr: string; ingrName: string; entp: string; kind: string; cls: string };
const toDrug = (p: Product): Drug => ({ edi: p[0], name: p[1], ingr: p[2], ingrName: p[3], entp: p[4], kind: p[5], cls: p[6] });

export function getDrug(edi: string): Drug | undefined {
  const p = byEdi.get(edi);
  return p ? toDrug(p) : undefined;
}

// 화면에 보여줄 짧은 이름: "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)" → "노바스크정5밀리그람"
export function shortName(name: string) {
  return name.split('_(')[0].replace(/\(.*\)$/, '').trim();
}
export function ingredientKo(name: string) {
  const m = name.split('_(')[0].match(/\(([^)]+)\)/);
  return m ? m[1] : '';
}

export function searchDrugs(q: string, limit = 20): Drug[] {
  const k = q.replace(/\s/g, '');
  if (k.length < 2) return [];
  const out: Product[] = [];
  for (const p of D.products) {
    if (p[1].replace(/\s/g, '').includes(k)) {
      out.push(p);
      if (out.length > 300) break;
    }
  }
  out.sort((a, b) => Number(!a[1].startsWith(k)) - Number(!b[1].startsWith(k)) || a[1].length - b[1].length);
  return out.slice(0, limit).map(toDrug);
}

export type Severity = 'danger' | 'caution' | 'info';
export type Warning = {
  id: string;
  type: 'interaction' | 'duplicate_ingredient' | 'duplicate_efficacy' | 'elderly' | 'age' | 'polypharmacy';
  severity: Severity;
  title: string;
  summary: string; // 템플릿 문장 (AI 생성 아님)
  reason: string; // DB 원문
  source: string;
  noticeDate?: string;
  drugs: { edi: string; name: string; hospital?: string }[];
};

export const CHECKED_ITEMS = [
  { type: 'interaction', label: '함께 먹으면 안 되는 약' },
  { type: 'duplicate', label: '같은 성분 · 같은 효과 중복' },
  { type: 'elderly_age', label: '어르신 주의 · 나이 금기' },
  { type: 'polypharmacy', label: '여러 약 함께 복용' },
];

const fmtDate = (d?: string) => (d && d.length === 8 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}` : undefined);

export function checkSafety(items: { edi: string; hospital?: string }[], birthYear: number, now = 2026): Warning[] {
  const ds = items.map((i) => ({ ...getDrug(i.edi)!, hospital: i.hospital })).filter((d) => d.edi);
  const age = now - birthYear;
  const w: Warning[] = [];
  const nm = (d: Drug) => shortName(d.name);

  for (let i = 0; i < ds.length; i++) {
    for (let j = i + 1; j < ds.length; j++) {
      const a = ds[i], b = ds[j];
      const [x, y] = [a.ingr, b.ingr].sort();
      const hit = D.interactions[`${x}|${y}`];
      if (hit) {
        const exc = D.exceptions[`${x}|${y}`] || [];
        if (!exc.includes(a.edi) && !exc.includes(b.edi)) {
          w.push({
            id: `int-${i}-${j}`, type: 'interaction', severity: 'danger', title: '함께 먹으면 안 되는 약',
            summary: `함께 먹으면 부작용 위험이 커질 수 있어요.`,
            reason: D.reasons[hit[0]] || '금기 사유 원문 없음', source: '식약처 병용금기 고시', noticeDate: fmtDate(hit[1]),
            drugs: [a, b].map((d) => ({ edi: d.edi, name: nm(d), hospital: d.hospital })),
          });
        }
      }
      if (a.ingr.slice(0, 4) === b.ingr.slice(0, 4)) {
        w.push({
          id: `dup-${i}-${j}`, type: 'duplicate_ingredient', severity: 'caution', title: '같은 성분이 겹쳐요',
          summary: `이름은 다르지만 같은 ${categoryOf(a.cls)}이에요.${a.hospital && b.hospital && a.hospital !== b.hospital ? ' 두 병원에서 처방받으셨어요.' : ''}`,
          reason: `주성분 코드 앞 4자리(성분)가 같음: ${a.ingr} · ${b.ingr}`, source: '식약처 동일성분 중복 정보 (프로토타입은 성분 코드로 근사)',
          drugs: [a, b].map((d) => ({ edi: d.edi, name: nm(d), hospital: d.hospital })),
        });
      } else {
        const ea = D.efficacy[a.edi], eb = D.efficacy[b.edi];
        if (ea && eb && ea[0] === eb[0]) {
          w.push({
            id: `eff-${i}-${j}`, type: 'duplicate_efficacy', severity: 'caution', title: '같은 효과 약이 겹쳐요',
            summary: `${nm(a)}과(와) ${nm(b)}은(는) 같은 효과(${ea[1]})를 내는 약이에요.`,
            reason: `효능군 중복 점검 코드 ${ea[0]} 동일`, source: '심평원 효능군중복 품목리스트 (2026-09)',
            drugs: [a, b].map((d) => ({ edi: d.edi, name: nm(d), hospital: d.hospital })),
          });
        }
      }
    }
  }
  for (const d of ds) {
    const e = D.elderly[d.ingr];
    if (e && age >= e[0]) {
      w.push({
        id: `eld-${d.edi}`, type: 'elderly', severity: 'caution', title: '어르신이 조심할 약',
        summary: `${e[0]}세 이상은 조심해서 드셔야 하는 약이에요.`,
        reason: D.reasons[e[1]], source: '식약처 노인주의 의약품', drugs: [{ edi: d.edi, name: nm(d), hospital: d.hospital }],
      });
    }
    const l = D.ageLimit[d.ingr];
    if (l && age < Number(l[0])) {
      w.push({
        id: `age-${d.edi}`, type: 'age', severity: 'danger', title: '나이 때문에 먹으면 안 되는 약',
        summary: `${nm(d)}은(는) ${l[0]}세 미만에게 쓰지 않는 약이에요.`,
        reason: D.reasons[l[3]] || '', source: '식약처 연령금기 고시 (DUR)', drugs: [{ edi: d.edi, name: nm(d), hospital: d.hospital }],
      });
    }
  }
  if (ds.length >= 5) {
    w.push({
      id: 'poly', type: 'polypharmacy', severity: 'info', title: '여러 약 함께 복용',
      summary: `지금 ${ds.length}가지 약을 함께 드시고 있어요. 약사에게 한 번 전체 점검을 받아 보세요.`,
      reason: '5종 이상 동시 복용 (기준 개수는 팀 확인 필요 · REQ-049)', source: '서비스 기준', drugs: ds.map((d) => ({ edi: d.edi, name: nm(d) })),
    });
  }
  const order = { danger: 0, caution: 1, info: 2 };
  return w.sort((a, b) => order[a.severity] - order[b.severity]);
}

// 식약분류 → 쉬운 말 (복약 안내 "무엇에 쓰나요" — 실제 서비스는 허가정보 기반 AI 생성)
const CLASS_PURPOSE: Record<string, string> = {
  '214': '혈압을 낮춰요', '213': '몸의 물을 빼서 혈압을 낮춰요', '396': '혈당을 낮춰요', '218': '콜레스테롤을 낮춰요',
  '114': '통증과 열을 줄여요', '232': '위를 보호해요', '614': '세균 감염을 치료해요', '618': '세균 감염을 치료해요',
  '339': '피가 굳지 않게 도와요', '222': '기침을 줄여요', '141': '콧물 · 알레르기를 줄여요', '211': '심장을 도와요',
  '219': '피가 굳어 혈관이 막히는 것을 막아요', '619': '세균 감염을 치료해요', '117': '불안 · 긴장을 줄여요',
};
const CLASS_NAME: Record<string, string> = { '214': '혈압약', '213': '혈압약', '396': '당뇨약', '218': '콜레스테롤약', '219': '혈전 예방약', '114': '진통제', '614': '항생제', '618': '항생제', '619': '항생제', '117': '신경안정제', '232': '위장약', '222': '기침약' };
export const categoryOf = (cls: string) => CLASS_NAME[cls] || '약';
// 주의할 점 예시 (실제 서비스는 허가정보 RAG로 생성)
const CAUTION: [RegExp, string][] = [[/암로디핀/, '어지러울 수 있으니 천천히 일어나세요'], [/메트포르민/, '술을 많이 마시면 위험할 수 있어요'], [/심바스타틴/, '근육이 아프거나 힘이 빠지면 의료진에게 알려 주세요'], [/아스피린/, '멍이 잘 들거나 피가 잘 멈추지 않으면 알려 주세요'], [/클래리스로마이신/, '정해진 기간 동안 끝까지 드세요'], [/디아제팜/, '졸릴 수 있으니 운전과 술은 피하세요']];
export const cautionOf = (name: string, ingrName: string) => CAUTION.find(([r]) => r.test(name + ingrName))?.[1];
export const purposeOf = (cls: string) => CLASS_PURPOSE[cls] || '처방받은 목적을 약사에게 확인해 주세요';
