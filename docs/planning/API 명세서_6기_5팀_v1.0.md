# API 명세서 v1.0

**5팀 · 2026. 9. 24 · 작성 이형준(PM)**

## 변경 이력

버전별 요약을 먼저 보고, ▶ 를 눌러 펼치면 **위치 · 현행(As-Is) · 개정(To-Be)** 을 볼 수 있습니다.
API를 바꿀 때마다 버전 요약 한 줄 + 세부 표를 추가하고, **현행에는 바꾸기 전 값을 그대로** 적어 주세요. 프론트 · 백엔드가 같은 버전을 보고 있는지 여기서 확인하세요.

| 버전 | 일자 | 변경 내용 | 담당 |
|---|---|---|---|
| v0.1 | 2026-09-23 | 최초 작성 — 30개 API (공통화면 · 피처2 RAG 와이어프레임, ERD v0.1 기준) | 이형준 |
| v0.2 | 2026-09-23 | 화면 번호를 통합표 기준(CM · OC · RG · CB · RW)으로 변경 | 이형준 |
| v1.0 | 2026-09-24 | 통합 와이어프레임(45개 화면) · ERD v1.0 반영 — 실천 · 보상 API 교체, 챗봇 2개 추가, OCR · 챗봇 응답 보완 | 이형준 |

<details>
<summary><b>v0.2</b> · 2026-09-23 · 화면 번호 통합 — 세부 5건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 전체 / 공통 화면 번호 | `C01` ~ `C08` (예: `C01-E1` 로그인 실패, `C04-E1` 기록 삭제 확인) | `CM-01` ~ `CM-08` (예: `CM-01-E1`, `CM-04-E1`) |
| 전체 / OCR 화면 번호 | `01` · `01-E1` ~ `01-E3` · `02` · `02-E1` | `OC-01` · `OC-01-E1` ~ `OC-01-E3` · `OC-02` · `OC-02-E1` |
| 전체 / RAG 화면 번호 | `04` · `04-E1` · `05-1` · `05-1E` · `05-1D` · `05-2` · `05-3` · `05-3E` | `RG-01` · `RG-01-E1` · `RG-02` · `RG-02-E1` · `RG-03` · `RG-04` · `RG-05` · `RG-05-E1` |
| 전체 / 챗봇 화면 번호 | 영문 프레임 이름 (`Chatbot` · `ChatbotEmpty` · `ChatHistoryCalendar` · `ChatHistoryList` …) | `CB-01` · `CB-01-E1` · `CB-02` · `CB-03` · `CB-04` · `CB-05` |
| 전체 / 실천 · 보상 화면 번호 | `G-01` ~ `G-07` (`G-06` 기록 없음, `G-07` 달성 현황) | `RW-01` ~ `RW-06-E1` (`RW-06-E1` 기록 없음, `RW-06` 달성 현황) — 전체 대응표는 [화면 번호 통합표](screen_id_table.md) "이전 번호" 칸 |

</details>

