#!/usr/bin/env python3
"""원작 첫 필드 맵의 타일셋(m0_*)에서 게임에 쓸 타일을 골라 아틀라스로 굽는다.

    python3 tools/rip_tiles.py /경로/assets -o web/

가로 = 타일 종류(게임의 TILE 상수 순서), 세로 = 변주 3종.
m0_4 처럼 투명 배경 오버레이인 페이지는 잔디 위에 합성해서 불투명 타일로 만든다.
잔디 3종은 톤이 거의 같은 것으로 골랐다 — 밝기가 다르면 바닥이 체크무늬로 보인다.
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image
import fbm

TS = 16
_cache: dict[str, Image.Image] = {}


def page(assets: Path, name: str) -> Image.Image:
    if name not in _cache:
        _cache[name] = fbm.load(str(assets / (name + '.fbm')))[0]
    return _cache[name]


def tile(assets: Path, name: str, idx: int) -> Image.Image:
    im = page(assets, name)
    cols = im.width // TS
    x, y = (idx % cols) * TS, (idx // cols) * TS
    return im.crop((x, y, x + TS, y + TS))


def onto(base: Image.Image, top: Image.Image) -> Image.Image:
    c = base.copy(); c.alpha_composite(top); return c


def tint(im: Image.Image, mul: float, add: int = 0) -> Image.Image:
    o = im.copy(); px = o.load()
    for y in range(TS):
        for x in range(TS):
            r, g, b, a = px[x, y]
            px[x, y] = (min(255, int(r*mul)+add), min(255, int(g*mul)+add),
                        min(255, int(b*mul)+add), a)
    return o


def build(assets: Path) -> Image.Image:
    T = lambda n, i: tile(assets, n, i)
    grass = [T('m0_0', i) for i in (5, 13, 14)]
    kinds = [
        [T('m0_6', i) for i in (1, 2, 3)],                                  # WATER
        [tint(T('m0_5', i), 1.06, 12) for i in (6, 7, 8)],                  # SAND
        grass,                                                              # GRASS
        [onto(grass[i], T('m0_4', j)) for i, j in enumerate((3, 7, 8))],    # TALL
        [T('m0_0', i) for i in (28, 30, 35)],                               # TREE
        [onto(grass[0], T('m0_4', 36)), onto(grass[1], T('m0_4', 43)),
         onto(grass[2], T('m0_4', 29))],                                    # ROCK
        [T('m0_5', i) for i in (1, 2, 3)],                                  # PATH
        [T('m0_0', i) for i in (32, 33, 26)],                               # FLOWER
        [T('m0_2', i) for i in (14, 15, 16)],                               # CLIFF
    ]
    atlas = Image.new('RGBA', (len(kinds) * TS, 3 * TS), (0, 0, 0, 255))
    for k, variants in enumerate(kinds):
        for v, im in enumerate(variants):
            flat = Image.new('RGBA', (TS, TS), (0, 0, 0, 255))
            flat.alpha_composite(im)
            atlas.paste(flat, (k * TS, v * TS))
    return atlas.convert('RGB')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assets", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("."))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    png = args.out / "tiles.png"
    build(args.assets).quantize(colors=200, method=Image.MEDIANCUT).save(png, optimize=True)
    b64 = base64.b64encode(png.read_bytes()).decode()
    (args.out / "tiledata.js").write_text(
        'const TILE_ATLAS_SRC = "data:image/png;base64,%s";\n' % b64, encoding='utf-8')
    print("%s (%d bytes)" % (png, png.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
