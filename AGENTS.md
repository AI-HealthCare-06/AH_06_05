# AGENTS.md

> AI 코딩 도구가 이 저장소에서 작업을 시작할 때 읽는 파일. 저장소 루트에 둠. 사람도 같은 규칙을 따름. 바꿀 때는 PR로 고치고 맨 아래 변경 이력을 남김
> 원칙: AI가 코드만 읽고는 알 수 없는 것만 짧게. 한 줄마다 "이 줄을 지우면 AI가 실수할까?"를 묻고 아니면 지움

## 이 파일을 쓰는 방법

- AGENTS.md는 여러 AI 코딩 도구가 함께 읽는 공통 형식. Claude Code도 저장소에 `CLAUDE.md`가 없으면 `AGENTS.md`를 대신 읽음 (v2.1.277 이상에서 확인)
- 그래서 `CLAUDE.md`는 만들지 않고 이 파일 하나를 팀 공통으로 씀. `CLAUDE.md`나 `CLAUDE.local.md`가 작업 폴더나 그 위쪽에 하나라도 생기면 Claude Code는 이 파일 대신 그걸 읽음
- 폴더별 규칙이 필요하면 `frontend/AGENTS.md`처럼 둠. 수정하는 파일에서 가장 가까운 파일이 우선
- `prototype/`은 회의용 프로토타입이고 실제 서비스 코드가 아님. 그 폴더 안에서 작업할 때만 그 폴더의 규칙 파일을 따름

## 프로젝트

다약제를 먹는 고령 만성질환자와 보호자가 처방전이나 약봉투를 찍으면, 약을 인식(OCR)하고 같이 먹으면 안 되는 약을 점검해 복약 안내, 생활습관 안내, 챗봇 상담을 주는 서비스 (OZ코딩스쿨 AI 헬스케어 6기 5팀)