<details>
<summary><b>v1.0</b> · 2026-09-24 · 통합 와이어프레임 · ERD v1.0 반영 — 세부 18건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 머리말 / 작성 기준 | 와이어프레임(공통화면 · 피처2 RAG)과 ERD v0.1 기준 | Figma 통합 와이어프레임(45개 화면) · 요구사항 정의서 v1.0 · ERD v1.0 기준 |
| 1. 전체 목록 / P-1 | `GET /practices/today` 오늘의 실천 (CM-03 · RW-03) | `GET /recommendations?analysisId=` 생활습관 추천 목록 (RW-01 · RG-05) <br>사유: 성규님 데이터 흐름(Recommendation → HabitGoal → HabitRecord → Reward) 기준 [성규 확인 필요] |
| 1. 전체 목록 / P-2 | `POST /practices/goals` 분석 결과로 목표 만들기 (RG-05 → RW-02) | `POST /habit-goals` 실천 목표 만들기 · 최대 3개 (RW-02) [성규 확인 필요] |
| 1. 전체 목록 / P-3 | `POST /practices/goals/{goalId}/checks` 실천 기록 (RW-03) | `GET /habit-goals/today` 오늘의 실천 (CM-03 · RW-03~05 · RW-03-E2) [성규 확인 필요] |
| 1. 전체 목록 / P-4 | `GET /practices/stats` 달성 현황 (RW-06 · RW-06-E1) | `POST /habit-goals/{goalId}/records` 실천 기록 · 체크 · 수량 (RW-03 · RW-04 · RW-03-E1) [성규 확인 필요] |
| 1. 전체 목록 / P-5 — 신규 | (없음) | `GET /habit-goals/history?period=week` 주간 달성 현황 (RW-06 · RW-06-E1) [성규 확인 필요] |
| 1. 전체 목록 / P-6 — 신규 | (없음) | `GET /rewards/summary` 포인트 요약 (RW-05 · RW-06) [성규 확인 필요] |
| 1. 전체 목록 / 홈 호출 조합 | 홈(CM-03) = U-1 + R-7(`size=1`) + **P-1** | 홈(CM-03) = U-1 + R-7(`size=1`) + **P-3** (P-1이 추천 목록으로 바뀜) |
| 6. 실천 · 보상 / 본문 | P-1 오늘의 실천 응답 예시만 있음 (`doneCount` · `totalCount` · `streakDays` · `items[goalId, title, done]`). P-2 요청 `{ analysisId, source: "lifestyle" }`, P-3 · P-4는 "담당자 설계 (사진 인증 도입 여부에 따라 요청 형식이 달라짐)" | P-1 ~ P-6 요청 · 응답 예시 작성. 오늘의 실천에 `reasonLabel` · `goalType`(check / quantity) · `targetValue` · `currentValue` · `todayPoints` · `allDoneBonus` 추가. 실천 기록은 같은 날 중복 완료 시 무시하고 `200` (포인트 중복 지급 없음) [성규 확인 필요] |
| 1. 전체 목록 / H-4 — 신규 | (없음) | `GET /chat/sessions?date=` · `?month=` 날짜별 대화 목록 (CB-02 · CB-03, 선택 구현 ⚪) [수인 확인 필요] |
| 1. 전체 목록 / H-5 — 신규 | (없음) | `PATCH /chat/sessions/{id}` 대화 제목 수정 (CB-03, 선택 구현 ⚪) [수인 확인 필요] |
| 1. 전체 목록 / H-1 · H-3 화면 | H-1 `CB-01` / H-3 `CB-01` | H-1 `CB-01 · CB-01-E1 · CB-01-E2` / H-3 `CB-01 · CB-01-E2` (분석 결과를 알고 시작하는 대화 화면 추가) |
| 5. 챗봇 / H-3 응답 형식 | "답변 종류(`answered` / `refused_medical` / `no_evidence`)를 함께 내려주면 CB-01의 예외 화면을 나눠 그릴 수 있음" (제안만) | 응답 끝에 `{ messageId, answerType, sources }` 를 내려줌. `answerType` 은 CB-01 말풍선 라벨과 1:1 [수인 확인 필요] |
| 3. OCR / O-1 요청 | `files[]` 최대 5장 · 1장 10MB 이하 · JPG / PNG / PDF | `files[]` **최대 5장** (OC-01에서 이어 찍은 사진을 한 번에) · 사진마다 품질 검사, 문제 있는 사진 번호를 `detail.fileIndex` 로 알려줌 [채연 확인 필요] |
| 3. OCR / O-1 에러 코드 | `FILE_TOO_LARGE` · `FILE_TYPE_NOT_SUPPORTED` · `TOO_MANY_FILES` · `IMAGE_QUALITY_LOW` · `OCR_FAILED` | 위 코드 + `422 NOT_A_DOCUMENT` (OC-01-E3 "문서를 찾지 못했어요") [채연 확인 필요] |
| 4. RAG / R-4 점검 항목 (`checkedItems.type`) | `interaction` · `duplicate` · `elderly_age` · `dose_exceed` (4개) | 위 4개 + `polypharmacy` (다제약물, REQ-049) — ⚠️ 변경 이력에만 적혀 있고 R-4 본문 예시에는 아직 반영 안 됨 |
| 7. ERD 반영 사항 | 제목 "ERD에 반영해야 할 것 (API를 쓰면서 발견)" · 9번 "실천 · 보상 테이블 없음 — 피처 4 담당자 설계 필요 (P-1~4)" | 제목 "ERD 반영 사항 — ✅ ERD v1.0에 반영 완료" · 9번 "실천 · 보상 테이블 4개 (`recommendations` · `habit_goals` · `habit_records` · `rewards`) (P-1~6)" |
| 8. 남은 결정 사항 | 토큰 만료 · OCR 동기/비동기 · 챗봇 SSE 여부 (3개) | 위 3개 + 챗봇 날짜별 여러 대화 여부(H-4 · H-5) · 한 주 끝난 뒤 목표 다시 고르기(P-2) (5개) |

</details>

---

> Figma 통합 와이어프레임(45개 화면) · 요구사항 정의서 v1.0 · ERD v1.0 기준입니다.
> 화면 번호는 [화면 번호 통합표](screen_id_table.md) 기준입니다 (CM 공통 · OC OCR · RG RAG · CB 챗봇 · RW 실천·보상).
> 피처 1 · 3 · 4 항목(🟡)은 담당자가 확정하면 변경 이력에 기록하고 상태를 ✅로 바꿔 주세요.
>
> 상태 표시 — ✅ 초안 작성 완료 · 🟡 담당자 확정 필요 · ⚪ 선택 구현

---

## 0. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 주소 | `/api/v1` |
| 형식 | 요청 · 응답 모두 JSON (`Content-Type: application/json`). 업로드만 `multipart/form-data` |
| 인증 | 로그인 후 받은 토큰을 헤더에 넣음 — `Authorization: Bearer {accessToken}` |
| 권한 | 본인 데이터만 조회 가능. 남의 데이터 요청 시 `404` (존재 여부도 숨김) — NFR-010 |
| 시간 | ISO 8601, 한국 시간 — `2026-09-23T14:05:00+09:00` |
| 이름 규칙 | 주소는 복수형 명사 + kebab-case (`/analyses`), JSON 필드는 camelCase (`birthYear`) |
| 목록 | 커서 방식 — `?cursor={다음 커서}&size=20`. 응답에 `nextCursor` (없으면 `null`) |
| 오래 걸리는 작업 | 분석은 즉시 `202` + ID 반환 → 상태 조회 API로 확인 (NFR-001 · NFR-002) |

### 에러 응답 형식 (모든 API 공통)

```json
{
  "error": {
    "code": "AUTH_INVALID_CREDENTIALS",
    "message": "이메일 또는 비밀번호가 맞지 않아요.",
    "field": "password",
    "detail": { "remainingAttempts": 2 }
  }
}
```

- `message`는 **화면에 그대로 띄울 수 있는 문장**으로 씁니다 (고령 사용자 대상, 쉬운 말)
- `field`는 입력칸 오류일 때만 — 프론트가 해당 칸 아래에 문구를 띄움
- `detail`은 코드별 추가 정보 (없으면 생략)

### 공통 에러 코드

