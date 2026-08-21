"""합성 결과의 품질 점수.

떨어져 나온 조각이 많거나, 넓은 단색 사각형(배경 파트)이 섞이면 감점한다.
"""
from collections import deque

def score(im):
    w, h = im.size
    if w < 14 or h < 14 or w > 90 or h > 90:
        return 0.0
    px = im.load()
    mask = [[px[x, y][3] > 32 for x in range(w)] for y in range(h)]
    total = sum(sum(r) for r in mask)
    if total < 120:
        return 0.0
    # 가장 큰 연결 성분 비율
    seen = [[False] * w for _ in range(h)]
    best = 0
    for sy in range(h):
        for sx in range(w):
            if not mask[sy][sx] or seen[sy][sx]:
                continue
            q = deque([(sx, sy)]); seen[sy][sx] = True; n = 0
            while q:
                x, y = q.popleft(); n += 1
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True; q.append((nx, ny))
            best = max(best, n)
    cohesion = best / total
    # 단색 사각형 검출: 같은 색이 12×12 이상 꽉 찬 블록
    flat = 0
    step = 6
    for y in range(0, h - 11, step):
        for x in range(0, w - 11, step):
            c = px[x, y]
            if c[3] < 32:
                continue
            if all(px[x+i, y+j] == c for j in range(12) for i in range(12)):
                flat += 1
    fill = total / (w * h)
    s = cohesion
    if fill < 0.16 or fill > 0.93:
        s *= 0.55
    s *= max(0.15, 1 - flat * 0.35)
    ar = max(w, h) / min(w, h)
    if ar > 2.4:
        s *= 0.5
    return s
