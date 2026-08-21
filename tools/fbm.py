"""배틀몬스터3 .fbm 디코더.

포맷 (리틀 엔디안):
  0      u8   버전
  1      u8   프레임 수 N
  2      u32×N  각 프레임의 파일 오프셋

  프레임 헤더 9바이트:
   +0 u8  피벗 X (w/2)
   +1 u8  피벗 Y (h/2)
   +2 u8  플래그
   +3 u16 너비
   +5 u16 높이
   +7 u8  1이면 팔레트가 뒤따름, 0이면 이전 프레임 팔레트를 그대로 씀
   +8 u8  팔레트 개수 - 1 (팔레트가 있을 때만 유효)
  팔레트: RGB0 4바이트 × 개수, #ff00ff는 투명색
  픽셀:   8비트 인덱스, 행 스트라이드는 4바이트 정렬, 행 순서는 아래에서 위로(BMP식)
"""
import struct
from PIL import Image

MAGENTA = (255, 0, 255)

def load(path):
    d = open(path, 'rb').read()
    n = d[1]
    offs = [struct.unpack_from('<I', d, 2 + 4 * i)[0] for i in range(n)]
    pal, out = None, []
    for o in offs:
        if o + 9 > len(d):
            out.append(None); continue
        px, py = d[o], d[o+1]
        w, h = struct.unpack_from('<HH', d, o + 3)
        p = o + 9
        if d[o+7]:
            cnt = d[o+8] + 1
            pal = [tuple(d[p+4*k : p+4*k+3]) for k in range(cnt)]
            p += 4 * cnt
        if not w or not h or pal is None:
            out.append(None); continue
        stride = (w + 3) & ~3
        im = Image.new('RGBA', (w, h))
        rows = []
        for y in range(h):
            base = p + y * stride
            for x in range(w):
                b = d[base + x] if base + x < len(d) else 0
                c = pal[b] if b < len(pal) else MAGENTA
                rows.append((0,0,0,0) if c == MAGENTA else (*c, 255))
        im.putdata(rows)
        im = im.transpose(Image.FLIP_TOP_BOTTOM)   # 아래에서 위로 저장됨
        im.info['pivot'] = (px, py)
        out.append(im)
    return out
