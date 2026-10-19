# SYSTEM_DESIGN.md

> 프로그램이 어떻게 생겼고 어떤 규칙으로 쓰는지. AI와 팀원이 새 기능을 기존 코드와 같은 모양으로 만들게 하는 파일. 저장소 루트에 둠. 바꿀 때는 PR로 고치고 맨 아래 변경 이력을 남김
> 3회차 멘토링(10/6) "물리적 코드 스타일, 아키텍처, 타입 선언 규칙"에 맞춰 씀. main 코드(10/12) 기준

---

## 1. 전체 구조

```
앱 (Expo SDK 57, frontend/)
  │  HTTPS, JSON, Authorization: Bearer {출입증}
  ▼
nginx (infra/nginx): /api/ 만 FastAPI로 넘김, 나머지는 404, proxy_buffering off
  ▼
FastAPI (app/): 짧은 일은 바로 처리
  ├──▶ PostgreSQL 16 + pgvector: 회원, 처방, 결과, 약, 질병 목록, 챗봇 대화, 벡터
  └──▶ Redis ──▶ arq 워커 (ai_worker/): 오래 걸리는 일
                    ├──▶ CLOVA OCR
                    ├──▶ OpenAI (지금 gpt-4o-mini, 데모 기간 gpt-4o)
                    └──▶ PostgreSQL
```

**설계 이유와 고려한 대안**
| 정한 것 | 이유 | 고려했지만 안 고른 것 |
|---|---|---|
| 서버 한 대(t3.small 2GB)에 docker compose 5개 | 캠프 배포 환경, 비용 | 서비스별 서버 분리 (관리 부담) |
| pgvector (PostgreSQL 안) | 2GB 메모리 절약, DB 하나로 | 별도 벡터 DB |
| arq | 유휴 메모리 약 31MB (Celery 약 49MB, 직접 측정) | Celery |
| OpenAI 직접 호출 | 단계가 단순하고 프롬프트 기록이 쉬움 | LangChain |

## 2. 요청 흐름: 짧은 일과 오래 걸리는 일

| 종류 | 예 | 방식 |
|---|---|---|
| 짧은 일 | 로그인, 결과 조회, 약 이름 검색 | FastAPI가 바로 처리하고 응답 |
| 오래 걸리는 일 | OCR, 분석, 챗봇 답변 | ① FastAPI가 바로 작업을 맡기고 응답 → ② Redis에 맡김 → ③ arq 워커가 처리하고 DB에 저장 → ④ 앱이 결과를 다시 불러옴 |

- 지금 구현 (10/19 기준): OCR(O-1)과 분석(R-1, R-3)은 아직 arq 워커가 아니라 FastAPI 백그라운드 작업(`BackgroundTasks`)으로 서버 안에서 돌립니다. `ai_worker/`에는 예제 작업만 있습니다. 서버가 다시 시작되면 돌던 작업이 끊기므로, 상태를 조회할 때 OCR 작업은 `STALE_JOB_SECONDS`(15분)를 넘기면 실패로 닫고(O-5), 분석은 60초를 넘기면 `TIMEOUT`으로 닫아(R-2) 앱이 다시 시도할 수 있게 해 둡니다. 위 표의 Redis와 arq 워커 방식으로 옮길지는 10/20 멘토링에서 여쭙고 정합니다.

- **시간 제한**
  - 워커 전체 `job_timeout`은 60초 (분석 기준). 챗봇 작업만 `@func(timeout=25)` (함수별 값이 전체 값보다 우선). 앱 시간 초과는 30초
  - arq는 작업을 기본 5번까지 다시 시도함(`max_tries`). 챗봇은 같은 질문에 답이 두 번 만들어지거나 비용이 늘 수 있어 함수별로 줄임 (횟수는 아래 "아직 정하지 않은 것")
- 같은 요청을 다시 보내도 두 번 처리되지 않게 `clientRequestId`를 씀 (챗봇)
- 챗봇 답변은 1단계에서 다 만든 뒤 검사하고 한 번에 보냄. 글자를 차례로 보내는 방식(SSE)은 고도화 때 다시 봄 (10/6, 10/7 회의). nginx는 이미 `proxy_buffering off`라 SSE를 막지 않음

## 3. 서버 (app/): 층 나누기

