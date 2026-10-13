// RG-05-E1에서 고를 수 있는 질환 (생활습관 안내를 갖고 있는 질환만, 지금은 3개 — 서버 안내 자료와 맞춰 늘릴 것)
export const PICKABLE_DISEASES: { code: string; name: string }[] = [
  { code: 'I10', name: '고혈압' },
  { code: 'E11', name: '2형 당뇨병' },
  { code: 'E78', name: '이상지질혈증' },
];
