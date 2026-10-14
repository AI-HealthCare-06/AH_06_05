"""OCR을 부르기 전 검사 (precheck) — 머리말에서 크기 읽기 · 너무 작은 사진 · 똑같은 파일"""

import struct

from app.services.ocr import precheck
from app.services.prescriptions import Blob


def jpeg(w: int, h: int, *, fill: bool = False, progressive: bool = False, before: bytes = b"") -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    comment = b"\xff\xfe\x00\x07hello"
    sof = (b"\xff\xc2" if progressive else b"\xff\xc0") + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    pad = b"\xff\xff\xff" if fill else b""
    return b"\xff\xd8" + app0 + comment + before + pad + sof + b"\xff\xda\x00\x08" + b"0" * 20


def png(w: int, h: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", w, h)
        + b"\x08\x02\x00\x00\x00"
        + b"0" * 8
    )


def test_size_from_jpeg_png_headers():
    assert precheck.image_size(jpeg(1200, 1600), "jpg") == (1200, 1600)
    assert precheck.image_size(jpeg(300, 235, progressive=True), "jpg") == (300, 235)  # progressive
    assert precheck.image_size(jpeg(800, 600, fill=True), "jpg") == (800, 600)  # 채움 바이트
    assert precheck.image_size(png(1279, 934), "png") == (1279, 934)


def test_unreadable_headers_return_none_instead_of_rejecting():
    assert precheck.image_size(b"\xff\xd8\xff\xe0" + b"0" * 100, "jpg") is None
    assert precheck.image_size(b"\xff\xd8", "jpg") is None
    assert precheck.image_size(b"\xff\xd8\xff", "jpg") is None
    assert precheck.image_size(b"", "jpg") is None
    assert precheck.image_size(b"\x89PNG\r\n\x1a\n", "png") is None
    assert precheck.image_size(b"%PDF-1.4", "pdf") is None
    assert precheck.image_size(jpeg(0, 0), "jpg") is None  # 크기 0은 믿지 않음
    # 이미지 데이터(SOS)가 먼저 나오면 더 찾지 않음
    assert precheck.image_size(b"\xff\xd8\xff\xda\x00\x08" + b"0" * 40, "jpg") is None


def test_screen_skips_small_and_identical_files_but_keeps_order():
    big, big2 = jpeg(1200, 1600), jpeg(1200, 1600, before=b"\xff\xfe\x00\x04zz")
    blobs = [
        Blob(1, big, "jpg", "p1"),
        Blob(2, jpeg(291, 400), "jpg", "p2"),  # 너무 작음
        Blob(3, big, "jpg", "p3"),  # 1번과 똑같음
        Blob(4, big2, "jpg", "p4"),  # 크기는 같지만 바이트가 다름 → 읽음
        Blob(5, b"%PDF-1.4 x", "pdf", "p5"),  # PDF는 크기를 보지 않음
        Blob(6, b"\xff\xd8\xff\xe0" + b"0" * 50, "jpg", "p6"),  # 머리말을 못 읽음 → 읽음
    ]
    out = precheck.screen(blobs)
    assert [b.file_index for b in out.ready] == [1, 4, 5, 6]
    assert out.too_small == [2] and out.duplicates == {3: 1}


def test_boundary_is_exclusive_at_min_side():
    ok = precheck.screen([Blob(1, jpeg(precheck.MIN_SIDE, 900), "jpg", "a")])
    small = precheck.screen([Blob(1, jpeg(precheck.MIN_SIDE - 1, 900), "jpg", "a")])
    assert ok.too_small == [] and small.too_small == [1]