| HTTP | code | 뜻 | 화면 처리 |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | 입력 형식이 틀림 | 해당 칸 아래 오류 문구 (`field`) |
| 401 | `TOKEN_EXPIRED` | 로그인 만료 | CM-08 "다시 로그인해 주세요" → CM-01 |
| 401 | `UNAUTHORIZED` | 토큰 없음 · 잘못됨 | CM-01 로그인 |
| 403 | `CONSENT_REQUIRED` | 민감정보 동의 안 함 | 동의 안내 (업로드 · 분석 불가) |
| 404 | `NOT_FOUND` | 없음 (또는 남의 데이터) | CM-08 또는 목록으로 |
| 429 | `TOO_MANY_REQUESTS` | 요청이 너무 많음 | CM-08 "잠시 후 다시" |
| 500 | `INTERNAL_ERROR` | 서버 오류 | CM-08 "잠시 문제가 생겼어요" |
| 503 | `EXTERNAL_API_ERROR` | OCR · LLM 등 외부 서비스 오류 | CM-08 또는 각 피처 예외 화면 |

---

## 1. 전체 목록

| # | 메서드 | 주소 | 설명 | 화면 | 담당 | 상태 |
|---|---|---|---|---|---|---|
| A-1 | POST | `/auth/signup` | 회원가입 | CM-02 · CM-02-E1 | 공통 | ✅ |
| A-2 | POST | `/auth/login` | 로그인 | CM-01 · CM-01-E1 · CM-01-E2 | 공통 | ✅ |
| A-3 | POST | `/auth/logout` | 로그아웃 | CM-05 | 공통 | ✅ |
| U-1 | GET | `/users/me` | 내 정보 조회 | CM-03 · CM-05 | 공통 | ✅ |
| U-2 | PATCH | `/users/me` | 내 정보 수정 | CM-06 | 공통 | ✅ |
| U-3 | DELETE | `/users/me` | 회원 탈퇴 | CM-07 | 공통 | ✅ |
| U-4 | GET | `/users/me/consents` | 동의 내역 조회 | CM-05 | 공통 | ✅ |
| U-5 | DELETE | `/users/me/consents/{type}` | 동의 철회 | CM-05 | 공통 | 🟡 철회 정책 미정 |
| O-1 | POST | `/prescriptions` | 처방전 · 약봉투 업로드 + OCR | OC-01 | 채연님 | 🟡 |
| O-2 | GET | `/prescriptions/{id}` | 인식 결과 조회 | OC-02 | 채연님 | 🟡 |
| O-3 | PATCH | `/prescriptions/{id}/items/{itemId}` | 인식 결과 수정 · 후보 선택 | OC-02 | 채연님 | 🟡 |
| O-4 | GET | `/drugs/search` | 약 이름 검색 (직접 입력용) | OC-02 | 채연님 | 🟡 |
| R-1 | POST | `/analyses` | 분석 시작 | OC-02 → RG-01 | 형준 | ✅ |
| R-2 | GET | `/analyses/{id}/status` | 분석 진행 상태 (폴링) | RG-01 · RG-01-E1 | 형준 | ✅ |
| R-3 | POST | `/analyses/{id}/retry` | 실패한 분석 다시 시도 | RG-01-E1 | 형준 | ✅ |
| R-4 | GET | `/analyses/{id}` | 분석 결과 (탭 3개 전체) | RG-02 · RG-02-E1 · RG-04 · RG-05 | 형준 | ✅ |
| R-5 | GET | `/analyses/{id}/warnings/{warningId}` | 경고 자세히 | RG-03 | 형준 | ✅ |
| R-6 | PUT | `/analyses/{id}/diseases` | 질환 직접 선택 | RG-05-E1 | 형준 | ✅ |
| R-7 | GET | `/analyses` | 지난 기록 목록 | CM-03 · CM-04 | 형준 | ✅ |
| R-8 | DELETE | `/analyses/{id}` | 기록 삭제 | CM-04-E1 | 형준 | ✅ |
| R-9 | POST | `/guides/{guideId}/feedback` | 안내문 피드백 | RG-04 | 형준 | ✅ |
| R-10 | GET | `/guides/{guideId}/tts` | 안내문 음성 | RG-04 | 형준 | ⚪ |
| H-1 | POST | `/chat/sessions` | 대화 시작 | CB-01 · CB-01-E1 · CB-01-E2 | 수인님 | 🟡 |
| H-2 | GET | `/chat/sessions/{id}/messages` | 이전 대화 조회 | CB-01 | 수인님 | 🟡 |
| H-3 | POST | `/chat/sessions/{id}/messages` | 질문 보내기 (글자가 차례로 나오는 응답) | CB-01 · CB-01-E2 | 수인님 | 🟡 |
| H-4 | GET | `/chat/sessions?date=` · `?month=` | 날짜별 대화 목록 | CB-02 · CB-03 | 수인님 | ⚪ |
| H-5 | PATCH | `/chat/sessions/{id}` | 대화 제목 수정 | CB-03 | 수인님 | ⚪ |
| P-1 | GET | `/recommendations?analysisId=` | 생활습관 추천 목록 | RW-01 · RG-05 | 성규님 | 🟡 |
| P-2 | POST | `/habit-goals` | 실천 목표 만들기 (최대 3개) | RW-02 | 성규님 | 🟡 |
| P-3 | GET | `/habit-goals/today` | 오늘의 실천 | CM-03 · RW-03~05 · RW-03-E2 | 성규님 | 🟡 |
| P-4 | POST | `/habit-goals/{goalId}/records` | 실천 기록 (체크 · 수량) | RW-03 · RW-04 · RW-03-E1 | 성규님 | 🟡 |
| P-5 | GET | `/habit-goals/history?period=week` | 주간 달성 현황 | RW-06 · RW-06-E1 | 성규님 | 🟡 |
| P-6 | GET | `/rewards/summary` | 포인트 요약 | RW-05 · RW-06 | 성규님 | 🟡 |

> 홈(CM-03)은 별도 API를 만들지 않고 U-1 + R-7(`size=1`) + P-3을 함께 호출합니다.
> 프론트가 1명이라 **API 개수를 늘리지 않는 쪽**으로 잡았습니다. 결과 화면도 탭별로 나누지 않고 R-4 한 번에 받습니다.

