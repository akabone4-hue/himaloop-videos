"""sims_swarm.py — 群れの型

  rps  グー・チョキ・パーの駒が、勝てる相手を追い、負ける相手から逃げる。触れた相手を自分の仲間に変える。
       1 種類だけになったら終わり
"""

import math

import numpy as np
import pygame

from engine import CX, CY, mix

KINDS = [("ROCK", (120, 170, 255)), ("PAPER", (245, 245, 245)), ("SCISSORS", (255, 90, 110))]
# 種類 k は (k + 2) % 3 に勝つ: グー(0) はチョキ(2) に、パー(1) はグー(0) に、チョキ(2) はパー(1) に勝つ


def _piece(v, kind, pos, r):
    x, y = pos
    col = KINDS[kind][1]
    if kind == 0:                               # グー: 丸
        v.circle(col, (x, y), r)
    elif kind == 1:                             # パー: 四角
        pygame.draw.rect(v.surf, col, (int(x - r * 0.9), int(y - r * 0.9), int(r * 1.8), int(r * 1.8)), border_radius=4)
    else:                                       # チョキ: ばつ印
        d = r * 0.85
        pygame.draw.line(v.surf, col, (x - d, y - d), (x + d, y + d), 7)
        pygame.draw.line(v.surf, col, (x - d, y + d), (x + d, y - d), 7)


# rps2: 記号の代わりに、炎・水・葉。種類 k が (k + 2) % 3 に勝つのは同じ:
# 炎(0) は葉(2) を燃やし、水(1) は炎(0) を消し、葉(2) は水(1) を吸う
ELEMENTS = [("FIRE", (255, 120, 40)), ("WATER", (70, 160, 255)), ("LEAF", (90, 220, 100))]


def _element(v, kind, pos, r):
    """炎・水・葉の小さな絵（半径 r の円に収まる大きさ）。"""
    x, y = pos
    col = ELEMENTS[kind][1]
    if kind == 0:                               # 炎: 上がとがった形に、黄色い芯
        pts = [(x, y - r * 1.25), (x + r * 0.55, y - r * 0.25), (x + r * 0.85, y + r * 0.35), (x + r * 0.5, y + r * 0.95),
               (x - r * 0.5, y + r * 0.95), (x - r * 0.85, y + r * 0.35), (x - r * 0.4, y - r * 0.15), (x - r * 0.35, y - r * 0.75)]
        pygame.draw.polygon(v.surf, col, pts)
        v.circle((255, 225, 110), (x, y + r * 0.4), r * 0.42)
    elif kind == 1:                             # 水: しずく（丸の上に三角）と、白い光
        v.circle(col, (x, y + r * 0.25), r * 0.8)
        pygame.draw.polygon(v.surf, col, [(x, y - r * 1.2), (x + r * 0.68, y - r * 0.12), (x - r * 0.68, y - r * 0.12)])
        v.circle((225, 240, 255), (x - r * 0.28, y + r * 0.1), r * 0.2)
    else:                                       # 葉: 斜めの木の葉の形に、まん中の筋
        pts = [(x - r * 0.95, y + r * 0.95), (x - r * 0.75, y - r * 0.15), (x + r * 0.05, y - r * 0.85), (x + r * 1.0, y - r * 1.0),
               (x + r * 0.85, y - r * 0.05), (x + r * 0.15, y + r * 0.75)]
        pygame.draw.polygon(v.surf, col, pts)
        pygame.draw.line(v.surf, (30, 110, 50), (x - r * 0.8, y + r * 0.8), (x + r * 0.7, y - r * 0.7), 3)


def run_rps2(v, rng):
    """rps の別バージョン: 炎・水・葉の 3 すくみ。動きは rps と同じ。"""
    return run_rps(v, rng, kinds=ELEMENTS, piece=_element, title="Fire  Water  Leaf")


