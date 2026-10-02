// 9/28 오후 미팅 안건 (data/회의안건_0928_오후.md) — 화면별로 같이 보면서 정할 것
export type Agenda = { no: number; title: string; body: string; who: string };

const A: Record<number, Agenda> = {
  1: { no: 1, title: '앱 vs 웹(PWA)', body: '지금 이 프로토타입은 Expo(앱 · 웹 둘 다 가능). 카메라 · 권한 · 설정 열기 방식이 앱/웹에 따라 달라짐', who: '전원 · 수인' },
  3: { no: 3, title: 'MVP 범위', body: '이 프로토타입 흐름 = MVP 제안 (업로드 → OCR 확인 → 분석 → 결과 → 결과 연계 챗봇 + 실천 목표 선택 · 체크)', who: '전원' },
  4: { no: 4, title: '포인트 MVP 포함', body: '포인트 · 달성 현황을 MVP에 넣을지 (요구사항 제안은 후순위, 06 페이지는 MVP)', who: '성규' },
  6: { no: 6, title: '파기 범위', body: '탈퇴 = 전부 삭제 / 동의 철회 = 건강 정보 삭제, 실천 기록 · 포인트 유지 / 기록 삭제 = 실천 목표 · 포인트 유지', who: '전원' },
  7: { no: 7, title: '권한 안내 방식 통일', body: '카메라(OC-01): OS 팝업 바로 → 거부 시 안내 / 마이크(CB-05-P): 이유 안내 화면 먼저 → OS 팝업. 하나로', who: '채연 · 수인' },
  9: { no: 9, title: 'OCR 비동기', body: '[인식 시작] → "읽는 중" 대기 → 결과. O-1 202 + O-5 작업 조회 구조', who: '채연' },
  10: { no: 10, title: '기본 카메라 / 필터 카메라', body: '구형 Android(10 이하)는 필터 앱이 열릴 수 있음 → 시스템 카메라 직접 지정. E4 화면은 축소', who: '채연 · 수인' },
  11: { no: 11, title: '갤러리 권한', body: '시스템 사진 선택기는 권한 불필요 → OC-01-E5 · REQ-019 삭제안', who: '채연 · 수인' },
  12: { no: 12, title: '직접 입력한 약 저장', body: '처방전 없이 약만 넣는 API(/prescriptions/manual) 필요', who: '채연 · 형준' },
  14: { no: 14, title: 'OC-02 확인 단계', body: '1순위 미리 선택 + [이 약이 맞아요]. 헷갈리기 쉬운 약은 미리 선택하지 않는 예외', who: '채연' },
  16: { no: 16, title: '답변 종류 8가지', body: 'API · ERD는 3가지, Figma 정책은 8가지(normal · clarify · partial · no_evidence · refer · emergency · crisis · error)', who: '수인 · 형준' },
  20: { no: 20, title: '챗봇 응답 시간', body: '전체 API P95 3초 vs 답변 생성 시간. 챗봇은 "첫 글자 3초" 같은 별도 기준', who: '수인 · 성규' },
  21: { no: 21, title: '긴급 · 자해 감지', body: '키워드 규칙 우선 (놓치지 않는 쪽). "가슴이 조여요" · "사라지고 싶어요"로 직접 확인', who: '수인 · 형준' },
  24: { no: 24, title: 'RW-03 · 04 · 05', body: '이 프로토타입은 "한 화면 + 상태 3개"로 구현 (Figma는 프레임 3개). 체크해 보면서 결정', who: '성규 · 수인' },
  25: { no: 25, title: '추천 개수', body: '추천 2~4개 vs 최대 3개 추천 → 하나로', who: '성규' },
  26: { no: 26, title: '연속 실천일 기준', body: '"하루 전부 완료" vs "하루 1개 이상 완료"', who: '성규' },
  27: { no: 27, title: '완료 취소', body: '체크형은 취소 불가, 수량형만 수정 허용할지', who: '성규' },
  29: { no: 29, title: '칼륨 권고', body: '이뇨제 · ACE억제제/ARB는 "의료진 확인" 안내만, 실천 목표로 안 만듦', who: '형준 · 성규' },
  30: { no: 30, title: '생활습관 출처', body: '지금은 기관명만 있음 → 문서명 · 판 · 발행일 · URL 채우기', who: '형준' },
  31: { no: 31, title: '중복 촬영 병합', body: '같은 처방전을 두 번 찍으면 "같은 성분 중복" 경고가 잘못 뜸 → 서버에서 합치기', who: '형준 · 채연' },
};

export const SCREEN_AGENDA: Record<string, number[]> = {
  login: [1, 6],
  home: [3, 4],
  capture: [9, 10, 11, 7, 31],
  recognize: [14, 12],
  analyzing: [9],
  safety: [31],
  med: [30],
  life: [29, 30, 25],
  warning: [16],
  chat: [16, 21, 20],
  goals: [25, 29],
  today: [24, 26, 27, 4],
  weekly: [4, 26],
  me: [6, 1],
};

export const agendaFor = (key: string) => (SCREEN_AGENDA[key] || []).map((n) => A[n]).filter(Boolean);
