"""CLOVA를 부르기 전에 걸러 내는 검사 — 부를 필요가 없는 사진에 호출을 쓰지 않으려고

멘토링 4회차: OCR을 부르기 전에 쓸 수 없는 사진 · 같은 사진을 먼저 거른다.
이미지를 디코딩하지 않고 파일 머리말만 읽어서 (빠르고, 이미지 폭탄 위험이 없고, 새 라이브러리가 필요 없음) 두 가지만 본다.

- 너무 작은 사진: 짧은 쪽이 MIN_SIDE 미만 → 다시 찍기 (시험 9장 중 못 읽힌 두 장이 291px · 235px였고 나머지는 440px 이상)
- 바이트가 완전히 같은 사진: 두 번째부터 건너뜀

일부러 하지 않는 것:
- 비슷한 사진 찾기: 같은 사진을 재압축 · 축소한 것과 숫자 한 글자만 다른 처방전이 이미지 비교로는 구분되지 않았다
  (실험: 글자 한 개 차이의 칸별 차이 0.012~0.024, 같은 사진 변형 0.006~0.054). 잘못 합치면 처방전이 사라지므로
  비슷한 처방전은 읽은 뒤 내용(병원 · 교부일 · 약 목록)으로 비교한다 (prescriptions.same_content)
- 흐림 · 밝기 검사: 시험 9장에서 읽힌 사진과 못 읽힌 사진이 수치로 나뉘지 않아 기준을 정할 수 없음. 실제 촬영 사진이 모이면 정한다
- 처방전이 아닌 사진 찾기: 손글씨 처방전처럼 종이가 하얗지 않은 정상 사진을 놓칠 수 있어서, OCR 결과(pipeline · _failure_code)로 판단
"""

import hashlib
import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.prescriptions import Blob

MIN_SIDE = 400
_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}  # 크기가 들어 있는 JPEG 구간 표시


def image_size(content: bytes, fmt: str) -> tuple[int, int] | None:
    """(가로, 세로). 머리말을 읽을 수 없으면 None — 이때는 걸러 내지 않고 OCR에 맡긴다"""
    try:
        if fmt == "png":
            if content[12:16] != b"IHDR":
                return None
            w, h = struct.unpack(">II", content[16:24])
            return (w, h) if w and h else None
        if fmt == "jpg":
            return _jpeg_size(content)
    except (struct.error, IndexError):
        return None
    return None  # pdf 등


def _jpeg_size(c: bytes) -> tuple[int, int] | None:
    i, n = 2, len(c)
    while i + 4 <= n:
        if c[i] != 0xFF:
            return None
        while i < n and c[i] == 0xFF:  # 채움 바이트
            i += 1
        if i >= n:
            return None
        marker = c[i]
        i += 1
        if marker in _SOF:
            h, w = struct.unpack(">HH", c[i + 3 : i + 7])
            return (w, h) if w and h else None
        if marker == 0xDA or marker == 0xD9:  # 이미지 데이터 시작 · 끝까지 크기 정보가 없음
            return None
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # 길이 없는 표시
            continue
        i += struct.unpack(">H", c[i : i + 2])[0]
    return None


@dataclass
class Screened:
    ready: list["Blob"] = field(default_factory=list)  # OCR에 보낼 사진
    too_small: list[int] = field(default_factory=list)  # 다시 찍어야 하는 사진 번호
    duplicates: dict[int, int] = field(default_factory=dict)  # 건너뛴 사진 번호 → 같은 사진의 먼저 올린 번호


def screen(blobs: list["Blob"]) -> Screened:
    out = Screened()
    seen: dict[str, int] = {}
    for b in blobs:
        digest = hashlib.sha256(b.content).hexdigest()
        if digest in seen:
            out.duplicates[b.file_index] = seen[digest]
            continue
        seen[digest] = b.file_index
        size = image_size(b.content, b.fmt)
        if size and min(size) < MIN_SIDE:
            out.too_small.append(b.file_index)
            continue
        out.ready.append(b)
    return out