---

## 2. 인증 · 회원 (공통)

### A-1. 회원가입 `POST /auth/signup`

화면 CM-02 · CM-02-E1 · 요구사항 REQ-001, REQ-005 · 인증 불필요

**요청**
```json
{
  "email": "hong@email.com",
  "password": "abcd1234",
  "nickname": "홍길동",
  "birthYear": 1958,
  "sex": "M",
  "consents": {
    "terms": true,
    "privacy": true,
    "sensitiveHealth": true
  }
}
```

| 필드 | 필수 | 규칙 |
|---|---|---|
| email | ✅ | 이메일 형식, 100자 이내 |
| password | ✅ | 영문 + 숫자 포함 8자 이상 |
| nickname | | 50자 이내. 없으면 홈에서 "안녕하세요"만 |
| birthYear | ✅ | 1900 ~ 올해. 노인주의 · 연령금기 판정에 사용 |
| sex | ✅ | `M` / `F` |
| consents.* | ✅ | 세 개 모두 `true`여야 가입 가능 |

**응답 `201`** — 가입과 동시에 로그인 처리
```json
{
  "accessToken": "eyJhbGciOi...",
  "user": { "id": 12, "nickname": "홍길동", "birthYear": 1958, "sex": "M" }
}
```

**에러**
| HTTP | code | 화면 |
|---|---|---|
| 409 | `EMAIL_DUPLICATED` (`field: email`) | CM-02-E1 "이미 가입된 이메일이에요" |
| 400 | `VALIDATION_ERROR` (`field: password` 등) | CM-02-E1 해당 칸 |
| 400 | `CONSENT_REQUIRED` (`field: consents.sensitiveHealth`) | CM-02-E1 동의 누락 문구 |

> 비밀번호 확인 칸 일치 여부는 프론트에서만 검사 (서버로 보내지 않음)

---

### A-2. 로그인 `POST /auth/login`

화면 CM-01 · CM-01-E1 · CM-01-E2 · 요구사항 REQ-002 · 인증 불필요

**요청**
```json
{ "email": "hong@email.com", "password": "abcd1234" }
```

**응답 `200`**
```json
{
  "accessToken": "eyJhbGciOi...",
  "user": { "id": 12, "nickname": "홍길동", "birthYear": 1958, "sex": "M" }
}
```

**에러**
| HTTP | code | detail | 화면 |
|---|---|---|---|
| 401 | `AUTH_INVALID_CREDENTIALS` | `{ "remainingAttempts": 2 }` | CM-01-E1 "(3 / 5회)" |
| 423 | `AUTH_LOCKED` | `{ "lockedUntil": "2026-09-23T14:15:00+09:00" }` | CM-01-E2 남은 시간 표시 |

> 보안상 이메일이 없는 경우와 비밀번호가 틀린 경우를 **같은 에러**로 응답합니다.

---

### A-3. 로그아웃 `POST /auth/logout`

화면 CM-05 · 요구사항 REQ-003

요청 본문 없음 · 응답 `204` · 서버에서 해당 토큰을 즉시 무효화

---

### U-1. 내 정보 조회 `GET /users/me`

화면 CM-03 (인사말) · CM-05

**응답 `200`**
```json
{
  "id": 12,
  "email": "hong@email.com",
  "nickname": "홍길동",
  "birthYear": 1958,
  "sex": "M",
  "createdAt": "2026-09-20T10:00:00+09:00"
}
```

---

### U-2. 내 정보 수정 `PATCH /users/me`

화면 CM-06 · 바꿀 필드만 보냄

**요청**
```json
{ "nickname": "길동", "birthYear": 1958, "sex": "M" }
```

**응답 `200`** — U-1과 같은 형식

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `email`을 보내면 거절 (수정 불가 항목) |

> 출생연도 · 성별이 바뀌면 **다음 분석부터** 반영. 지난 결과는 다시 계산하지 않음

---

### U-3. 회원 탈퇴 `DELETE /users/me`

화면 CM-07 · 요구사항 REQ-004

**요청**
```json
{ "confirmed": true }
```

응답 `204` · 처방 정보 · 분석 결과 · 안내문 · 챗봇 대화 · 실천 기록을 **즉시 삭제**, 사용자 행은 개인정보를 지운 뒤 `deleted_at`만 남김

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `confirmed`가 `true`가 아님 |

---

### U-4. 동의 내역 조회 `GET /users/me/consents`

화면 CM-05 → 민감정보 동의 내역

**응답 `200`**
```json
{
  "items": [
    { "type": "terms", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00" },
    { "type": "privacy", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00" },
    { "type": "sensitiveHealth", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00" }
  ]
}
```

### U-5. 동의 철회 `DELETE /users/me/consents/{type}` 🟡

`type = sensitiveHealth`만 철회 가능. 철회하면 업로드 · 분석 API가 `403 CONSENT_REQUIRED`.
**기존 분석 기록을 지울지는 팀 결정 필요.**

---

## 3. 피처 1 — OCR (채연님) 🟡

> 피처 2와 **주고받는 형식만** 먼저 맞추기 위한 최소 정의입니다. 세부 사항은 담당자가 확정해 주세요.

### O-1. 업로드 + OCR `POST /prescriptions`

`multipart/form-data` · `files[]` **최대 5장** (OC-01에서 이어서 찍은 사진을 한 번에) · 1장 10MB 이하 · JPG / PNG / PDF (REQ-010~014)
사진마다 품질 검사를 하고, 한 장이라도 문제가 있으면 해당 사진 번호를 `detail.fileIndex`로 알려줌

**응답 `201`** — OCR이 수 초 걸리면 R-1처럼 비동기로 바꾸는 것 검토
```json
{ "prescriptionIds": [101, 102] }
```

