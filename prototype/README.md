# 5팀 프로토타입 (회의용)

Figma 통합 와이어프레임 · 요구사항 · API 명세를 바탕으로 만든 Expo 앱입니다. 화면을 보면서 회의하려고 만든 것이라 실제 서비스 코드는 아닙니다. 실제 개발 코드로 이어 쓸지는 팀에서 정합니다.

- 배포본: https://ai-healthcare-06.github.io/AH_06_05/ (`gh-pages` 브랜치)
- 기준: Figma 화면 문구 (9/29 갱신), 요구사항 v1.4 · API v1.2 · 화면 번호 통합표 v0.4
- 만든 사람: 이형준 (9/30 수료로 인수인계)

## 변경 이력

| 버전 | 일자 | 위치 | 현행 (As-Is) | 개정 (To-Be) | 담당 |
|---|---|---|---|---|---|
| v1.0 | 2026-09-28 | 전체 | (없음) | 최초 작성 — 회의용 프로토타입, gh-pages 배포 | 이형준 |
| v1.1 | 2026-09-29 | 전체 화면 | 요구사항 · API 문서를 보고 구성한 화면 (회원가입 등 누락) | Figma 각 화면 문구 그대로 다시 맞춤 (회원가입 · 지난 기록 · 내정보 등 추가) | 이형준 |
| v1.2 | 2026-09-30 | 저장 위치 · 배포 · 데이터 | 소스는 형준 로컬에만 있음, 배포는 수동으로 경로 수정, dur.json 만드는 스크립트 없음 | 팀 저장소 `prototype/`에 소스 추가, `scripts/build_pages.sh` · `scripts/build_dur_json.py` 추가 | 이형준 |

## 무엇이 진짜이고 무엇이 가짜인가

| 부분 | 상태 |
|---|---|
| 약 이름 검색 | 진짜 — 심평원 약제급여목록 2026-09-01 (먹는 약 17,450개) |
| 안전성 점검 (병용금기 · 동일성분 · 효능군 중복 · 노인주의 · 연령금기 · 다제약물) | 진짜 — 심평원 DUR m.db (2026-08-24) · 효능군중복 목록 (2026-09). LLM 없이 DB 조회로만 판정 (`src/dur.ts`) |
| 생활습관 · 약-생활수칙 연결 | 진짜 — 팩트 테이블 v0.2 (`src/data/facts.json`) |
| OCR | 가짜 — 어떤 사진을 올려도 샘플 처방전 2장 결과 (`src/scenario.ts`) |
| 복약 안내문 · 챗봇 답변 | 가짜 — 규칙 · 고정 문구 (답변 종류 8가지는 Figma 05 정책 기준) |
| 로그인 · 포인트 누적 · 요일 기록 | 가짜 |

화면 오른쪽 위 노란 배지 = Figma 화면 ID, 오른쪽 아래 "안건 n" = 그 화면에서 정할 9/28 미팅 안건 (`src/agenda.ts`).

## 파일 구성

```
prototype/
├─ App.tsx              화면 전환 (라우팅 라이브러리 없이 상태로)
├─ src/
│  ├─ screens/          Login · Home · Capture(OC-01) · Recognize(OC-02) · Analyzing(RG-01) · Result(RG-02~05) · Chat(CB) · Reward(RW) · Me(CM-05~07 · MY-S1) · Exception
│  ├─ dur.ts            DUR 점검 로직
│  ├─ scenario.ts       샘플 처방전 · 가짜 OCR 결과
│  ├─ store.tsx         앱 상태
│  ├─ theme.ts · ui.tsx 톤앤매너 색 · 글자 · 공통 컴포넌트
│  ├─ agenda.ts         화면별 회의 안건
│  └─ data/             dur.json (DUR 가공 데이터) · facts.json (생활습관 팩트 테이블)
├─ scripts/
│  ├─ build_dur_json.py dur.json 다시 만들기
│  └─ build_pages.sh    gh-pages 배포 파일 만들기
└─ web/pages-index.html 배포용 index.html (가운데 휴대폰 폭으로 보이게)
```

## 실행

```bash
cd prototype
npm install
npx expo start
```

- 같은 와이파이의 휴대폰: Expo Go 앱 → QR 찍기 (카메라 · 갤러리가 실제로 열림). Expo Go는 SDK 57 버전이어야 함
- 브라우저: `npx expo start --web` → http://localhost:8081
- 다른 네트워크의 팀원에게 보여 줄 때는 아래 배포본 링크를 씀

## 데이터 다시 만들기

`src/data/dur.json`은 공개 원본 3개로 만듭니다. 원본은 git에 올리지 않고 `docs/data/SOURCES.md`의 출처에서 받아 `data/raw/`에 둡니다 (m.db 포함 모두 공개 파일).

```bash
pip install openpyxl
python3 prototype/scripts/build_dur_json.py --raw data/raw --out prototype/src/data/dur.json
```

- 필요한 파일: `data/raw/hira/약제급여목록및급여상한금액표_(2026.9.1.)_공개용(비인가자) 1부.xlsx` · `data/raw/dur/m.db` · `data/raw/dur/게시_효능군중복 품목리스트_2609.xlsx`
- `--today 20261001`처럼 기준일을 바꾸면 그날 적용 중인 규칙만 들어감 (기본 20260928)
- 원본 월이 바뀌면 스크립트 안 파일 이름도 바꿈

생활습관 팩트 테이블을 고쳤으면 `data/lifestyle_guide_facts.json`을 `src/data/facts.json`으로 복사합니다.

## 배포 (gh-pages)

```bash
cd prototype
sh scripts/build_pages.sh
```

`pages/`에 `index.html` · `js/app.js` · `favicon.ico`가 생깁니다. 이 세 파일을 `gh-pages` 브랜치 최상위에 덮어써서 올립니다.

```bash
git fetch origin gh-pages
git worktree add ../gh-pages-work gh-pages
cp -R pages/. ../gh-pages-work/
cd ../gh-pages-work
git add -A
git commit -m "chore: 프로토타입 배포"
git push origin gh-pages
cd - && git worktree remove ../gh-pages-work
```

1~2분 뒤 배포본 링크에 반영됩니다. 저장소 Settings → Pages에서 `gh-pages` 브랜치 / root로 설정돼 있습니다.

## 고칠 때

- 화면은 Figma 각 `col` 프레임 [1] 실제 화면 문구 그대로 맞춥니다. 문서만 보고 화면을 새로 구성하지 않습니다.
- Figma와 다르게 바꾸려면 Figma · 요구사항을 먼저 고칩니다.
- 수정하면 위 변경 이력에 한 줄 추가합니다.
- 팀원 피드백으로 받은 수정 목록: 챗봇은 PR #3 `CB/DESIGN.md` 10번(부록), OCR은 채연님 "OCR 프로토타입 업그레이드 목록"(9/28).
