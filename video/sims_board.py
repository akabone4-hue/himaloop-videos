"""sims_board.py — 盤上ゲーム: 王冠を目指して、壁で邪魔し合う

4 色のボールが盤の四辺から中央の王冠を目指す。自分の番では「1 マス進む」か「壁を 1 枚置く」。
壁は相手の最短経路を伸ばすために置く（どのボールにも、王冠までの道は必ず 1 本は残す）。
あと 1 歩のところで壁を置かれる展開が見どころ。

先に全部の手を決めてから、その記録を再生する形で描く。
"""

import math
from collections import deque

import pygame

from engine import CX, CY, Particles, mix

N = 13
CELL = 72
K = CELL / 84.0       # 盤を細かくしたぶん、駒や王冠を縮める倍率
OX, OY = CX - N * CELL // 2, CY - N * CELL // 2
GOAL = (N // 2, N // 2)
PLAYERS = [("RED", (255, 77, 110)), ("YELLOW", (255, 214, 60)), ("GREEN", (90, 220, 90)), ("BLUE", (70, 130, 255))]
STARTS = [(N // 2, 0), (N - 1, N // 2), (N // 2, N - 1), (0, N // 2)]
WALLS_EACH = 6        # 1 色が置ける壁の枚数
T_MOVE, T_WALL = 0.30, 0.56


def _edges(orient, x, y):
    """壁 1 枚がふさぐ 2 つの「マスとマスの境目」。"""
    if orient == "h":         # 行 y と y+1 のあいだ、列 x と x+1
        return [frozenset({(x, y), (x, y + 1)}), frozenset({(x + 1, y), (x + 1, y + 1)})]
    return [frozenset({(x, y), (x + 1, y)}), frozenset({(x, y + 1), (x + 1, y + 1)})]


def _dist_map(blocked):
    """王冠から各マスまでの歩数（壁を越えられない）。"""
    dist = {GOAL: 0}
    q = deque([GOAL])
    while q:
        c = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if not (0 <= n[0] < N and 0 <= n[1] < N) or n in dist or frozenset({c, n}) in blocked:
                continue
            dist[n] = dist[c] + 1
            q.append(n)
    return dist


def _play(rng):
    """1 局ぶんの手を決める。戻り値: (手の一覧, 勝者)。手は dict。"""
    pos = list(STARTS)
    walls_left = [WALLS_EACH] * 4
    blocked = set()
    slots = set()
    turns = []
    order = list(range(4))
    rng.shuffle(order)
    winner = None
    for step in range(400):
        p = order[step % 4]
        dist = _dist_map(blocked)
        d = [dist.get(pos[i], 999) for i in range(4)]
        rivals = [i for i in range(4) if i != p]
        target = min(rivals, key=lambda i: (d[i], rng.random()))
        threat = d[target]
        want_wall = 0.0
        if walls_left[p] > 0:
            # 相手が王冠に近いほど壁を使う。枚数に限りがあるので、遠いうちはあまり使わない
            if threat <= 1:
                want_wall = 0.97
            elif threat == 2:
                want_wall = 0.9
            elif threat == 3:
                want_wall = 0.7
            elif threat == 4:
                want_wall = 0.45
            else:
                want_wall = 0.1
        placed = None
        if rng.random() < want_wall:
            best = None
            tx, ty = pos[target]
            for orient in ("h", "v"):
                for x in range(max(0, tx - 3), min(N - 2, tx + 3) + 1):
                    for y in range(max(0, ty - 3), min(N - 2, ty + 3) + 1):
                        if (orient, x, y) in slots or (("v" if orient == "h" else "h"), x, y) in slots:
                            continue
                        es = _edges(orient, x, y)
                        if any(e in blocked for e in es):
                            continue
                        nd = _dist_map(blocked | set(es))
                        if any(pos[i] not in nd for i in range(4)):
                            continue                       # だれかの道を完全にふさぐ壁は置けない
                        gain = (nd[pos[target]] - d[target]) - 1.2 * (nd[pos[p]] - d[p]) + rng.random() * 0.3
                        if best is None or gain > best[0]:
                            best = (gain, orient, x, y, es)
            if best and best[0] >= 0.8:
                _, orient, x, y, es = best
                blocked |= set(es)
                slots.add((orient, x, y))
                walls_left[p] -= 1
                nd = _dist_map(blocked)
                placed = {"type": "wall", "p": p, "orient": orient, "x": x, "y": y, "target": target,
                          "was": d[target], "now": nd[pos[target]]}
        if placed:
            turns.append(placed)
            continue
        # 進む: 王冠に近づくマスのうち、空いているもの
        here = pos[p]
        options = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (here[0] + dx, here[1] + dy)
            if n not in dist or frozenset({here, n}) in blocked:
                continue
            if n != GOAL and n in pos:
                continue
            options.append((dist[n], rng.random(), n))
        if options:
            options.sort()
            nxt = options[0][2]
            turns.append({"type": "move", "p": p, "from": here, "to": nxt})
            pos[p] = nxt
            if nxt == GOAL:
                winner = p
                break
        else:
            turns.append({"type": "wait", "p": p})
    if winner is None:
        dist = _dist_map(blocked)
        winner = min(range(4), key=lambda i: dist.get(pos[i], 999))
    return turns, winner


def _cell_center(c):
    return OX + c[0] * CELL + CELL / 2, OY + c[1] * CELL + CELL / 2


def run_walls(v, rng):
    # 見どころ（あと 1〜2 歩で壁を置かれる場面）が多く、長さもちょうどよい対局を選ぶ
    turns, winner = None, None
    best = None
    for _ in range(40):
        tn_, w_ = _play(rng)
        denied_ = sum(1 for x in tn_ if x["type"] == "wall" and x["was"] <= 2)
        dur_ = sum(T_WALL if x["type"] == "wall" else T_MOVE for x in tn_)
        score = (denied_ >= 5, 30 <= dur_ <= 46, denied_, -abs(dur_ - 38))
        if best is None or score > best[0]:
            best = (score, tn_, w_)
        if score[0] and score[1]:
            break
    turns, winner = best[1], best[2]
    # 手に開始時刻を付ける
    t = 1.2
    for tn in turns:
        tn["t"] = t
        t += T_WALL if tn["type"] == "wall" else T_MOVE
    end_at = t
    total = end_at + 2.6
    walls_used = sum(1 for tn in turns if tn["type"] == "wall")
    denied = sum(1 for tn in turns if tn["type"] == "wall" and tn["was"] <= 2)
    result = {"result": f"{PLAYERS[winner][0]} wins after {len(turns)} turns, {walls_used} walls, {denied} close blocks"}

    # 音
    chord = [64, 67, 71, 60]
    for tn in turns:
        if tn["type"] == "move":
            v.audio.note(tn["t"], chord[tn["p"]] + 12, 0.3, "pluck")
        elif tn["type"] == "wall":
            v.audio.play(tn["t"] + 0.05, 150, 0.6, "thud")
            v.audio.play(tn["t"] + 0.05, 2300, 0.2, "click")
            if tn["was"] <= 1:
                v.audio.note(tn["t"] + 0.1, 40, 0.8, "piano")
    for i, m in enumerate((60, 64, 67, 72, 76)):
        v.audio.note(end_at + 0.07 * i, m, 0.8, "piano")
    if v.dry:
        while v.t < total:
            v.end()
        return result

    parts = Particles()
    board = pygame.Rect(OX - 26, OY - 26, N * CELL + 52, N * CELL + 52)
    burst_done = False
    while v.t < total:
        now = v.t
        pos = list(STARTS)
        walls = []
        blocked = set()
        active = None
        caption = None
        moving = None
        used = [0, 0, 0, 0]
        for tn in turns:
            if tn["t"] > now:
                break
            active = tn["p"]
            if tn["type"] == "wall":
                used[tn["p"]] += 1
            if tn["type"] == "move":
                k = min(1.0, (now - tn["t"]) / (T_MOVE * 0.75))
                if k < 1.0:
                    moving = (tn["p"], tn["from"], tn["to"], k)
                pos[tn["p"]] = tn["to"]
            elif tn["type"] == "wall":
                walls.append(tn)
                blocked |= set(_edges(tn["orient"], tn["x"], tn["y"]))
                if tn["was"] <= 2 and now - tn["t"] < 1.7:
                    caption = (f"{PLAYERS[tn['target']][0]} was {tn['was']} step{'s' if tn['was'] != 1 else ''} away...",
                               PLAYERS[tn["target"]][1])
        dist = _dist_map(blocked)

        v.begin(bg=(6, 8, 14))
        pygame.draw.rect(v.surf, (10, 14, 26), board, border_radius=22)
        pygame.draw.rect(v.surf, (60, 220, 230), board, 4, border_radius=22)
        for gx in range(N):
            for gy in range(N):
                pygame.draw.rect(v.surf, (22, 28, 44), (OX + gx * CELL + 5, OY + gy * CELL + 5, CELL - 10, CELL - 10),
                                 border_radius=10)
        # 王冠
        gx0, gy0 = OX + GOAL[0] * CELL, OY + GOAL[1] * CELL
        pygame.draw.rect(v.surf, (240, 180, 40), (gx0 + 7, gy0 + 7, CELL - 14, CELL - 14), border_radius=12)
        cx0, cy0 = gx0 + CELL / 2, gy0 + CELL / 2
        crown = [(cx0 + dx * K, cy0 + dy * K) for dx, dy in
                 ((-24, 16), (-26, -12), (-12, 0), (0, -20), (12, 0), (26, -12), (24, 16))]
        pygame.draw.polygon(v.surf, (70, 45, 5), crown)
        # 壁
        for w in walls:
            age = now - w["t"]
            grow = min(1.0, age / 0.16)
            col = mix((255, 255, 255), PLAYERS[w["p"]][1], min(1.0, age / 0.35))
            if w["orient"] == "h":
                yy = OY + (w["y"] + 1) * CELL
                xm = OX + (w["x"] + 1) * CELL
                v.line(col, (xm - CELL * grow + 8, yy), (xm + CELL * grow - 8, yy), 11)
            else:
                xx = OX + (w["x"] + 1) * CELL
                ym = OY + (w["y"] + 1) * CELL
                v.line(col, (xx, ym - CELL * grow + 8), (xx, ym + CELL * grow - 8), 11)
        # ボール
        for i in range(4):
            x, y = _cell_center(pos[i])
            if moving and moving[0] == i:
                fx, fy = _cell_center(moving[1])
                k = moving[3]
                k = k * k * (3 - 2 * k)
                x, y = fx + (x - fx) * k, fy + (y - fy) * k
            col = PLAYERS[i][1]
            if i == active and now < end_at:
                v.circle((255, 255, 255), (x, y), 37 * K, width=3)
            v.circle(mix(col, (0, 0, 0), 0.45), (x, y), 31 * K)
            v.circle(col, (x, y), 27 * K)
            v.circle(mix(col, (255, 255, 255), 0.65), (x - 9 * K, y - 9 * K), 7 * K)
        # 上の字幕
        if now >= end_at:
            v.text(f"{PLAYERS[winner][0]} WINS", 130, (CX, 230), color=PLAYERS[winner][1], outline=6)
            if not burst_done:
                burst_done = True
                gxc, gyc = _cell_center(GOAL)
                parts.burst(rng, (gxc, gyc), PLAYERS[winner][1], n=70, speed=760, life=1.2, size=9)
        elif caption:
            v.text(caption[0], 84, (CX, 215), color=caption[1], outline=5)
        else:
            v.text("First to the crown wins", 88, (CX, 215))
        if now < end_at:
            v.text(f"{WALLS_EACH} walls each - a path must always stay open", 46, (CX, 300), color=(190, 195, 210),
                   outline=3)
        # 下: 王冠までの残り歩数
        for i in range(4):
            px = CX - 330 + i * 220
            py = OY + N * CELL + 130
            v.circle(PLAYERS[i][1], (px, py - 8), 30)
            for k in range(WALLS_EACH):               # 残りの壁（使った分は暗くなる）
                wx = px - 78 + k * 27
                c = PLAYERS[i][1] if k < WALLS_EACH - used[i] else (48, 52, 66)
                pygame.draw.rect(v.surf, c, (int(wx), int(py + 44), 21, 10), border_radius=3)
        v.text("walls left", 46, (CX, OY + N * CELL + 232), color=(190, 195, 210), outline=3)
        parts.step(1 / v.fps)
        parts.draw(v)
        v.end(glow=0.3)
    return result