| HTTP | code | 화면 |
|---|---|---|
| 400 | `FILE_TOO_LARGE` · `FILE_TYPE_NOT_SUPPORTED` · `TOO_MANY_FILES` | OC-01 업로드 실패 안내 |
| 422 | `IMAGE_QUALITY_LOW` | OC-01-E1 "다시 찍어 주세요" |
| 422 | `NOT_A_DOCUMENT` | OC-01-E3 "문서를 찾지 못했어요" |
| 422 | `OCR_FAILED` | OC-02-E1 재촬영 + 직접 입력 경로 |

### O-2. 인식 결과 조회 `GET /prescriptions/{id}`

⭐ **피처 2가 받는 입력 형식** — 이 형식이 확정되어야 분석이 붙습니다

```json
{
  "id": 101,
  "docType": "prescription",
  "issuedDate": "2026-09-20",
  "hospitalName": "○○내과",
  "diseaseCodes": ["I10", "E11"],
  "items": [
    {
      "id": 1001,
      "rawName": "암로디핀5mg",
      "matchStatus": "needs_confirm",
      "ediCode": null,
      "candidates": [
        { "ediCode": "645301220", "itemName": "노바스크정5밀리그람", "score": 0.82 },
        { "ediCode": "...", "itemName": "아모디핀정5밀리그람", "score": 0.79 }
      ],
      "dosePerTime": 1,
      "timesPerDay": 1,
      "totalDays": 30,
      "timing": "아침 식후"
    }
  ]
}
```

- `docType`: `prescription`(처방전) / `pill_bag`(약봉투) — 약봉투는 `diseaseCodes`가 빈 배열 → RG-05-E1로 이어짐
- `matchStatus`: `auto`(자동 확정) / `needs_confirm`(후보 선택 필요) / `user_confirmed` / `unmatched`(끝내 못 찾음)

### O-3. 인식 결과 수정 `PATCH /prescriptions/{id}/items/{itemId}`

```json
{ "ediCode": "645301220", "dosePerTime": 1, "timesPerDay": 1, "totalDays": 30 }
```
`ediCode: null` + `"exclude": true` → 이 약은 점검에서 빼고 진행 (REQ-032)

### O-4. 약 이름 검색 `GET /drugs/search?q=암로디핀&size=5`

```json
{ "items": [ { "ediCode": "645301220", "itemName": "노바스크정5밀리그람", "entpName": "한국화이자", "score": 0.91 } ] }
```

---

## 4. 피처 2 — RAG 분석 (형준) ✅

### R-1. 분석 시작 `POST /analyses`

화면 OC-02 [분석 시작] → RG-01 · 요구사항 REQ-040~062, NFR-002

**요청**
```json
{ "prescriptionIds": [101, 102] }
```

- 여러 병원 처방전을 **한 번에 점검**하는 것이 핵심 (최대 5장)
- `matchStatus`가 `needs_confirm`인 약이 남아 있으면 거절

**응답 `202`** — 즉시 반환, 분석은 뒤에서 진행
```json
{ "analysisId": 5001, "status": "queued" }
```

| HTTP | code | 설명 |
|---|---|---|
| 409 | `ITEMS_NOT_CONFIRMED` | 확인 안 된 약이 있음 → OC-02로 돌아감 |
| 403 | `CONSENT_REQUIRED` | 민감정보 동의 없음 |

---

### R-2. 분석 진행 상태 `GET /analyses/{id}/status`

화면 RG-01 · RG-01-E1 · **2초마다 호출** (완료 · 실패면 중단)

**응답 `200` — 진행 중**
```json
{
  "analysisId": 5001,
  "status": "running",
  "steps": [
    { "key": "drug_info", "label": "약 정보 확인", "state": "done" },
    { "key": "safety_check", "label": "같이 먹으면 안 되는 약 점검", "state": "running" },
    { "key": "guide_generation", "label": "안내문 작성", "state": "pending" }
  ],
  "drugCount": 6,
  "excludedCount": 1,
  "estimatedSeconds": 20
}
```

**응답 `200` — 실패 (RG-01-E1)**
```json
{
  "analysisId": 5001,
  "status": "failed",
  "steps": [
    { "key": "drug_info", "state": "done" },
    { "key": "safety_check", "state": "done" },
    { "key": "guide_generation", "state": "failed" }
  ],
  "error": { "code": "GUIDE_GENERATION_FAILED", "message": "안내문을 만들지 못했어요." },
  "partialResultAvailable": true,
  "retryCount": 1
}
```

| 값 | 뜻 |
|---|---|
| `status` | `queued` / `running` / `done` / `failed` |
| `steps[].state` | `pending`(대기) / `running`(진행 중) / `done`(완료) / `failed`(실패) — 화면 라벨과 1:1 |
| `partialResultAvailable` | `true`면 RG-01-E1에 [안전성 결과만 먼저 보기] 표시 |
| `error.code` | `GUIDE_GENERATION_FAILED` / `SAFETY_CHECK_FAILED` / `TIMEOUT`(60초 초과) |

> 안전성 점검은 DB 조회라 거의 실패하지 않고, 실패는 대부분 AI 생성 단계에서 납니다.
> 그래서 단계를 나눠 두면 **경고는 AI 실패와 상관없이** 보여줄 수 있습니다.

---

### R-3. 다시 시도 `POST /analyses/{id}/retry`

화면 RG-01-E1 [다시 시도] · 실패한 단계부터 다시 · 응답 `202` (R-1과 같음)

| HTTP | code | 설명 |
|---|---|---|
| 409 | `ANALYSIS_NOT_FAILED` | 실패 상태가 아님 |
| 429 | `RETRY_LIMIT_EXCEEDED` | 3회 초과 → "잠시 후 다시 시도해 주세요" |

