"""피처 1 OCR 서버 코드 — 시험 폴더(ocr_sandbox)의 10/13 개선 파이프라인을 서버로 옮긴 것

흐름: CLOVA 결과 → prepare(기울임 · 숫자 칸 정리) → table(표 읽기) → meta(교부일 · 출생연도)
      → icd(질병분류기호 보정) → matcher(약 이름 맞추기) → numeric(숫자 범위) → pipeline.read()
"""
