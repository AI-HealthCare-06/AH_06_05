// RG-05-E1에서 고를 수 있는 질환 = 서버 생활습관 안내 자료(팩트 테이블)가 있는 질환 10개 (대표 질병분류기호)
export const PICKABLE_DISEASES: { code: string; name: string }[] = [
  { code: 'I10', name: '고혈압' },
  { code: 'E11', name: '제2형 당뇨병' },
  { code: 'E78', name: '이상지질혈증' },
  { code: 'N18', name: '만성신장병' },
  { code: 'I25', name: '허혈성심질환' },
  { code: 'I63', name: '뇌졸중' },
  { code: 'I48', name: '심방세동' },
  { code: 'J44', name: '만성폐쇄성폐질환' },
  { code: 'M81', name: '골다공증' },
  { code: 'M17', name: '골관절염' },
];
