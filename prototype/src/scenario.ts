// OCR · AI 안내문은 아직 연결 전이라 샘플 인식 결과를 씀. 약 이름 · 성분 · DUR 판정은 실제 데이터.
import facts from './data/facts.json';
import { Drug, ingredientKo, shortName } from './dur';

export type ItemStatus = 'auto' | 'needs_confirm' | 'unmatched' | 'user_confirmed' | 'excluded';
export type RxItem = {
  id: string;
  rxId: string;
  raw: string; // 처방전에 적힌 이름 (OCR 원문)
  edi?: string;
  status: ItemStatus;
  candidates?: string[]; // 후보 edi (1순위부터)
  dose: string;
  timing: string;
  days: number;
};
export type Rx = { id: string; hospital: string; date: string; docType: 'prescription' | 'pill_bag'; diseases: string[] };

export function sampleRecognition(): { rxs: Rx[]; items: RxItem[] } {
  // Figma OC-02 · RG-02 예시와 같은 조합 (○○내과 + △△의원). 약 코드는 실제 약제급여목록
  return {
    rxs: [
      { id: 'rx1', hospital: '○○내과', date: '2026-09-20', docType: 'prescription', diseases: ['I10', 'E11', 'E78'] },
      { id: 'rx2', hospital: '△△의원', date: '2026-09-26', docType: 'prescription', diseases: ['J20'] },
    ],
    items: [
      { id: 'i1', rxId: 'rx1', raw: '노바스크정 5mg', edi: '073400360', status: 'auto', dose: '1알', timing: '1일 1회 · 아침 식후', days: 30 },
      { id: 'i2', rxId: 'rx1', raw: '메트____정', status: 'needs_confirm', candidates: ['641600390', '664602800', '651200020'], dose: '1알', timing: '1일 2회 · 아침 · 저녁 식후', days: 30 },
      { id: 'i3', rxId: 'rx1', raw: '심바스타틴정 20mg', edi: '623006210', status: 'auto', dose: '1알', timing: '1일 1회 · 저녁 식후', days: 30 },
      { id: 'i4', rxId: 'rx1', raw: '아스피린정 100mg', edi: '642104440', status: 'auto', dose: '1알', timing: '1일 1회 · 아침 식후', days: 30 },
      { id: 'i5', rxId: 'rx2', raw: '암로디핀정 5mg', edi: '649805060', status: 'auto', dose: '1알', timing: '1일 1회 · 아침 식후', days: 7 },
      { id: 'i6', rxId: 'rx2', raw: '클래리스로마이신정 250mg', edi: '649404570', status: 'auto', dose: '1알', timing: '1일 2회 · 아침 · 저녁 식후', days: 7 },
      { id: 'i7', rxId: 'rx2', raw: '디아제팜정 2mg', edi: '651900530', status: 'auto', dose: '1알', timing: '1일 1회 · 자기 전', days: 7 },
      { id: 'i8', rxId: 'rx2', raw: '○○연질캡슐', status: 'unmatched', dose: '1캡슐', timing: '1일 3회 · 식후', days: 7 },
    ],
  };
}
export const SIMILARITY = [92, 78, 61];

// ---------- 생활습관 (lifestyle_guide_facts.json v0.2) ----------
type Fact = {
  id: string; name: string; kcd: string[];
  lifestyle: { category: string; goal: string; actions: string[]; source: string }[];
  medication_link: { drug_class: string; caution: string; advice: string; requires_clinician?: boolean; goal_eligible?: boolean }[];
};
const F = facts as unknown as { diseases: Fact[]; cross_disease_rules: { condition: string; rule: string }[]; disclaimer: string };
export const LIFESTYLE_DISCLAIMER = F.disclaimer;

export function diseasesFor(codes: string[]) {
  return F.diseases.filter((d) => d.kcd.some((k) => codes.some((c) => c.startsWith(k))));
}

function classTokens(cls: string): string[] {
  const head = cls.split('(')[0];
  const inner = (cls.match(/\(([^)]*)\)/)?.[1] || '').split('—')[0];
  return [...head.split(/[·/]/), ...inner.split(/[,·]/)]
    .map((s) => s.replace(/등|제외|계열|\s/g, '').trim())
    .filter((s) => s.length >= 3);
}

export function medicationLinks(drugs: Drug[], diseases: Fact[]) {
  const out: { drug: string; advice: string; caution: string; requiresClinician: boolean; goalEligible: boolean; disease: string }[] = [];
  for (const dis of diseases) {
    for (const m of dis.medication_link) {
      const toks = classTokens(m.drug_class);
      for (const d of drugs) {
        const ko = ingredientKo(d.name) + d.name;
        if (toks.some((t) => ko.includes(t)) && !out.some((o) => o.drug === shortName(d.name) && o.advice === m.advice)) {
          out.push({ drug: shortName(d.name), advice: m.advice, caution: m.caution, requiresClinician: !!m.requires_clinician, goalEligible: m.goal_eligible !== false, disease: dis.name });
        }
      }
    }
  }
  return out;
}

export function conflictsFor(diseases: Fact[]) {
  const names = diseases.map((d) => d.name);
  return F.cross_disease_rules.filter((r) => {
    const parts = r.condition.split('+').map((s) => s.replace('동시 보유', '').trim());
    return parts.every((p) => names.some((n) => n.includes(p) || p.includes(n)));
  });
}

// ---------- 실천 목표 추천 (P-1) ----------
export type Rec = { id: string; title: string; desc: string; reason: string; type: 'check' | 'quantity'; target?: number; unit?: string };
export function recommendations(diseases: Fact[], drugs: Drug[] = []): Rec[] {
  // Figma RW-02 순서: 국물 남기기 · 빠르게 걷기 30분 · 술 마시지 않기(약과 함께) · 식사 거르지 않기
  const recs: Rec[] = [];
  const names = diseases.map((d) => d.id);
  const lbl = (ids: string[]) => diseases.filter((d) => ids.includes(d.id)).map((d) => d.name.replace('제2형 당뇨병', '당뇨')).join(' · ');
  if (names.includes('HTN')) recs.push({ id: 'na', title: '국물 남기기', desc: '하루 소금 5g 이하', reason: '고혈압', type: 'check' });
  const walk = names.filter((n) => ['HTN', 'DM2', 'DLP', 'IHD'].includes(n));
  if (walk.length) recs.push({ id: 'walk', title: '빠르게 걷기 30분', desc: '주 5일 이상', reason: lbl(walk.slice(0, 2)), type: 'quantity', target: 30, unit: '분' });
  const met = drugs.find((d) => /메트포르민/.test(d.name));
  if (met) recs.push({ id: 'alc', title: '술 마시지 않기', desc: `${shortName(met.name).replace(/\d.*$/, '')}을 드시는 동안`, reason: '약과 함께', type: 'check' });
  if (names.includes('DM2')) recs.push({ id: 'meal', title: '식사 거르지 않기', desc: '세 끼를 제때 드세요', reason: '당뇨', type: 'check' });
  // "물 6잔" 같은 일반 목표는 넣지 않음 (심부전 · 신장병 수분 제한)
  return recs;
}
