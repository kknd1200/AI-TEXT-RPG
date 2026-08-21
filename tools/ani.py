"""배틀몬스터3 .ani 디코더.

  0..3  "ANI\0"
  4     u8  버전
  5     u8  엔트리 수 N
  6..   u32×N  엔트리 오프셋

엔트리 0 = 프레임 목록: u8 M, u32×M 프레임 오프셋
프레임:  u16 ?, u8 레코드 수 K, 그 뒤 10바이트 레코드 × K
레코드:  [0] ?  [1..2] s16 x  [3] ?  [4..5] s16 y
         [6] 그리기 플래그(0이면 메타 레코드)  [7] .fbm 파트 번호  [8] ?  [9] ?
파트는 자기 피벗(w/2, h/2)을 기준으로 (x, y)에 놓인다.
"""
import struct

def frames(path):
    d = open(path, 'rb').read()
    if d[:4] != b'ANI\x00':
        return []
    cnt = d[5]
    offs = [struct.unpack_from('<I', d, 6 + 4 * i)[0] for i in range(cnt)]
    o = offs[0]
    n = d[o]
    subs = [struct.unpack_from('<I', d, o + 1 + 4 * i)[0] for i in range(n)]
    subs.append(offs[1] if cnt > 1 else len(d))
    out = []
    for i in range(n):
        b = d[subs[i]:subs[i + 1]]
        if len(b) < 3:
            out.append([]); continue
        recs = []
        for j in range(b[2]):
            r = b[3 + j * 10 : 13 + j * 10]
            if len(r) < 10:
                break
            if r[6] == 0:            # 메타 레코드는 그리지 않는다
                continue
            recs.append((r[7],
                         struct.unpack_from('<h', r, 1)[0],
                         struct.unpack_from('<h', r, 4)[0]))
        out.append(recs)
    return out
