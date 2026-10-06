// 화면 문구 — 뼈대 · 로그인에 쓰는 것부터 (프로토타입 화면 · 챗봇 설계 메모 6-1 항목 확정 문구)
// 화면을 만들 때 그 화면 문구를 여기에 이어서 옮김

export const copy = {
  appName: '[서비스명]', // 이름 확정 전 자리표시
  common: {
    back: '뒤로',
    cancel: '취소',
    retry: '다시 시도',
    goHome: '홈으로',
    disclaimer: '의학적 진단 · 처방이 아닌 참고용 안내예요',
  },
  nav: {
    home: '홈',
    challenge: '실천',
    me: '내정보',
    menu: '주 메뉴',
  },
  // CM-03-E1 처음 홈 — 큰 버튼 (와이어프레임 HomeEmpty)
  home: {
    heroTitle: '처방전이나 약봉투를\n찍어 보세요',
    heroBody: '먹는 약을 함께 점검하고 복약 안내를 만들어 드려요',
    capture: '처방전 찍기',
  },
  preparing: '준비 중인 화면이에요',
  // CM-01 로그인 · CM-01-E1 로그인 실패 · CM-01-E2 로그인 잠김
  login: {
    title: '로그인',
    tagline: '처방전을 찍으면 약 정보와 주의사항을 알려드려요',
    email: '이메일',
    emailPlaceholder: 'example@email.com',
    password: '비밀번호',
    passwordPlaceholder: '비밀번호 입력',
    submit: '로그인',
    noAccount: '아직 계정이 없으신가요?',
    signup: '회원가입',
    failed: (n: number, max: number) => `이메일 또는 비밀번호가 맞지 않아요. (${n} / ${max}회)`,
    lockWarning: (max: number, minutes: number) => `${max}번 틀리면 ${minutes}분 동안 로그인할 수 없어요.`,
    lockedTitle: '로그인이 잠시 잠겼어요',
    lockedChip: '잠김',
    lockedBody: (max: number, minutes: number) => `비밀번호를 ${max}번 틀려서 ${minutes}분 동안 로그인할 수 없어요.`,
    lockedLeft: (mmss: string) => `남은 시간  ${mmss}`,
    lockedSubmit: (mmss: string) => `로그인  (${mmss} 후 가능)`,
  },
  // CM-08 연결 오류
  network: {
    title: '인터넷 연결이 불안정해요',
    body: '연결 상태를 확인하고 다시 시도해 주세요.',
  },
  chatbot: {
    // 플로팅 버튼 — 글자 없음, 스크린 리더 이름만
    launcher: 'AI 챗봇 열기',
    launcherNew: 'AI 챗봇 열기, 새 답변 있음',
    close: '챗봇 닫기',
    title: 'AI 챗봇',
    recommended: [
      '약은 언제 먹는 게 좋나요?',
      '같이 먹으면 안 되는 음식이 있나요?',
      '약 먹는 동안 운동해도 되나요?',
    ],
    attachNotice: '※ 처방전 · 약봉투는 홈 화면에서 찍어 올려 주세요.', // CB-04
  },
  // CM-03-E2 첫 사용 안내 (코치 마크 2단계, 챗봇 → 처방전 찍기)
  coachMark: {
    chatbot: [
      '궁금한 점은 여기를 눌러 물어보세요',
      '약이나 생활습관에 대해 답해 드려요',
      '새 답이 오면 버튼에 빨간 점이 생겨요',
    ],
    capture: ['여기를 누르면 바로 찍을 수 있어요', '찍은 사진으로 먹는 약을 함께 확인해 드려요'],
    skip: '건너뛰기',
    next: '다음',
    start: '시작하기',
  },
} as const;