---

### R-4. 분석 결과 `GET /analyses/{id}`

화면 RG-02 · RG-02-E1 · RG-04 · RG-05 · **탭 3개를 한 번에** 받음

**응답 `200`**
```json
{
  "analysisId": 5001,
  "status": "done",
  "createdAt": "2026-09-23T14:05:00+09:00",
  "summary": {
    "prescriptionCount": 2,
    "hospitals": ["○○내과", "△△의원"],
    "drugCount": 6,
    "warningCounts": { "danger": 1, "caution": 2, "info": 0 }
  },
  "excludedDrugs": [
    { "rawName": "○○연질캡슐", "reason": "unmatched" }
  ],

  "warnings": [
    {
      "id": 9001,
      "type": "interaction",
      "severity": "danger",
      "title": "함께 먹으면 안 되는 약",
      "drugs": [
        { "ediCode": "...", "itemName": "심바스타틴정20mg", "hospitalName": "○○내과" },
        { "ediCode": "...", "itemName": "클래리스로마이신정250mg", "hospitalName": "△△의원" }
      ],
      "summary": "함께 먹으면 근육이 상하는 부작용 위험이 커질 수 있어요.",
      "source": { "name": "식약처 병용금기 성분 고시", "noticeDate": "2019-01-01" }
    }
  ],
  "checkedItems": [
    { "type": "interaction", "label": "함께 먹으면 안 되는 약", "state": "checked" },
    { "type": "duplicate", "label": "같은 성분 · 같은 효과 중복", "state": "checked" },
    { "type": "elderly_age", "label": "어르신 주의 · 나이 금기", "state": "checked" },
    { "type": "dose_exceed", "label": "하루 최대량 초과", "state": "checked" }
  ],

  "medication": {
    "guideId": 7001,
    "status": "done",
    "items": [
      {
        "ediCode": "645301220",
        "itemName": "노바스크정 5mg",
        "category": "혈압약",
        "purpose": "혈압을 낮춰요",
        "howToTake": "하루 1번, 아침 식후 1알 · 30일",
        "caution": "어지러울 수 있으니 천천히 일어나세요",
        "source": "식약처 의약품 허가정보"
      }
    ]
  },

  "lifestyle": {
    "guideId": 7002,
    "status": "done",
    "diseases": [
      { "code": "I10", "name": "고혈압", "origin": "prescription" }
    ],
    "medicationLinks": [
      { "itemName": "다이아벡스정", "advice": "술은 되도록 피하세요" }
    ],
    "sections": [
      {
        "diseaseCode": "I10",
        "title": "고혈압",
        "actions": ["국물은 남기고, 하루 소금 5g 이하로", "빠르게 걷기 하루 30분, 주 5일 이상"],
        "conflict": null
      }
    ],
    "source": "질병관리청 · 관련 학회 지침의 권고 수치를 정리"
  },

  "disclaimer": "의학적 진단 · 처방이 아닌 참고용 안내예요"
}
```

**필드 설명**

| 필드 | 설명 | 화면 |
|---|---|---|
| `excludedDrugs` | 점검에서 빠진 약 — **숨기지 않고** 맨 위에 표시 (REQ-032) | RG-02 · RG-04 |
| `warnings` | 위험한 순서(`danger` → `caution` → `info`)로 정렬해서 내려줌. **빈 배열이면 RG-02-E1** | RG-02 |
| `warnings[].severity` | `danger` 위험 / `caution` 주의 / `info` 참고 (REQ-048) | 등급 라벨 |
| `warnings[].summary` | DB 금기 사유를 **템플릿으로** 만든 문장. AI를 거치지 않음 | 경고 카드 |
| `checkedItems` | 경고가 없을 때 "무엇을 점검했는지" 보여주기 위한 목록 | RG-02-E1 |
| `medication.status` · `lifestyle.status` | `done` / `failed` — RG-01-E1에서 안전성만 보고 들어온 경우 `failed` | RG-04 · RG-05 "만들지 못했어요" |
| `medication.items[]` | 항목 순서 · 이름 고정 (결과 일관성 NFR-030). 근거가 없으면 값 `null` → "허가정보에 내용이 없어요" | RG-04 약 카드 |
| `lifestyle.diseases[].origin` | `prescription`(처방전 코드) / `user`(RG-05-E1에서 직접 선택) | RG-05 |
| `lifestyle.diseases` 빈 배열 | 질병분류기호 없음 (약봉투 등) → **RG-05-E1** | RG-05-E1 |
| `lifestyle.sections[].conflict` | 질환끼리 권고가 부딪힐 때 `{ "message": "...", "label": "의료진 상담 필요" }` (REQ-062) | RG-05 |

| HTTP | code | 설명 |
|---|---|---|
| 409 | `ANALYSIS_NOT_READY` | 아직 진행 중 → RG-01로 |
| 404 | `NOT_FOUND` | 없음 또는 삭제됨 |

---

### R-5. 경고 자세히 `GET /analyses/{id}/warnings/{warningId}`

화면 RG-03 · 요구사항 REQ-047, REQ-052

**응답 `200`**
```json
{
  "id": 9001,
  "type": "interaction",
  "severity": "danger",
  "title": "함께 먹으면 안 되는 약",
  "drugs": [
    { "itemName": "심바스타틴정 20mg", "hospitalName": "○○내과", "category": "콜레스테롤 약", "ingredient": "심바스타틴" },
    { "itemName": "클래리스로마이신정 250mg", "hospitalName": "△△의원", "category": "항생제", "ingredient": "클래리스로마이신" }
  ],
  "explanation": "함께 먹으면 콜레스테롤 약이 몸에 많이 쌓여 근육이 상하는 부작용 위험이 커질 수 있어요.",
  "reasonOriginal": "(DUR 금기 사유 원문)",
  "source": { "name": "식약처 병용금기 성분 고시", "noticeDate": "2019-01-01", "noticeNo": "2019-xx" },
  "judgedBy": "database",
  "doseDetail": null,
  "actionAdvice": "약을 임의로 끊지 말고, 처방한 의사나 약사와 먼저 상의하세요."
}
```

