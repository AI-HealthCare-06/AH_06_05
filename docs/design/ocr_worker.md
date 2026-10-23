# OCR 워커 이전 (10/26, #118 연결)

OCR 읽기를 서버(FastAPI) 안 백그라운드 작업에서 arq 워커(`ai-worker` 컨테이너)로 옮긴다. 꺼짐이 기본이고 `OCR_WORKER=true`로 켠다.

## 흐름

```
앱 ── O-1 업로드 ──▶ FastAPI: 검사 → 작업 만들기 → (OCR_WORKER 켜짐) 사진을 S3에 올림(8초 안) → ocr_jobs.photos에 위치 기록 → 대기열에 넣기 → 202
                                                                      │ 못 올리거나 못 넣거나 워커가 죽었으면
                                                                      ▼
                                                      서버 안 백그라운드 (예전과 같음, 사진 저장은 OCR과 동시에)
ai-worker ◀─ 대기열 ── ocr_job(job_id, user_id) → S3에서 사진 읽기 → 기존 읽기 파이프라인(run_job) → 결과는 DB
```

- 처리 코드는 하나(`app/services/prescriptions.py`의 `run_job`)이고, 워커는 사진을 저장소에서 읽어 부르기만 한다 (`ai_worker/tasks/ocr_tasks.py`).
- 워커 이미지에 `app/` 코드와 app 의존성(tortoise, boto3 등)을 함께 넣는다 (`ai_worker/Dockerfile`).
- 워커가 시작할 때 DB에 연결하고 약 이름 색인을 미리 만든다 (첫 작업이 느려지지 않게).

## 정한 값 (10/23)

| 항목 | 값 | 이유 |
|---|---|---|
| 다시 시도 | CLOVA가 **모두** 실패했을 때만 1번 더 (총 2번, `OCR_WORKER_MAX_TRIES`) | 하나도 저장되지 않았으니 처음부터 다시 해도 안전. 한 장이라도 읽었으면 다시 읽지 않음 |
| 다시 시도 간격 | 20초 (`OCR_WORKER_RETRY_DELAY_SEC`) | CLOVA 일시 장애는 보통 짧음. 화면은 계속 "읽는 중" |
| 한 번 시도 제한 | 300초 (`OCR_WORKER_TIMEOUT_SEC`) | 사진 5장 × CLOVA 40초 + 여유. 챗봇 작업(25초)과 별도 (`func(timeout)`) |
| 실패로 닫기 | 2번째도 모두 실패하면 `OCR_FAILED` | 조회 때 15분이 지난 작업은 실패로 닫는 기존 규칙도 그대로 |
| 업로드 응답이 저장을 기다리는 시간 | 최대 8초 (`OCR_UPLOAD_WAIT_SEC`) | 넘으면 서버 안 처리로 바꿔 사용자에게는 오류가 아님 |
| 사진 삭제 | 워커가 매시간 17분 (켠 직후에도 1번), 24시간 지난 것 | S3 보관 규칙(1일)은 마지막 안전장치 |
| 워커 생존 확인 | 워커가 30초마다 Redis 키를 갱신, 업로드 API가 없으면 서버 안 처리 | 워커가 죽은 채 작업이 쌓이지 않게 |

## 배포 순서 (서버)

1. main 병합 뒤 `bash scripts/deployment.sh` 에서 `1 2` (fastapi, ai_worker 둘 다 새로 빌드).
2. 서버에서 `git pull`, `aerich upgrade` (15, 16번 마이그레이션).
3. `.env`에 `PHOTO_STORAGE=s3`, `PHOTO_S3_BUCKET=ah06-5-prescription-photos`를 넣고 컨테이너를 새 이미지로 다시 띄운다. 이때 `OCR_WORKER`는 아직 `false`.
4. `docker logs ai-worker`에 `Starting worker for 3 functions: example_echo_task, ocr_job, cron:purge_photos`가 보이는지, `docker stats ai-worker`가 768MB 한도에 여유가 있는지 본다.
5. `.env`의 `OCR_WORKER=true`로 바꾸고 fastapi를 다시 띄운다.
6. 처방전 1장을 올려 본다: 결과가 나오고 → S3 `ocr/…`에 파일이 생기고 → 같은 파일을 다시 올리면 CLOVA를 부르지 않음(로그에 "지난번에 올린 같은 파일"). 워커 로그에 `ocr_job`이 찍혀야 워커가 읽은 것이다 (안 찍히면 서버 안 처리로 바뀐 것).
7. 앱 안내문과 NFR-011은 6번까지 확인한 뒤에만 바꾼다.

## 확인 방법과 한계

- 클라우드 시험: 진짜 arq 워커 + Redis + DB로 업로드 → 읽기 → 삭제, CLOVA 전부 실패 → 20초 뒤 재시도 → 실패로 닫기를 확인했다. S3는 moto(가짜 S3)로 진짜 boto3 경로를 확인했다.
- 서버에서만 확인할 수 있는 것: 진짜 AWS 권한(역할로 읽기·쓰기·지우기), 워커 컨테이너 메모리, 컨테이너 이미지 빌드.
