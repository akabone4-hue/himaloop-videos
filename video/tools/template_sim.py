#!/usr/bin/env python3
"""template_sim.py — 新しい型を作るときの骨組み（そのまま動く見本）

  python video/tools/template_sim.py                 絵なしで 8 回まわして、長さと勝者を出す
  python video/tools/template_sim.py --preview OUT   OUT/template_1.mp4 を低画質で書き出す

使い方: この run_template を sims_○○.py へ写して中身を書き換え、registry.py の SIMS と COPY に足す。
決まり（video/QUALITY.md）のうち、骨組みの側で守れるものは下の【】の所に入れてある。

見本の中身: 大きさの違う 3 個のボールが円の中を跳ね回り、壁に当たるたびに小さくなる。最後まで残った 1 個が勝ち。
見本の数字は、わざと釣り合わせていない（いつも BIG が勝ち、12 秒で終わる）。
これを tools/balance.py と tools/review.py にかけると「かたより」と「短すぎ」が出る。そこを直すところまでが手順。
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np                                             # noqa: E402

from engine import CX, CY, Particles, Video, mix, penta        # noqa: E402

# 【条件を変える】全員同じ条件にしない。数字は丸く（有効数字 3 桁まで）。
# 【試算でそろえる】ここの数字を変えたら tools/balance.py で勝ち方の内訳を見直す。
KINDS = [("BIG", 60.0, 12, (255, 110, 90)), ("MEDIUM", 40.0, 8, (90, 170, 255)), ("SMALL", 25.0, 5, (120, 230, 140))]


def run_template(v, rng):
    R = 440.0
    C = np.array([CX, CY], dtype=float)
    n = len(KINDS)
    P = np.array([C + np.array([math.cos(a), math.sin(a)]) * 200 for a in (rng.uniform(0, math.tau) + k * math.tau / n
                                                                           for k in range(n))])
    ang = [rng.uniform(0, math.tau) for _ in range(n)]
    V = np.array([[math.cos(a), math.sin(a)] for a in ang]) * 560.0          # 【遅くしない】
    hp = [k[2] for k in KINDS]
    rad = [k[1] for k in KINDS]
    out_order = []
    parts = Particles()
    flashes = []                                                # 【理由を見せる】当たった場所の輪 [x, y, 色, 経過]
    done_at = None
    while True:
        t = v.t
        # ---- 物理。v.sub 回に分けて進める（1 コマぶん。コマ数が変わっても刻みは同じ = 試し書き出しと本番で結果がずれにくい）
        for _ in range(v.sub):
            if done_at is not None:
                break
            for i in range(n):
                if hp[i] <= 0:
                    continue
                P[i] += V[i] * v.dt
                D = P[i] - C
                d = float(np.hypot(*D))
                if d + rad[i] > R:                              # 壁に当たった
                    N = D / d
                    V[i] -= 2 * float(V[i] @ N) * N
                    P[i] = C + N * (R - rad[i])
                    hp[i] -= 1
                    rad[i] = KINDS[i][1] * (0.35 + 0.65 * hp[i] / KINDS[i][2])
                    flashes.append([float(P[i][0] + N[0] * rad[i]), float(P[i][1] + N[1] * rad[i]), KINDS[i][3], 0.0])
                    # 【音】当たった瞬間だけ鳴らす。音階（penta）に沿わせ、同じチャンネルの連打は間引く
                    v.audio.note(t, penta(4 + 2 * i + hp[i] % 3, 57), 0.4, "marimba", channel=f"b{i}", min_gap=0.05)
                    if hp[i] <= 0:                              # 【消えるときは理由としるしを見せる】
                        out_order.append(i)
                        parts.burst(rng, tuple(P[i]), KINDS[i][3], n=30, speed=500, life=0.7, gravity=False)
                        v.audio.play(t, 200, 0.6, "pop")
            alive = [i for i in range(n) if hp[i] > 0]
            if len(alive) <= 1 and done_at is None:
                done_at = t
                for k, m in enumerate((60, 64, 67, 72, 76)):    # 【最後は弾けて終わる】決着の和音
                    v.audio.note(t + 0.07 * k, m, 0.8, "piano")
        parts.step(1 / v.fps)
        for f in flashes:
            f[3] += 1 / v.fps
        flashes = [f for f in flashes if f[3] < 0.3]

        # ---- 絵。v.dry のときは描かない（試算を速くするため）
        if not v.dry:
            v.begin(bg=(8, 9, 16))                              # 【軌跡を残さない】fade を使わず、毎コマ塗り直す
            v.circle((245, 245, 245), C, R + 4, width=5)
            for x, y, col, age in flashes:
                v.circle(mix(col, (8, 9, 16), age / 0.3), (x, y), 12 + 120 * age, width=3)
            parts.draw(v)
            for i in range(n):
                if hp[i] > 0:
                    v.circle((255, 255, 255), P[i], rad[i] + 3)
                    v.circle(KINDS[i][3], P[i], rad[i])
                    v.text(str(hp[i]), 40, P[i], outline=3)     # 【結果を先に見せない】残り回数は出してよい
            v.text("Every wall hit = smaller", 84, (CX, 160))   # 【文字は英語・端から離す】題名は y=150 前後
            if done_at is not None and alive:
                w = alive[0]
                v.text(f"{KINDS[w][0]} WINS", 150, (CX, CY + 640), color=KINDS[w][3], outline=7)
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.5:
            break
        if v.t > 80:                                            # 決着がつかないときの打ち切り（長さの範囲から外れて選ばれなくなる）
            break
    alive = [i for i in range(n) if hp[i] > 0]
    name = KINDS[alive[0]][0] if alive else "nobody"
    # 【戻り値】result は投稿文と記録に出る。winner は tools/balance.py が勝ち方の内訳に使う
    return {"result": f"{name} wins", "winner": name}


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--preview":
        os.makedirs(sys.argv[2], exist_ok=True)
        vid = Video(os.path.join(sys.argv[2], "template_1.mp4"), fps=30, preview=True)
        print(run_template(vid, random.Random(1)), round(vid.finish(), 1), "秒")
    else:
        wins = {}
        for seed in range(1, 9):
            vid = Video("", dry=True)
            meta = run_template(vid, random.Random(seed))
            wins[meta["winner"]] = wins.get(meta["winner"], 0) + 1
            print(seed, round(vid.finish(), 1), meta["result"])
        print(wins)