- `explanation`만 AI가 쉬운 말로 다듬은 문장. `reasonOriginal`은 원문 그대로 (검증용)
- `judgedBy`: 항상 `"database"` — 화면에 "AI가 판단하지 않음" 표시 근거
- `doseDetail`: 1일 최대용량 초과일 때만 `{ "dailyTotal": 30, "maxDaily": 20, "unit": "mg" }`

---

### R-6. 질환 직접 선택 `PUT /analyses/{id}/diseases`

화면 RG-05-E1 [선택한 질환으로 다시 보기] · 요구사항 REQ-060

**요청**
```json
{ "diseaseCodes": ["I10", "E11"] }
```
빈 배열 = "해당 없음 · 모르겠어요"

**응답 `200`** — R-4의 `lifestyle` 부분만 새로 만들어 반환 (`diseases[].origin = "user"`)

> 생활습관 부분은 팩트 테이블 조회 + 짧은 생성이라 동기 처리로 둡니다. 느리면 비동기로 바꿈.

---

### R-7. 지난 기록 목록 `GET /analyses?cursor=&size=20`

화면 CM-04 · CM-03(`size=1`로 최근 1건) · 요구사항 REQ-080

**응답 `200`**
```json
{
  "items": [
    {
      "analysisId": 5001,
      "createdAt": "2026-09-20T10:00:00+09:00",
      "hospitals": ["○○내과"],
      "drugCount": 5,
      "diseaseNames": ["고혈압", "당뇨"],
      "status": "done",
      "resultLabel": "확인 필요 2건"
    },
    {
      "analysisId": 4990,
      "createdAt": "2026-08-14T09:00:00+09:00",
      "status": "failed",
      "resultLabel": "분석 실패"
    }
  ],
  "nextCursor": "eyJpZCI6NDk5MH0"
}
```

- `status`: `running`(분석 중) / `done` / `failed`
- `resultLabel`: 화면 라벨을 **서버가 만들어** 내려줌 — `확인 필요 N건` / `확인된 위험 없음` / `분석 중` / `분석 실패`
- 빈 배열이면 CM-04-E2 · 홈은 CM-03-E1

---

### R-8. 기록 삭제 `DELETE /analyses/{id}`

화면 CM-04-E1 · 요구사항 REQ-081 · 응답 `204`

분석 결과 · 경고 · 안내문 · 피드백 · 연결된 챗봇 대화 삭제.
**이 분석으로 만든 실천 목표 · 포인트를 남길지는 성규님과 결정 필요** 🟡

---

### R-9. 안내문 피드백 `POST /guides/{guideId}/feedback`

화면 RG-04 · 요구사항 REQ-090, REQ-091

**요청**
```json
{ "rating": 1, "comment": "글씨가 더 컸으면 좋겠어요" }
```
`rating`: `1` 도움됐어요 / `-1` 도움이 안 됐어요 · `comment` 선택 · 응답 `201`

---

### R-10. 안내문 음성 `GET /guides/{guideId}/tts` ⚪

화면 RG-04 [음성으로 듣기] · 요구사항 REQ-100, REQ-101 (선택 구현)

**응답 `200`**
```json
{ "audioUrl": "https://.../7001.mp3", "durationSeconds": 95 }
```
재생 속도는 프론트 플레이어에서 조절 (서버 관여 없음)

---

## 5. 피처 3 — 챗봇 (수인님) 🟡

### H-1. 대화 시작 `POST /chat/sessions`

```json
{ "analysisId": 5001, "context": { "type": "warning", "id": 9001 } }
```
- `analysisId` 없으면 일반 질문 모드 (CM-03-E1에서 분석 전에 들어온 경우)
- `context`: RG-03 [이 경고 물어보기] · RG-04 [이 약 물어보기]에서 넘어올 때 (`warning` / `drug`)

**응답 `201`** `{ "sessionId": 301 }`

### H-2. 이전 대화 `GET /chat/sessions/{id}/messages`

### H-3. 질문 보내기 `POST /chat/sessions/{id}/messages`

```json
{ "content": "이 약은 밥 먹고 먹어야 하나요?" }
```
응답은 **글자가 차례로 나오는 방식(SSE)** 검토 — 담당자 확정 필요.
응답 끝에 답변 종류와 출처를 함께 내려줌:
```json
{ "messageId": 9101, "answerType": "answered", "sources": ["식약처 의약품 허가정보"] }
```
- `answerType`: `answered` / `refused_medical`(의료진 상담 필요) / `no_evidence`(확인이 어렵습니다) — CB-01 말풍선 라벨과 1:1

### H-4. 날짜별 대화 목록 `GET /chat/sessions?date=2026-09-16` ⚪

CB-02(`?month=2026-09` → 기록 있는 날짜 목록) · CB-03(`?date=` → 그날 대화 목록)
```json
{ "items": [ { "sessionId": 301, "title": "혈압약 먹는 시간 질문", "preview": "아침에 먹는 게 좋은지...", "updatedAt": "2026-09-16T09:12:00+09:00" } ] }
```
날짜별 여러 대화 구조로 확정될 때만 구현 (REQ-077)

### H-5. 대화 제목 수정 `PATCH /chat/sessions/{id}` ⚪

```json
{ "title": "혈압약 복용 시간" }
```

---

## 6. 피처 4 — 실천 · 보상 (성규님) 🟡

