#!/usr/bin/env python3
"""배틀몬스터3 APK에서 몬스터 스프라이트와 이름을 뽑아 게임용 데이터로 굽는다.

    python3 tools/rip_monsters.py /경로/assets -o web/

만들어지는 것:
  * 몬스터 아틀라스 PNG 한 장 (131마리, 256색 양자화, 약 68KB)
  * mondata.js — 아틀라스 base64 + [이름, 속성, 고유기술, 설명, x, y, w, h, 능력치]

이름과 고유기술은 assets/item_mon.dat 에서 그대로 가져온다.
스프라이트는 m_b_XXX_1.fbm 안의 파트 중 '완성된 전신'을 골라 쓴다 —
.ani 로 조립하면 무기·이펙트 파트까지 섞여 지저분해지는 개체가 많아서다.
속성은 원작 데이터에 없어서 이름 규칙으로 배정했다.

포맷 해독 내용은 docs/reversing.md 참고. Pillow가 필요하다.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

import fbm
import sprite_quality

CELL = 80

# 원작에 속성 데이터가 없어 작명 규칙으로 나눴다.
TYPE_RULES = [
    ("물",   r"터틀|돌핀|히포|머메이드|갓파|워터|프로그|옥터|오리|가오리|레비아|네시|운디네|"
             r"나이아스|크로커|덕|아귀|아이스|프리슨|스파이럴|미트로브|푸키"),
    ("불",   r"파이어|레드|헬라이더|피닉스|폭렬|켈베로스|바알|나타|라이언|히트|사도|"
             r"제천대성|복싱|크라운|킹랍토르"),
    ("풀",   r"스넥|모스|플리오스|드라이어드|꿈틀|머쉬|플라워|버섯|안트|웜|립페리|키투스|"
             r"스넬|슬라임|고블링|에그|얼리아드|비글"),
    ("바람", r"바람|윈드|윙|그리폰|콘도르|아울|이글|제피로스|마루트|가브리엘|선녀|고스트|"
             r"뱀파이어|뱀프|메두사|리리스|조커|플라이|하늘|오리온|위니아|호라이|캣츠아이|"
             r"나이트가너|멀린|흑마법사|스켈위자드|달로스|깨몽"),
]
# 속성별 (체력, 공격, 방어, 속도) 성향
TYPE_MOD = {
    "물":   (1.14, 0.94, 1.06, 0.92),
    "불":   (0.90, 1.22, 0.88, 1.08),
    "풀":   (1.02, 0.96, 1.14, 0.94),
    "땅":   (1.12, 1.04, 1.18, 0.74),
    "바람": (0.88, 1.02, 0.86, 1.32),
}


def type_of(name: str) -> str:
    for t, pat in TYPE_RULES:
        if re.search(pat, name):
            return t
    return "땅"


def read_names(path: Path):
    """item_mon.dat: u8 개수, u32 오프셋 배열, 그 뒤 레코드.

    레코드 = [이름 길이+이름] [0x01] [u32 자기참조] [설명 길이+설명] ...
    문자열은 CP949.
    """
    d = path.read_bytes()
    cnt = d[0]
    offs = [struct.unpack_from('<I', d, 1 + 4 * i)[0] for i in range(cnt)]
    out = []
    for o in offs:
        p = o
        ln = d[p]; name = d[p + 1:p + 1 + ln].decode('cp949', 'replace'); p += 1 + ln
        p += 1 + 4
        ln2 = d[p]; skill = d[p + 1:p + 1 + ln2].decode('cp949', 'replace')
        out.append((name, skill))
    return out


def best_sprite(assets: Path, idx: int):
    """전신으로 보이는 파트 하나를 고른다 (품질점수 × 면적 최대)."""
    f = assets / ('m_b_%03d_1.fbm' % idx)
    if not f.exists():
        return None, 0.0
    try:
        parts = fbm.load(str(f))
    except Exception:
        return None, 0.0
    best, score, quality = None, -1.0, 0.0
    for p in parts:
        if p is None:
            continue
        bb = p.getbbox()
        if not bb:
            continue
        c = p.crop(bb)
        if not (20 <= c.width <= CELL and 20 <= c.height <= CELL):
            continue
        q = sprite_quality.score(c)
        v = q * (c.width * c.height) ** 0.6
        if v > score:
            score, best, quality = v, c, q
    return best, quality


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assets", type=Path, help="APK를 푼 assets 디렉터리")
    ap.add_argument("-o", "--out", type=Path, default=Path("."))
    ap.add_argument("--min-quality", type=float, default=0.9)
    args = ap.parse_args()

    names = read_names(args.assets / "item_mon.dat")
    mons = []
    for i, (name, skill) in enumerate(names):
        im, q = best_sprite(args.assets, i)
        if im is None or q < args.min_quality:
            continue
        mons.append(dict(name=name, skill=skill.split('/')[0],
                         desc=skill.split('/')[-1], type=type_of(name), im=im))
    print("몬스터 %d/%d 마리 사용" % (len(mons), len(names)))

    cols = 12
    rows = (len(mons) + cols - 1) // cols
    atlas = Image.new('RGBA', (cols * CELL, rows * CELL), (0, 0, 0, 0))
    table = []
    for k, m in enumerate(mons):
        im = m['im']
        # 셀 안에서 가로 가운데, 세로 바닥 정렬 — 전투 화면에서 발이 맞는다
        x = (k % cols) * CELL + (CELL - im.width) // 2
        y = (k // cols) * CELL + (CELL - im.height)
        atlas.alpha_composite(im, (x, y))

        h = int(hashlib.md5(m['name'].encode()).hexdigest()[:8], 16)
        rank = k / max(1, len(mons) - 1)              # 도감 순번 = 대략의 강함
        power = 21 + rank * 30
        area = (im.width * im.height) / 1600.0
        mh, ma, md, ms = TYPE_MOD[m['type']]
        jit = lambda s: 0.88 + ((h >> (s * 5)) & 31) / 31 * 0.24
        table.append([
            m['name'], m['type'], m['skill'], m['desc'], x, y, im.width, im.height,
            round(power * 1.55 * mh * (0.8 + area * 0.4) * jit(0)),
            round(power * 0.52 * ma * jit(1)),
            round(power * 0.48 * md * (0.85 + area * 0.3) * jit(2)),
            round(power * 0.50 * ms * jit(3)),
        ])

    args.out.mkdir(parents=True, exist_ok=True)
    png = args.out / "monsters.png"
    atlas.quantize(colors=255, method=Image.FASTOCTREE).save(png, optimize=True)
    b64 = base64.b64encode(png.read_bytes()).decode()
    js = ('const MON_ATLAS_SRC = "data:image/png;base64,%s";\n' % b64 +
          "/* [이름, 속성, 고유기술, 기술설명, 아틀라스x, y, w, h, HP, 공격, 방어, 속도] */\n"
          "const MON = " + json.dumps(table, ensure_ascii=False, separators=(',', ':')) + ";\n")
    (args.out / "mondata.js").write_text(js, encoding='utf-8')
    print("%s (%d bytes), mondata.js (%d bytes)" % (png, png.stat().st_size, len(js)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