def run_rps(v, rng, kinds=None, piece=None, title="Rock  Paper  Scissors"):
    kinds = kinds or KINDS
    piece = piece or _piece
    side = 940.0
    ox, oy = CX - side / 2, CY - side / 2 + 30
    per = 34
    n = per * 3
    r = 15.0
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    kind = np.repeat(np.arange(3), per)
    # 最初は種類ごとに 3 か所へ固めて置く（どこがどこを攻めるかが見える）
    P = np.zeros((n, 2))
    a0 = rng.uniform(0, math.tau)
    for k in range(3):
        c = (CX + math.cos(a0 + k * math.tau / 3) * 270, CY + 30 + math.sin(a0 + k * math.tau / 3) * 270)
        P[kind == k] = np.array(c) + nrng.normal(0, 90, (per, 2))
    P[:, 0] = np.clip(P[:, 0], ox + r, ox + side - r)
    P[:, 1] = np.clip(P[:, 1], oy + r, oy + side - r)
    V = nrng.normal(0, 1, (n, 2))
    speed = 195.0
    done_at = None
    winner = None
    flashes = []                                # 変わった瞬間の光 [x, y, 種類, 経過]
    limit = 42.0
    while True:
        t = v.t
        for _ in range(max(1, v.sub // 2)):
            if done_at is not None:
                break
            dt = 2 * v.dt
            D = P[None, :, :] - P[:, None, :]                      # i から j への向き
            dist = np.hypot(D[..., 0], D[..., 1]) + np.eye(n) * 1e9
            prey = (kind[None, :] == (kind[:, None] + 2) % 3)       # j は i が勝てる相手
            hunter = (kind[None, :] == (kind[:, None] + 1) % 3)     # j は i が負ける相手
            want = np.zeros((n, 2))
            d_prey = np.where(prey, dist, 1e9)
            j = d_prey.argmin(axis=1)
            has = d_prey[np.arange(n), j] < 1e8
            want[has] += (D[np.arange(n), j] / dist[np.arange(n), j][:, None])[has]
            d_hunt = np.where(hunter, dist, 1e9)
            j2 = d_hunt.argmin(axis=1)
            near = d_hunt[np.arange(n), j2] < 170
            want[near] -= 1.25 * (D[np.arange(n), j2] / dist[np.arange(n), j2][:, None])[near]
            close = (dist < 2.3 * r) & (kind[None, :] == kind[:, None])      # 仲間どうしは重ならない
            push = (D / dist[..., None]) * close[..., None]
            want -= 0.8 * push.sum(axis=1)
            want += nrng.normal(0, 0.25, (n, 2))
            V = V * 0.86 + want * 0.14
            sp_ = np.hypot(V[:, 0], V[:, 1]) + 1e-9
            V = V / sp_[:, None]
            # 勝てる相手がいなくなった種類は、もう増えられない。逃げ足を落として、決着を長引かせない
            alive_n = np.array([(kind == k).sum() for k in range(3)])
            tired = np.where(alive_n[(kind + 2) % 3] == 0, 0.5, 1.0)
            P += V * (speed * (1 + 0.5 * min(1.0, t / limit)) * tired)[:, None] * dt
            for ax, lo, hi in ((0, ox + r, ox + side - r), (1, oy + r, oy + side - r)):
                out = (P[:, ax] < lo) | (P[:, ax] > hi)
                V[out, ax] *= -1
                P[:, ax] = np.clip(P[:, ax], lo, hi)
            # 触れた相手を仲間に変える
            touch = (dist < 2 * r) & prey
            ii, jj = np.nonzero(touch)
            changed = set()
            for i_, j_ in zip(ii, jj):
                if j_ in changed or kind[j_] != (kind[i_] + 2) % 3:
                    continue
                kind[j_] = kind[i_]
                changed.add(int(j_))
                flashes.append([float(P[j_, 0]), float(P[j_, 1]), int(kind[i_]), 0.0])
            if changed:
                k_ = int(kind[next(iter(changed))])
                v.audio.note(t, (60, 64, 67)[k_] + (12 if len(changed) > 1 else 0), 0.28, "marimba", channel=f"k{k_}", min_gap=0.07)
            counts = [int((kind == k).sum()) for k in range(3)]
            if max(counts) == n or t >= limit:
                done_at = t
                winner = int(np.argmax(counts))
                for i_, mm in enumerate((60, 64, 67, 72, 76)):
                    v.audio.note(t + 0.07 * i_, mm, 0.8, "piano")
        for f in flashes:
            f[3] += 1 / v.fps
        flashes = [f for f in flashes if f[3] < 0.3][-60:]
        counts = [int((kind == k).sum()) for k in range(3)]

        if not v.dry:
            v.begin(bg=(6, 8, 14))
            pygame.draw.rect(v.surf, (12, 16, 28), (int(ox - 8), int(oy - 8), int(side + 16), int(side + 16)), border_radius=18)
            pygame.draw.rect(v.surf, (235, 235, 240), (int(ox - 8), int(oy - 8), int(side + 16), int(side + 16)), 4, border_radius=18)
            for x, y, k, age in flashes:
                v.circle(mix(kinds[k][1], (6, 8, 14), age / 0.3), (x, y), r + 60 * age, width=3)
            for i in range(n):
                piece(v, int(kind[i]), P[i], r)
            v.text(title, 90, (CX, 150))
            # ルールの図: 丸は ばつ に勝ち、ばつ は 四角 に勝ち、四角 は 丸 に勝つ
            y0 = 236
            for i, (a_, b_) in enumerate(((0, 2), (2, 1), (1, 0))):
                x0 = CX - 330 + i * 330
                piece(v, a_, (x0 - 62, y0), 17)
                v.text("beats", 38, (x0, y0), color=(190, 195, 210), outline=2)
                piece(v, b_, (x0 + 62, y0), 17)
            # 勢力バー
            x = ox
            for k in range(3):
                wdt = side * counts[k] / n
                pygame.draw.rect(v.surf, kinds[k][1], (int(x), 292, int(wdt) + 1, 40))
                if wdt > 90:
                    v.text(str(counts[k]), 38, (x + wdt / 2, 313), color=(10, 10, 16), outline=0)
                x += wdt
            pygame.draw.rect(v.surf, (235, 235, 240), (int(ox - 3), 289, int(side + 6), 46), 3)
            if done_at is not None:
                v.text(f"{kinds[winner][0]} WINS", 140, (CX, oy + side + 110), color=kinds[winner][1], outline=7)
        v.end(glow=0.22)
        if done_at is not None and v.t - done_at > 2.4:
            break
        if v.t > 80:
            break
    return {"result": f"{kinds[winner][0]} wins ({counts[winner]} of {n})", "winner": kinds[winner][0]}