```
app/
├─ apis/v1/        라우터: URL, 요청 받기, 응답 돌려주기만 (로직 없음)
├─ dtos/           요청과 응답 모양 (Pydantic, JSON은 camelCase)
├─ services/       로직: 규칙, 계산, 외부 API
├─ repositories/   DB 읽기와 쓰기
├─ models/         DB 테이블 (Tortoise ORM)
├─ dependencies/   공통 의존성 (로그인한 사용자 꺼내기)
├─ core/           설정, DB, JWT, 공통 에러, 검증
└─ tests/          기능별 폴더 (auth_apis, user_apis, masters, ocr_models)
```

- 라우터는 기능별 `APIRouter`로 나누고 `app/main.py`에서 모음 (FastAPI 공식 "큰 앱" 구조와 같음)
- 의존 방향은 apis → services → repositories → models 한쪽으로만. 라우터에서 DB를 바로 부르지 않음
- 새 기능 순서: 명세서 → dto → (model, 마이그레이션) → repository → service → router → 시험
- **등록을 잊기 쉬운 곳**: 새 라우터는 `app/apis/v1/__init__.py`의 `v1_routers`에 `include_router`, 새 모델 파일은 `app/core/db/databases.py`의 `TORTOISE_APP_MODELS`에 추가
- 피처 코드가 커지면 `services/chatbot/`, `services/ocr/`처럼 하위 폴더
- 오래 걸리는 일의 실제 처리는 `ai_worker/tasks/`, FastAPI는 맡기기만

## 4. API 규칙 (명세서 0장을 따름)

- 주소는 `/api/v1` + 복수형 명사 kebab-case (`/analyses`, `/habit-goals`), 시간은 한국 시간 ISO 8601
- **에러 모양** (`app/core/errors.py`)
  ```json
  { "error": { "code": "AUTH_INVALID_CREDENTIALS", "message": "이메일 또는 비밀번호가 맞지 않아요.", "field": "password", "detail": {} } }
  ```
  - `message`는 화면에 그대로 띄울 수 있는 쉬운 문장
  - 에러는 `raise AppError(상태, "코드", "문장", field=…, detail=…)`로 냄 (`HTTPException`을 직접 쓰지 않음)
- 그 밖(인증, 목록, 커서)은 명세서가 기준. 이 파일에 옮겨 적지 않음 (두 곳이 어긋나지 않게)

## 5. 보안과 개인정보

