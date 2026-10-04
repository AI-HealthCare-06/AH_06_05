# 챌린지(실천 · 보상) 플로우차트

5팀 · 2026. 10. 3 · 작성 한성규 (피처: 챌린지)

화면 흐름과 서버 흐름을 나눠서 그렸습니다. 화면 번호는 `screen_id_table.md`, API 번호는 API 명세서 v1.2, 요구사항은 v1.4 기준입니다.

| 색 · 선 | 뜻 |
|---|---|
| 파란색 | MVP (REQ-110 · 111 · 112 · 115) |
| 회색 점선 | 후순위 (REQ-113 · 114 · 116) — 10/6 회의에서 MVP 범위 결정 |
| 보라색 점선 | 제안 (아직 팀에서 정하지 않음) |
| 주황색 | 분기 (예 / 아니오) |
| 빨간색 | 예외 화면 |

## 1. 화면 흐름

```mermaid
flowchart TD
  classDef mvp fill:#E6F1FB,stroke:#185FA5,color:#0C447C
  classDef dec fill:#FAEEDA,stroke:#854F0B,color:#633806
  classDef err fill:#FCEBEB,stroke:#A32D2D,color:#791F1F
  classDef later fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A,stroke-dasharray:4 3
  classDef prop fill:#EEEDFE,stroke:#534AB7,color:#3C3489,stroke-dasharray:4 3

  CM03["홈 CM-03<br/>오늘의 실천 카드"]:::mvp
  TAB["실천 탭"]:::mvp
  RG05["RG-05 추천 결과 · P-1<br/>이 목표로 실천 시작하기"]:::mvp
  HAS{"목표가 있나? · P-3"}:::dec
  E2["RW-03-E2 목표 없음<br/>분석 먼저 해 주세요 안내 · REQ-112"]:::err
  OC01["OC-01 촬영 · 업로드"]:::mvp
  RW02["RW-02 목표 선택 · P-2<br/>최대 3개 · 의료진 확인 항목은 선택 불가<br/>목표가 이미 있으면 현재 선택이 체크된 채 열림 · 제안"]:::mvp
  ZERO{"선택한 목표가 0개?"}:::dec
  RW03["RW-03 ~ 05 오늘의 실천 · P-3<br/>미실천 → 일부 완료 → 전체 완료 · REQ-112"]:::mvp
  KIND{"목표 종류?"}:::dec
  CHK["체크형<br/>실천 완료 버튼"]:::mvp
  QTY["수량형 예 빠르게 걷기 30분<br/>+ / - 입력 · 목표량에 닿으면 자동 완료"]:::mvp
  UNDO["체크 해제 · 수량 줄이기 · 10/2 허용<br/>P-4에 해제 요청 형식 보강 필요 · 제안"]:::prop
  SAVE{"기록 저장 성공? · P-4"}:::dec
  E1["RW-03-E1 저장 실패 배너<br/>다시 시도 · REQ-115"]:::err
  ALL{"오늘 목표를 전부 완료?"}:::dec

  CM03 --> HAS
  TAB --> HAS
  HAS -->|아니오| E2
  E2 -->|분석 아직 안 함| OC01
  E2 -->|분석 O · 목표 미선택| RW02
  HAS -->|예| RW03
  RG05 --> RW02
  RW02 --> ZERO
  ZERO -->|예 · 시작 불가| RW02
  ZERO -->|아니오| RW03
  RW03 --> KIND
  KIND -->|체크형| CHK
  KIND -->|수량형| QTY
  CHK --> SAVE
  QTY --> SAVE
  RW03 -.->|상태 되돌림| UNDO
  UNDO -.-> SAVE
  SAVE -->|아니오| E1
  E1 -->|다시 시도| SAVE
  SAVE -->|예| ALL
  ALL -->|아니오 · 다음 목표 계속| RW03

  subgraph LATER["후순위 · REQ-113 · 114 · 116 · 10/6 회의에서 MVP 범위 결정"]
    RW05["RW-05 전체 완료 · P-6<br/>개당 +10P · 보너스 +10P · 제안"]:::later
    RW06["RW-06 달성 현황 · P-5 · P-6<br/>이번 주 달성률 · 연속 실천일 · 포인트"]:::later
    REC{"이번 주 기록이 있나?"}:::dec
    E1B["RW-06-E1 기록 없음<br/>오늘의 실천으로 이동"]:::err
    MON{"매주 월요일 0시?"}:::dec
    BANNER["목표 이어가기 · 다시 고르기 안내<br/>제안 · API 명세서에 아직 안 정함"]:::prop
  end

  ALL -->|예| RW05
  RW05 -.->|달성 현황 보기| RW06
  RW06 --> REC
  REC -->|아니오| E1B
  E1B --> RW03
  RW06 -.-> MON
  MON -.->|예| BANNER
  BANNER -.->|이어가기 안 하면| RW02
```

## 2. 서버 흐름 — P-4 실천 기록

`POST /habit-goals/{goalId}/records` 한 번에 서버가 하는 일입니다. 점선 · 보라색 부분은 완료 취소를 허용하기로 한 10/2 결정을 서버에 반영하기 위한 제안입니다.

