// RG-05-E1에서 고를 수 있는 질환 = 서버 생활습관 안내 자료(팩트 테이블)가 있는 질환 10개 (대표 질병분류기호)
// id는 내 정보 질환 id(팩트표 id)라 내 정보의 질환을 같은 질환으로 찾을 때 씀
export const PICKABLE_DISEASES: { id: string; code: string; name: string }[] = [
  { id: 'HTN', code: 'I10', name: '고혈압' },
  { id: 'DM2', code: 'E11', name: '제2형 당뇨병' },
  { id: 'DLP', code: 'E78', name: '이상지질혈증' },
  { id: 'CKD', code: 'N18', name: '만성신장병' },
  { id: 'IHD', code: 'I25', name: '허혈성심질환' },
  { id: 'STROKE', code: 'I63', name: '뇌졸중' },
  { id: 'AF', code: 'I48', name: '심방세동' },
  { id: 'COPD', code: 'J44', name: '만성폐쇄성폐질환' },
  { id: 'OP', code: 'M81', name: '골다공증' },
  { id: 'OA', code: 'M17', name: '골관절염' },
];