| 규칙 | 근거 |
|---|---|
| 남의 데이터는 `404`. 데이터를 다루는 모든 함수에서 "이 사용자의 것인지" 확인하고, 이 확인을 시험으로 남김 | OWASP API 보안 1위, 객체 단위 권한 누락(BOLA). 다른 사람의 ID로 바꿔 요청하는 공격 |
| 출입증과 재발급권을 서로 바꿔 쓰지 못하게 토큰 종류를 검사 (`type` 확인, #77에서 구현됨) | JWT 모범 사례 RFC 8725: 종류가 다른 JWT는 검증 규칙이 서로 배타적이어야 함 |
| 출입증 60분, 재발급권 14일. 앱은 재발급권을 `expo-secure-store`(iOS 키체인, Android Keystore)에 저장 | API 명세서 A-2, A-4, Expo SecureStore 문서 |
| 건강 정보는 민감정보: 가입 때 다른 동의와 따로 동의받고, 분실이나 유출이 없게 안전 조치 → OCR 원문은 저장하지 않고(10/15 결정, `docs/design/ocr_mask.md`), 저장하는 약 이름과 복약 안내 문장은 마스킹 | 개인정보 보호법 제23조 |
| 원본 사진은 저장하지 않음 (OCR 뒤 바로 지움) | 민감정보 최소 처리 |
| 비밀값은 환경 변수(`envs/`, git 제외)로만, 코드에 쓰지 않음 | 12-Factor App "설정은 환경 변수에" |
| 동의하지 않은 사용자도 챗봇은 쓰되 일반 정보만 답함 (REQ-133) | 요구사항 v1.5 |

## 6. 이름과 타입 규칙

| 대상 | 규칙 | 예 |
|---|---|---|
| 파이썬 변수, 함수, 파일 | snake_case | `normalize_name`, `drug_names.py` |
| 파이썬 클래스 | PascalCase | `AuthService`, `DrugProduct` |
| JSON 칸 | camelCase (`CamelModel`이 자동 변환) | `birthYear`, `refreshToken` |
| DB 테이블과 칸 | snake_case, 테이블은 복수형 | `prescription_items.match_status` |
| 상태 값 | `StrEnum` + 소문자 | `MatchStatus.NEEDS_CONFIRM = "needs_confirm"` |
| TypeScript | 컴포넌트 PascalCase, `@/` 경로 | `ChatLauncherProvider`, `@/shared/theme` |

- 파이썬 함수는 입력과 출력 타입을 모두 적고, `Any`는 피함. 요청과 응답은 dict 대신 dto 모델
- 파이썬은 3.13으로 실행하고(`requires-python >= 3.13`, Dockerfile, CI), Ruff 문법 기준은 3.12(`target-version`). 앱은 TypeScript `strict`, `any` 금지
- 타입 검사: 앱은 `npm run typecheck`. 서버 mypy는 개발 패키지와 `scripts/ci/check_mypy.sh`에 있지만 설정과 CI에는 아직 없음

## 7. 데이터

- 공공데이터(약제급여목록, 상병마스터, 식약처 허가정보, DUR)는 미리 DB에 넣고 요청 때 외부 API를 부르지 않음. 원본은 git에 올리지 않음 (`docs/data/SOURCES.md`)
- 안전성 판정은 DB 조회로만 하고, AI는 판정하지 않음
- 약 이름 맞추기는 `app/services/drug_names.py` 하나로 (OCR, 약 이름 검색, 챗봇 공용)
- 회원 정보는 최소 (이메일, 출생연도, 성별, 닉네임)

## 8. 앱 (frontend/)

```
frontend/src/
├─ app/          화면 경로 (Expo Router): (tabs)/ 홈, 실천, 내정보 / chat 챗봇 창(모달)
├─ features/     피처별 (common, ocr, rag, chatbot, challenge)
└─ shared/       theme, ui, copy, api, storage
```

- 화면 규칙은 [DESIGN.md](DESIGN.md), 색과 크기 값은 `shared/theme`에서만 가져다 씀
- 서버가 준비되기 전에는 명세서 모양의 가짜 응답을 씀 (`EXPO_PUBLIC_USE_MOCK=true`)
- `EXPO_PUBLIC_`로 시작하는 값은 앱 안에 그대로 들어가므로 비밀값을 넣지 않음

## 9. 시험과 검사

- 서버: pytest + pytest-asyncio, 시험용 PostgreSQL (CI도 `pgvector/pgvector:pg16-trixie`)
- 시험 이름은 확인하는 내용이 드러나게 (`test_login_locked_after_five_failures`)
- 권한 시험 필수: "다른 사용자의 ID로 요청하면 404"
- AI 답변처럼 매번 결과가 다른 것은 규칙 부분만 시험으로 고정하고, AI 부분은 골든셋(`docs/testing/golden_set.md`) 결과 표로 남김
- **커밋 전 자동 검사** (`.pre-commit-config.yaml`): 줄 끝 공백, 파일 끝 줄바꿈, yaml과 toml 문법, 병합 충돌 표시, 1MB가 넘는 새 파일, 비밀키, Ruff 검사와 포맷(CI와 같은 0.16.10), `frontend/`가 바뀌면 앱 타입 검사. 처음 한 번 각자 `uv run pre-commit install`
- **PR 검사** (CI): Ruff 검사와 포맷, pytest. 초록색이어야 병합

---

### 아직 정하지 않은 것
- [ ] mypy를 pre-commit이나 CI에 넣을지
- [ ] 챗봇 작업의 arq 재시도 횟수 (제안: 1~2번)
- [ ] 레코드 ID를 순서 숫자(지금) 그대로 둘지. OWASP는 예측하기 어려운 ID를 권하지만, 모든 함수에서 권한을 확인하면 숫자 ID도 괜찮음
- [ ] Ruff에 보안 규칙 `S`, 비동기 실수 규칙 `ASYNC`를 더할지 (지금 코드에서 `S`는 110건, 대부분 시험 코드의 `assert`와 시험용 비밀번호라 `app/tests`는 빼야 함. `ASYNC`는 0건)

## 변경 이력

| 날짜 | 내용 | 작성 |
|---|---|---|
| 2026-10-12 | 첫 버전 | 이수인 |
