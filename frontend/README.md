# frontend — 5팀 앱 (Expo)

고령 사용자 · 보호자용 복약 안내 앱의 화면 코드. 서버는 저장소 루트의 `app/` (FastAPI)

- Expo SDK 57 · Expo Router · TypeScript
- 화면 기준: 화면 번호표 `docs/planning/screen_id_table.md` · API 명세서 `docs/planning/`
- 챗봇 설계: `docs/design/chatbot_frontend.md`

## 실행

```bash
cd frontend
npm install
cp .env.example .env        # 값 확인 (.env는 커밋하지 않음)
npx expo start              # 휴대폰 Expo Go 앱으로 QR 찍기, 웹은 w
```

- 패키지 추가는 `npx expo install <이름>` (SDK에 맞는 버전으로 설치됨)
- 타입 검사: `npm run typecheck`
- 서버가 준비되기 전에는 `EXPO_PUBLIC_USE_MOCK=true`로 API 명세서 응답 모양의 가짜 응답을 씀

## 폴더

```
frontend/src/
├─ app/            화면 경로 (Expo Router) — 파일 하나가 화면 하나
├─ features/       피처별 화면 부품 · API 호출
│  ├─ common/      공통 (로그인 · 회원가입 · 홈 · 내정보) — CM · MY
│  ├─ ocr/         OCR — OC
│  ├─ rag/         분석 결과 — RG
│  ├─ chatbot/     챗봇 (플로팅 버튼 · 챗봇 창) — CB
│  └─ challenge/   챌린지 — RW
└─ shared/         여러 피처가 같이 쓰는 것
   ├─ theme/       색 · 글자 · 간격 (톤앤매너)
   ├─ ui/          공통 버튼 · 카드
   ├─ api/         API 호출 함수 · 토큰 처리
   ├─ storage/     기기 저장 (토큰은 expo-secure-store)
   └─ copy/        화면 문구
```

가져다 쓸 때는 `@/shared/theme`처럼 `@/`로 시작 (`src/` 기준)
