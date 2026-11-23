"""sims_light.py — 光線の反射（1 本 → 2 本 → 4 本 … と倍々に増える）

鏡でできた器の中心から光のパルスを放つ。パルスは壁で反射を繰り返し、本数が増えるほど
軌跡が重なって光の模様（集光模様）になる。

描き方: 光は重なるほど明るくなるので、線を上書きする通常の描画ではなく、半分の解像度の
明るさバッファに全パルスの位置を足し込んでから色に変換している。経路は最初に全部計算しておく。
"""

import math

import numpy as np
import pygame

from engine import CX, CY, H, W, hsv, penta

HW, HH = W // 2, H // 2          # 明るさバッファの大きさ（半分の解像度）


def _shape(n, p, rot, R):
    """辺がふくらんだ正 n 角形。極座標の半径 r(θ) を返す関数。p=1 でまっすぐな多角形、0 に近いほど円。"""
    half = math.pi / n

    def r(theta):
        phi = np.mod(theta - rot, 2 * half)
        return R * (math.cos(half) / np.cos(phi - half)) ** p
    return r


def _trace(r_fn, n_rays, angle0, total_len, K=1440):
    """中心から等角度で出た n_rays 本の光線を、道のりが total_len を超えるまで反射させる。
    戻り値: 各光線の頂点列 [本数, 頂点数, 2] と、頂点までの道のり [本数, 頂点数]。"""
    th = np.linspace(0, math.tau, K, endpoint=False)
    rr = r_fn(th)
    A = np.column_stack([rr * np.cos(th), rr * np.sin(th)])
    E = np.roll(A, -1, axis=0) - A
    ang = angle0 + np.arange(n_rays) / n_rays * math.tau
    O = np.zeros((n_rays, 2))
    D = np.column_stack([np.cos(ang), np.sin(ang)])
    verts = [O.copy()]
    dist = [np.zeros(n_rays)]
    travelled = np.zeros(n_rays)
    # 角に入り込んだ光線は、ごく短い反射を延々と繰り返して計算が終わらなくなる。
    # 反射の回数に上限を設け、1px 未満の反射が出た光線は中心へ向け直して角から出す。
    for _bounce in range(90):
        if travelled.min() >= total_len:
            break
        T = np.full(n_rays, np.inf)
        for s in range(0, n_rays, 256):                         # メモリを抑えるため 256 本ずつ
            o, d = O[s:s + 256], D[s:s + 256]
            ao = A[None, :, :] - o[:, None, :]
            denom = d[:, None, 0] * E[None, :, 1] - d[:, None, 1] * E[None, :, 0]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (ao[..., 0] * E[None, :, 1] - ao[..., 1] * E[None, :, 0]) / denom
                u = (ao[..., 0] * d[:, None, 1] - ao[..., 1] * d[:, None, 0]) / denom
            t[~((t > 1e-3) & (u >= 0) & (u <= 1) & np.isfinite(t))] = np.inf
            T[s:s + 256] = t.min(axis=1)
        T[~np.isfinite(T)] = 1.0
        P = O + D * T[:, None]
        # 当たった点での壁の向き（式から求めるので、折れ線近似の角ばりが反射に出ない）
        theta = np.arctan2(P[:, 1], P[:, 0])
        h = 1e-4
        dr = (r_fn(theta + h) - r_fn(theta - h)) / (2 * h)
        rv = r_fn(theta)
        tx = dr * np.cos(theta) - rv * np.sin(theta)
        ty = dr * np.sin(theta) + rv * np.cos(theta)
        tl = np.hypot(tx, ty)
        nx, ny = -ty / tl, tx / tl
        dn = D[:, 0] * nx + D[:, 1] * ny
        D = D - 2 * dn[:, None] * np.column_stack([nx, ny])
        D /= np.hypot(D[:, 0], D[:, 1])[:, None]
        stuck = T < 1.0
        if stuck.any():
            to_c = -P[stuck]
            D[stuck] = to_c / np.hypot(to_c[:, 0], to_c[:, 1])[:, None]
        travelled = travelled + T
        O = P * (1 - 1e-6)                                      # ごくわずかに内側へ（同じ辺に当たり直さない）
        verts.append(P.copy())
        dist.append(travelled.copy())
    return np.stack(verts, axis=1), np.stack(dist, axis=1)


