#!/usr/bin/env python3
"""구형 안드로이드 게임 APK의 .fbm 이미지 컨테이너를 PNG로 푼다(선택 도구).

포맷은 저장소 밖의 APK를 조사해 알아낸 것이고, 이 저장소는 그 결과물을 담지 않는다.
표준 라이브러리만 쓴다(PNG도 직접 쓴다).

    컨테이너
        [u8 0x01][u8 frameCount][u32 offset × frameCount][frames...]
        offset 은 파일 선두 기준 절대값. 마지막 프레임의 끝은 파일 끝.

    프레임
        [u8 anchorX][u8 anchorY][u16BE width][u16BE height][u8 예약][u8 hasPalette]
        hasPalette 가 1이면  [u8 palCount][ (R, G, B, 0x00) × palCount ]
        hasPalette 가 0이면  팔레트가 없다. 시트의 첫 프레임 팔레트를 그대로 쓴다.
        이어서 8비트 팔레트 인덱스 픽셀. 한 행의 길이는 4의 배수로 맞춰져 있고,
        마지막에 4바이트가 남는다.

    가장 흔한 실수는 팔레트 엔트리를 3바이트로 읽는 것이다. 실제로는 패딩 한 바이트가
    붙어 4바이트라, 3으로 읽으면 색이 엔트리마다 한 칸씩 밀려 화면이 전부 깨진다.

사용법
    python3 tools/decode_fbm.py <assets 디렉터리 또는 .fbm 파일> -o out/
    python3 tools/decode_fbm.py assets/m0_0.fbm --sheet     # 프레임을 한 장으로
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

MAGENTA = (255, 0, 255)          # 투명으로 취급하는 색


class FrameError(ValueError):
    pass


def split_container(blob: bytes) -> list[tuple[int, int]]:
    if len(blob) < 2 or blob[0] != 0x01:
        raise FrameError("fbm 컨테이너가 아니다")
    count = blob[1]
    bounds = list(struct.unpack_from("<%dI" % count, blob, 2)) + [len(blob)]
    return [(bounds[i], bounds[i + 1]) for i in range(count)]


def decode_frame(chunk: bytes, shared_palette: list[tuple[int, int, int]] | None):
    """한 프레임을 (너비, 높이, 앵커, 팔레트, 행별 인덱스)로 푼다."""
    if len(chunk) < 8:
        raise FrameError("프레임이 너무 짧다")
    anchor = (chunk[0], chunk[1])
    width, height = struct.unpack_from(">HH", chunk, 2)
    has_palette = chunk[7]

    pos = 8
    if has_palette:
        count = chunk[pos]
        pos += 1
        palette = []
        for _ in range(count):
            palette.append((chunk[pos], chunk[pos + 1], chunk[pos + 2]))
            pos += 4                      # RGB + 패딩 1바이트
    else:
        palette = list(shared_palette or [])

    stride = (width + 3) // 4 * 4          # 행 길이는 4의 배수
    pixels = chunk[pos:]
    rows = []
    for y in range(height):
        row = pixels[y * stride: y * stride + width]
        rows.append(row + bytes(width - len(row)) if len(row) < width else row)
    return width, height, anchor, palette, rows


def write_png(path: Path, width: int, height: int, rgba: bytearray) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)                      # 필터 없음
        raw += rgba[y * width * 4:(y + 1) * width * 4]

    def chunk(tag: bytes, body: bytes) -> bytes:
        payload = tag + body
        return struct.pack(">I", len(body)) + payload + struct.pack(">I", zlib.crc32(payload))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def paint(rgba: bytearray, canvas_width: int, left: int, frame) -> None:
    width, height, _anchor, palette, rows = frame
    for y in range(height):
        for x, index in enumerate(rows[y]):
            red, green, blue = palette[index] if index < len(palette) else MAGENTA
            alpha = 0 if (red, green, blue) == MAGENTA else 255
            at = ((y * canvas_width) + left + x) * 4
            rgba[at:at + 4] = bytes((red, green, blue, alpha))


def decode_file(path: Path, out_dir: Path, as_sheet: bool) -> int:
    blob = path.read_bytes()
    frames, shared = [], None
    for begin, end in split_container(blob):
        frame = decode_frame(blob[begin:end], shared)
        if shared is None and frame[3]:
            shared = frame[3]
        frames.append(frame)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    if as_sheet:
        width = sum(f[0] for f in frames)
        height = max(f[1] for f in frames)
        rgba = bytearray(width * height * 4)
        left = 0
        for frame in frames:
            paint(rgba, width, left, frame)
            left += frame[0]
        write_png(out_dir / f"{stem}.png", width, height, rgba)
    else:
        for index, frame in enumerate(frames):
            rgba = bytearray(frame[0] * frame[1] * 4)
            paint(rgba, frame[0], 0, frame)
            write_png(out_dir / f"{stem}_{index:02d}.png", frame[0], frame[1], rgba)
    return len(frames)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help=".fbm 파일 또는 그것들이 든 디렉터리")
    parser.add_argument("-o", "--out", type=Path, default=Path("out"))
    parser.add_argument("--sheet", action="store_true", help="프레임을 가로로 이어 한 장으로 저장")
    args = parser.parse_args()

    targets = sorted(args.source.glob("*.fbm")) if args.source.is_dir() else [args.source]
    if not targets:
        raise SystemExit(f"{args.source} 에서 .fbm 을 찾지 못했다")

    total_files = total_frames = 0
    for target in targets:
        try:
            total_frames += decode_file(target, args.out, args.sheet)
            total_files += 1
        except (FrameError, IndexError, struct.error) as error:
            print(f"  건너뜀 {target.name}: {error}")
    print(f"{total_files}개 파일에서 프레임 {total_frames}장을 {args.out} 에 썼다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
