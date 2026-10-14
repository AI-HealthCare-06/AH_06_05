"""CLOVA를 부르기 전에 걸러 내는 검사 — 부를 필요가 없는 사진에 호출을 쓰지 않으려고

멘토링 4회차: OCR을 부르기 전에 쓸 수 없는 사진 · 같은 사진을 먼저 거른다.
세 가지를 본다. 앞의 둘은 이미지를 열지 않고 파일 머리말만 읽는다 (빠르고 이미지 폭탄 위험이 없음).

- 너무 작은 사진: 짧은 쪽이 MIN_SIDE 미만 → 다시 찍기 (시험 9장 중 못 읽힌 두 장이 291px · 235px였고 나머지는 440px 이상)
- 바이트가 완전히 같은 사진: 두 번째부터 건너뜀
- 너무 흐린 사진: 글자가 가장 많은 칸 3개의 선명도가 OCR_MIN_SHARPNESS 미만 → 다시 찍기.
  전체 평균이 아니라 가장 선명한 칸으로 재서, 글자가 적은 처방전이 흰 종이 때문에 흐리다고 잘못 판정되지 않게 한다

일부러 하지 않는 것:
- 비슷한 사진 찾기: 같은 사진을 재압축 · 축소한 것과 숫자 한 글자만 다른 처방전이 이미지 비교로는 구분되지 않았다
  (실험: 글자 한 개 차이의 칸별 차이 0.012~0.024, 같은 사진 변형 0.006~0.054). 잘못 합치면 처방전이 사라지므로
  비슷한 처방전은 읽은 뒤 내용(병원 · 교부일 · 약 목록)으로 비교한다 (prescriptions.same_content)
- 밝기 검사: 어둡게 만든 시험 사진(평균 밝기 136)도 정상으로 읽혀서 거를 근거가 없음
- 처방전이 아닌 사진 찾기: 손글씨 처방전처럼 종이가 하얗지 않은 정상 사진을 놓칠 수 있어서, OCR 결과(pipeline · _failure_code)로 판단
"""

import hashlib
import io
import logging
import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PIL import Image, ImageFilter, ImageStat

from app.core import config

if TYPE_CHECKING:
    from app.services.prescriptions import Blob

logger = logging.getLogger(__name__)

MIN_SIDE = 400
MAX_PIXELS = (
    40_000_000  # 이보다 크면 열지 않음 (10MB 파일이 거대한 그림으로 풀리는 이미지 폭탄 방지) → 흐림 검사 건너뜀
)
THUMB = 1000  # 선명도는 긴 쪽 1000px로 줄여서 잰다 (해상도가 달라도 같은 기준)
GRID = (4, 6)  # 가로 4 × 세로 6칸
TOP_TILES = 3  # 글자가 가장 많은(가장 선명한) 칸 3개의 평균
_LAPLACE = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128)
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


def sharpness(content: bytes, fmt: str) -> float | None:
    """글자가 가장 많은 칸 3개의 선명도 (라플라시안 분산). 잴 수 없으면 None — 이때는 걸러 내지 않고 OCR에 맡긴다.
    흰 종이 0 · 심하게 흐림 한 자리 · 흐려도 읽힘 약 230 · 정상 사진 900 이상 (10/13 시험 사진)"""
    size = image_size(content, fmt)
    if size is None or size[0] * size[1] > MAX_PIXELS:
        return None
    try:
        with Image.open(io.BytesIO(content)) as im:
            im.draft("L", (THUMB * 2, THUMB * 2))  # JPEG는 줄여서 읽어 빠름 · 메모리 적음
            g = im.convert("L")
        g.thumbnail((THUMB, THUMB))
        lap = g.filter(_LAPLACE)
        # 필터가 처리하지 않는 가장자리 1픽셀은 가짜 신호라 뺀다 (빼지 않으면 흰 종이도 186이 나옴)
        lap = lap.crop((1, 1, lap.width - 1, lap.height - 1))
        gx, gy = GRID
        if lap.width < gx or lap.height < gy:
            return None
        w, h = lap.size
        tiles = sorted(
            ImageStat.Stat(lap.crop((i * w // gx, j * h // gy, (i + 1) * w // gx, (j + 1) * h // gy))).var[0]
            for j in range(gy)
            for i in range(gx)
        )
        return float(sum(tiles[-TOP_TILES:]) / TOP_TILES)
    except Exception as e:  # 깨진 파일 · 지원하지 않는 모양 — 검사만 건너뛰고 OCR로 보냄
        logger.info("선명도를 재지 못함 (%s)", type(e).__name__)
        return None


@dataclass
class Screened:
    ready: list["Blob"] = field(default_factory=list)  # OCR에 보낼 사진
    too_small: list[int] = field(default_factory=list)  # 다시 찍어야 하는 사진 번호 (너무 작음)
    blurry: list[int] = field(default_factory=list)  # 다시 찍어야 하는 사진 번호 (너무 흐림)
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
        limit = config.OCR_MIN_SHARPNESS
        if limit > 0 and b.fmt in ("jpg", "png"):
            sharp = sharpness(b.content, b.fmt)
            if sharp is not None and sharp < limit:
                out.blurry.append(b.file_index)
                continue
        out.ready.append(b)
    return out