def run_rays(v, rng):
    rounds = 12                        # 1, 2, 4, …, 2048 本
    gap = 2.45                         # 次の本数に増えるまでの秒数
    t0 = 0.5
    speed = 1450.0                     # 光の速さ（px/秒）
    tail = 1500.0                      # 光の尾の長さ（px）
    tail_early = 3400.0                # 本数が少ない回は尾を長くして、通った道筋が見えるようにする
    life = 4.3                         # 1 回分が光っている秒数（最後の回だけ長い）
    last_life = 6.2
    total = t0 + gap * (rounds - 1) + last_life + 0.4
    n_max = 2 ** (rounds - 1)
    if v.dry:
        while v.t < total:
            v.end()
        return {"result": f"1 -> {n_max} rays"}

    sides = rng.choice([3, 4, 5, 6, 6, 7])
    bulge = rng.uniform(0.45, 0.7)
    rot = rng.uniform(0, math.tau)
    R = 500.0
    r_fn = _shape(sides, bulge, rot, R)
    hue0 = rng.random()
    hue_span = rng.uniform(0.35, 0.5) * rng.choice([-1, 1])
    angle0 = rng.uniform(0, math.tau)

    ds = 4.0
    path_len = speed * last_life + tail_early
    verts, dist = _trace(r_fn, n_max, angle0, path_len)
    S = int(path_len / ds)
    grid = np.arange(S) * ds
    # 経路を ds ごとの点列にしておく（半分の解像度のバッファ上の画素番号で持つ）
    pix = np.empty((n_max, S), dtype=np.int32)
    for i in range(n_max):
        x = (np.interp(grid, dist[i], verts[i, :, 0]) + CX) * 0.5
        y = (np.interp(grid, dist[i], verts[i, :, 1]) + CY) * 0.5
        xi = np.clip(x.astype(np.int32), 0, HW - 1)
        yi = np.clip(y.astype(np.int32), 0, HH - 1)
        pix[i] = yi * HW + xi
    # 彩度を少し落としておくと、光が重なった所が白く飛んで「強い光」に見える
    ray_rgb = np.array([hsv(hue0 + hue_span * i / n_max, 0.78, 1.0) for i in range(n_max)], dtype=np.float32) / 255.0
    M = int(tail / ds)
    M_early = int(tail_early / ds)
    fall = np.exp(-3.0 * np.arange(M) / M).astype(np.float32)      # 尾は後ろほど暗い
    fall_early = np.exp(-2.2 * np.arange(M_early) / M_early).astype(np.float32)

    th = np.linspace(0, math.tau, 361)
    outline = [(CX + r_fn(a) * math.cos(a), CY + r_fn(a) * math.sin(a)) for a in th]
    wall_col = hsv(hue0 + hue_span * 0.6, 0.35, 1.0)

    # 音: 回が始まるたびに 1 音ずつ上がる。本数が少ないうちは、壁に当たる瞬間にも鳴らす
    for i in range(rounds):
        ti = t0 + gap * i
        v.audio.note(ti, penta(i, 48), 0.75, "piano")
        v.audio.note(ti, penta(i, 60), 0.4, "pluck")
        n = 2 ** i
        if n <= 8:
            step = n_max // n
            for k in range(n):
                for dv in dist[k * step, 1:10]:
                    if dv / speed < gap + 1.0:
                        v.audio.note(ti + dv / speed, penta(i + k % 3, 72), 0.22, "pluck", channel=f"h{i}", min_gap=0.05)
    v.audio.note(total - 0.9, 36, 0.9, "piano")
    v.audio.note(total - 0.9, 60, 0.6, "piano")

    buf_surf = pygame.Surface((HW, HH))
    light = pygame.Surface((W, H))
    every = max(1, v.fps // 30)        # 光の計算は重いので毎秒 30 回まで（60fps では 1 コマおき）
    shown = 1
    while v.t < total:
        t = v.t
        compute = v.frames % every == 0
        acc = np.zeros((3, HW * HH), dtype=np.float64) if compute else None
        for i in range(rounds):
            if not compute:
                break
            ti = t0 + gap * i
            age = t - ti
            dur = last_life if i == rounds - 1 else life
            if age < 0 or age > dur:
                continue
            n = 2 ** i
            shown = max(shown, n)
            step = n_max // n
            head = min(int(age * speed / ds), S)
            m, fl = (M_early, fall_early) if n <= 8 else (M, fall)
            lo = max(0, head - m)
            if head <= lo:
                continue
            fade = min(1.0, (dur - age) / 1.1)                     # 終わりぎわは暗くして消す
            gain = 10.0 / n ** 0.5 * fade
            idx = pix[::step, lo:head]                              # [n, 点数]
            w = fl[:head - lo][::-1] * gain                         # 先頭（head 側）が明るい
            flat = idx.ravel()
            cols = ray_rgb[::step]
            for c in range(3):
                acc[c] += np.bincount(flat, weights=np.multiply.outer(cols[:, c], w).ravel(), minlength=HW * HH)
        if compute:
            a = acc.reshape(3, HH, HW)
            a = 0.5 * a + 0.25 * (np.roll(a, 1, axis=2) + np.roll(a, -1, axis=2))     # 1 画素ぶんにじませて線を太く
            a = 0.5 * a + 0.25 * (np.roll(a, 1, axis=1) + np.roll(a, -1, axis=1))
            img = (255.0 * (1.0 - np.exp(-a))).astype(np.uint8)
            pygame.surfarray.blit_array(buf_surf, img.transpose(2, 1, 0))
            pygame.transform.smoothscale(buf_surf, (W, H), light)
        v.begin(bg=(0, 0, 0))
        v.surf.blit(light, (0, 0))
        pygame.draw.aalines(v.surf, wall_col, True, outline)
        pygame.draw.lines(v.surf, wall_col, True, outline, 3)
        for i in range(rounds):                                     # 放つ瞬間の輪
            age = t - (t0 + gap * i)
            if 0 <= age < 0.45:
                k = age / 0.45
                c = tuple(int(x * (1 - k)) for x in hsv(hue0 + hue_span * 0.2, 0.5, 1.0))
                v.circle(c, (CX, CY), 20 + 150 * k, width=4)
        end_k = (t - (total - 0.9)) / 0.9                          # 最後は中心が白く光って終わる
        if end_k > 0:
            v.circle((255, 255, 255), (CX, CY), 12 + 70 * end_k)
        v.text("Light rays double every round", 78, (CX, 235))
        v.text(f"{shown}", 140, (CX, CY + 640), color=hsv(hue0 + hue_span * 0.3, 0.45, 1.0))
        v.text("rays", 56, (CX, CY + 730), color=(200, 200, 210), outline=3)
        v.end(glow=0.55)
    return {"result": f"1 -> {n_max} rays in a {sides}-sided mirror"}