```mermaid
flowchart TD
  classDef mvp fill:#E6F1FB,stroke:#185FA5,color:#0C447C
  classDef dec fill:#FAEEDA,stroke:#854F0B,color:#633806
  classDef err fill:#FCEBEB,stroke:#A32D2D,color:#791F1F
  classDef later fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A,stroke-dasharray:4 3
  classDef prop fill:#EEEDFE,stroke:#534AB7,color:#3C3489,stroke-dasharray:4 3

  REQ["P-4 요청<br/>완료 체크 또는 수량 입력"]:::mvp
  OWN{"내 목표이고 활성 상태?"}:::dec
  FAIL["오류 응답<br/>프론트는 RW-03-E1 배너"]:::err
  DIR{"완료 또는 해제?"}:::dec
  DUP{"같은 날 같은 목표가 이미 완료?"}:::dec
  IGN["무시하고 200 응답<br/>포인트 중복 지급 없음 · REQ-112"]:::mvp
  REC["HabitRecord 생성 · 수정<br/>수량형은 값을 더하고 목표량에 닿으면 완료"]:::mvp
  PT["Reward 이력 +10P<br/>목표 1개 완료 · REQ-113"]:::later
  ALL{"오늘 전부 완료 · 보너스 이력 없음?"}:::dec
  BON["Reward 이력 +10P<br/>전부 완료 보너스 · 하루 1회 · REQ-113"]:::later
  RES["응답<br/>pointsEarned · allDone"]:::mvp

  UREC["HabitRecord 되돌림<br/>제안"]:::prop
  UPT["Reward 이력 -10P 추가<br/>삭제하지 않고 음수 이력으로 남김 · 제안"]:::prop
  UALL{"전부 완료가 풀렸나?"}:::dec
  UBON["Reward 이력 -10P 추가<br/>보너스 회수 · 제안"]:::prop

  REQ --> OWN
  OWN -->|아니오| FAIL
  OWN -->|예| DIR
  DIR -->|완료 · 수량 입력| DUP
  DUP -->|예| IGN
  IGN --> RES
  DUP -->|아니오| REC
  REC --> PT
  PT --> ALL
  ALL -->|예| BON
  BON --> RES
  ALL -->|아니오| RES
  DIR -.->|체크 해제 · 수량 줄임| UREC
  UREC -.-> UPT
  UPT -.-> UALL
  UALL -.->|예| UBON
  UBON -.-> RES
  UALL -.->|아니오| RES
```

## 3. 정한 것과 제안

| 항목 | 내용 | 상태 | 근거 |
|---|---|---|---|
| 목표 최대 3개 | 0개면 시작 불가, 4개 이상은 400 | 확정 | REQ-111 · API P-2 |
| RG-05 → RW-02 바로 연결 | RW-01 제외 | 확정 | REQ-110 (v1.4) |
| 연속 실천일 | 하루 1개 이상 완료하면 인정 | 확정 | 10/2 회의 |
| 완료 취소 | 허용 | 10/2 결정, 문서 반영 필요 | 아래 "문서 맞출 곳" 참고 |
| 의료진 확인 항목 | 실천 목표로 만들지 않음 | 확정 | ERD v1.2 `goal_eligible` |
| 포인트 숫자 | 목표 1개 완료마다 +10P, 하루 전부 완료 보너스 +10P (3개면 하루 최대 40P) | 제안 | API P-3 `todayPoints` · `allDoneBonus`, RW-04 화면 문구 |
| 취소할 때 포인트 | 받은 포인트를 음수 이력으로 빼고, 다시 완료하면 다시 줌 (반복해도 합계는 그대로) | 제안 | 중복 지급 금지(REQ-113) 유지 |
| 연속 실천일 끊기는 기준 | 한국 시간(Asia/Seoul) 자정 기준으로 그날 하나도 완료하지 않으면 다음 날부터 0 | 제안 | `TIMEZONE`이 이미 Asia/Seoul |
| 연속 실천일 계산 | 저장하지 않고 HabitRecord에서 매번 계산 (취소해도 자동으로 다시 맞춰짐) | 제안 | 값이 어긋날 일이 없음 |
| 목표가 이미 있는데 다시 들어오면 | 더하지 않고 교체. RW-02가 현재 선택이 체크된 채 열리고, 최종 선택(최대 3개)으로 덮어씀. 기존 기록은 남김 | 제안 | P-2가 "1~3개 묶음"을 받는 API라 자연스러움 |
| 월요일 다시 고르기 | 안내 배너, 안 바꾸면 지난주 목표 유지 | 제안 · 후순위 | REQ-116 · API 명세서 "아직 안 정함" |

## 4. 문서 맞출 곳 (이 플로우차트와 어긋나는 부분)

1. **RW-05 화면 "+30P 획득"과 API P-6 예시 `todayPoints: 30`**: 개당 10P + 보너스 10P 기준이면 3개 전부 완료는 40P이고, 마지막 목표를 완료하는 순간 받는 건 20P입니다. 숫자를 하나로 정해야 합니다.
2. **`screen_id_table.md` RW-04 행**: "완료 취소는 MVP에서 제공하지 않음"으로 남아 있어 10/2 결정(허용)과 다릅니다.
3. **API P-4**: 체크 해제 · 수량 줄이기 요청 형식이 없습니다 (현재는 `completed: true` 또는 `value`만 있음).

## 변경 이력

| 버전 | 일자 | 위치 | 현행 (As-Is) | 개정 (To-Be) | 담당 |
|---|---|---|---|---|---|
| v0.1 | 2026-10-03 | 전체 | (없음) | 챌린지 플로우차트 최초 작성 — 화면 흐름 · 서버 흐름(P-4) 분리, 화면 · API 번호, MVP · 후순위 · 제안 구분 | 성규 (Claude 초안) |
