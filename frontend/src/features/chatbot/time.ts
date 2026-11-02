// 한국 시간 계산 (설계 메모 7-5 항목): 시간대 이름을 쓰지 않고 UTC에 9시간을 더함
const KST_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

const kstDayIndex = (ms: number) => Math.floor((ms + KST_MS) / DAY_MS);

// 다음 한국 자정 (서버 안전 모드 끝 시각과 같음, 명세서 H-8)
export const nextKstMidnight = (now = Date.now()) => (kstDayIndex(now) + 1) * DAY_MS - KST_MS;

// "9월 23일" 과 오늘까지 며칠 지났는지
export function analyzedAt(iso: string, now = Date.now()) {
  const ms = Date.parse(iso);
  const d = new Date(ms + KST_MS);
  return { label: `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`, daysAgo: kstDayIndex(now) - kstDayIndex(ms) };
}

// 오늘 날짜 2026-09-16 (달력, CB-03)
export const kstToday = (now = Date.now()) => new Date(now + KST_MS).toISOString().slice(0, 10);

// "2026-09-16" → "9월 16일"
export const dayLabel = (date: string) => {
  const [, m, d] = date.split('-').map(Number);
  return `${m}월 ${d}일`;
};

// 달력 한 달: 1일 앞 빈칸 수(일요일 0)와 날짜 수. m은 1 ~ 12
export const monthGrid = (y: number, m: number) => ({
  blanks: new Date(Date.UTC(y, m - 1, 1)).getUTCDay(),
  days: new Date(Date.UTC(y, m, 0)).getUTCDate(),
});

// 대화 카드 시각 "오전 9:12"
export function startTime(iso: string) {
  const d = new Date(Date.parse(iso) + KST_MS);
  const h = d.getUTCHours();
  return `${h < 12 ? '오전' : '오후'} ${h % 12 || 12}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
}

// 요청 번호 (명세서 H-1, H-3, H-7 clientRequestId). 설계 메모 7-7은 expo-crypto지만 패키지를 더하지 않고 시각과 난수로 만듦
export const newRequestId = () => `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
