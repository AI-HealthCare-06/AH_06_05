# API 명세서 v1.5 초안 (R-4 약 번호와 복약 안내, 별명 제거, 2장 건강 정보, 5장 챗봇 정리가 바뀜, 나머지는 v1.4 그대로)

**5팀 · 2026. 10. 7 · 작성 이형준 · 수정 김채연(PM)**

## 변경 이력

버전별 요약을 먼저 보고, ▶ 를 눌러 펼치면 **위치 · 현행(As-Is) · 개정(To-Be)** 을 볼 수 있습니다.
API를 바꿀 때마다 버전 요약 한 줄 + 세부 표를 추가하고, **현행에는 바꾸기 전 값을 그대로** 적어 주세요. 프론트 · 백엔드가 같은 버전을 보고 있는지 여기서 확인하세요.

| 버전 | 일자 | 변경 내용 | 담당 |
|---|---|---|---|
| v0.1 | 2026-09-23 | 최초 작성 — 30개 API (공통화면 · 피처2 RAG 와이어프레임, ERD v0.1 기준) | 이형준 |
| v0.2 | 2026-09-23 | 화면 번호를 통합표 기준(CM · OC · RG · CB · RW)으로 변경 | 이형준 |
| v1.0 | 2026-09-24 | 통합 와이어프레임(45개 화면) · ERD v1.0 반영 — 실천 · 보상 API 교체, 챗봇 2개 추가, OCR · 챗봇 응답 보완 | 이형준 |
| v1.1 | 2026-09-28 | 리뷰 반영 — OCR 업로드 202 + 작업 조회(O-5) 추가, 생활습관 출처를 실천 항목별로, 칼륨 등 "의료진 확인" 표시, 파기 범위 제안, R-4 다제약물 반영 | 이형준 |
| v1.2 | 2026-09-29 | RW-01 제외 확정 반영 (P-1 화면을 RG-05로), 기준 화면 수 50개 | 이형준 |
| v1.3 | 2026-10-06 | 챗봇 1단계 반영 (PR #3) — answerType 8가지, H-1 · H-3 `clientRequestId` · `sources` 형식, H-2 응답 형식, 대화 삭제(H-6) · 맥락 추가(H-7) 추가 / 기준 화면 수 50개 · 요구사항 v1.5 · ERD v1.3 / RAG 담당 채연 / 10/6: 로그인 재발급(A-4 신규) · 로그아웃 제외 · 약 이름 검색 결과 3가지(O-4) | 김채연 |
| v1.4 | 2026-10-07 | 담당을 피처 단위로 다시 정함(화면부터 서버까지 한 사람이 맡음). 공통과 챗봇은 수인, OCR과 RAG는 채연, 실천과 보상은 담당 미정(챌린지는 뒤로 미룸). 성규님 조기 수료로 2인 체제 / 10/8: 챗봇 점검 결과 카드 칸 `safetyCard` 제안 (H-2, H-3, 수인 확인 필요) | 김채연 |
| v1.5 초안 | 2026-10-12 | R-4 `medication.items[]`와 `lifestyle.medicationLinks[]`에 약 번호 `itemId` 추가 (챗봇 설계 메모 v0.9, PR #80의 요청 4번). 챗봇 5장 정리(수인 10/12 정리안): `safetyCard` 확정, H-1 `firstMessage`, H-2 `status`, H-3 `drugMatch`와 `safety` 칸, H-4 `createdAt`, H-8 오늘 대화 찾기 신규, 2단계 API 목록 | 채연 (챗봇은 수인 정리안 반영) |
| v1.5 초안 추가 | 2026-10-16 | 별명(`nickname`) 제거 (A-1 · A-2 · U-1 · U-2, #96 · 10/14 팀 합의) / O-5 `duplicatedFiles`, O-2 `notices`, `itemName`, `suggestedBy`, `guidance`, `checkFields` 추가 / R-4 `summary.drugCount`는 점검한 약만 셈 / R-4 복약 안내: `purpose` 문구를 "~에 쓰는 약이에요"로, `cautions`(문장 배열) 추가, 사람이 확인한 안내문만 채움 (`drug_guides`) | 김채연 |
| v1.5 초안 추가 | 2026-10-19 | R-7(지난 기록 목록), R-8(기록 삭제), R-9(안내문 피드백)을 서버에 구현하면서 세부 규칙을 적음: R-7 `size` 1~50, 잘못된 `cursor`는 400, R-8 진행 중이면 `409 ANALYSIS_RUNNING`, R-9 한 사람 한 안내문 하나(다시 보내면 덮어씀), 응답 `201` `{feedbackId}` / ERD `feedbacks`에 `unique (guide_id, user_id)` 제안 | 채연 |
| v1.5 초안 추가 | 2026-10-19 | 건강 정보(#101): A-1 요청 `health`(흡연, 음주), U-1 응답과 U-2 요청 `health`, U-3과 U-5 삭제 목록에 건강 정보 / 1장 U-1 화면을 CM-05로(#96) | 이수인 |
| v1.5 초안 추가 | 2026-10-20 | R-4 `lifestyle.diseases[].origin`에 `profile`(내 정보 질환) 추가. 분석 질환은 처방전 질환과 내 정보 질환을 합쳐 씀 (#101, 10/19 합의) | 이수인 |
| v1.5 초안 추가 | 2026-10-22 | H-3 응답을 `202` `{ messageId }`로 바꾸고 답은 H-2로 받음(2초마다 조회, 30초 지나면 E6). H-3 `content` 1~500자, 벗어나면 `400 VALIDATION_ERROR`. 답 만들기가 실패하면 만드는 중이던 답 줄을 지우고, 30초를 넘긴 줄은 다시 시도 때 지움. H-2 답 줄에 `safety`, ERD 반영 14번. H-3 요청 `emergencyDismissed`, 1층은 저장 전에 보고 걸린 질문은 원문 없이(`content` 빈 글), H-1과 H-7 `firstMessage`는 아직 보내지 않음(#116), H-8 `safetyModeUntil`은 그날 자정, H-2 답 줄 `replyTo`(ERD 반영 15번), H-1 `analysisId`는 맥락 카드 줄을 만들지 않음, H-7 같은 요청은 카드 줄을 한 번만. O-4의 `drugMatch` 줄을 H-2로, R-8은 대화의 분석 연결만 비움(채연과 정할 것) (#100) | 이수인 |
| v1.5 초안 추가 | 2026-10-23 | R-8: 분석을 지우면 그 분석으로 시작한 챗봇 대화와 그 분석의 맥락 카드가 붙은 대화를 지움(10/22의 "분석 연결만 비움"을 바꿈, 채연 리뷰). FK는 `set null` 그대로 두고 R-8 코드에서 지움(마이그레이션 없음) (#100) | 이수인 |
| v1.5 초안 추가 | 2026-10-28 | H-2 답 줄 `safetyCard`: 상담 갈래(끊거나 바꾸려는 질문, 증상)에서 카드가 붙으면 `answerType`은 `refer`. 새 유형이 아니라 있던 유형이라 화면 라벨은 그대로 (#134 리뷰) | 이수인 |
| v1.5 초안 추가 | 2026-10-28 | U-3, U-4, U-5를 #136 코드와 시험에 맞춤: U-3과 U-5 삭제에 보관 중인 사진, U-3 남는 칸(자리 값)과 쿠키, 401, U-4 `withdrawnAt`, U-5 응답 204(다시 불러도 같음)와 400, U-6 다시 동의 제안(담당자 확정 전) (#137, 10/28 수인) | 이수인 |
| v1.5 초안 추가 | 2026-10-28 | 7장 ERD 반영 사항 16번 `chat_messages.route_kind` 추가(범위 밖 질문과 답을 대화 기억에서 뺌). API 응답 모양은 그대로 (#140, 10/28 수인) | 이수인 |
| v1.5 초안 추가 | 2026-10-30 | 6장 P-1 ~ P-4를 서버 코드에 맞춤: 추천은 9/23에 정한 세 가지(국물 남기기, 빠르게 걷기 30분, 술 마시지 않기)를 분석 질환과 약에 팩트표 근거가 있을 때만, P-1 `hasDiseases`, `cautionLabel`, P-2 응답 `goalIds`와 다시 고르면 같은 목표는 유지, P-4 오늘 기록만, 수량형 `value`는 그날 총량, 완료 취소 허용, 포인트 칸(`todayPoints`, `allDoneBonus`, `pointsEarned`)은 P-6과 함께 뒤로. 7장 ERD 반영 17번. 담당 P-1 ~ P-4 채연 (10/30 회의) | 이수인 |
| v1.5 초안 추가 | 2026-10-31 | U-6 다시 동의 확정: 같은 줄을 새 시각으로 고치고 철회 시각은 비움, 지운 기록은 돌아오지 않음 (#137, 10/31 수인) | 이수인 |
| v1.5 초안 추가 | 2026-10-31 | H-3: 질문의 번호(주민번호, 전화번호, 이메일, 생년월일 등)를 저장과 OpenAI로 가기 전에 가림. 요청과 응답 모양은 그대로 (10/31 수인) | 이수인 |
| v1.5 초안 추가 | 2026-10-31 | H-1: `analysisId`도 맥락 카드도 없는 대화는 가장 최근 완료 분석을 쓰고 대화에 적음(R-8로 같이 지워짐). 완료 분석이 없으면 일반 질문 모드 그대로. API 요청과 응답 모양은 그대로 (#159, 10/31 수인) | 이수인 |

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

<details>
<summary><b>v1.1</b> · 2026-09-28 · 리뷰 반영 — 세부 13건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 머리말 / 작성 기준 | 요구사항 정의서 v1.0 · ERD v1.0 기준 | 요구사항 정의서 v1.3 · ERD v1.2 기준 |
| 1. 전체 목록 / O-1 | `POST /prescriptions` 처방전 · 약봉투 업로드 + OCR | `POST /prescriptions` 처방전 · 약봉투 업로드 → OCR 작업 시작 (`202`) |
| 1. 전체 목록 / O-5 — 신규 | (없음) | `GET /ocr-jobs/{jobId}` OCR 작업 상태 (폴링) · OC-01 → OC-02 [채연 확인 필요] |
| 3. OCR / O-1 응답 | **`201`** `{ "prescriptionIds": [101, 102] }` — "OCR이 수 초 걸리면 R-1처럼 비동기로 바꾸는 것 검토" | **`202`** `{ "jobId": 9001, "status": "queued" }` → O-5로 결과 조회<br>사유: OCR 처리 시간이 NFR-001(P95 3초)과 충돌할 수 있어 측정 전에 비동기로 준비 [채연 확인 필요] |
| 3. OCR / O-1 에러 코드 | `400` 파일 형식 · 크기 · 장수 / `422` `IMAGE_QUALITY_LOW` · `NOT_A_DOCUMENT` · `OCR_FAILED` (모두 O-1 응답) | `400`은 그대로 O-1에서 바로 응답. `IMAGE_QUALITY_LOW` · `NOT_A_DOCUMENT` · `OCR_FAILED`는 O-5 결과의 `failedFiles[].code`로 이동 |
| 4. RAG / R-4 `checkedItems` | `interaction` · `duplicate` · `elderly_age` · `dose_exceed` (4개) — v1.0 이력에만 polypharmacy 추가가 적혀 있고 본문엔 없었음 | 위 4개 + `polypharmacy` "여러 약 함께 복용" (REQ-049) |
| 4. RAG / R-4 `lifestyle.sections[].actions` | 문자열 배열 `["국물은 남기고, 하루 소금 5g 이하로", …]` | 객체 배열 `[{ "text": "…", "sourceId": 31 }]` — 실천 항목마다 출처 ID |
| 4. RAG / R-4 `lifestyle.source` | `"source": "질병관리청 · 관련 학회 지침의 권고 수치를 정리"` (문자열 1개) | 삭제 → `lifestyle.sources[]` `{ id, org, title, edition, publishedAt, url }` 목록<br>사유: 기관 · 문서명 · 발행일 · URL이 있어야 검증 · 갱신 가능 (리뷰 지적 5) |
| 4. RAG / R-4 `lifestyle.medicationLinks[]` | `{ itemName, advice }` | `{ itemName, advice, requiresClinician, sourceId }` — `requiresClinician: true`면 "의료진 확인" 라벨로만 표시하고 실천 목표로 만들지 않음 (예: 이뇨제 · ACE억제제/ARB와 칼륨)<br>사유: 칼륨 권고는 신장 기능 · 병용 약에 따라 위험 (리뷰 지적 3) |
| 2. 회원 / U-3 탈퇴 | "처방 정보 · 분석 결과 · 안내문 · 챗봇 대화 · 실천 기록을 즉시 삭제" (한 줄) | 삭제 대상 표로 정리 (포인트 · 피드백 · 동의 기록 포함) [팀 확인 필요] |
| 2. 회원 / U-5 동의 철회 | "**기존 분석 기록을 지울지는 팀 결정 필요.**" | 제안: 처방전 · 분석 · 안내문 · 피드백 · 챗봇 대화 삭제, 실천 목표는 종료하고 기록 · 포인트는 남김 (질환 라벨은 지움) [팀 확인 필요] |
| 4. RAG / R-8 기록 삭제 | "**이 분석으로 만든 실천 목표 · 포인트를 남길지는 성규님과 결정 필요**" | 제안: 이 분석에만 쓰인 처방전까지 삭제. 이미 만든 실천 목표 · 기록 · 포인트는 남기고 추천 연결만 끊음 [성규 확인 필요] |
| 8. 남은 결정 사항 | OCR 동기 / 비동기 · 삭제 시 실천 기록 · 동의 철회 시 기록 처리 (미정) 등 8개 | OCR은 비동기로 준비(측정 후 확정) · 삭제 · 철회는 제안안 확인으로 변경, MVP 범위 · RW-01 삭제 · RW-03~05 통합 3개 추가 (11개) |

</details>

<details>
<summary><b>v1.2</b> · 2026-09-29 · RW-01 제외 반영 — 세부 5건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 머리말 / 작성 기준 | Figma 통합 와이어프레임(45개 화면) · 요구사항 정의서 v1.3 · ERD v1.2 기준 | Figma 통합 와이어프레임(50개 화면, RW-01 제외 · 챗봇 6개 추가) · 요구사항 정의서 v1.4 · ERD v1.2 기준 |
| 1. 전체 목록 / P-1 화면 | RW-01 · RG-05 | RG-05<br>사유: RW-01 제외 확정 (2026-09-28, 한성규) — RG-05 [이 목표로 실천 시작하기]에서 RW-02로 바로 연결 |
| 6. 실천 · 보상 / P-1 본문 | 화면 RW-01 · REQ-110 | 화면 RG-05 · REQ-110 |
| 8. 남은 결정 사항 / RW-01 | [ ] RW-01 삭제 → RG-05 [실천 시작하기]에서 RW-02로 바로 연결할지 (P-1 화면이 RG-05만 남음) 🟡 성규 | [x] 완료 — RW-01 제외 확정 (2026-09-28, 한성규) |
| 8. 남은 결정 사항 / MVP 범위 | MVP 범위 확정 — 요구사항 정의서 v1.3 "MVP (제안)" 칸 (9/28 16시 오후 미팅) | MVP 범위 확정 — 요구사항 정의서 v1.4 "MVP (제안)" 칸 (다음 팀 회의) |

</details>

<details>
<summary><b>v1.3</b> · 2026-10-06 · 챗봇 1단계 · 담당 변경 · 로그인 재발급 · 약 이름 검색 — 세부 33건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 머리말 / 작성 기준 | Figma 통합 와이어프레임(50개 화면) · 요구사항 정의서 v1.4 · ERD v1.2 기준 | Figma 통합 와이어프레임(53개 화면, 화면 번호표 v0.5) · 요구사항 정의서 v1.5 · ERD v1.3 기준 |
| 머리말 / 영역 코드 | CM 공통 · OC OCR · RG RAG · CB 챗봇 · RW 실천·보상 | CM 공통 · MY 내정보 설정 · OC OCR · RG RAG · CB 챗봇 · RW 실천·보상 |
| 1. 전체 목록 / R-1 ~ R-10 담당 · 4장 제목 | 형준 | 채연 (10/1 역할 재분배) |
| 1. 전체 목록 / H-6 | (없음) | `DELETE /chat/sessions/{id}` 대화 삭제 · CB-03 · MY-S1 |
| 1. 전체 목록 / H-7 | (없음) | `POST /chat/sessions/{id}/context` 맥락 추가 · CB-01-E2 |
| 5. 챗봇 / H-1 요청 | `{ analysisId, context }` | `clientRequestId` 추가 (다시 시도 때 대화 중복 생성 방지) |
| 5. 챗봇 / H-2 응답 | 형식 없음 | `{ items: Message[] }` — `id` · `role` · `content` · `answerType` · `sources` · `contextCard` · `createdAt` |
| 5. 챗봇 / H-3 요청 | `{ content }` | `{ content, clientRequestId }` |
| 5. 챗봇 / H-3 응답 | `{ messageId, answerType: "answered", sources: ["식약처 의약품 허가정보"] }` | `{ messageId, answerType, content, sources: [{ title, basedOn }] }` |
| 5. 챗봇 / answerType | `answered` / `refused_medical` / `no_evidence` 3가지 | `normal` · `clarify` · `partial` · `no_evidence` · `refer` · `emergency` · `crisis` 7가지 + 프론트 전용 `error` (챗봇 설계 메모 3-1) |
| 5. 챗봇 / H-3 응답 방식 | 글자가 차례로 나오는 방식(SSE) 검토 — 담당자 확정 필요 | 1단계는 답을 다 만든 뒤 검사하고 한 번에 보냄 (수인 제안, 10/6 회의 확인) |
| 5. 챗봇 / 1단계 대화 규칙 | (없음) | 1단계는 하루 한 대화, 분석 결과에서 들어오면 H-7로 오늘 대화에 맥락 카드를 붙임 |
| 8. 남은 결정 사항 / 백엔드 프레임워크 | [ ] 백엔드 프레임워크가 정해지면 자동 문서화(Swagger / OpenAPI)로 옮길지 | [x] FastAPI로 확정 (템플릿) — 서버를 켜면 `/api/docs`에서 자동 문서 확인 |
| 8. 남은 결정 사항 / 챗봇 API 후보 | (없음) | 오늘 대화 찾기 · 긴급 기록 API는 챗봇 서버 담당이 정해지면 추가 (설계 메모 3-2) |
| 8. 남은 결정 사항 / MVP 범위 | 요구사항 정의서 v1.4 "MVP (제안)" 칸 (다음 팀 회의) | 요구사항 정의서 v1.5 "MVP (제안)" 칸 (10/6 팀 회의) |
| 2. 회원 / U-5 철회 시 남김 | 실천 목표(`status = ended`로 종료, `reason_label` 질환 라벨은 지움) | 실천 목표(`status = ended`로 종료, 추천 연결 `recommendation_id`는 비움 — 질환 라벨 `reason_label`은 추천과 함께 삭제). `reason_label`은 `habit_goals`가 아니라 `recommendations`에 있음 (성규 10/6 확인) |
| 4. RAG / R-8 실천 목표 처리 | 추천(`recommendations`) 연결만 끊음 | 같은 내용 + 근거 "ERD v1.3: `habit_goals.recommendation_id` ON DELETE SET NULL" (성규 10/6 확인 — 없으면 분석 삭제가 막힘) |
| 0. 공통 규칙 / 인증 | 로그인 후 받은 토큰을 헤더에 넣음 | 출입증 60분 · 끝나면 재발급권(14일)으로 A-4 (10/6) |
| 1. 전체 목록 / A-3 로그아웃 | `POST /auth/logout` ✅ | 넣지 않음 (10/6 결정) |
| 1. 전체 목록 / A-4 — 신규 | (없음) | `POST /auth/token/refresh` 출입증 다시 받기 (10/6) |
| 2. 회원 / A-2 응답 | `accessToken` · `user` | + `refreshToken` (앱 보안 저장소용), 쿠키도 같이 (10/6) |
| 2. 회원 / A-4 — 신규 | (없음, 코드는 `GET` · 쿠키에서만 읽음) | `POST` · 본문 `refreshToken` (없으면 쿠키) · 에러 2가지 · 앱 처리 순서 (10/6) |
| 3. OCR / O-4 응답 | `{ items[ediCode, itemName, entpName, score] }` | `status`(matched · candidates · not_found) 추가, `items`에 `itemSeq` · `etcOtc` 추가, 찾는 범위 급여목록 + 허가정보, 챗봇도 같이 씀 (10/6 수인 요청) |
| 8. 남은 결정 / 토큰 | [ ] 만료 시간 · 재발급 도입 여부 | [x] 60분 · 14일 · 앱 보안 저장소 (10/6) |
| 2. 회원 / A-1 응답 | `accessToken` · `user` | + `refreshToken` · 재발급권 쿠키 (A-2와 같은 모양, 가입하자마자 앱 보안 저장소에 저장) (10/6) |
| 3. OCR / O-2 응답 | `items[].ediCode` · `candidates[].ediCode` | `itemSeq` 추가 (급여목록에 없는 약은 `itemSeq`만), `issuedDate`는 약봉투면 조제일 (수인 PR #48 리뷰, 10/6) |
| 1. 전체 목록 / 담당 열 | 공통 · 채연님 · 수인님 · 성규님 (피처별) | `서버 담당`으로 이름을 바꾸고 전부 채연 — 화면은 수인 (10/6 서면 결정, 성규님 조기 수료로 2인 체제). 5 · 6 · 3 · 2장 제목도 같이 고침 |
| 2. 회원 / U-3 · U-5 · 4. RAG / R-8 | 파기 범위 · 실천 목표 처리 [팀 확인 필요] | 확정 — 삭제 · 남김 표 그대로 (10/6 서면 결정 3번). U-5 상태 🟡 → ✅ |
| 5. 챗봇 / H-1 | (없음) | 동의하지 않았거나 철회한 사용자도 챗봇 사용 가능 — 일반 정보만 답하고 내 약 · 분석 결과는 안 넣음, 챗봇 API에는 `403 CONSENT_REQUIRED`를 쓰지 않음 (10/6 결정 3번 · 수인 설계 메모 9번) |
| 3. OCR / O-3 요청 | `ediCode`로 약을 고름 | 급여목록에 없는 약은 `itemSeq`로 고름, 점검에서 빼려면 `ediCode` · `itemSeq` 둘 다 null + `exclude` (10/6) |
| 8. 남은 결정 / RW-03 · 04 · 05 합치기 | [ ] 한 화면의 상태로 합칠지 🟡 성규 | 담당을 수인으로 바꿈 — 화면 쪽 결정이라서 (10/6 수인 PR #74 리뷰) |
| 0. 공통 / 공통 에러 코드 | (없음 — 403은 `CONSENT_REQUIRED`만 있음) | `403 FORBIDDEN` 추가 — 앱은 `UNAUTHORIZED`를 받으면 로그인 화면으로 보내서, 권한 오류와 구분함 (10/6 수인 PR #77 리뷰) |
| 머리말 / 작성 기준 (화면 수) | Figma 통합 와이어프레임(53개 화면, 화면 번호표 v0.5) | 50개 화면, 화면 번호표 v0.6 — 키보드 받아쓰기로 바뀌어 CB-05-E1 · CB-05-P · CB-05-E2 삭제, CB-05는 "받아쓰기 안내" (10/6 수인 #50) |

</details>

<details>
<summary><b>v1.4</b> 2026-10-07 담당 변경, 10/8 점검 결과 카드 칸과 생활습관 R-4 모양 세부 19건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 1. 전체 목록 / 목록 표 머리글 | `서버 담당` | `담당` (화면부터 서버까지 한 사람이 맡으므로 서버만 가리키는 말을 뺌) |
| 1. 전체 목록 / A-1 ~ A-4, U-1 ~ U-5 담당 | 채연 | 수인 (공통은 수인이 화면부터 서버까지 맡음) |
| 1. 전체 목록 / H-1 ~ H-7 담당 | 채연 | 수인 (챗봇은 수인이 화면부터 서버까지 맡음) |
| 1. 전체 목록 / O-1 ~ O-5, R-1 ~ R-10 담당 | 채연 (화면은 수인) | 채연 (OCR과 RAG는 채연이 화면부터 서버까지 맡음) |
| 1. 전체 목록 / P-1 ~ P-6 담당 | 채연 (화면은 수인) | 미정 (챌린지는 뒤로 미뤄서 담당을 아직 정하지 않음) |
| 2장 제목 | 인증 · 회원 (공통 — 서버 채연 · 화면 수인) | 인증 · 회원 (공통, 수인) |
| 3장 제목 | 피처 1 — OCR (서버 채연 · 화면 수인) | 피처 1 — OCR (채연) |
| 5장 제목 | 피처 3 — 챗봇 (설계 · 화면 수인 · 서버 채연) | 피처 3 — 챗봇 (수인) |
| 6장 제목 | 피처 4 — 실천 · 보상 (서버 채연 · 화면 수인) | 피처 4 — 실천 · 보상 (담당 미정, 챌린지는 뒤로 미룸) |
| 8. 남은 결정 사항 / 챗봇 API 후보 | 챗봇 서버(채연)를 만들 때 정해서 추가 | 챗봇 담당(수인)이 서버를 만들 때 정해서 추가 |
| 5. 챗봇 / H-2 응답 | `{ items: Message[] }`로 `id` `role` `content` `answerType` `sources` `contextCard` `createdAt` | `safetyCard` 추가 (제안, 점검 결과 카드가 붙은 답을 다시 열었을 때 카드를 그대로 그림) [수인 확인 필요] |
| 5. 챗봇 / H-3 응답 | `{ messageId, answerType, content, sources }` | `safetyCard` 추가 (제안). 카드가 붙는 답도 `answerType`은 `normal`로 두고 카드는 이 칸으로 붙임 (수인 10/8 답: 유형을 새로 만들면 명세서와 화면 라벨이 같이 바뀌어서). 칸 이름은 채연 제안 [수인 확인 필요] |
| 1. 전체 목록 / H-3 설명 | 질문 보내기 (글자가 차례로 나오는 응답) | 질문 보내기 (1단계는 다 만든 뒤 한 번에 응답). 5장 H-3 본문은 이미 이렇게 적혀 있어서 목록만 맞춤 (10/7 수인 답 6번) |
| 4. RAG / R-4 `lifestyle.sections[].actions[]` | `{ text, sourceId }` | `{ text, kind, sourceIds }` (kind는 fact 또는 safety_notice, 문장 하나에 출처가 2개 이상인 곳이 42개라 목록으로) (10/8 채연) |
| 4. RAG / R-4 `lifestyle.sections[]` | `title`, `actions`, `conflict` | `goal` 추가. 해야 할 일 문장이 없는 줄 4개는 `actions`가 빈 배열 (10/8 채연 결정 가) |
| 4. RAG / R-4 `lifestyle.medicationLinks[]` | `{ itemName, advice, requiresClinician, sourceId }` | `{ itemName, requiresClinician, actions[], advice }`. `advice`는 화면이 `actions`로 옮겨 갈 때까지만 같이 내려주고 그 뒤에 지움 (10/8 채연 결정 나) |
| 4. RAG / R-4 `lifestyle.warningSigns[]` | (없음) | 신규. 질환별 위험 신호 문장 (10/8 채연) |
| 4. RAG / R-4 투석 줄 | (없음) | 서버가 투석 여부를 모르면 만성콩팥병 수분 줄을 내려주지 않음. 응답 모양은 그대로 (10/8 채연 결정 라) |
| 4. RAG / R-4 `lifestyle.sections[].conflict` | 질환끼리 권고가 부딪힐 때 `{ message, label }` (조건이 코드로 안 정해져 있었음) | 교차 규칙 4개의 조건(질환 코드 조합)을 정함. `message`는 사람이 쓴 템플릿 (10/8 채연) |

10/6 서면 결정의 "서버는 채연, 화면은 수인"을 10/7 팀 회의에서 피처 단위로 바꿨습니다.

</details>

<details>
<summary><b>v1.5 초안</b> 2026-10-12 R-4 약 번호 추가 2건, 챗봇 정리 8건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 4. RAG / R-4 `medication.items[]` | `{ ediCode, itemName, category, purpose, howToTake, caution, source }` (약 번호 없음) | `itemId` 추가. 값은 `prescription_items.id`로, ERD `chat_sessions.context_ref`가 약에서 챗봇을 열 때 쓰는 번호와 같음. 챗봇은 약 화면에서 열 때 이 값을 `context.id`로 보냄 (10/12 채연, PR #80 요청 4번) |
| 4. RAG / R-4 `lifestyle.medicationLinks[]` | `{ itemName, requiresClinician, actions[], advice }` | `itemId` 추가. 같은 약을 `medication.items[]`와 번호로 이을 수 있게 함. 이름 글자 비교는 약 이름 표기가 달라 맞추기 어려워서 (10/12 채연, PR #80 요청 1번의 R-4 쪽) |
| 5. 챗봇 / H-1 응답 | `{ sessionId }` | `{ sessionId, firstMessage? }`. `context`가 있으면 첫 답변을 함께 줌 (H-7 응답과 같은 모양) (10/12 수인) |
| 5. 챗봇 / H-2 `items[]` | `id` `role` `content` `answerType` `sources` `contextCard` `createdAt` (`safetyCard`는 제안) | `status` 추가 (`generating` 또는 `done`, 화면을 나갔다 와도 만드는 중인 답을 알 수 있게). `safetyCard` 확정, 카드가 없는 답은 칸을 생략 (`null`로 보내지 않음, `contextCard`와 같게) (10/12 수인) |
| 5. 챗봇 / H-3 응답 | `{ messageId, answerType, content, sources }` (`safetyCard`는 제안) | `safetyCard?`, `drugMatch?`, `safety?` 추가. 카드가 붙는 답도 `answerType`은 `normal` (10/12 수인) |
| 5. 챗봇 / H-4 응답 `items[]` | `sessionId` `title` `preview` `updatedAt` | `createdAt` 추가. 날짜와 카드 시각은 대화를 시작한 시각 기준 ⚪ (10/12 수인) |
| 5. 챗봇 / H-8 (신규) | (없음) | `GET /chat/sessions/today`: 들어올 때 이어 갈 오늘 대화 찾기. 찾기만 하고 만들지 않음 🟡 (10/12 수인) |
| 5. 챗봇 / 2단계 API | (없음) | 사진 올리기, 앱이 감지한 긴급 기록, 답변 피드백을 5장 표(H-9 ~ H-11)에 둠 ⚪ (10/12 수인) |
| 1. 전체 목록 / H-9 ~ H-11 — 신규 | (없음) | `POST /chat/sessions/{id}/attachments` 사진, 파일 올리기 (CB-04), `POST /chat/sessions/{id}/safety-events` 앱 감지 긴급 기록 (CB-01-E4), `POST /chat/messages/{id}/feedback` 답변 피드백 (CB-01). 모두 2단계 ⚪ (10/12 수인 댓글: 정리안의 "목록에만"은 1장 목록을 말한 것) |
| 1. 전체 목록 / 챗봇 상태 | H-1, H-2, H-3, H-7 🟡 | H-1, H-2, H-3, H-7 ✅ (모양 정함), H-8 🟡 (10/12 수인) |
| 0. 공통 / `403 FORBIDDEN` | 로그인 화면으로 보내지 않고 `message`를 안내 [수인 확인 필요] | 로그인 화면으로 보내지 않고 `message`를 안내. 챗봇 화면은 `message`를 오류 카드 자리에 보여 주고 [다시 시도]는 숨김 (10/12 수인 확인) |

</details>

<details>
<summary><b>v1.5 초안 추가</b> 2026-10-16 별명 제거, R-4 복약 안내, OCR 응답 필드 세부 13건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 2. 회원 / A-1 요청 | `nickname` (선택, 50자 이내) | 삭제 — 홈 인사말을 뺐고(3회차 멘토링 · 10/7 회의) 인사말용 별명이 쓸 곳이 없어 최소 수집 원칙에 맞춤 (10/14 팀 합의 · #96) |
| 2. 회원 / A-1 · A-2 응답 `user` | `{ id, nickname, birthYear, sex }` | `{ id, birthYear, sex }` |
| 2. 회원 / U-1 응답 · 화면 | 화면 `CM-03 (인사말) · CM-05`, 응답에 `nickname` | 화면 `CM-05`, `nickname` 삭제 |
| 2. 회원 / U-2 요청 | `{ nickname, birthYear, sex }` | `{ birthYear, sex }` |
| 4. RAG / R-4 `medication.items[].purpose` 예시 | `"혈압을 낮춰요"` | `"혈압 관리에 쓰는 약이에요"` — 의료 표현 목록(#61)의 "효과를 약속하는 말"을 피해 "~에 쓰는 약이에요" 꼴로 통일 |
| 4. RAG / R-4 `medication.items[].caution` 예시 | `"어지러울 수 있으니 천천히 일어나세요"` | 허가정보 문장을 줄바꿈으로 이은 문자열 |
| 4. RAG / R-4 `medication.items[].cautions` | (없음) | 문장별 배열 추가 (최대 3개, 없으면 빈 배열). 수인 찬성 (10/16 PR #97 리뷰) |
| 4. RAG / R-4 `medication.items[]` 채우는 기준 | 근거가 없으면 `null` | 미리 저장한 안내문(`drug_guides`) 중 사람이 확인한(approved) 약만 채움. 아니면 `purpose`는 "처방받은 목적을 약사에게 확인해 주세요", 나머지는 `null` |
| 3. OCR / O-5 응답 | `prescriptionIds`, `failedFiles` | `duplicatedFiles[{ fileIndex, prescriptionId }]` 추가 (같은 사진 중복 업로드) |
| 3. OCR / O-2 응답 `items[]` | `itemName`, `suggestedBy`, `guidance`, `checkFields` 없음 | 4개 추가 (코드에는 이미 있음, 문서에 빠져 있던 것) |
| 3. OCR / O-2 응답 최상위 | `notices` 없음 | `notices[]` 추가 |
| 4. RAG / R-4 `summary.drugCount` | 올라온 약 전체 개수 | 점검한 약(먹는 약)만 셈. 외용약은 `excludedDrugs`에 `not_oral`로 나옴 |
| 머리말 / 작성 기준 (ERD) | ERD v1.5 초안 (10/12) | `users.nickname` 삭제 · `drug_guides` 추가 반영 (ERD 변경 이력 참고) |

</details>

<details>
<summary><b>v1.5 초안 추가</b> 2026-10-19 건강 정보 (수인) 세부 7건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 2. 회원 / A-1 요청 | (없음) | `health: { smoking, drinking }` 필수. 값은 국민건강영양조사 문항(BS3_1, BD1_11)에 `unknown`("잘 모르겠어요")을 더함 (10/14 회의 3번, 10/19 수인) |
| 2. 회원 / U-1 응답 | (없음) | `health: { smoking, drinking, diseases, pregnant, dialysis, heightCm, weightKg, upcomingExams }` 추가 |
| 2. 회원 / U-2 요청 | `{ birthYear, sex }` | `health` 안에서 바꿀 칸만 보냄. `diseases`는 생활습관 질환 id(`lifestyle_diseases.id`), `pregnant`는 여성만, `sex`를 `M`으로 바꾸면 `pregnant`를 비움 |
| 2. 회원 / U-3 삭제 | 처방전 ~ 동의 기록 | 건강 정보 추가 |
| 2. 회원 / U-5 삭제 | 처방전 ~ 챗봇 대화 | 건강 정보 추가 |
| 1. 전체 목록 / U-1 화면 | CM-03 · CM-05 | CM-05 (홈 인사말을 빼서, 2장 U-1과 맞춤. #96) |
| 머리말 / 작성 기준 (ERD) | ERD v1.5 초안 | `user_health_profiles`, `analyses.health_snapshot` 추가 반영 (ERD 변경 이력 참고) |

</details>

<details>
<summary><b>v1.5 초안 추가</b> 2026-10-20 분석 질환에 내 정보 질환 (수인) 세부 1건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 4. RAG / R-4 `lifestyle.diseases[].origin` | `prescription` / `user` | `prescription` / `profile` / `user`. 분석을 시작할 때 처방전 질환 뒤에 내 정보 질환을 대표 질병분류기호로 넣고, 처방전에 같은 질환이 있으면 코드가 달라도 뺌 (#101, 10/19 합의) |

</details>

<details>
<summary><b>v1.5 초안 추가</b> 2026-10-22 챗봇 질문 보내기를 202로 (수인) 세부 18건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 5. 챗봇 / H-3 응답 | `201` `{ messageId, answerType, content, sources }`. 1단계는 답을 다 만든 뒤 검사하고 한 번에 보냄 | `202` `{ messageId }` (답 줄 번호). 서버는 `202`를 돌려주기 전에 `generating` 답 줄을 만들어 둠. 답은 H-2로 받음 (10/6 디코에서 수인이 말한 방식, 10/21 수인 결정, 답 줄을 먼저 만드는 것은 10/22, #100) |
| 5. 챗봇 / H-3 `content` | 길이 규칙 없음 | 앞뒤 공백을 지운 뒤 1~500자, 벗어나면 `400 VALIDATION_ERROR` (10/21 회의 4절에서 #100에 맡김, 500자는 설계 메모 4-8, 9 항목) |
| 5. 챗봇 / H-3 `clientRequestId` | 다시 시도(CB-01-E6) 때 같은 값을 보내면 질문을 두 번 저장하지 않음 | 위와 같고, 답 줄이 있으면 같은 `messageId`를 돌려줌. 답 줄이 실패로 지워졌거나 만드는 중으로 30초를 넘었으면(답 줄을 만든 때부터, 넘은 줄은 지움) 답을 새로 만들어 새 `messageId`를 돌려줌 (10/22) |
| 5. 챗봇 / 답 만들기 실패 | 명세서에 없음 (ERD: 답을 저장하지 않고 앱이 E6) | 만드는 중이던 답 줄을 지움. 앱은 그 줄이 없어지면 E6 (`failed`는 두지 않음 10/12, 줄을 지우는 것은 10/22) |
| 5. 챗봇 / 1층이 잡은 질문 | 명세서에 없음 (설계 메모 4-6: 원문을 저장하지 않음) | H-3에서 질문을 저장하기 전에 1층과 문맥 파악을 봄. 1층에 걸리고 문맥 파악이 풀지 않으면 질문 원문을 저장하지 않고(`content`는 빈 글) 긴급 답 줄을 바로 `done`으로 만든 뒤 `202` (10/22, #100) |
| 5. 챗봇 / H-3 `emergencyDismissed` | 없음 | [지금은 증상이 없어요] 뒤 같은 질문을 다시 보낼 때 `true`. 1층 응급 규칙과 2층 `emergency`를 건너뛰고 자해(`crisis`)는 그대로 봄 (설계 메모 3-3, 2층은 10/22, #100) |
| 5. 챗봇 / H-1, H-7 `firstMessage` | `context`가 있으면 첫 답변을 함께 줌 | 위와 같고, #100에서는 아직 보내지 않음 (#116) |
| 5. 챗봇 / H-8 `safetyModeUntil` | 1단계는 같은 대화 안에서만 씀 | 위와 같고, 1단계는 `crisis`가 나온 날 자정(한국 시간)까지 (10/22, #100) |
| 5. 챗봇 / H-2 답 줄 `replyTo` | 없음 | 답 줄이 어느 질문의 답인지 질문 줄 번호. 다시 시도한 답이 대화 맨 아래에 생겨도 짝을 찾고 질문을 인용할 수 있게 (설계 메모 4-7, 10/22, #100) |
| 5. 챗봇 / H-1 `analysisId` | 없으면 일반 질문 모드 | 위와 같고, 대화에만 적고 맥락 카드 줄은 만들지 않음. 맥락 카드 줄은 H-7에서만 만듦 (10/22, #100) |
| 5. 챗봇 / H-7 다시 보내기 | 요청에 `clientRequestId`만 있음 | 같은 `clientRequestId`면 맥락 카드 줄을 새로 만들지 않음 (10/22, #100) |
| 5. 챗봇 / H-2 1층이 잡은 질문 줄 표시 | (없음) | 원문 대신 안내 글을 흐리게 보이고 복원된 카드의 [지금은 증상이 없어요]는 비활성화. 설계 메모 4-6의 앱 감지 경우(원문이 서버에 없음)와 같게 (10/22 #100) |
| 5. 챗봇 / 답에 붙는 칸 | `safetyCard`, `drugMatch`, `safety`를 H-3 응답에 | H-2 답 줄에 실음. `drugMatch`는 지금 코드에서 만들지 않아 만들 때 저장 방법을 정함 (확정 전) |
| 1. 전체 목록 / H-3 설명 | 질문 보내기 (1단계는 다 만든 뒤 한 번에 응답) | 질문 보내기 (`202`로 받고 답은 H-2로 확인) |
| 3. OCR / O-4 챗봇 줄 | 질문에서 약 이름을 찾으면 H-3 응답에 `drugMatch` | H-2 답 줄에 `drugMatch`. 지금 코드에서 만들지 않아 만들 때 저장 방법을 정함 (확정 전, 10/22 #100) |
| 4. RAG / R-8 구현 범위 | 챗봇 대화는 해당 표가 서버에 생길 때 이어서 처리 | 분석을 지우면 그 분석으로 시작한 대화(`chat_sessions.analysis_id`)와 그 분석의 맥락 카드가 붙은 대화를 메시지째 지움. 1단계는 하루 한 대화라 그날 분석과 상관없는 질문과 그 대화의 안전 모드도 함께 지워짐 (10/23, #119 채연 리뷰, 10/22의 "연결만 비움"을 바꿈) |
| 7. ERD 반영 사항 | 13번까지 | 14번 `chat_messages.safety` 추가 |
| 7. ERD 반영 사항 | 14번까지 | 15번 `chat_messages.reply_to_id` 추가 |

</details>

<details>
<summary><b>v1.5 초안 추가</b> 2026-10-28 탈퇴와 동의 철회를 서버에 맞춤 (수인) 세부 8건</summary>

| 위치 | 현행 (As-Is) | 개정 (To-Be) |
|---|---|---|
| 2. 회원 / U-3 삭제 | 처방전부터 동의 기록, 건강 정보까지 | 맨 앞에 보관 중인 처방전 사진(올린 지 24시간 안) |
| 2. 회원 / U-3 남김 | `id`, `deleted_at`만 남김 | 개인정보를 지우고 `deleted_at`을 남김, 다른 칸은 자리 값으로 덮어씀(`withdrawn-{id}`, 무작위 비밀번호, 출생연도 0, 성별 M) |
| 2. 회원 / U-3 탈퇴 뒤 | 없음 | 재발급권 쿠키를 지움. 로그인과 API는 `401`, 재발급(A-4)은 탈퇴 여부를 보지 않음 |
| 2. 회원 / U-3 `400` | `confirmed`가 `true`가 아님 | 본문이 없을 때도 |
| 2. 회원 / U-4 응답 | `type`, `agreed`, `agreedAt` | `withdrawnAt` 추가 (철회하지 않았으면 `null`) |
| 2. 회원 / U-5 삭제 | 처방전부터 챗봇 대화, 건강 정보까지 | 맨 앞에 보관 중인 처방전 사진(올린 지 24시간 안) |
| 2. 회원 / U-5 응답 | 없음 | `204`, 이미 철회했으면 다시 불러도 `204`, `sensitiveHealth`가 아니면 `400 VALIDATION_ERROR`(`field: type`) |
| 1. 전체 목록, 2. 회원 / U-6, 8. 남은 결정 사항 | 없음 | 다시 동의 `PUT /users/me/consents/{type}` 제안, 상태는 담당자 확정 필요, 정할 것 2가지 (#137) |

</details>

---

> Figma 통합 와이어프레임(50개 화면, 화면 번호표 v0.6) 요구사항 정의서 v1.5 ERD v1.3 기준입니다. (53개는 10/6 오전 결정이었고, 그날 오후 CB-05가 음성에서 받아쓰기로 바뀌면서 50개로 다시 바뀌었어요. main의 v1.3과 맞췄어요)
> 화면 번호는 [화면 번호 통합표](screen_id_table.md) 기준입니다 (CM 공통 · MY 내정보 설정 · OC OCR · RG RAG · CB 챗봇 · RW 실천·보상).
> 피처 1 · 3 · 4 항목(🟡)은 담당자가 확정하면 변경 이력에 기록하고 상태를 ✅로 바꿔 주세요.
>
> 상태 표시 — ✅ 초안 작성 완료 · 🟡 담당자 확정 필요 · ⚪ 선택 구현

---

## 0. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기본 주소 | `/api/v1` |
| 형식 | 요청 · 응답 모두 JSON (`Content-Type: application/json`). 업로드만 `multipart/form-data` |
| 인증 | 로그인 후 받은 출입증(`accessToken`, 60분)을 헤더에 넣음 — `Authorization: Bearer {accessToken}`. 끝나면(`401 TOKEN_EXPIRED`) 재발급권(`refreshToken`, 14일)으로 A-4를 불러 새로 받음 |
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
| 403 | `FORBIDDEN` | 권한이 없음 (지금은 쓰는 곳 없음 — 나중에 권한 오류가 생길 때 `UNAUTHORIZED`와 구분하려고 만들어 둠) | 로그인 화면으로 보내지 않고 `message`를 안내. 챗봇 화면은 `message`를 오류 카드 자리에 보여 주고 [다시 시도]는 숨김 (수인 10/12 확인) |
| 404 | `NOT_FOUND` | 없음 (또는 남의 데이터) | CM-08 또는 목록으로 |
| 429 | `TOO_MANY_REQUESTS` | 요청이 너무 많음 | CM-08 "잠시 후 다시" |
| 500 | `INTERNAL_ERROR` | 서버 오류 | CM-08 "잠시 문제가 생겼어요" |
| 503 | `EXTERNAL_API_ERROR` | OCR · LLM 등 외부 서비스 오류 | CM-08 또는 각 피처 예외 화면 |

---

## 1. 전체 목록

| # | 메서드 | 주소 | 설명 | 화면 | 담당 | 상태 |
|---|---|---|---|---|---|---|
| A-1 | POST | `/auth/signup` | 회원가입 | CM-02 · CM-02-E1 | 수인 | ✅ |
| A-2 | POST | `/auth/login` | 로그인 | CM-01 · CM-01-E1 · CM-01-E2 | 수인 | ✅ |
| ~~A-3~~ | ~~POST~~ | ~~`/auth/logout`~~ | 로그아웃 — **10/6 결정으로 넣지 않음** | - | 수인 | - |
| A-4 | POST | `/auth/token/refresh` | 출입증 다시 받기 | (화면 없음 · 모든 화면 공통) | 수인 | ✅ |
| U-1 | GET | `/users/me` | 내 정보 조회 | CM-05 | 수인 | ✅ |
| U-2 | PATCH | `/users/me` | 내 정보 수정 | CM-06 | 수인 | ✅ |
| U-3 | DELETE | `/users/me` | 회원 탈퇴 | CM-07 | 수인 | ✅ |
| U-4 | GET | `/users/me/consents` | 동의 내역 조회 | CM-05 | 수인 | ✅ |
| U-5 | DELETE | `/users/me/consents/{type}` | 동의 철회 | CM-05 | 수인 | ✅ |
| U-6 | PUT | `/users/me/consents/{type}` | 다시 동의 | CM-05 | 수인 | ✅ |
| O-1 | POST | `/prescriptions` | 처방전 · 약봉투 업로드 → OCR 작업 시작 (`202`) | OC-01 | 채연 | 🟡 |
| O-2 | GET | `/prescriptions/{id}` | 인식 결과 조회 | OC-02 | 채연 | 🟡 |
| O-3 | PATCH | `/prescriptions/{id}/items/{itemId}` | 인식 결과 수정 · 후보 선택 | OC-02 | 채연 | 🟡 |
| O-4 | GET | `/drugs/search` | 약 이름 검색 (직접 입력용) | OC-02 | 채연 | 🟡 |
| O-5 | GET | `/ocr-jobs/{jobId}` | OCR 작업 상태 (폴링) | OC-01 → OC-02 · OC-01-E1 · OC-01-E3 · OC-02-E1 | 채연 | 🟡 |
| R-1 | POST | `/analyses` | 분석 시작 | OC-02 → RG-01 | 채연 | ✅ |
| R-2 | GET | `/analyses/{id}/status` | 분석 진행 상태 (폴링) | RG-01 · RG-01-E1 | 채연 | ✅ |
| R-3 | POST | `/analyses/{id}/retry` | 실패한 분석 다시 시도 | RG-01-E1 | 채연 | ✅ |
| R-4 | GET | `/analyses/{id}` | 분석 결과 (탭 3개 전체) | RG-02 · RG-02-E1 · RG-04 · RG-05 | 채연 | ✅ |
| R-5 | GET | `/analyses/{id}/warnings/{warningId}` | 경고 자세히 | RG-03 | 채연 | ✅ |
| R-6 | PUT | `/analyses/{id}/diseases` | 질환 직접 선택 | RG-05-E1 | 채연 | ✅ |
| R-7 | GET | `/analyses` | 지난 기록 목록 | CM-03 · CM-04 | 채연 | ✅ |
| R-8 | DELETE | `/analyses/{id}` | 기록 삭제 | CM-04-E1 | 채연 | ✅ |
| R-9 | POST | `/guides/{guideId}/feedback` | 안내문 피드백 | RG-04 | 채연 | ✅ |
| R-10 | GET | `/guides/{guideId}/tts` | 안내문 음성 | RG-04 | 채연 | ⚪ |
| H-1 | POST | `/chat/sessions` | 대화 시작 | CB-01 · CB-01-E1 · CB-01-E2 | 수인 | ✅ |
| H-2 | GET | `/chat/sessions/{id}/messages` | 이전 대화 조회 | CB-01 | 수인 | ✅ |
| H-3 | POST | `/chat/sessions/{id}/messages` | 질문 보내기 (`202`로 받고 답은 H-2로 확인) | CB-01 · CB-01-E2 | 수인 | ✅ |
| H-4 | GET | `/chat/sessions?date=` · `?month=` | 날짜별 대화 목록 | CB-02 · CB-03 | 수인 | ⚪ |
| H-5 | PATCH | `/chat/sessions/{id}` | 대화 제목 수정 | CB-03 | 수인 | ⚪ |
| H-6 | DELETE | `/chat/sessions/{id}` | 대화 삭제 | CB-03 · MY-S1 | 수인 | ✅ |
| H-7 | POST | `/chat/sessions/{id}/context` | 오늘 대화에 분석 맥락 붙이기 (1단계) | CB-01-E2 | 수인 | ✅ |
| H-8 | GET | `/chat/sessions/today` | 오늘 대화 찾기 (찾기만 하고 만들지 않음) | CB-01 · CB-01-E1 | 수인 | 🟡 |
| H-9 | POST | `/chat/sessions/{id}/attachments` | 사진, 파일 올리기 (2단계) | CB-04 | 수인 | ⚪ |
| H-10 | POST | `/chat/sessions/{id}/safety-events` | 앱에서 먼저 감지한 긴급, 자해 기록 (2단계) | CB-01-E4 | 수인 | ⚪ |
| H-11 | POST | `/chat/messages/{id}/feedback` | 답변 피드백 (2단계) | CB-01 | 수인 | ⚪ |
| P-1 | GET | `/recommendations?analysisId=` | 생활습관 추천 목록 | RG-05 | 채연 | 🟡 |
| P-2 | POST | `/habit-goals` | 실천 목표 만들기 (최대 3개) | RW-02 | 채연 | 🟡 |
| P-3 | GET | `/habit-goals/today` | 오늘의 실천 | CM-03 · RW-03~05 · RW-03-E2 | 채연 | 🟡 |
| P-4 | POST | `/habit-goals/{goalId}/records` | 실천 기록 (체크 · 수량) | RW-03 · RW-04 · RW-03-E1 | 채연 | 🟡 |
| P-5 | GET | `/habit-goals/history?period=week` | 주간 달성 현황 | RW-06 · RW-06-E1 | 미정 | 🟡 |
| P-6 | GET | `/rewards/summary` | 포인트 요약 | RW-05 · RW-06 | 미정 | 🟡 |

> 홈(CM-03)은 별도 API를 만들지 않고 U-1 + R-7(`size=1`) + P-3을 함께 호출합니다.
> 프론트가 1명이라 **API 개수를 늘리지 않는 쪽**으로 잡았습니다. 결과 화면도 탭별로 나누지 않고 R-4 한 번에 받습니다.

---

## 2. 인증 · 회원 (공통, 수인)

### A-1. 회원가입 `POST /auth/signup`

화면 CM-02 · CM-02-E1 · 요구사항 REQ-001, REQ-005 · 인증 불필요

> 건강 정보(`health`)는 민감정보 동의(`sensitiveHealth`) 범위예요. 가입 때는 흡연과 음주만 받고, 나머지는 내 정보(U-2)에서 받아요 (10/14 회의). A-1, A-2 응답의 `user`에는 건강 정보를 넣지 않아요

**요청**
```json
{
  "email": "hong@email.com",
  "password": "abcd1234",
  "birthYear": 1958,
  "sex": "M",
  "health": { "smoking": "never", "drinking": "monthly" },
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
| birthYear | ✅ | 1900 ~ 올해. 노인주의 · 연령금기 판정에 사용 |
| sex | ✅ | `M` / `F` |
| health.smoking | ✅ | `daily` 매일 / `sometimes` 가끔 / `past` 예전에 피웠지만 지금은 안 피움 / `never` 피운 적 없음 / `unknown` 잘 모르겠어요 (국민건강영양조사 BS3_1) |
| health.drinking | ✅ | `none` 최근 1년간 안 마심 / `lt_monthly` 월 1회 미만 / `monthly` 월 1회 정도 / `2_4_monthly` 월 2~4회 / `2_3_weekly` 주 2~3회 / `4plus_weekly` 주 4회 이상 / `unknown` 잘 모르겠어요 (국민건강영양조사 BD1_11) |
| consents.* | ✅ | 세 개 모두 `true`여야 가입 가능 |

**응답 `201`** — 가입과 동시에 로그인 처리 (A-2 로그인 응답과 같은 모양)
```json
{
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "eyJhbGciOi...",
  "user": { "id": 12, "birthYear": 1958, "sex": "M" }
}
```
- 재발급권 쿠키 `refresh_token`도 같이 보냄 (A-2와 같음)

**에러**
| HTTP | code | 화면 |
|---|---|---|
| 409 | `EMAIL_DUPLICATED` (`field: email`) | CM-02-E1 "이미 가입된 이메일이에요" |
| 400 | `VALIDATION_ERROR` (`field: password` 등) | CM-02-E1 해당 칸. 명세서에 없는 칸(예: 지운 `nickname`)을 보내도 이 에러 |
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
  "refreshToken": "eyJhbGciOi...",
  "user": { "id": 12, "birthYear": 1958, "sex": "M" }
}
```

- `accessToken` (출입증): 60분. `refreshToken` (재발급권): 14일 — 앱은 expo-secure-store에 저장 (10/6 결정)
- 쿠키 `refresh_token`도 같이 보냄 (웹 · Swagger에서 시험할 때용, 앱은 안 써도 됨)

**에러**
| HTTP | code | detail | 화면 |
|---|---|---|---|
| 401 | `AUTH_INVALID_CREDENTIALS` | `{ "remainingAttempts": 2 }` | CM-01-E1 "(3 / 5회)" |
| 423 | `AUTH_LOCKED` | `{ "lockedUntil": "2026-09-23T14:15:00+09:00" }` | CM-01-E2 남은 시간 표시 |

> 보안상 이메일이 없는 경우와 비밀번호가 틀린 경우를 **같은 에러**로 응답합니다.

---

### ~~A-3. 로그아웃 `POST /auth/logout`~~ — 넣지 않음 (10/6 결정)

멘토님 "없어도 됨"에 따라 10/6 결정으로 넣지 않음. 앱에 저장한 값은 탈퇴 · 동의 철회 때만 지움

---

### A-4. 출입증 다시 받기 `POST /auth/token/refresh`

화면 없음 (모든 화면 공통) · 요구사항 REQ-008 · 인증 불필요

**요청**
```json
{ "refreshToken": "eyJhbGciOi..." }
```
- 본문이 없으면 쿠키 `refresh_token`을 읽음 (웹 · Swagger용)
- `GET`이 아니라 `POST`인 이유: `GET` 요청에는 본문을 실을 수 없음

**응답 `200`**
```json
{ "accessToken": "eyJhbGciOi..." }
```
- 재발급권은 새로 주지 않음 → 로그인 14일 뒤에는 다시 로그인 (10/6 결정)

**에러**
| HTTP | code | 언제 | 화면 |
|---|---|---|---|
| 401 | `TOKEN_EXPIRED` | 재발급권도 끝남 (14일 지남) | CM-08 "다시 로그인해 주세요" → CM-01 |
| 401 | `UNAUTHORIZED` | 재발급권이 없거나 잘못됨 (출입증을 넣은 경우 포함) | CM-01 로그인 |

**앱에서 하는 순서**
1. 아무 API나 부름 → `401 TOKEN_EXPIRED` (출입증 60분 끝남)
2. A-4를 부름 → 새 출입증을 저장
3. 1번 요청을 **한 번만** 다시 보냄
4. A-4도 401이면 → 저장한 두 값을 지우고 로그인 화면

---

### U-1. 내 정보 조회 `GET /users/me`

화면 CM-05

**응답 `200`**
```json
{
  "id": 12,
  "email": "hong@email.com",
  "birthYear": 1958,
  "sex": "M",
  "createdAt": "2026-09-20T10:00:00+09:00",
  "health": {
    "smoking": "never",
    "drinking": "monthly",
    "diseases": ["HTN", "DM2"],
    "pregnant": null,
    "dialysis": null,
    "heightCm": 165,
    "weightKg": 62.5,
    "upcomingExams": [{ "name": "조영 CT", "date": "2026-10-27" }]
  }
}
```

---

### U-2. 내 정보 수정 `PATCH /users/me`

화면 CM-06 · 바꿀 필드만 보냄

**요청**
```json
{ "birthYear": 1958, "sex": "M", "health": { "dialysis": "no", "upcomingExams": [] } }
```
- `health` 안에서도 바꿀 칸만 보냄. 목록 칸(`diseases`, `upcomingExams`)은 보낸 목록으로 통째로 바꿈

| 필드 | 규칙 |
|---|---|
| health.smoking, health.drinking | A-1과 같음 |
| health.diseases | 생활습관 질환 id(`HTN` `DM2` `DLP` `CKD` `IHD` `STROKE` `AF` `COPD` `OP` `OA`, `lifestyle_diseases.id`) 중에서 (10/14 회의 3번 채연 안) |
| health.pregnant | `yes` / `no` / `null`. `sex`가 `F`일 때만. `sex`를 `M`으로 바꾸면 저장된 값을 비움 |
| health.dialysis | `yes` / `no` / `unknown` / `null` |
| health.heightCm, health.weightKg | 0보다 큰 수. 키는 정수, 몸무게는 소수 한 자리까지 |
| health.upcomingExams[] | `name` 50자 이내, `date`는 `YYYY-MM-DD` |

**응답 `200`** — U-1과 같은 형식

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `email`을 보내면 거절 (수정 불가 항목). 위 `health` 규칙에 맞지 않으면 그 칸을 `field`로 (예: `health.pregnant`) |

> 출생연도, 성별, 건강 정보가 바뀌면 **다음 분석부터** 반영. 지난 결과는 다시 계산하지 않음
> 분석은 처방전 질환과 `health.diseases`를 합쳐 씀. 질환 기준으로 중복을 빼고(한 질환에 코드가 여러 개라 코드가 달라도 같은 질환이면 하나) 대표 질병분류기호로 바꿔 넣으며 출처는 `profile`, RG-05-E1을 미리 채움(사용자가 빼거나 더할 수 있음) (10/19 채연 제안으로 확인됨, 구현은 #105 다음 PR에서 수인, 리뷰 채연)

---

### U-3. 회원 탈퇴 `DELETE /users/me`

화면 CM-07 · 요구사항 REQ-004

**요청**
```json
{ "confirmed": true }
```

응답 `204` · 아래 데이터를 **즉시 삭제**하고, 사용자 행은 개인정보를 지우고 `deleted_at`을 남김 (10/6 확정, 남는 칸은 아래 표)

| 삭제 | 남김 |
|---|---|
| 보관 중인 처방전 사진(올린 지 24시간 안), 처방전 · OCR 원문 · 처방 약 · 분석 · 경고 · 안내문 · 피드백 · 챗봇 대화 · 실천 목표 · 실천 기록 · 포인트 · 동의 기록, 건강 정보 | `users` 행의 `id` · `deleted_at` (탈퇴 처리 확인용). 다른 칸은 비울 수 없어 자리 값으로 덮어씀: `login_id`는 `withdrawn-{id}`(같은 이메일로 다시 가입할 수 있게), 비밀번호는 무작위 값, `birth_year` 0, `sex` M. 개인정보는 남지 않음 (10/28, #136) |

- 탈퇴하면 재발급권 쿠키를 지우고, 그 뒤 로그인은 `401`. 남은 출입증이나 재발급권으로 받은 출입증으로 부르는 API도 `401` (재발급 A-4는 탈퇴 여부를 보지 않음, 10/28 #136)

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | `confirmed`가 `true`가 아니거나 본문이 없음 |

---

### U-4. 동의 내역 조회 `GET /users/me/consents`

화면 CM-05 → 민감정보 동의 내역

**응답 `200`**
```json
{
  "items": [
    { "type": "terms", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00", "withdrawnAt": null },
    { "type": "privacy", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00", "withdrawnAt": null },
    { "type": "sensitiveHealth", "agreed": true, "agreedAt": "2026-09-20T10:00:00+09:00", "withdrawnAt": null }
  ]
}
```
- `withdrawnAt`: 철회한 시각, 철회하지 않았으면 `null`. 철회하면 `agreed`는 `false`이고 `agreedAt`은 처음 동의한 시각 그대로 (10/28, #136)

### U-5. 동의 철회 `DELETE /users/me/consents/{type}`

`type = sensitiveHealth`만 철회 가능. 철회하면 업로드 · 분석 API가 `403 CONSENT_REQUIRED`.

**철회 시 파기 범위** (10/6 확정, REQ-007)

| 삭제 | 남김 |
|---|---|
| 보관 중인 처방전 사진(올린 지 24시간 안), 처방전 · OCR 원문 · 처방 약 · 분석 · 경고 · 안내문 · 피드백 · 챗봇 대화 (건강 정보가 들어 있을 수 있음), 건강 정보(`user_health_profiles`) | 실천 목표(`status = ended`로 종료, 추천 연결 `recommendation_id`는 비움 — 질환 라벨 `reason_label`은 추천과 함께 삭제) · 실천 기록 · 포인트 · 동의 기록(철회 시각 포함) |

응답 `204`. 이미 철회했으면 다시 불러도 `204`(아무것도 바뀌지 않음) (10/28, #136)

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` (`field: type`) | `sensitiveHealth`가 아님 (terms, privacy는 철회할 수 없음) |

### U-6. 다시 동의 `PUT /users/me/consents/{type}` (#137)

화면 CM-05 → 동의 내역

`type = sensitiveHealth`만. U-5로 철회한 뒤 다시 동의할 때 씀. 앱은 가입 때와 같은 건강 정보 동의 글을 다시 보여 주고 [동의하기]를 눌렀을 때만 부름

**요청**
```json
{ "agreed": true }
```

응답 `204`. 이미 동의한 상태면 다시 불러도 `204`, 동의 줄이 없으면 새로 만듦. 다시 동의하면 업로드와 분석이 다시 됨. 같은 줄의 `agreed`를 true, `agreedAt`을 새 시각으로 고치고 `withdrawnAt`은 비움(철회 이력은 남기지 않음). 철회 때 지운 기록은 돌아오지 않음 (10/31 수인이 시연 전에 넣기로 함, 기록 방식은 #137 제안대로)

| HTTP | code | 설명 |
|---|---|---|
| 400 | `VALIDATION_ERROR` (`field: type`) | `sensitiveHealth`가 아님 |
| 400 | `VALIDATION_ERROR` (`field: agreed`) | `agreed`가 `true`가 아니거나 본문이 없음 (끄기는 U-5) |

정할 것 (#137)
- 동의 기록: (제안) 같은 줄의 `agreed`를 `true`, `agreedAt`을 새 시각으로, `withdrawnAt`은 비움. 대가: 처음 동의한 시각과 철회 기록이 남지 않음. 이력을 남기려면 동의 기록을 줄마다 쌓는 표로 바꿔야 하고 마이그레이션과 동의 확인 코드(has_health_consent)도 바뀜
- 11/5 시연 전에 넣을지

---

## 3. 피처 1 — OCR (채연) 🟡

> 피처 2와 **주고받는 형식만** 먼저 맞추기 위한 최소 정의입니다. 세부 사항은 담당자가 확정해 주세요.

### O-1. 업로드 + OCR `POST /prescriptions`

`multipart/form-data` · `files[]` **최대 5장** (OC-01에서 이어서 찍은 사진을 한 번에) · 1장 10MB 이하 · JPG / PNG / PDF (REQ-010~014)
사진마다 품질 검사를 하고, 한 장이라도 문제가 있으면 해당 사진 번호를 `detail.fileIndex`로 알려줌

**응답 `202`** — 파일 검사만 바로 하고, OCR은 작업으로 돌린 뒤 O-5로 결과를 조회 (NFR-001 · NFR-002) 🟡 채연 확인
```json
{ "jobId": 9001, "status": "queued" }
```

| HTTP | code | 화면 |
|---|---|---|
| 400 | `FILE_TOO_LARGE` · `FILE_TYPE_NOT_SUPPORTED` · `TOO_MANY_FILES` | OC-01 업로드 실패 안내 (바로 응답) |
| 429 | `DAILY_LIMIT_EXCEEDED` (`detail`: `limit`, `used`) | 하루(한국 시간 자정부터) 올릴 수 있는 사진 수(`OCR_DAILY_FILE_LIMIT`, 기본 30장) 초과. 작업을 만들지 않아 OCR을 부르지 않음. 앱은 서버 문구를 그대로 보여 줌 |

사진 품질 · 문서 여부 · 인식 실패는 O-5 결과의 `failedFiles[].code`로 알려줌

### O-5. OCR 작업 상태 `GET /ocr-jobs/{jobId}` 🟡

화면 OC-01 → OC-02 · 요구사항 REQ-013 · NFR-002 — 1초 간격 폴링 (R-2와 같은 방식)

**응답 `200`**
```json
{
  "jobId": 9001,
  "status": "done",
  "prescriptionIds": [101, 102],
  "failedFiles": [
    { "fileIndex": 2, "code": "IMAGE_QUALITY_LOW" }
  ],
  "duplicatedFiles": [
    { "fileIndex": 3, "prescriptionId": 101 }
  ]
}
```

- `duplicatedFiles`: 같은 사진을 두 번 올리면 다시 읽지 않고, 먼저 읽은 사진의 처방전 번호를 알려줌 (없으면 빈 배열)

| `status` · `failedFiles[].code` | 화면 |
|---|---|
| `queued` · `running` | OC-01 "읽는 중" |
| `done` + `failedFiles` 비어 있음 | OC-02 |
| `IMAGE_QUALITY_LOW` | OC-01-E1 "다시 찍어 주세요" (해당 사진 번호 표시) |
| `NOT_A_DOCUMENT` | OC-01-E3 "문서를 찾지 못했어요" |
| `failed` · `OCR_FAILED` | OC-02-E1 재촬영 + 직접 입력 경로 |

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
      "itemSeq": null,
      "itemName": null,
      "suggestedBy": "similar",
      "candidates": [
        { "ediCode": "645301220", "itemSeq": null, "itemName": "노바스크정5밀리그람", "score": 0.82 },
        { "ediCode": "...", "itemSeq": null, "itemName": "아모디핀정5밀리그람", "score": 0.79 }
      ],
      "dosePerTime": 1,
      "timesPerDay": 1,
      "totalDays": 30,
      "timing": "아침 식후",
      "guidance": [],
      "checkFields": []
    }
  ],
  "notices": []
}
```

- `docType`: `prescription`(처방전) / `pill_bag`(약봉투) — 약봉투는 `diseaseCodes`가 빈 배열 → RG-05-E1로 이어짐
- `matchStatus`: `auto`(자동 확정) / `needs_confirm`(후보 선택 필요) / `user_confirmed` / `unmatched`(끝내 못 찾음)
- `itemName`: 약이 정해진 항목(`auto`, `user_confirmed`)만 약 이름이 있고, 나머지는 `null`
- `suggestedBy`: `needs_confirm` 항목에서 후보를 어떻게 찾았는지 (`similar` 이름이 비슷한 약 / `llm` 모델이 고른 후보 / `null` 후보 없음). 다른 상태에서는 `null`
- `guidance[]`: 약봉투에 적힌 복약 안내 문장 (개인정보는 가린 뒤 저장). 처방전이거나 없으면 빈 배열
- `checkFields[]`: 값이 이상해서 사용자가 다시 확인해야 할 칸 이름 (`"1회량"`, `"하루 횟수"`, `"총 일수"`). 문제가 없거나 점검에서 뺀 약이면 빈 배열
- `notices[]`: 읽는 중 만든 확인 안내 문장 (예: 약 줄 수가 맞지 않음). 없으면 빈 배열
- `issuedDate`: 처방전은 처방 교부일, 약봉투는 조제일 (약봉투에는 교부일이 없음)
- `ediCode` · `itemSeq`: 약이 정해진 항목과 후보는 둘 중 하나는 꼭 있음 (O-4와 같은 규칙). 급여목록에 없는 약(일반약 등)은 `itemSeq`만 있고 `ediCode`는 null (예시의 `itemSeq: null`은 값을 비워 둔 것)

### O-3. 인식 결과 수정 `PATCH /prescriptions/{id}/items/{itemId}`

```json
{ "ediCode": "645301220", "dosePerTime": 1, "timesPerDay": 1, "totalDays": 30 }
```
- 급여목록에 없는 약을 고르면 `ediCode` 대신 `itemSeq`를 보냄 (O-4 결과의 값 그대로)
- `ediCode: null` · `itemSeq: null` + `"exclude": true` → 이 약은 점검에서 빼고 진행 (REQ-032)

### O-4. 약 이름 검색 `GET /drugs/search?q=타이래놀&size=5`

화면 OC-02 (직접 입력) · 챗봇에서도 같이 씀 · 이름 맞추기는 OCR과 같은 함수 (`app/services/drug_names.py`)

- `q`: 사용자가 친 이름 (오타 · 띄어쓰기 · "mg"/"밀리그람" 섞여도 됨)
- `size`: 후보 최대 개수 (기본 5)

**응답 `200`**
```json
{
  "status": "candidates",
  "items": [
    { "itemSeq": "199903123", "ediCode": null, "itemName": "타이레놀정500밀리그램(아세트아미노펜)", "entpName": "한국존슨앤드존슨판매(유)", "etcOtc": "일반", "score": 0.82 },
    { "itemSeq": null, "ediCode": "672300240", "itemName": "타이레놀8시간이알서방정(아세트아미노펜)", "entpName": "한국존슨앤드존슨판매(유)", "etcOtc": "일반", "score": 0.74 }
  ]
}
```
(모양을 보여 주는 예시 — `itemSeq` 숫자는 지어낸 값)

| `status` | 뜻 | 언제 | 화면 (제안) |
|---|---|---|---|
| `matched` | 확실 | 이름을 맞춘 결과가 정확히 같은 약 1개 | 그 약으로 바로 진행 (`items` 1개) |
| `candidates` | 애매 → 후보 | 비슷한 약이 여러 개, 또는 정확히 같지 않음 | 후보에서 고르기 (`items` 최대 `size`개, 점수 높은 순) |
| `not_found` | 못 찾음 | 기준 점수를 넘는 약이 없음 | "약 이름을 다시 확인해 주세요" + 다시 입력 (`items` 빈 배열) |

- OCR 설계 결정과 같은 기준: 정확히 같을 때만 확실. 이름이 비슷한 다른 약(노바스크 ↔ 노바크) · 함량만 다른 약(노바스크 2.5 · 5 · 10)은 항상 후보로
- 기준 점수는 만들 때 시험 문장으로 정함 🟡 채연
- `itemSeq`(식약처 품목기준코드)와 `ediCode`(심평원 제품코드) 중 하나는 꼭 있음 — 일반약은 급여목록에 없어서 `ediCode`가 비는 경우가 많음
- 찾는 범위: 약제급여목록 22,045개 + 식약처 허가정보 42,707건 (허가정보는 RAG 작업 때 DB에 넣음)
- 챗봇 (제안, 챗봇 설계 수인 확정): 질문에서 약 이름을 찾으면 H-2 답 줄에 같은 모양을 `drugMatch: { status, items }`로 넣고, `candidates` · `not_found`면 `answerType: "clarify"`로 다시 물음. 지금 코드에서 만들지 않아 만들 때 저장 방법을 정함 (확정 전, 10/22 #100)

---

## 4. 피처 2 — RAG 분석 (채연) ✅

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
    { "type": "dose_exceed", "label": "하루 최대량 초과", "state": "checked" },
    { "type": "polypharmacy", "label": "여러 약 함께 복용", "state": "checked" }
  ],

  "medication": {
    "guideId": 7001,
    "status": "done",
    "items": [
      {
        "itemId": 3001,
        "ediCode": "645301220",
        "itemName": "노바스크정 5mg",
        "category": "혈압약",
        "purpose": "혈압 관리에 쓰는 약이에요",
        "howToTake": "하루 1번, 아침 식후 1알 · 30일",
        "caution": "부종이 생기면 의사에게 알리세요.\n자몽이나 자몽주스는 함께 드시는 것을 피하세요.",
        "cautions": ["부종이 생기면 의사에게 알리세요.", "자몽이나 자몽주스는 함께 드시는 것을 피하세요."],
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
      {
        "itemId": 3002,
        "itemName": "다이아벡스정",
        "requiresClinician": false,
        "actions": [
          { "text": "술은 되도록 피하기", "kind": "fact", "sourceIds": [32] }
        ]
      },
      {
        "itemId": 3003,
        "itemName": "히드로클로로티아지드정",
        "requiresClinician": true,
        "actions": [
          { "text": "칼륨을 더 먹을지는 혈액검사 결과를 보고 의료진이 정해요", "kind": "safety_notice", "sourceIds": [] },
          { "text": "칼륨이 많은 음식이나 보충제를 임의로 늘리지 않기", "kind": "safety_notice", "sourceIds": [] }
        ]
      }
    ],
    "sections": [
      {
        "diseaseCode": "I10",
        "title": "나트륨 줄이기",
        "goal": "1일 나트륨 2,000mg 이하 (소금 약 5g)",
        "actions": [
          { "text": "국물은 남기고 건더기 위주로 먹기", "kind": "fact", "sourceIds": [31] },
          { "text": "빠르게 걷기 하루 30분, 주 5일 이상", "kind": "fact", "sourceIds": [31, 34] }
        ],
        "conflict": null
      },
      {
        "diseaseCode": "I10",
        "title": "음주",
        "goal": "(목표만 있고 해야 할 일 문장이 없는 줄의 예)",
        "actions": [],
        "conflict": null
      }
    ],
    "warningSigns": [
      {
        "diseaseCode": "I10",
        "actions": [
          { "text": "(위험 신호 문장 예)", "kind": "fact", "sourceIds": [35] }
        ]
      }
    ],
    "sources": [
      { "id": 31, "org": "대한고혈압학회", "title": "고혈압 진료지침", "edition": "YYYY", "publishedAt": "YYYY-MM-DD", "url": "https://…" },
      { "id": 32, "org": "…", "title": "…", "edition": null, "publishedAt": null, "url": "…" },
      { "id": 33, "org": "…", "title": "…", "edition": null, "publishedAt": null, "url": "…" }
    ]
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
| `medication.items[]` | 항목 순서 · 이름 고정 (결과 일관성 NFR-030). 근거가 없으면 값 `null` → "허가정보에 내용이 없어요". 미리 저장해 둔 안내문(`drug_guides`) 중 사람이 확인한(approved) 약만 채워지고, 아니면 `purpose`는 "처방받은 목적을 약사에게 확인해 주세요", `category` · `caution` · `source`는 `null` | RG-04 약 카드 |
| `medication.items[].caution` · `cautions` | `cautions`는 문장별 배열(최대 3개, 없으면 빈 배열), `caution`은 그 문장을 줄바꿈으로 이은 문자열. 각 문장은 허가정보 원문 문장을 근거로 쓰고 근거 번호와 원문을 `drug_guides.evidence_ids`에 저장 — **`cautions`는 명세서에 추가 제안 (수인 확인)** | RG-04 약 카드 |
| `medication.items[].purpose` | "~에 쓰는 약이에요" 꼴. 의료 표현 목록(#61)의 "효과를 약속하는 말"을 피해 "혈압을 낮춰요" 같은 표현은 쓰지 않음 | RG-04 약 카드 |
| `medication.items[].itemId`, `lifestyle.medicationLinks[].itemId` | (v1.5 초안) 처방 약 항목 번호(`prescription_items.id`). 약 화면에서 챗봇을 열 때 `context.id`로 쓰고, 생활습관의 약 연결 줄을 약 카드와 번호로 이음 | RG-04, RG-05, CB-01 |
| `lifestyle.diseases[].origin` | `prescription`(처방전 코드) / `profile`(내 정보 질환, 대표 질병분류기호로 바꿔 넣음) / `user`(RG-05-E1에서 직접 선택) | RG-05 |
| `lifestyle.diseases` 빈 배열 | 질병분류기호 없음 (약봉투 등) → **RG-05-E1** | RG-05-E1 |
| `lifestyle.sections[].conflict` | 질환끼리 권고가 부딪힐 때 `{ "message": "...", "label": "의료진 상담 필요" }` (REQ-062) | RG-05 |
| `lifestyle.sections[].actions[].sourceIds`와 `lifestyle.sources[]` | (v1.4) 문장 하나에 출처가 2개 이상일 수 있어 `sourceId`를 `sourceIds` 목록으로 바꿈. 기관, 문서명, 판, 발행일, URL (REQ-060). 예시 값은 형식만 보여주는 자리표시 | RG-05 출처 |
| `lifestyle.sections[].actions[].kind` | (v1.4) `fact` 근거 문장 / `safety_notice` 안전 안내 문구. 화면에서 따로 표시하지 않고 같이 보여줌(10/8 결정 다). 안전 안내 문구는 `sourceIds`가 빈 목록 | RG-05 |
| `lifestyle.sections[].goal` | (v1.4) 줄의 목표. 해야 할 일 문장이 없는 줄(음주, 열량, 금연과 절주, 맥박 자가측정)은 `actions`가 빈 배열이고 `goal`만 그림 (10/8 결정 가) | RG-05 |
| `lifestyle.medicationLinks[].actions[]` | (v1.4) `advice` 글 하나를 문장 목록으로 바꿈(10/8 결정 나). 문장마다 `kind`, `sourceIds`. 과도기에는 `advice`(문장을 이어 붙인 글)도 같이 내려줘서 화면이 바뀌기 전에도 안 깨지게 함. 화면이 `actions`로 옮겨 가면 `advice`를 지움 | RG-04, RG-05 |
| `lifestyle.warningSigns[]` | (v1.4 신규) 질환별 위험 신호 문장. 고혈압, 당뇨병 등 질환마다 `diseaseCode`로 묶음. 구조는 `sections[].actions[]`와 같음 | RG-05 |
| `lifestyle.medicationLinks[].requiresClinician` | `true`면 "의료진 확인" 라벨로만 표시하고 실천 목표(P-1 추천)로 만들지 않음 (REQ-061) | RG-05 |
| 투석 여부에 따라 숨기는 줄 | (v1.4) 만성콩팥병 수분 줄은 투석 중인 사람에게만 해당. 서버가 투석 여부를 알 수 없으면 이 줄을 내려주지 않음(10/8 결정 라). 응답 모양은 바뀌지 않음 | RG-05 |
| `lifestyle.sections[].conflict` (교차 규칙 4개) | (v1.4) 사용자의 질환 코드가 규칙의 조건을 모두 채우면 `{ message, label }`로 내려줌. `message`는 사람이 쓴 문장 템플릿(AI가 새로 쓰지 않음, 채연 승인 전 초안), `label`은 `의료진 상담 필요`. 조건은 1 고혈압과 만성콩팥병 / 2 당뇨병과 만성콩팥병 / 3 골관절염과 (만성콩팥병 또는 심부전 또는 위궤양) / 4 (심방세동과 골다공증) 또는 여러 약 함께 복용(`polypharmacy`, 함께 먹는 약 5개 이상, REQ-049). 질병 코드가 없으면 사용자가 직접 고른 질환으로 판단하고, 아무것도 없으면 내려주지 않음 | RG-05 |

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
- `resultLabel`: 화면 라벨을 **서버가 만들어** 내려줌 — `확인 필요 N건` / `걸린 항목 없음` / `분석 중` / `분석 실패`
- 빈 배열이면 CM-04-E2 · 홈은 CM-03-E1
- `size`는 1~50(기본 20), 범위를 벗어나면 `400 VALIDATION_ERROR`. `cursor`는 앞 응답의 `nextCursor`를 그대로 넘기고, 읽을 수 없는 값이면 `400 VALIDATION_ERROR`(`field: cursor`). 마지막 쪽이면 `nextCursor`는 `null`
- 분석 중(`running`)과 실패(`failed`) 항목에는 `analysisId`, `createdAt`, `status`, `resultLabel`만 있고, 병원, 약 수, 질환은 `done`일 때만 있음. 대기(`queued`)는 `running`으로 내려줌
- `diseaseNames`는 생활습관 안내문에 쓴 질환 이름(예: 고혈압), 안내문이 없으면 질환 표의 이름. `drugCount`는 R-4 `summary.drugCount`와 같은 값(외용약 제외)

---

### R-8. 기록 삭제 `DELETE /analyses/{id}`

화면 CM-04-E1 · 요구사항 REQ-081 · 응답 `204`

분석 결과 · 경고 · 안내문 · 피드백 · 연결된 챗봇 대화 삭제.

- 남의 분석이거나 없으면 `404`, 분석이 아직 진행 중(대기, 진행)이면 `409 ANALYSIS_RUNNING`(끝난 뒤에 지울 수 있음). 60초가 넘어 멈춘 분석은 실패로 닫히므로 지울 수 있음
- 2026-10-19 구현 범위: 분석 결과, 경고, 안내문, 피드백과 이 분석에만 쓰인 처방전(약 포함) 삭제까지. 챗봇 대화와 실천 목표는 해당 표가 서버에 생길 때 이어서 처리
- 2026-10-23 챗봇 대화(#100, #119 채연 리뷰): 그 분석으로 시작한 대화(`chat_sessions.analysis_id`)와 그 분석의 맥락 카드(H-7)가 붙은 대화를 메시지째 지움. 1단계는 하루 한 대화라 카드는 대화 중간에 붙어 `analysis_id`로는 잡히지 않으므로 카드 줄도 봄. 그날 분석과 상관없는 질문과 그 대화의 안전 모드(`safety_mode_until`)도 함께 지워짐. 앱 삭제 확인(CM-04-E1)은 "분석 결과, 안내문, 이어진 챗봇 대화가 지워지고, 이 분석에만 쓰인 처방전도 함께 지워져요. 지운 기록은 되돌릴 수 없어요."

**실천 목표 처리** (10/6 확정, REQ-081)
- 이 분석에만 쓰인 처방전 · 처방 약도 같이 삭제 (다른 분석에도 쓰였으면 남김)
- 이미 만든 실천 목표 · 기록 · 포인트는 남기고, 추천(`recommendations`) 연결만 끊음 — 사용자가 한 실천은 사용자 몫 (ERD v1.3: `habit_goals.recommendation_id` ON DELETE SET NULL)

---

### R-9. 안내문 피드백 `POST /guides/{guideId}/feedback`

화면 RG-04 · 요구사항 REQ-090, REQ-091

**요청**
```json
{ "rating": 1, "comment": "글씨가 더 컸으면 좋겠어요" }
```
`rating`: `1` 도움됐어요 / `-1` 도움이 안 됐어요, `comment` 선택(최대 500자, 앞뒤 공백을 지우고 비면 저장하지 않음), 응답 `201` `{ "feedbackId": 1 }`

- 한 사람이 안내문 하나에 하나만 남김: 다시 보내면 앞의 것을 덮어쓰고 같은 `feedbackId`를 돌려줌 (ERD `feedbacks`에 `unique (guide_id, user_id)`)
- 남의 안내문이거나 없으면 `404`, `rating`이 1 또는 -1이 아니면 `400 VALIDATION_ERROR`
- 안내문 ID(`guideId`)는 R-4의 `medication.guideId` 또는 `lifestyle.guideId`. 화면은 RG-04(복약 안내) 탭에 붙임

---

### R-10. 안내문 음성 `GET /guides/{guideId}/tts` ⚪

화면 RG-04 [음성으로 듣기] · 요구사항 REQ-100, REQ-101 (선택 구현)

**응답 `200`**
```json
{ "audioUrl": "https://.../7001.mp3", "durationSeconds": 95 }
```
재생 속도는 프론트 플레이어에서 조절 (서버 관여 없음)

---

## 5. 피처 3 — 챗봇 (수인) 🟡

### H-1. 대화 시작 `POST /chat/sessions`

```json
{ "analysisId": 5001, "context": { "type": "warning", "id": 9001 }, "clientRequestId": "c-20261002-0001" }
```
- `analysisId` 없으면 일반 질문 모드 (CM-03-E1에서 분석 전에 들어온 경우). 있으면 대화에만 적고 맥락 카드 줄은 만들지 않음. 맥락 카드 줄은 H-7에서만 만듦 (10/22, #100)
- `analysisId`도 맥락 카드도 없는 대화(홈에서 연 대화)는 질문을 받을 때 그 사용자의 가장 최근 완료 분석을 쓰고 대화에 적음. 그래서 R-8로 그 분석을 지우면 이 대화도 지워짐. 완료 분석이 없으면 일반 질문 모드. 민감정보 동의가 없으면 쓰지도 적지도 않음 (#159, 10/31 수인)
- `context`: RG-03 [이 경고 물어보기] · RG-04 [이 약 물어보기]에서 넘어올 때 (`warning` / `drug`)
- `clientRequestId`: 앱이 만드는 요청 번호. 다시 시도할 때 같은 값을 보내면 대화를 새로 만들지 않음
- 민감정보 동의를 하지 않았거나 철회한 사용자도 챗봇은 쓸 수 있음 (10/6 결정). 일반 정보만 답하고 내 약 · 분석 결과는 넣지 않음. 그래서 챗봇 API에는 `403 CONSENT_REQUIRED`를 쓰지 않음 (업로드 · 분석 API만)

**응답 `201`**
```json
{ "sessionId": 301, "firstMessage": { "id": 9103, "role": "assistant", "content": "...", "answerType": "normal", "sources": [], "createdAt": "2026-10-12T09:10:00+09:00" } }
```
- `firstMessage`는 `context`가 있을 때만 있음 (H-7 응답과 같은 모양). `context`가 없으면 칸을 생략
- #100에서는 `firstMessage`를 아직 보내지 않음 (#116)
- 대화는 첫 질문 때 만들고, 첫 답변이 있는 진입(경고나 약에서 챗봇을 연 경우)만 들어올 때 만듦 (수인 10/12)

### H-2. 이전 대화 `GET /chat/sessions/{id}/messages`

**응답 `200`**
```json
{
  "items": [
    { "id": 9100, "role": "assistant", "content": "", "status": "done", "contextCard": { "analysisId": 5001, "context": { "type": "warning", "id": 9001 } }, "createdAt": "2026-10-02T09:10:00+09:00" },
    { "id": 9101, "role": "user", "content": "이 약은 밥 먹고 먹어야 하나요?", "status": "done", "createdAt": "2026-10-02T09:11:00+09:00" },
    { "id": 9102, "role": "assistant", "content": "...", "answerType": "normal", "status": "done", "replyTo": 9101, "sources": [{ "title": "식약처 의약품 허가정보", "basedOn": "2026-09 기준" }], "createdAt": "2026-10-02T09:11:05+09:00" }
  ]
}
```
- `contextCard`: H-7로 붙인 분석 맥락 카드. 다시 들어왔을 때 카드를 그대로 그림
- `replyTo` (답 줄만): 이 답이 어느 질문의 답인지 질문 줄 번호. 다시 시도한 답이 대화 맨 아래에 생기면 앱이 질문을 인용해 보여 줌 (설계 메모 4-7, 10/22, #100). 맥락 카드 줄에는 없음
- `status` (10/12 수인): `generating` 또는 `done`. 화면을 나갔다 와도 서버가 답을 끝까지 만들어 저장하므로, 다시 들어왔을 때 아직 만드는 중인지 알려서 "답변을 만들고 있어요"를 이어서 보여 줌. 사용자 줄은 늘 `done`. 답 만들기가 실패하면 만드는 중이던 줄을 지움 (`failed`는 두지 않음 10/12, 줄을 지우는 것은 10/22 #100)
- 답 줄에는 H-3 아래 표의 칸(`safetyCard`, `safety`)이 해당할 때만 붙음 (10/22, #100)
- 1층이 잡은 질문의 사용자 줄은 `content`가 빈 글 (원문을 저장하지 않음, H-3). 화면은 원문 대신 안내 글을 흐리게 보이고 복원된 카드의 [지금은 증상이 없어요]는 비활성화 (설계 메모 4-6의 앱 감지 경우와 같게, 10/22). 앱에 그리는 것은 #117
- `safetyCard` (10/12 수인 확정): 안전성 점검 결과 카드가 붙은 답에만 있음. 모양은 `{ "analysisId": 5001, "warningIds": [9001] }`로 R-4 `warnings[]`를 가리키기만 하고, 경고 문구는 AI가 새로 쓰지 않음. 카드가 없는 답은 칸을 생략 (`null`로 보내지 않음, `contextCard`와 같게)
- 그 밖의 칸(재질문 칩, 후속 질문, 첨부 등)은 2단계 범위가 정해지면 추가 (챗봇 설계 메모 3-3)

### H-3. 질문 보내기 `POST /chat/sessions/{id}/messages`

```json
{ "content": "이 약은 밥 먹고 먹어야 하나요?", "clientRequestId": "c-20261002-0002" }
```
- `content`: 앞뒤 공백을 지운 뒤 1~500자. 비었거나 500자를 넘으면 `400 VALIDATION_ERROR`(`field: "content"`). 앱 입력창도 500자에서 막음 (10/21 회의 4절에서 #100에 맡김, 500자는 설계 메모 4-8, 9 항목)
- `clientRequestId`: 다시 시도(CB-01-E6) 때 같은 값을 보내면 질문을 두 번 저장하지 않음. 답 줄이 있으면(만드는 중 포함) 같은 `messageId`를 돌려줌. 답 줄이 실패로 지워졌거나 만드는 중으로 30초를 넘었으면(답 줄을 만든 때부터) 그 줄을 지우고 답을 새로 만들어 새 `messageId`를 돌려줌 (10/22)
- 응답 방식: 질문을 저장하고 `generating` 답 줄을 만든 뒤 바로 `202`를 돌려줌 (10/6 디코에서 수인이 말한 방식, 10/21 수인 결정, #100). 서버는 답을 끝까지 만들고 검사한 뒤 한 번에 저장함 (10/6 회의 확인). 앱은 H-2를 2초마다 불러 `messageId` 줄이 `done`이 되면 그림. 화면을 나가도 서버는 답을 끝까지 만듦 (설계 메모 4-3 항목)
- 주민번호, 전화번호, 이메일, 생년월일 같은 번호는 저장과 OpenAI로 가기 전에 `[전화번호]`처럼 가림. 그래서 H-2의 질문 줄 `content`는 보낸 글과 다를 수 있음. 이름은 가리지 않음 (10/31 수인 결정)
- 1층과 문맥 파악(AI 없음)은 질문을 저장하기 전에 봄. 1층에 걸리고 문맥 파악이 풀지 않으면 질문 원문을 저장하지 않고(`content`는 빈 글, 설계 메모 4-6 항목) 긴급 답 줄을 바로 `done`으로 만든 뒤 `202` (10/22, #100)
- `emergencyDismissed` (선택, 기본 `false`): [지금은 증상이 없어요] 뒤 같은 질문을 다시 보낼 때 `true`. 1층 응급 규칙과 2층 `emergency`를 건너뛰고, 자해(`crisis`)는 그대로 봄 (설계 메모 3-3, 2층은 10/22, #100)
- 앱이 E6을 보여 주는 때: 질문을 보낸 때부터 30초가 지나도 `done`이 아닐 때(설계 메모 0-1 항목 7), `messageId` 줄이 없어졌을 때(10/22)
- 글자가 차례로 나오는 방식(SSE)은 2단계에 다시 봄

**응답 `202`**
```json
{ "messageId": 9102 }
```

H-2 답 줄에 더하는 칸 (10/12 수인 확정, 10/22 H-3 응답에서 옮김). 해당하는 답에만 넣고, 없으면 칸을 생략함.

| 칸 | 언제 | 모양 |
|---|---|---|
| `safetyCard` | 안전성 점검 결과를 전하는 답에만 | `{ analysisId, warningIds }`. 경고 문구는 R-4 `warnings[]`를 그대로 그림 (AI가 새로 쓰지 않음). 카드가 붙는 답도 `answerType`은 `normal`. 끊거나 바꾸려는 질문과 증상(상담 갈래 `next_visit`, `soon`)이면 `refer` (10/28, #134 리뷰) |
| `drugMatch` | 질문에서 약 이름을 찾았을 때만 | O-4와 같은 `{ status, items }`. `status`가 `candidates` 또는 `not_found`면 `answerType`은 `clarify`. 지금 코드에서 만들지 않아 만들 때 저장 방법을 정함 (확정 전) |
| `safety` | 서버가 긴급이나 자해를 감지했을 때만 (`answerType`이 `emergency` 또는 `crisis`) | `{ types, overdose, rule }`. `types`는 동시에 해당하면 둘 다 담고, `overdose`가 참이면 [지금은 증상이 없어요] 칩을 숨김. 질문 원문은 담지 않음 |

되묻는 답(`clarify`) 예시 (H-2 답 줄)
```json
{
  "id": 9102,
  "role": "assistant",
  "content": "정확한 안내를 위해 두 가지만 확인할게요. 어떤 약을 말씀하시는 건가요?",
  "answerType": "clarify",
  "status": "done",
  "sources": [],
  "createdAt": "2026-10-02T09:11:05+09:00"
}
```

`answerType` — CB-01 말풍선 라벨과 1:1 (챗봇 설계 메모 3-1)

| 값 | 라벨 | 화면 |
|---|---|---|
| `normal` | (없음) | CB-01 정상 답변 + 출처 |
| `clarify` | 정보 확인 | CB-01-E3 재질문 |
| `partial` | 일부만 확인됐어요 | CB-01-E3 부분 근거 |
| `no_evidence` | 확인이 어렵습니다 | CB-01 근거 없음 (REQ-073) |
| `refer` | 의료진 상담 필요 | CB-01 일반 정보 + 상담 안내 (REQ-074) |
| `emergency` | 긴급 안내 | CB-01-E4 (REQ-130) |
| `crisis` | 도움 연결 | CB-01-E5 (REQ-131) |
| `error` | 연결 오류 | CB-01-E6 — **프론트 전용**, 서버는 보내지 않음 (REQ-132) |

### H-4. 날짜별 대화 목록 `GET /chat/sessions?date=2026-09-16` ⚪

CB-02(`?month=2026-09` → 기록 있는 날짜 목록) · CB-03(`?date=` → 그날 대화 목록)
```json
{ "items": [ { "sessionId": 301, "title": "혈압약 먹는 시간 질문", "preview": "아침에 먹는 게 좋은지...", "createdAt": "2026-09-16T09:10:00+09:00", "updatedAt": "2026-09-16T09:12:00+09:00" } ] }
```
날짜별 여러 대화 구조로 확정될 때만 구현 (REQ-077)
- `createdAt` (10/12 수인): 날짜와 카드에 보이는 시각은 대화를 시작한 시각 기준

### H-5. 대화 제목 수정 `PATCH /chat/sessions/{id}` ⚪

```json
{ "title": "혈압약 복용 시간" }
```

### H-6. 대화 삭제 `DELETE /chat/sessions/{id}`

**응답 `204`** (내용 없음)
- CB-03 대화 삭제에서 씀. MY-S1 전체 삭제는 (제안) 대화마다 이 API를 부르고, 대화가 많아지면 전체 삭제 API를 따로 만듦
- 지운 대화는 되돌릴 수 없음. 서버에서도 30일 안에 완전히 지움 (MY-S1 안내 문구)
- 남의 대화 · 없는 대화는 `404`

### H-7. 맥락 추가 `POST /chat/sessions/{id}/context` 🟡

1단계는 대화를 고르는 화면이 없어서 **하루 한 대화**로 씀 (챗봇 설계 메모 3-5, v0.7). 분석 결과(RG-02 ~ RG-04)에서 챗봇을 열면 새 대화를 만들지 않고, 오늘 대화에 맥락 카드를 붙임.

```json
{ "analysisId": 5001, "context": { "type": "drug", "id": 7001 }, "clientRequestId": "c-20261002-0003" }
```
**응답 `201`** `{ "firstMessage": { "id": 9103, "role": "assistant", "content": "...", "answerType": "normal", "sources": [], "createdAt": "..." } }`
- 맥락 카드 메시지(`contextCard`)를 대화에 넣고, `context`가 있으면 첫 답변(`firstMessage`)도 함께 줌. 없으면 `firstMessage` 생략
- #100에서는 `firstMessage`를 아직 보내지 않음 (#116)
- 오늘 대화가 아직 없으면 H-1로 먼저 만든 뒤 호출
- 같은 `clientRequestId`로 다시 보내면 맥락 카드 줄을 새로 만들지 않음 (10/22, #100)
- 10/6 회의에서 확인 (챗봇 설계 v0.7)

### H-8. 오늘 대화 찾기 `GET /chat/sessions/today` 🟡

챗봇을 열 때 이어 갈 오늘 대화가 있는지 **찾기만 하고 만들지 않음** (대화는 첫 질문 때 만듦). 10/12 수인 정리안.

**응답 `200`**
```json
{ "sessionId": 301, "hasHistory": true, "safetyModeUntil": null }
```
- `sessionId`: 오늘 시작한 마지막 대화. 없으면 `null` (빈 첫 대화 화면 CB-01-E1)
- `hasHistory`: 지난 대화가 하나라도 있는지. 첫 대화 화면의 문구가 달라짐
- `safetyModeUntil`: 자해 표현 뒤 안전 모드가 끝나는 시각. 없으면 `null`. 1단계는 같은 대화 안에서만, `crisis`가 나온 날 자정(한국 시간)까지 씀 (ERD `chat_sessions.safety_mode_until`, 자정은 10/22 #100)
- 2단계에서 `?analysisId=&contextType=&contextId=`로 같은 날, 같은 대상의 대화를 찾도록 넓힘

### 2단계 API (H-9 ~ H-11, 1장 전체 목록에도 ⚪로 있음) ⚪

> 번호 H-9 ~ H-11은 1장 목록에 넣으면서 채연이 붙인 제안입니다. 바꾸고 싶으면 알려 주세요.

| API | 용도 | 비고 |
|---|---|---|
| H-9 `POST /chat/sessions/{id}/attachments` | CB-04 사진, 파일 올리기 | `multipart/form-data`로 보내고 `{ attachmentId }`를 받음. H-3 요청의 `attachmentIds`로 씀. REQ-079 |
| H-10 `POST /chat/sessions/{id}/safety-events` | 앱에서 먼저 감지한 긴급, 자해 기록 | 원문 없이 `{ types, overdose, rule, clientRequestId }`. 긴급 기록 표는 민감정보 보관 문제로 팀 확인 뒤에 정함 |
| H-11 `POST /chat/messages/{id}/feedback` | 답변 피드백 | 지금은 화면만 있음 |

---

## 6. 피처 4 — 실천 · 보상 (P-1 ~ P-4 채연, P-5와 P-6은 뒤로) 🟡

> 성규님 데이터 흐름 기준: Analysis → **Recommendation** → **HabitGoal** → **HabitRecord** → **Reward**
> 추천(Recommendation)은 사용자가 골라야 목표(HabitGoal)가 됨. 아래 요청 · 응답은 화면에 필요한 최소 형식이며 담당자가 확정

### P-1. 생활습관 추천 `GET /recommendations?analysisId=5001`

화면 RG-05 → RW-02, REQ-110. 분석 질환(처방전, 내 정보, 질환 직접 선택)과 약에 팩트표 근거가 있을 때만, 9/23에 정한 세 가지 안에서 추천 (10/30 수인)
```json
{ "items": [ { "id": 1, "title": "국물 남기기", "desc": "1일 나트륨 2,000mg 이하 (소금 약 5g)", "reasonLabel": "고혈압", "goalType": "check" },
             { "id": 2, "title": "빠르게 걷기 30분", "desc": "주 5회 이상, 회당 30분 이상 (중강도)", "reasonLabel": "고혈압", "goalType": "quantity", "targetValue": 30, "unit": "분" } ],
  "hasDiseases": true }
```
- 국물 남기기: 고혈압, 만성신장병 / 빠르게 걷기 30분: 고혈압, 이상지질혈증, 당뇨병, 골다공증, 만성폐쇄성폐질환 / 술 마시지 않기: 뇌졸중, 이상지질혈증, 당뇨병의 설포닐우레아 약, 골관절염의 아세트아미노펜 약 (금주까지 말하는 근거만, 내 정보 음주가 "안 마심"이면 뺌). 약 근거도 그 질환이 분석에 있을 때만 봄 (생활습관 탭과 같은 기준, 10/30 수인)
- 허혈성심질환이 있으면 걷기는 제목 "걷기", 체크형, `cautionLabel: "의료진이 정한 강도로"`. `desc`는 팩트표의 "의료진이 정한 강도로 주 5회"와 시술이나 수술 뒤에는 의료진 승인 후 시작하라는 실천 문장을 고치지 않고 이어 붙임 (REQ-110. "의료진 확인"은 목표로 만들지 않는 항목의 라벨이라 쓰지 않음)
- `desc`는 팩트표 글 그대로. `reasonLabel`은 근거가 된 질환 이름을 쉼표로, 약 근거는 "약과 함께"
- 질환이 없으면 `items: []`, `hasDiseases: false` → 앱은 질환 고르기(RG-05-E1)로. 질환은 있는데 근거가 없으면 `items: []`, `hasDiseases: true`
- 부를 때마다 다시 계산해 저장하고 같은 챌린지는 `id`를 그대로 둠. 남의 분석은 `404`, 분석이 끝나지 않았으면 `409 ANALYSIS_NOT_READY`

### P-2. 목표 만들기 `POST /habit-goals`

화면 RW-02, REQ-111
```json
{ "recommendationIds": [1, 2] }
```
응답 `201` `{ "goalIds": [11, 12] }`
- 1~3개만 허용, 0개 또는 4개 이상, 같은 번호 두 번, 다른 분석의 같은 목표를 함께 고르면 `400 VALIDATION_ERROR`. 남의 추천이 섞이면 `404`
- 다시 고르면 지금 목표 중 같은 목표(제목과 종류가 같음)는 그대로 두고 `goalIds`에 같은 번호를 돌려줌(오늘 기록이 남음). 뺀 목표만 끝내고(`ended`) 새로 고른 것만 만듦 (#43 목표 교체, 10/30 수인). 주간 다시 고르기 REQ-116은 뒤로

### P-3. 오늘의 실천 `GET /habit-goals/today`

화면 CM-03 카드, RW-03 (미실천, 일부 완료, 전체 완료), RW-03-E2, REQ-112
```json
{
  "hasGoals": true,
  "doneCount": 1, "totalCount": 2, "streakDays": 3,
  "items": [ { "goalId": 11, "title": "국물 남기기", "reasonLabel": "고혈압", "goalType": "check", "done": true },
             { "goalId": 12, "title": "빠르게 걷기 30분", "reasonLabel": "고혈압", "goalType": "quantity", "targetValue": 30, "currentValue": 10, "unit": "분", "done": false } ]
}
```
- `hasGoals: false` → 홈 카드는 목표 없음, 실천 탭은 RW-03-E2
- `streakDays`: 어떤 목표든 하루 1개 이상 완료한 날이 이어진 수. 목표가 바뀌어도 이어지고, 오늘 아직 안 했으면 어제까지 셈 (REQ-114)
- 분석을 지웠으면(R-8) `reasonLabel`, `cautionLabel`이 빠짐 (질환 정보라 추천과 함께 지움)
- 포인트 칸(`todayPoints`, `allDoneBonus`)은 P-6과 함께 뒤로

### P-4. 실천 기록 `POST /habit-goals/{goalId}/records`

화면 RW-03, REQ-112, REQ-115
```json
{ "date": "2026-10-30", "completed": true }
{ "date": "2026-10-30", "value": 10 }
```
응답 `200` `{ "goalId": 11, "done": true, "allDone": false }` (수량형은 `currentValue`도)
- 체크형은 `completed`. `false`면 완료 취소 (10/2 회의 결정 "완료 취소", #43)
- 수량형은 `value`(0~600, 상한 600분은 제안)가 그날 한 총량이고 목표에 닿으면 완료, 줄여서 목표 아래로 내려가면 완료가 풀림. 총량이라 같은 요청을 다시 보내도 두 번 더해지지 않음
- 오늘 날짜만 받음, 다른 날이면 `400 VALIDATION_ERROR` (몰아서 체크 막기)
- 같은 날 같은 목표를 다시 완료하면 무시하고 `200`
- 남의 목표나 끝난 목표는 `404`
- `allDone: true`면 RW-03 전체 완료 상태로. 저장 실패 시 앱은 RW-03-E1 배너와 같은 요청 다시 보내기
- `pointsEarned`는 P-6과 함께 뒤로

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

## 7. ERD 반영 사항 — ✅ 1~9 ERD v1.0 · 10~11 ERD v1.2 · 12 ERD v1.3에 반영 완료 · 13 ~ 16은 ERD v1.5 초안에 반영 (확정 전)

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
| 10 | `ocr_jobs` 신규 · `prescriptions.ocr_job_id` · `file_index` (ERD v1.2) | OCR 비동기 | O-1 · O-5 |
| 11 | `lifestyle_guide_sources` · `lifestyle_guide_actions` 신규, `lifestyle_medication_links.requires_clinician` · `goal_eligible` (ERD v1.2) | 실천 항목별 출처 · 칼륨 등 의료진 확인 | R-4 · P-1 |
| 12 | `drug_details` 키를 `edi_code` → `item_seq`로, `prescription_items` · `prescription_item_candidates`에 `item_seq` 추가 (ERD v1.3) | 급여목록에 없는 약(허가정보에만 있는 약)도 담기 — 허가정보 유효 35,194건 중 14,436건은 EDI 코드가 없음 | O-2 · O-3 · O-4 |
| 13 | `chat_messages`에 `safety_card`, `status`, `model`, `prompt_tokens`, `completion_tokens`, `latency_ms` 추가, `chat_sessions`에 `safety_mode_until` 추가 (ERD v1.5 초안, 이슈 #88) | 점검 결과 카드 다시 그리기, 만드는 중인 답 표시, 답변마다 비용과 시간 측정, 안전 모드 끝나는 시각 | H-2 · H-3 · H-8 |
| 14 | `chat_messages.safety` 추가 (ERD v1.5 초안, #100) | H-3을 202로 바꾸면 답을 H-2로 받으므로, 긴급, 자해 안내 카드를 처음 그릴 때도 이 칸이 필요함. 원문은 담지 않음 | H-2 |
| 15 | `chat_messages.reply_to_id` 추가 (ERD v1.5 초안, #100) | 답 줄이 어느 질문의 답인지. `client_request_id`는 질문 줄에만 둘 수 있어서(대화 안에서 겹치면 안 됨) 다시 시도 때 답 줄을 찾고, 맨 아래에 생긴 답에 질문을 인용하려면 필요함 | H-2, H-3 |
| 16 | `chat_messages.route_kind` 추가 (ERD v1.5 초안, #140) | 답 줄에 답을 만든 갈래를 남겨, 범위 밖으로 걸러진 질문과 답을 다음 질문의 대화 기억에서 뺌(5회차 멘토링 시연). 응답에는 내보내지 않음 | H-2, H-3 (응답 모양은 그대로) |
| 17 | 실천 표 세 개 `recommendations`, `habit_goals`, `habit_records` (ERD v1.5 초안, 마이그레이션 18번). `recommendations`는 ERD의 `guide_id`, `medication_link_id`, `action_id` 대신 `challenge_key`, `fact_refs`(팩트표 "질환 id:항목 이름"), `desc`, `caution_label`. 팩트표가 JSON 파일이라 가리킬 표가 없음. `rewards`는 P-6과 함께 뒤로 | 분석을 지우면 추천은 같이 지우고 목표는 연결만 비움(R-8). 동의 철회는 목표를 끝내고 기록을 남김(U-5), 탈퇴는 모두 지움(U-3) | P-1 ~ P-4, R-8, U-3, U-5 |

---

## 8. 남은 결정 사항

- [x] 토큰 만료 시간 · 재발급 → 출입증 60분 · 재발급권 14일, 재발급권은 앱 보안 저장소 · A-4 본문으로 (10/6 결정, 버그 3개는 PR #45)
- [x] OCR(O-1) 동기 / 비동기 → v1.1에서 **비동기(202 + O-5)로 준비**. CLOVA OCR 응답 시간 측정(9/30 키 제공) 후 확정 🟡 채연
- [ ] 챗봇 응답을 SSE로 할지 — 1단계는 한 번에 보내는 쪽으로 제안 (H-3, 10/6 회의)
- [x] 오늘 대화 찾기 `GET /chat/sessions/today`는 H-8로 정함 🟡 (10/12 수인 정리안). 긴급 기록 `POST /chat/sessions/{id}/safety-events`는 H-10(2단계 ⚪)으로 1장 전체 목록에 둠, 긴급 기록 표는 민감정보 보관 문제로 팀 확인 뒤
- [x] 기록 삭제 시 실천 기록 처리 (R-8) — 그 분석만 삭제, 실천 목표 · 포인트는 남김 (10/6 확정)
- [ ] 챗봇을 날짜별 여러 대화로 갈지 (H-4 · H-5 구현 여부)
- [ ] 한 주가 끝난 뒤 목표 다시 고르기 흐름 (P-2)
- [x] 동의 철회 시 기존 기록 처리 (U-5) — 위 표대로 (10/6 확정)
- [x] 다시 동의(U-6): 같은 줄을 덮어씀(#137 제안), 11/5 시연 전에 넣음 (10/31 수인 결정)
- [x] MVP 범위 확정 — 요구사항 정의서 v1.5 "MVP" 칸 (10/6 확정, 후순위 12건은 여유 있을 때만)
- [x] RW-01 제외 확정 (2026-09-28, 한성규) — RG-05 [이 목표로 실천 시작하기]에서 RW-02로 바로 연결
- [ ] RW-03 · RW-04 · RW-05를 한 화면의 상태(미실천 · 일부 완료 · 전체 완료)로 합칠지 🟡 수인
- [x] FastAPI로 확정 (템플릿) — 서버를 켜면 `/api/docs`에서 자동 문서 확인