> 성규님 데이터 흐름 기준: Analysis → **Recommendation** → **HabitGoal** → **HabitRecord** → **Reward**
> 추천(Recommendation)은 사용자가 골라야 목표(HabitGoal)가 됨. 아래 요청 · 응답은 화면에 필요한 최소 형식이며 담당자가 확정

### P-1. 생활습관 추천 `GET /recommendations?analysisId=5001`

화면 RW-01 · REQ-110 — 분석 결과의 질환 · 약 기준, 팩트 테이블에서만 추천
```json
{ "items": [ { "id": 1, "title": "국물 남기기", "desc": "하루 소금 5g 이하", "reasonLabel": "고혈압", "goalType": "check" },
             { "id": 2, "title": "빠르게 걷기 30분", "reasonLabel": "고혈압 · 당뇨", "goalType": "quantity", "targetValue": 30, "unit": "분" } ] }
```

### P-2. 목표 만들기 `POST /habit-goals`

화면 RW-02 · REQ-111
```json
{ "recommendationIds": [1, 2, 3] }
```
응답 `201` · 1~3개만 허용, 0개 또는 4개 이상이면 `400 VALIDATION_ERROR`

### P-3. 오늘의 실천 `GET /habit-goals/today`

화면 CM-03 카드 · RW-03 · RW-04 · RW-05 · REQ-112
```json
{
  "hasGoals": true,
  "doneCount": 1, "totalCount": 3, "streakDays": 3,
  "items": [ { "goalId": 11, "title": "국물 남기기", "reasonLabel": "고혈압", "goalType": "check", "done": true },
             { "goalId": 12, "title": "빠르게 걷기", "goalType": "quantity", "targetValue": 30, "currentValue": 0, "unit": "분", "done": false } ],
  "todayPoints": 10, "allDoneBonus": 10
}
```
`hasGoals: false` → CM-03-E1 "목표 없음" · 실천 탭은 RW-03-E2

### P-4. 실천 기록 `POST /habit-goals/{goalId}/records`

화면 RW-03 · RW-04 · REQ-112 · 113 · 115
```json
{ "date": "2026-09-24", "completed": true }
{ "date": "2026-09-24", "value": 10 }
```
- 같은 날 같은 목표를 다시 완료하면 무시하고 `200` (포인트 중복 지급 없음)
- 응답에 `pointsEarned`, `allDone` 포함 → `allDone: true`면 RW-05로 이동
- 저장 실패 시 프론트는 RW-03-E1 배너 + 같은 요청 재시도

### P-5. 주간 달성 현황 `GET /habit-goals/history?period=week`

화면 RW-06 · RW-06-E1 · REQ-114
```json
{ "days": [ { "date": "2026-09-21", "done": true } ], "doneDays": 4, "rate": 0.57, "streakDays": 3 }
```
이번 주 0건이면 RW-06-E1

### P-6. 포인트 요약 `GET /rewards/summary`

화면 RW-05 · RW-06
```json
{ "weekPoints": 120, "totalPoints": 480, "todayPoints": 30 }
```

---

## 7. ERD 반영 사항 — ✅ ERD v1.0에 반영 완료

| # | 내용 | 이유 | 관련 API |
|---|---|---|---|
| 1 | `analyses.prescription_id` 1개 → **분석 : 처방전 = 1 : N** (`analysis_prescriptions` 연결 테이블) | 여러 병원 처방전을 한 번에 점검 (최대 5장) | R-1 |
| 2 | `prescriptions.disease_code` 1개 → **N개** (`prescription_diseases`) | 처방전 질병분류기호는 주상병 + 부상병 여러 개 | O-2 · R-4 |
| 3 | `analysis_diseases` (`analysis_id`, `disease_code`, `origin`) 추가 | RG-05-E1에서 사용자가 직접 고른 질환을 처방전 코드와 구분 | R-6 |
| 4 | `analyses`에 `failed_step`, `retry_count` 추가 · `status` 값 정리 | RG-01-E1 단계별 실패 표시 · 부분 결과 · 재시도 제한 | R-2 · R-3 |
| 5 | `user_consents` (`user_id`, `type`, `agreed`, `agreed_at`, `withdrawn_at`) 추가 | 민감정보 별도 동의 기록 · 동의 내역 화면 | A-1 · U-4 · U-5 |
| 6 | `users`에 `failed_login_count`, `locked_until` 추가 | 5회 실패 10분 잠금 | A-2 |
| 7 | `prescriptions.doc_type` 추가 (`prescription` / `pill_bag`) | 약봉투는 질병코드가 없어 RG-05-E1로 분기 | O-2 · R-4 |
| 8 | `prescription_items.match_status`에 `needs_confirm`, `excluded` 추가 | 확인 전 분석 시작 막기 · 점검 제외 약 표시 | O-3 · R-1 |
| 9 | 실천 · 보상 테이블 4개 (`recommendations` · `habit_goals` · `habit_records` · `rewards`) | 피처 4 데이터 흐름 (🟡 성규 확인) | P-1~6 |

---

## 8. 남은 결정 사항

- [ ] 토큰 만료 시간 · 재발급(refresh) 도입 여부 — 고령 사용자라 자주 로그아웃되면 불편
- [ ] OCR(O-1)을 동기로 둘지, 분석처럼 비동기로 둘지 — CLOVA OCR 응답 시간 측정 후 (9/30 키 제공)
- [ ] 챗봇 응답을 SSE로 할지
- [ ] 기록 삭제 시 실천 기록 처리 (R-8)
- [ ] 챗봇을 날짜별 여러 대화로 갈지 (H-4 · H-5 구현 여부)
- [ ] 한 주가 끝난 뒤 목표 다시 고르기 흐름 (P-2)
- [ ] 동의 철회 시 기존 기록 처리 (U-5)
- [ ] 백엔드 프레임워크가 정해지면 자동 문서화(Swagger / OpenAPI)로 옮길지 — FastAPI · Spring 모두 지원
