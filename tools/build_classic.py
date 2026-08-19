#!/usr/bin/env python3
"""원작 복원 그래픽판의 에셋 번들을 만든다(선택 도구).

APK의 assets/ 를 읽어 웹 런타임이 바로 쓸 수 있는 PNG + JSON 으로 바꾼다.
결과물은 원저작물이므로 저장소에 넣지 않는다(.gitignore 로 classic/ 을 막아 둔다).

    python3 tools/build_classic.py <APK 또는 assets 디렉터리> -o classic --map 0

포맷 메모
    .fbm  이미지 컨테이너            → docs/data-format.md
    .mdt  화면 한 장의 타일맵
          [u8 width][u8 height][u8 n][u8 flag][... 헤더 총 9+n 바이트]
          [타일 레이어 3장][충돌 레이어 1장]  각 width*height 바이트
          타일 값 255 는 '빈 칸', 그 외는 타일 번호를 그대로 가리킨다.
          충돌 레이어는 0 통과, 1 막힘, 255 특수.
    .mif  맵 이름과 화면 연결 정보. 이름만 읽는다(나머지는 아직 해독 못 함).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from decode_fbm import decode_frame, split_container, write_png   # noqa: E402

TILE = 8
EMPTY_TILE = 255
TILE_LAYERS = 3


class Source:
    """APK(zip)든 풀어놓은 디렉터리든 같은 방식으로 읽는다."""

    def __init__(self, path: Path):
        self.zip = None
        self.dir = None
        if path.is_dir():
            self.dir = path / "assets" if (path / "assets").is_dir() else path
        else:
            self.zip = zipfile.ZipFile(path)

    def read(self, name: str) -> bytes:
        if self.dir is not None:
            return (self.dir / name).read_bytes()
        return self.zip.read("assets/" + name)

    def names(self) -> list[str]:
        if self.dir is not None:
            return sorted(p.name for p in self.dir.iterdir() if p.is_file())
        return sorted(n[len("assets/"):] for n in self.zip.namelist() if n.startswith("assets/"))

    def exists(self, name: str) -> bool:
        return name in set(self.names())


def decode_sheet(blob: bytes):
    """시트의 모든 프레임을 (너비, 높이, 앵커, 팔레트, 행) 목록으로."""
    frames, shared = [], None
    for begin, end in split_container(blob):
        frame = decode_frame(blob[begin:end], shared)
        if shared is None and frame[3]:
            shared = frame[3]
        frames.append(frame)
    return frames


def frames_to_png(path: Path, frames) -> list[dict]:
    """프레임을 가로로 이어 한 장으로 저장하고, 각 프레임의 위치를 돌려준다."""
    width = sum(f[0] for f in frames)
    height = max(f[1] for f in frames)
    rgba = bytearray(width * height * 4)
    boxes, left = [], 0
    for w, h, anchor, palette, rows in frames:
        for y in range(h):
            for x, index in enumerate(rows[y]):
                red, green, blue = palette[index] if index < len(palette) else (255, 0, 255)
                alpha = 0 if (red, green, blue) == (255, 0, 255) else 255
                at = ((y * width) + left + x) * 4
                rgba[at:at + 4] = bytes((red, green, blue, alpha))
        boxes.append({"x": left, "y": 0, "w": w, "h": h, "ax": anchor[0], "ay": anchor[1]})
        left += w
    write_png(path, width, height, rgba)
    return boxes


def build_tileset(source: Source, group: int, out_dir: Path) -> dict:
    """맵 그룹이 쓰는 타일 시트들을 하나의 아틀라스로 굽는다."""
    names = [n for n in source.names() if re.fullmatch(rf"m{group}_\d+\.fbm", n)]
    names.sort(key=lambda n: int(n.split("_")[1].split(".")[0]))
    banks = []
    for name in names:
        frame = decode_sheet(source.read(name))[0]
        banks.append(frame)

    # 아틀라스는 세로로 쌓는다. 타일 번호는 시트마다 0부터 다시 센다.
    width = max(f[0] for f in banks)
    height = sum(f[1] for f in banks)
    rgba = bytearray(width * height * 4)
    sheets, top = [], 0
    for w, h, anchor, palette, rows in banks:
        for y in range(h):
            for x, index in enumerate(rows[y]):
                red, green, blue = palette[index] if index < len(palette) else (255, 0, 255)
                alpha = 0 if (red, green, blue) == (255, 0, 255) else 255
                at = (((top + y) * width) + x) * 4
                rgba[at:at + 4] = bytes((red, green, blue, alpha))
        sheets.append({"top": top, "cols": w // TILE, "rows": h // TILE})
        top += h
    write_png(out_dir / f"tiles_m{group}.png", width, height, rgba)
    return {"image": f"tiles_m{group}.png", "tile": TILE, "sheets": sheets}


def build_maps(source: Source, group: int) -> list[dict]:
    names = [n for n in source.names() if re.fullmatch(rf"m{group}_\d+\.mdt", n)]
    names.sort(key=lambda n: int(n.split("_")[1].split(".")[0]))
    screens = []
    for name in names:
        blob = source.read(name)
        width, height = blob[0], blob[1]
        plane = width * height
        start = len(blob) - (TILE_LAYERS + 1) * plane
        if start < 4:
            print(f"  건너뜀 {name}: 크기가 맞지 않는다")
            continue
        layers = [
            list(blob[start + i * plane: start + (i + 1) * plane]) for i in range(TILE_LAYERS)
        ]
        collision = list(blob[start + TILE_LAYERS * plane: start + (TILE_LAYERS + 1) * plane])
        screens.append({
            "id": int(name.split("_")[1].split(".")[0]),
            "w": width, "h": height,
            "layers": layers, "collision": collision,
        })
    return screens


def map_name(source: Source, group: int) -> str:
    try:
        blob = source.read(f"m{group}.mif")
    except (KeyError, FileNotFoundError):
        return f"맵 {group}"
    start = 4
    while start < 40 and blob[start] == 0:
        start += 1
    end = start
    while end < len(blob) and blob[end] != 0:
        end += 1
    return blob[start:end].decode("cp949", "replace") or f"맵 {group}"


def build_sprites(source: Source, out_dir: Path, pattern: str, folder: str, limit: int | None = None):
    out = out_dir / folder
    out.mkdir(parents=True, exist_ok=True)
    names = sorted(n for n in source.names() if re.fullmatch(pattern, n))
    if limit:
        names = names[:limit]
    index = {}
    for name in names:
        try:
            frames = decode_sheet(source.read(name))
        except Exception as error:                       # 포맷이 다른 파일은 건너뛴다
            print(f"  건너뜀 {name}: {error}")
            continue
        stem = name.rsplit(".", 1)[0]
        index[stem] = {
            "image": f"{folder}/{stem}.png",
            "frames": frames_to_png(out / f"{stem}.png", frames),
        }
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="APK 또는 assets 디렉터리")
    parser.add_argument("-o", "--out", type=Path, default=Path("classic"))
    parser.add_argument("--map", type=int, default=0, help="구울 맵 그룹 번호")
    parser.add_argument("--audio", action="store_true", help="ogg 도 함께 복사")
    args = parser.parse_args()

    source = Source(args.source)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    print(f"타일셋 굽는 중 (m{args.map})")
    tileset = build_tileset(source, args.map, out)
    print(f"맵 화면 읽는 중")
    screens = build_maps(source, args.map)
    print(f"  화면 {len(screens)}장")

    print("스프라이트 굽는 중")
    field = build_sprites(source, out, r"m_f_\d+\.fbm", "field")
    battle = build_sprites(source, out, r"m_b_\d+_1\.fbm", "battle")
    hero = build_sprites(source, out, r"h_f_\d+\.fbm", "hero")
    print(f"  필드 {len(field)} · 전투 {len(battle)} · 주인공 {len(hero)}")

    if args.audio:
        audio_dir = out / "audio"
        audio_dir.mkdir(exist_ok=True)
        count = 0
        for name in source.names():
            if name.endswith(".ogg"):
                (audio_dir / name).write_bytes(source.read(name))
                count += 1
        print(f"  오디오 {count}개")

    bundle = {
        "map": {"group": args.map, "name": map_name(source, args.map),
                "tileset": tileset, "screens": screens},
        "field": field, "battle": battle, "hero": hero,
    }
    (out / "bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for name in ("classic.html", "classic.js", "classic.css"):
        origin = Path(__file__).resolve().parent.parent / "web-classic" / name
        if origin.exists():
            shutil.copy(origin, out / name)

    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\n{out}/  {size / 1024 / 1024:.1f} MB — classic.html 을 브라우저로 열면 된다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