- `app/` FastAPI 서버, `ai_worker/` arq 워커, `frontend/` Expo 앱, `infra/` nginx와 배포, `scripts/` CI와 배포와 데이터 넣기, `docs/` 기획 문서와 멘토링 기록과 데이터 출처
- 구조와 코드 규칙은 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), 화면 규칙은 [DESIGN.md](DESIGN.md)를 먼저 읽을 것. 커밋 전 검사는 `.pre-commit-config.yaml`
- 기준 문서는 `docs/planning/`에 있음: 요구사항 v1.5, API 명세서 v1.3, ERD v1.3, 화면 번호표
- 피처 담당은 화면부터 서버까지 한 사람이 맡음 (10/7 합의). 공통과 챗봇은 수인, OCR과 RAG는 채연. 실천(챌린지)은 서버 수인(#155), 이어서 채연 / 실천 탭 앱 화면 채연 (10/30 회의, 포인트와 달성 현황은 뒤로)

## 명령

```bash
# 서버 (저장소 루트)
uv sync --all-groups                                          # 패키지 설치 (app, dev 묶음)
docker compose up --build -d                                  # postgres, redis, fastapi, ai-worker, nginx (API 문서는 http://localhost/api/docs)
docker compose exec fastapi uv run --no-sync aerich upgrade   # 마이그레이션 적용
DB_HOST=localhost REDIS_HOST=localhost PGDATABASE=postgres uv run pytest app/tests/auth_apis -q   # 시험 하나 (먼저 이것)
DB_HOST=localhost REDIS_HOST=localhost PGDATABASE=postgres uv run pytest app       # 전체 시험
bash scripts/ci/code_fommatting.sh                            # ruff 고치기, 검사, 포맷 (파일 이름 철자 그대로, 실행 권한이 없어 bash로 실행)
bash scripts/ci/run_test.sh                                   # CI와 같은 방식의 시험 (DB 컨테이너가 떠 있어야 함)
uv run --with openpyxl python scripts/data/load_masters.py    # 약과 질병 목록 넣기 (data/raw/hira 필요)

# 앱 (frontend/)
npm install
npx expo start                                                # Expo Go로 QR
npx expo install <패키지>                                      # 패키지 추가 (SDK 57에 맞는 버전)
npm run typecheck

# 커밋 전 자동 검사 (처음 한 번, 각자)
uv run pre-commit install                                     # git에 연결. 이후 커밋마다 자동으로 돔 (앱 타입 검사가 있어 frontend/에서 npm install을 먼저)
uv run pre-commit run --all-files                             # 전체 파일 한 번에 검사
```

## 일하는 순서

1. **탐색**: 관련 코드와 명세서를 먼저 읽음. 바로 고치지 않음
2. **계획**: 방법이 확실하지 않거나 파일 여러 개를 바꾸면 먼저 계획을 쓰고 사람이 확인한 뒤 구현함. 한 문장으로 설명되는 수정은 바로 고침
   - 계획에는 목표, 하지 않는 것, 근거(명세서와 요구사항 번호), 바꿀 파일, 확인 방법을 적음. 개인정보나 권한이 걸리면 그것도 적음
   - 계획 문서는 커밋하지 않고 각자 로컬에 둠
3. **구현은 시험 먼저**: 실패하는 시험, 통과하는 코드, 정리 순서 (Red, Green, Refactor)
   - 서버는 pytest 필수. 앱은 타입 검사와 Expo Go로 직접 확인
   - AI 답변처럼 매번 결과가 다른 것은 규칙 부분(긴급 단어 등)만 시험으로 고정하고, AI 부분은 골든셋 결과 표로 남김
4. **검증**: 시험, 린트, 타입 검사를 직접 돌리고 명령과 결과를 보여 줄 것. "될 것 같다"로 끝내지 않음
5. **커밋과 PR**: 아래 규칙대로. 커밋, 푸시, PR 전에 사람에게 확인

## 꼭 지킬 것

- **API는 명세서가 약속**: 요청과 응답 모양을 바꾸려면 `docs/planning/API 명세서`부터 고치고 상대 담당에게 알림
- **이 저장소는 Public**: 비밀값(`envs/`, `.env`, API 키, 토큰, 비밀번호)을 코드, 문서, 이슈, PR, 커밋 메시지, 출력 어디에도 쓰지 않음. 설정은 환경 변수로만 넣고 코드에서는 `from app.core import config`로 읽음 (설정 항목은 `app/core/config.py`의 `Config`)
- 키가 실수로 올라가면 커밋을 지워도 회수되지 않음. 바로 팀에 알리고 키를 폐기하고 다시 발급받음
- 실제 진료기록, 처방전, 개인정보가 담긴 파일은 올리지 않음. 시험은 직접 만든 가짜 처방전으로만 함
- **민감정보(건강 정보)**: 원본 사진과 OCR 원문은 저장하지 않음 (10/15 결정, `docs/design/ocr_mask.md`). 저장하는 약 이름과 복약 안내 문장은 저장 전에 마스킹을 거침
- **권한**: 남의 데이터 요청은 `404`. 데이터를 다루는 모든 함수에서 "이 사용자의 것인지" 확인
- **안전성 판정은 AI가 하지 않음**: 병용금기, 동일성분, 효능군 중복, 노인주의, 연령금기는 심평원 DUR 데이터를 DB에서 조회해서만 판정함. AI는 문장을 쉬운 말로 바꾸는 데만 쓰고 경고 문장을 새로 만들지 않음. 경고 문구는 템플릿으로 (NFR-032)
- **약 정보**: 식약처 의약품 제품 허가정보를 씀. e약은요 API는 전문의약품이 없어서 쓰지 않음. 약 식별은 급여목록에 있으면 `ediCode`(심평원 제품코드), 없으면 `itemSeq`(식약처 품목기준코드)로 하고, 이름 맞추기는 `app/services/drug_names.py` 하나로 함
- **생활습관 안내**는 우리가 만든 팩트 테이블의 수치와 권고만 씀. 국가건강정보포털 글은 공공누리 4유형이라 고쳐 쓰지 않음. 근거 문장마다 출처를 표시함 (안전 안내 문구는 출처 없음). 칼륨 권고는 이뇨제, ACE억제제, ARB 복용자에게 "의료진 확인" 안내만 하고 실천 목표로 만들지 않음
- **진단하지 않음**: 안내만 함. 의료 표현은 요구사항 NFR-033과 의료 표현 목록(#61)을 따름
- **AI가 만드는 문장**(안내문, 챗봇 답변, 문서, 커밋과 PR 글)에는 `**` 같은 마크다운 기호, 이모지, 줄표(—), 가운뎃점(·)을 남기지 않음. 프롬프트 파일, 스킬 파일, 화면 문구는 예외
- 화면 기준은 Figma. 화면 문구나 동작을 바꿀 때는 Figma와 요구사항을 먼저 고친 뒤 코드를 고침
- 마이그레이션 파일은 손으로 고치지 않고 `aerich migrate`로 만듦
- 실패하는 시험을 지우거나 건너뛰게 바꿔서 통과시키지 않음. 원인을 고침
- 공공데이터 원본(`data/raw/`)은 git에 올리지 않음. 출처는 `docs/data/SOURCES.md`

## AI 도구에게 부탁

- 모르는 것은 지어내지 말고 "모름"이라고 함. 약과 질병 정보는 반드시 데이터나 공식 출처에서 가져옴
- 정해지지 않은 것(버전, 정책, 기준값)을 임의로 정하지 않음. 제안은 "(제안)"이라고 표시함
- 요청받지 않은 파일은 고치지 않음. 큰 변경은 먼저 계획을 보여 주고 확인받음
- 문서, 주석, 커밋 메시지는 한국어로 씀

## 겪어 본 함정

- `tortoise-orm`은 `<1.0.0`으로 고정 (1.x는 시험 설정이 깨짐)
- `arq`는 `==0.25.0` (0.26 이상은 redis 버전과 충돌)
- 시험할 때 `PGDATABASE=postgres`가 없으면 "database root does not exist"가 나옴
- 컨테이너 안 실행은 `uv run --no-sync` (없으면 켤 때마다 개발용 패키지를 다시 설치함)
- Expo는 SDK마다 API가 바뀜. `frontend/package.json`의 `expo`(57)에 맞는 문서를 볼 것
- `evidence_chunks` 마이그레이션(10번)은 맨 위 `CREATE EXTENSION vector`, `pg_trgm` 두 줄을 손으로 넣은 예외임. aerich가 확장 기능은 만들지 않기 때문이고, 이 파일을 다시 만들면 두 줄도 다시 넣어야 함
- 로컬 DB 컨테이너가 예전 `postgres:16` 이미지이면 시험이 `extension "vector" is not available`로 멈춤. `docker-compose.yml`의 `pgvector/pgvector:pg16-trixie` 이미지로 `docker compose up -d --no-deps postgres`를 실행해 다시 만들 것 (수인 님 로컬에서 데이터가 남은 채 해결됨)
- Windows는 `.env`가 링크가 아니라 복사본이라서 `envs/.local.env`를 고칠 때마다 다시 복사해야 함

## 브랜치, 커밋, PR

- 작업 하나는 이슈 하나, 브랜치 하나, PR 하나 (`docs/CONVENTIONS.md`)
- 브랜치: `feature/*`, `fix/*`, `docs/*`, `chore/*` (예: `feature/ocr-upload`). `main`으로 PR을 올리고 직접 push하지 않음
- 커밋: `<type>: <한글 요약>`. `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore` 중 하나. 제목은 50자 안, 마침표 없이 (Conventional Commits와 같은 형식)
- PR: `.github/PULL_REQUEST_TEMPLATE.md` 양식을 쓰고 본문에 `Closes #이슈번호`를 적음. 상대 1명이 승인하면 올린 사람이 병합함
- GitHub CI(lint, test)가 초록색이어야 병합함. 새 기능에는 시험을 같이 추가함
- 리뷰할 때는 코드만 읽지 않고 로컬에서 시험을 돌려 봄

## 변경 이력

| 날짜 | 내용 | 작성 |
|---|---|---|
| 2026-10-07 | 첫 버전 | 이수인, 김채연 |
| 2026-10-08 | 수인 의견 반영: 참여기업 이름, 줄 길이 120자, 칸반 카드, 지표 기록 줄을 뺌(칸반 카드는 `docs/CONVENTIONS.md`로). 줄표와 가운뎃점 예외에 스킬 파일을 추가. 설정 읽는 방법을 실제 코드(`from app.core import config`)에 맞게 고침 | 김채연 |
| 2026-10-12 | 출처 번호와 출처 정리 파일 링크를 뺌(출처 정리는 노션에 둠). pre-commit 명령 추가. 생활습관 출처 표현을 팩트표 v0.12에 맞춤, 의료 표현 목록에 #61 표시 | 이수인 |
| 2026-10-19 | 시험 명령에 `REDIS_HOST=localhost`를 붙임(`.env`의 `redis`는 docker 안에서만 읽힘). 겪어 본 함정에 `evidence_chunks` 마이그레이션의 `CREATE EXTENSION` 예외와 pgvector 이미지 안내를 추가 (#107) | 김채연 |
| 2026-10-30 | 실천(챌린지) 담당을 채연으로 적음(10/30 회의). P-1 ~ P-4 서버를 먼저 만듦, 포인트와 달성 현황은 뒤로 | 이수인 |
| 2026-10-31 | 실천(챌린지) 담당 표기를 나눔: 서버는 수인(#155) 이어서 채연, 실천 탭 앱 화면은 채연 (#155 머지 반영) | 김채연 |
