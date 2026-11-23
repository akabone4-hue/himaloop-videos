"""sims_pack.py — ぎっしり詰まるボール系（ボール同士がぶつかり合う）

  fill   1 個のボールが増え続け、円がいっぱいになると弾ける
  arms   四角い箱の四隅で回るアームに当たると増える
  glass  大きなガラスが砕けていき、倍率のくぼみでボールが増える

ボール同士の衝突は物理エンジン pymunk に任せる（数百個が押し合う計算を自前で書くより速くて安定）。
物理は 1/120 秒刻み。プレビュー(30fps)でも本番(60fps)でも同じ展開になる。
"""

import math

import numpy as np
import pygame
import pygame.gfxdraw
import pymunk

from engine import ARP_PAT, ARP_PROG, CX, CY, H, W, Particles, hsv, mix, penta

GLASS_FREE = 0.40        # 砲台に 1 発が補給される間隔（秒）
GLASS_SPRAY = 0.60       # ねらいのぶれ（ラジアン）。大きいほど外れ弾が増えて、ボールが増えやすい
GLASS_WEAK = 0.22        # 弱い弾の割合。砲台に近いくぼみ（x2・x3）を使わせる
GLASS_QUEUE_MAX = 220    # 撃つのを待つボールの上限
GLASS_RATE = 0.10       # 1 秒に削れるのは全体のこの割合まで
GLASS_HP = 0.34           # ガラス 1 マスの丈夫さ
GLASS_REACH = 3          # 1 回の当たりで欠ける範囲の上限（マス数）
GLASS_SPREAD = 8.0       # 欠ける範囲が 1 マス広がるまでの秒数
GLASS_HIT = 2.6    # ガラスに勢いよく当たったときの削れ方（大きいほど早く割れる）
GEAR_PINCH = 6.0   # 歯車の型で「潰された」とみなすすき間のゆとり（ピクセル）
PINCH = 6.0        # 「挟まれた」とみなすすき間のゆとり（ピクセル）
CANDY = [(255, 107, 157), (72, 202, 228), (255, 214, 92), (167, 139, 250), (52, 211, 153), (251, 146, 60)]


def _space(gravity=1500.0):
    sp = pymunk.Space()
    sp.gravity = (0, gravity)
    sp.iterations = 14
    return sp


def _ring(sp, center, radius, n=120, thick=5.0, elasticity=0.25, friction=0.5):
    """円形の壁（短い線分をつないで作る）。あとで消せるよう線分のリストを返す。"""
    segs = []
    for i in range(n):
        a0, a1 = i / n * math.tau, (i + 1) / n * math.tau
        s = pymunk.Segment(sp.static_body,
                           (center[0] + math.cos(a0) * radius, center[1] + math.sin(a0) * radius),
                           (center[0] + math.cos(a1) * radius, center[1] + math.sin(a1) * radius), thick)
        s.elasticity, s.friction = elasticity, friction
        sp.add(s)
        segs.append(s)
    return segs


def _ball(sp, pos, r, vel=(0, 0), elasticity=0.25, friction=0.4, mass=1.0):
    b = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
    b.position = pos
    b.velocity = vel
    c = pymunk.Circle(b, r)
    c.elasticity, c.friction = elasticity, friction
    sp.add(b, c)
    return b, c


def _steps(v):
    """1 コマあたりの物理ステップ数と刻み幅（常に 1/120 秒）。"""
    return max(1, v.sub // 2), 2 * v.dt


# ============================================================ fill: 増えて円がいっぱいになる
def run_fill(v, rng):
    """固定の棒と、中心で留めた板のあいだにボールが詰まっている。ボールが増えるほど板が押されて
    扇形が広がり、ほぼ 1 周したところで円が弾ける。重力なし。"""
    R = 470.0
    br = 17.0
    C = (CX, CY)
    sp = _space(gravity=0.0)
    sp.damping = 0.75
    sp.iterations = 20
    wall = _ring(sp, C, R + 5, elasticity=0.05, friction=0.2)
    group = pymunk.ShapeFilter(group=1)
    bar = pymunk.Segment(sp.static_body, C, (CX + R, CY), 8)           # 固定の棒（右向き）
    bar.elasticity, bar.friction, bar.filter = 0.05, 0.2, group
    sp.add(bar)

    blade_len = R - 12
    blade = pymunk.Body(6, pymunk.moment_for_segment(6, (0, 0), (blade_len, 0), 9))
    blade.position = C
    blade.angle = -0.16                                                 # 棒のすぐ上から始まる
    bshape = pymunk.Segment(blade, (0, 0), (blade_len, 0), 9)
    bshape.elasticity, bshape.friction, bshape.filter = 0.05, 0.2, group
    pivot = pymunk.PivotJoint(sp.static_body, blade, C)
    limit = pymunk.RotaryLimitJoint(sp.static_body, blade, -math.tau + 0.02, -0.14)
    squeeze = pymunk.SimpleMotor(sp.static_body, blade, -1.6)           # 板を閉じる向きに押し続ける力
    squeeze.max_force = 2.5e4
    sp.add(blade, bshape, pivot, limit, squeeze)

    balls = []                      # [body, shape, 色, 次に分裂する時刻]
    b, c = _ball(sp, (CX + 250, CY - 22), br, elasticity=0.05, friction=0.2)
    balls.append([b, c, rng.choice(CANDY), 1.0])
    parts = Particles()
    n_steps, dt = _steps(v)
    boom_at = None
    period = (1.6, 2.4)             # 1 個が 2 個に分かれるまでの時間
    while True:
        for _ in range(n_steps):
            sp.step(dt)
        t = v.t
        opened = -blade.angle / math.tau          # 扇形が円に占める割合（0〜1）
        if boom_at is None:
            # 詰まり具合（扇形の面積に対するボールの面積）。詰まりすぎているあいだは増やさず、板が開くのを待つ
            density = len(balls) * br * br / max(opened * R * R, 1.0)
            born = 0
            for item in list(balls):
                if born >= 6 or density > 0.93:
                    break
                if t < item[3]:
                    continue
                body = item[0]
                item[3] = t + rng.uniform(*period)
                a = rng.uniform(0, math.tau)
                nb, nc = _ball(sp, (body.position.x + math.cos(a) * 4, body.position.y + math.sin(a) * 4), br,
                               elasticity=0.05, friction=0.2)
                balls.append([nb, nc, rng.choice(CANDY), t + rng.uniform(*period)])
                born += 1
            if born:
                v.audio.note(t, penta(int(opened * 17), 60), 0.3, "pluck", channel="s", min_gap=0.05)
            if opened > 0.955:
                boom_at = t
                for s in wall:
                    sp.remove(s)
                sp.remove(bar, bshape, pivot, limit, squeeze, blade)
                sp.gravity = (0, 1400)
                sp.damping = 1.0
                for body, _c, col, _n in balls:
                    dx, dy = body.position.x - CX, body.position.y - CY
                    d = math.hypot(dx, dy) or 1.0
                    k = rng.uniform(600, 1500)
                    body.velocity = (dx / d * k, dy / d * k - 250)
                for i in range(48):
                    a = i / 48 * math.tau
                    parts.burst(rng, (CX + math.cos(a) * R, CY + math.sin(a) * R), (255, 255, 255), n=3, speed=420, life=0.9)
                v.audio.play(t, 90, 1.0, "thud")
                for i, m in enumerate((48, 55, 60, 64, 67, 72)):
                    v.audio.note(t + 0.03 * i, m, 0.8, "piano")
        parts.step(1 / v.fps)

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            for body, _c, col, _n in balls:
                x, y = body.position.x, body.position.y
                if -40 < y < H + 40 and -40 < x < W + 40:
                    v.circle(col, (x, y), br)
                    v.circle(mix(col, (255, 255, 255), 0.55), (x - 5, y - 5), 4)
            if boom_at is None:
                v.circle((235, 235, 235), C, R + 8, width=5)
                v.line((165, 165, 180), C, (CX + R, CY), 16)
                ux, uy = math.cos(blade.angle), math.sin(blade.angle)
                tip = (CX + ux * blade_len, CY + uy * blade_len)
                v.line((110, 150, 190), C, tip, 26)
                v.line((225, 240, 255), C, tip, 14)
                gx, gy = CX + ux * 44, CY + uy * 44
                v.line((230, 160, 40), (gx - uy * 50, gy + ux * 50), (gx + uy * 50, gy - ux * 50), 16)
                v.circle((230, 160, 40), C, 26)
                v.circle((120, 70, 20), C, 11)
            parts.draw(v)
            v.text("1 ball fills the whole circle", 84, (CX, 240))
            v.text(f"{len(balls)}", 150, (CX, CY + R + 170))
        v.end(glow=0.22)
        if boom_at is not None and v.t - boom_at > 2.6:
            break
        if v.t > 80:
            break
    return {"result": f"1 -> {len(balls)} balls"}


# ============================================================ arms: 四隅のアームに当たると増える
def run_arms(v, rng):
    """四角い箱の四隅で C 字のアームが回っている。アームと壁のあいだに挟まれて潰されたボールは
    2 個に増える。重力なし。増えた時刻で色が変わるので、世代ごとに色の波ができる。"""
    half = 390.0
    br = 10.0
    cap = 320
    C = (CX, CY)
    sp = _space(gravity=0.0)
    sp.iterations = 12
    corners = [(CX - half, CY - half), (CX + half, CY - half), (CX + half, CY + half), (CX - half, CY + half)]
    box = []
    for p, q in zip(corners, corners[1:] + corners[:1]):
        seg = pymunk.Segment(sp.static_body, p, q, 4)
        seg.elasticity, seg.friction = 1.0, 0.0
        sp.add(seg)
        box.append(seg)

    rho, span, n_seg = 185.0, 3.5, 16          # アームは半径 rho の円弧。片方の端が角の軸に付いている
    arms = []                                  # [回転体, ローカル座標の線分の始点配列, 終点配列]
    for i, corner in enumerate(corners):
        rotor = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        rotor.position = corner
        rotor.angle = rng.uniform(0, math.tau)
        turn = 1 if i % 2 == 0 else -1
        rotor.angular_velocity = turn * rng.uniform(2.7, 3.3)
        # 逆回りのアームは形も鏡写しにする（どのアームも、回る向きに対して同じ側ですくう。
        # 形を同じままにすると、逆回りの 2 本は背中で押すだけになり、ボールをはさまなくなる）
        pts = [(rho + math.cos(math.pi + turn * span * k / n_seg) * rho, math.sin(math.pi + turn * span * k / n_seg) * rho)
               for k in range(n_seg + 1)]
        sp.add(rotor)
        for p, q in zip(pts[:-1], pts[1:]):
            seg = pymunk.Segment(rotor, p, q, 8)
            seg.elasticity, seg.friction = 1.0, 0.0
            sp.add(seg)
        arms.append([rotor, np.array(pts[:-1], dtype=float), np.array(pts[1:], dtype=float), pts])

    hue0 = rng.random()

    def colour(t):
        return hsv(hue0 + t * 0.055 + rng.uniform(-0.02, 0.02), 1.0, 1.0)

    balls = []                                 # [body, shape, 色, 次に増えてよい時刻]
    a0 = rng.uniform(0, math.tau)
    b, c = _ball(sp, (CX + rng.uniform(-80, 80), CY + rng.uniform(-80, 80)), br,
                 vel=(math.cos(a0) * 430, math.sin(a0) * 430), elasticity=1.0, friction=0.0)
    balls.append([b, c, colour(0.0), 0.3])
    rings = []                                 # 増えた瞬間に広がる輪 [x, y, 色, 経過時間]
    per_arm = [0, 0, 0, 0]                     # アームごとの「潰して増やした回数」（左上・右上・右下・左下）
    n_steps, dt = _steps(v)
    done_at = None
    while True:
        for _ in range(n_steps):
            sp.step(dt)
        t = v.t
        if done_at is None:
            P = np.array([[b_[0].position.x, b_[0].position.y] for b_ in balls])
            near = np.full(len(balls), 1e9)
            away = np.zeros((len(balls), 2))                 # いちばん近いアームからボールへ向かう向き
            which = np.zeros(len(balls), dtype=int)          # いちばん近いアームの番号
            for arm_no, (rotor, A_loc, B_loc, _pts) in enumerate(arms):
                ca, sa = math.cos(rotor.angle), math.sin(rotor.angle)
                rot = np.array([[ca, sa], [-sa, ca]])
                A = A_loc @ rot + np.array(rotor.position)
                Bw = B_loc @ rot + np.array(rotor.position)
                AB = Bw - A
                AP = P[:, None, :] - A[None, :, :]
                tt = np.clip((AP * AB[None]).sum(-1) / (AB * AB).sum(-1)[None], 0.0, 1.0)
                vec = AP - tt[..., None] * AB[None]
                dall = np.hypot(vec[..., 0], vec[..., 1])
                k_min = dall.argmin(axis=1)
                dist = dall[np.arange(len(P)), k_min]
                closer = dist < near
                away[closer] = vec[np.arange(len(P)), k_min][closer] / (dist[closer, None] + 1e-9)
                which[closer] = arm_no
                near = np.minimum(near, dist)
            born = 0
            # 壁: 4 辺それぞれまでの距離。いちばん近い辺と、その辺から箱の内側へ向かう向き
            dw = np.stack([P[:, 0] - (CX - half), (CX + half) - P[:, 0], P[:, 1] - (CY - half), (CY + half) - P[:, 1]], axis=1)
            side = dw.argmin(axis=1)
            wall_d = dw[np.arange(len(P)), side]
            inward = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])[side]
            # 潰された = アームと壁がボールをはさんで向かい合い、すき間がボールの直径より狭い
            gap = (near - 8) + (wall_d - 4)
            squeezed = (gap < 2 * br + PINCH) & ((away * inward).sum(axis=1) < -0.4)
            for i in np.nonzero(squeezed)[0]:
                item = balls[int(i)]
                if len(balls) >= cap or born >= 5:
                    break
                if t < item[3]:
                    continue
                item[3] = t + rng.uniform(0.6, 1.0)
                body = item[0]
                col = colour(t)
                # その場で 2 つに割れ、壁に沿って左右へ弾け飛ぶ（少しだけ箱の内側へも押し出す）
                nx_, ny_ = float(inward[i][0]), float(inward[i][1])
                tx_, ty_ = -ny_, nx_
                body.velocity = (tx_ * 520 + nx_ * 170, ty_ * 520 + ny_ * 170)
                nb, nc = _ball(sp, (body.position.x - tx_ * 3, body.position.y - ty_ * 3), br,
                               vel=(-tx_ * 520 + nx_ * 170, -ty_ * 520 + ny_ * 170), elasticity=1.0, friction=0.0)
                body.position = (body.position.x + tx_ * 3, body.position.y + ty_ * 3)
                a = 0.0
                balls.append([nb, nc, col, t + rng.uniform(0.6, 1.0)])
                item[2] = col
                rings.append([body.position.x, body.position.y, col, 0.0])
                per_arm[int(which[i])] += 1
                born += 1
            if born:
                v.audio.note(t, penta(min(int(math.log2(len(balls)) * 2), 18), 57), 0.3, "pluck", channel="s", min_gap=0.045)
            for body, _c, _col, _n in balls:
                spd = body.velocity.length
                x, y = body.position.x, body.position.y
                # アームに押されて壁の外へ出かけた球は、その場で壁の内側へ戻す（中央へ飛ばさない）
                lim = half - 4 - br
                nx_, ny_ = min(max(x, CX - lim), CX + lim), min(max(y, CY - lim), CY + lim)
                if nx_ != x or ny_ != y:
                    vx_, vy_ = body.velocity
                    if (x - nx_) * vx_ > 0:
                        vx_ = -vx_
                    if (y - ny_) * vy_ > 0:
                        vy_ = -vy_
                    body.position, body.velocity = (nx_, ny_), (vx_, vy_)
                if spd > 780:
                    body.velocity = body.velocity * (780 / spd)
                elif spd < 320:
                    a = rng.uniform(0, math.tau)
                    body.velocity = (math.cos(a) * 380, math.sin(a) * 380)
            if len(balls) >= cap:
                done_at = t
                for seg in box:
                    sp.remove(seg)
                for body, _c, _col, _n in balls:
                    dx, dy = body.position.x - CX, body.position.y - CY
                    d = math.hypot(dx, dy) or 1.0
                    k = rng.uniform(700, 1500)
                    body.velocity = (dx / d * k, dy / d * k)
                v.audio.play(t, 90, 1.0, "thud")
                for i, m in enumerate((48, 55, 60, 64, 67, 72)):
                    v.audio.note(t + 0.03 * i, m, 0.8, "piano")
        for r in rings:
            r[3] += 1 / v.fps
        rings = [r for r in rings if r[3] < 0.6][-40:]

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            for x, y, col, age in rings:
                v.circle(mix((0, 0, 0), col, 0.5 * (1 - age / 0.6)), (x, y), 14 + 110 * age / 0.6, width=2)
            if done_at is None:
                pygame.draw.rect(v.surf, (245, 245, 245), (CX - half - 3, CY - half - 3, 2 * half + 6, 2 * half + 6), 5)
            for body, _c, col, _n in balls:
                x, y = body.position.x, body.position.y
                if -30 < x < W + 30 and -30 < y < H + 30:
                    v.circle(col, (x, y), br)
                    v.circle(mix(col, (255, 255, 255), 0.6), (x - 3, y - 3), 3)
            for rotor, _a, _b, pts in arms:
                ca, sa = math.cos(rotor.angle), math.sin(rotor.angle)
                px, py = rotor.position
                world = [(px + x * ca - y * sa, py + x * sa + y * ca) for x, y in pts]
                pygame.draw.lines(v.surf, (95, 95, 100), False, world, 20)
                pygame.draw.lines(v.surf, (150, 150, 156), False, world, 12)
                v.circle((150, 150, 156), (px, py), 16)
                v.circle((60, 60, 66), (px, py), 7)
            v.text("Squeezed = x2", 100, (CX, 250))
            v.text(f"{len(balls)}", 150, (CX, CY + half + 190))
        v.end(glow=0.28)
        if done_at is not None and v.t - done_at > 2.3:
            break
        if v.t > 80:
            break
    return {"result": f"1 -> {len(balls)} balls", "marks": per_arm}


# ============================================================ glass: 大きなガラスが砕けていく
def run_glass(v, rng):
    """右下の砲台（いつも同じ場所）がガラスへ向けてボールを撃つ。ガラスに当たったボールは消えて、
    当たった所が欠ける。外れて下のくぼみへ落ちたボールは、底の倍率（x2・x3・x4・x10）に触れて消え、
    その数だけ砲台から撃ち直される。ガラスが減るほど外れ弾が増え、ボールも増えていく。
    x10 と左側の入口はガラスの奥にあり、ガラスが欠けると届くようになる。"""
    R = 470.0
    br = 15.0
    C = (CX, CY)
    B = (CX - 30, CY + 40)                    # くぼみ（同心の半円）の中心
    radii = [105.0, 215.0, 325.0]
    sp = _space(gravity=1500.0)
    _ring(sp, C, R + 5, elasticity=0.5, friction=0.2)
    for r in radii:                           # 下半分だけの半円 = 上が開いたくぼみ
        for i in range(30):
            a0, a1 = math.pi * i / 30, math.pi * (i + 1) / 30
            s_ = pymunk.Segment(sp.static_body, (B[0] + math.cos(a0) * r, B[1] + math.sin(a0) * r),
                                (B[0] + math.cos(a1) * r, B[1] + math.sin(a1) * r), 5)
            s_.elasticity, s_.friction = 0.45, 0.2
            sp.add(s_)

    # ---- ガラス: 細かいマスの集まり。当たったところから欠ける（当たり判定は自前。ボールは当たると消える）
    g = 11.0
    cells = {}                                # (ix, iy) -> [残り, x0, y0]
    top_y = CY - R

    def edge_x(y):                            # ガラスの右のふち（上ほど右に張り出し、少し波打つ）
        k = (y - top_y) / (B[1] - top_y)
        return (CX + 150) + ((B[0] + radii[0] + 20) - (CX + 150)) * k + 20 * math.sin(y / 55.0)

    for iy in range(int((CY - R) // g), int(B[1] // g) + 1):
        for ix in range(int((CX - R) // g), int((CX + R) // g) + 1):
            mx, my = ix * g + g / 2, iy * g + g / 2
            if math.hypot(mx - CX, my - CY) > R - 8 or my > B[1] - 8 or mx > edge_x(my):
                continue
            cells[(ix, iy)] = [GLASS_HP, ix * g, iy * g]
    total_hp = sum(c[0] for c in cells.values())

    tr = 34.0
    tokens = [                                # [倍率, x, y, 色, 光っている残り時間]
        # 外れ弾がいちばん落ちやすい真ん中が x2。外側ほど入りにくく、倍率が高い（x10 は砲台の真下のいちばん外）
        [2, B[0], B[1] + 54, (125, 211, 252), 0.0],
        [3, B[0], B[1] + (radii[0] + radii[1]) / 2, (192, 132, 252), 0.0],
        [4, B[0], B[1] + (radii[1] + radii[2]) / 2, (74, 222, 128), 0.0],
        [10, B[0], (B[1] + radii[2] + CY + R) / 2, (251, 146, 60), 0.0],
    ]
    balls = []                                # [body, shape, 色]
    th_c = -0.06                              # 砲台の位置（右の壁ぎわ。くぼみのふちより上）
    E = (CX + math.cos(th_c) * (R - 46), CY + math.sin(th_c) * (R - 46))
    aim = (CX + 60.0, CY - 200.0)             # ねらう点（ガラスの右のふちのあたり）
    queue = []                                # これから撃つボールの色
    targets, next_aim = [], 0.0
    next_fire, next_free = 0.7, 0.7
    fired = 0
    recoil = 0.0
    barrel = (-0.6, -0.8)
    n_steps, dt = _steps(v)
    parts = Particles()
    shards = []                               # 欠けたガラスの破片 [x, y, vx, vy, 回転, 回転速度, 残り時間]
    broke_at = None
    budget = 0.0
    owed = {}                                 # まだ効かせていない削れ（マス → 量）
    trace = []
    hits = 0
    used = {2: 0, 3: 0, 4: 0, 10: 0}          # 倍率ごとの使われた回数（配置の確認用）
    hue0 = rng.random()

    def chip(key, amount, kick=160):
        """マス key を amount だけ削る。1 秒に削れる量には上限があり、超えた分はあとで効かせる。"""
        nonlocal budget
        cell = cells.get(key)
        if cell is None:
            return
        now = max(0.0, min(budget, amount))
        if amount > now:
            owed[key] = owed.get(key, 0.0) + amount - now
        budget -= now
        cell[0] -= now
        if cell[0] <= 0:
            del cells[key]
            owed.pop(key, None)
            if rng.random() < 0.5:
                shards.append([cell[1] + g / 2, cell[2] + g / 2, rng.uniform(-kick, kick), rng.uniform(-260, 60),
                               rng.uniform(0, math.tau), rng.uniform(-6, 6), 1.1])

    while True:
        for _ in range(n_steps):
            sp.step(dt)
        t = v.t
        left = sum(c[0] for c in cells.values())
        pct = 100.0 * left / total_hp
        if v.frames % (3 * v.fps) == 0:
            trace.append(int(round(pct)))             # 3 秒ごとの残り（減り方がなめらかかを確かめる用）
        budget = min(budget + total_hp * GLASS_RATE / v.fps, total_hp * GLASS_RATE * 0.4)
        for key in list(owed)[:80]:                   # 持ち越した分を少しずつ効かせる（ひびが遅れて広がる）
            amount = owed.pop(key)
            if key in cells and budget > 0:
                chip(key, amount)
        # ---- 砲台: 一定の間隔で 1 発ずつ補給される。倍率で増えた分は、待ち行列から続けて撃つ
        if t >= next_free and broke_at is None:
            next_free = t + GLASS_FREE
            if len(queue) < 3:
                queue.append(rng.choice(CANDY))
        if cells and t >= next_aim:                   # ねらいを更新: 残っているガラスのうち、砲台に近い側のどこか
            next_aim = t + 0.25
            near_cells = sorted(cells.values(), key=lambda c_: (c_[1] - E[0]) ** 2 + (c_[2] - E[1]) ** 2)
            targets = near_cells[:max(12, len(near_cells) // 4)]
        if queue and t >= next_fire:
            if targets:
                c_ = rng.choice(targets)
                aim = (c_[1] + g / 2, c_[2] + g / 2)
            dist = math.hypot(aim[0] - E[0], aim[1] - E[1])
            tof = dist / rng.uniform(760, 940)                    # 飛ぶ時間をばらつかせる（当たる所と外れ方が変わる）
            vx_ = (aim[0] - E[0]) / tof
            vy_ = (aim[1] - E[1]) / tof - 0.5 * 1500.0 * tof
            turn = rng.uniform(-GLASS_SPRAY, GLASS_SPRAY)         # ねらいのぶれ
            if rng.random() < GLASS_WEAK:                         # 弱い弾: 届かずに手前のくぼみ（x2・x3）へ落ちる
                weak = rng.uniform(0.42, 0.8)
                vx_, vy_ = vx_ * weak, vy_ * weak
            ca, sa = math.cos(turn), math.sin(turn)
            b_, c_ = _ball(sp, E, br, vel=(vx_ * ca - vy_ * sa, vx_ * sa + vy_ * ca), elasticity=0.55, friction=0.1)
            balls.append([b_, c_, queue.pop(0)])
            next_fire = t + (0.05 if len(queue) < 40 else 0.03)
            fired += 1
            recoil = 0.09
            v.audio.play(t, 300 + 6 * (fired % 30), 0.2, "pop", channel="em", min_gap=0.045)
        # ---- 倍率に触れたボールは消えて、その数だけ撃ち直される
        for tok in tokens:
            for item in list(balls):
                body = item[0]
                if math.hypot(body.position.x - tok[1], body.position.y - tok[2]) >= tr + br:
                    continue
                sp.remove(body, item[1])
                balls.remove(item)
                if len(queue) < GLASS_QUEUE_MAX:
                    queue.extend([rng.choice(CANDY)] * tok[0])
                tok[4] = 0.28
                used[tok[0]] += 1
                parts.burst(rng, (tok[1], tok[2]), tok[3], n=6, speed=220, life=0.3, gravity=False)
                v.audio.note(t, {2: 60, 3: 64, 4: 67, 10: 76}[tok[0]], 0.4, "marimba", channel="tk", min_gap=0.05)
        # ---- ガラスに当たったボールは消えて、当たった所が欠ける
        if cells:
            reach = min(GLASS_REACH, 2 + int(max(0.0, t - 6.0) / GLASS_SPREAD))
            span = int((br + 2) // g) + 1
            for item in list(balls):
                body = item[0]
                x, y = body.position.x, body.position.y
                if math.hypot(x - CX, y - CY) > R + 40:             # 万一外へ出たら消す
                    sp.remove(body, item[1])
                    balls.remove(item)
                    continue
                ix0, iy0 = int(x // g), int(y // g)
                hit = None
                for cy_ in range(iy0 - span, iy0 + span + 1):
                    for cx_ in range(ix0 - span, ix0 + span + 1):
                        cell = cells.get((cx_, cy_))
                        if cell is None:
                            continue
                        nx = min(max(x, cell[1]), cell[1] + g)
                        ny = min(max(y, cell[2]), cell[2] + g)
                        if (x - nx) ** 2 + (y - ny) ** 2 < (br + 2) ** 2:
                            hit = (cx_, cy_)
                            break
                    if hit:
                        break
                if not hit:
                    continue
                hits += 1
                spd = body.velocity.length
                power = GLASS_HIT * min(1.6, max(0.6, spd / 800))
                for dx_ in range(-reach, reach + 1):
                    for dy_ in range(-reach, reach + 1):
                        far = math.hypot(dx_, dy_)
                        if far <= reach + 0.5:
                            chip((hit[0] + dx_, hit[1] + dy_), power * (1.0 if far == 0 else 0.5 / max(1.0, far)))
                parts.burst(rng, (x, y), mix(item[2], (255, 255, 255), 0.5), n=7, speed=420, life=0.35)
                for _ in range(3):
                    shards.append([x, y, rng.uniform(-320, 320), rng.uniform(-360, 80), rng.uniform(0, math.tau),
                                   rng.uniform(-8, 8), 0.9])
                v.audio.play(t, 1800 + rng.uniform(0, 1400), 0.22, "click", channel="g", min_gap=0.03)
                if hits % 6 == 0:
                    v.audio.note(t, penta(min(hits // 6, 19), 67), 0.3, "glock", channel="gg", min_gap=0.08, dur=0.4)
                sp.remove(body, item[1])
                balls.remove(item)
            # 残りがわずかになったら、届かない場所の破片ごと砕ける
            if left <= total_hp * 0.05:
                for cell in list(cells.values()):
                    shards.append([cell[1] + g / 2, cell[2] + g / 2, rng.uniform(-300, 300), rng.uniform(-460, 40),
                                   rng.uniform(0, math.tau), rng.uniform(-7, 7), 1.5])
                cells.clear()
                owed.clear()
                pct = 0.0
                broke_at = t
                v.audio.play(t, 90, 0.9, "thud")
                for i, m in enumerate((60, 64, 67, 72, 76)):
                    v.audio.note(t + 0.06 * i, m, 0.8, "piano")
                v.audio.play(t, 2800, 0.8, "click")
        for sh in shards:
            sh[3] += 1500 / v.fps
            sh[0] += sh[2] / v.fps
            sh[1] += sh[3] / v.fps
            sh[4] += sh[5] / v.fps
            sh[6] -= 1 / v.fps
        shards = [sh for sh in shards if sh[6] > 0 and sh[1] < H + 60][-320:]
        for tok in tokens:
            tok[4] = max(0.0, tok[4] - 1 / v.fps)
        recoil = max(0.0, recoil - 1 / v.fps)
        parts.step(1 / v.fps)

        if not v.dry:
            ring = hsv(hue0 + t * 0.045, 0.85, 1.0)             # 枠の色はゆっくり変わっていく
            v.begin(bg=(0, 0, 0))
            glass_fill = mix((10, 14, 20), ring, 0.24)
            for cell in cells.values():
                pygame.draw.rect(v.surf, glass_fill, (int(cell[1]), int(cell[2]), int(g) + 1, int(g) + 1))
            v.circle(ring, C, R + 8, width=7)
            for r in radii:
                v.arc_band(ring, B, r - 5, r + 5, 0.0, math.pi)
            for mult, tx, ty, col, glow in tokens:
                c2 = mix(col, (255, 255, 255), min(1.0, glow / 0.28))
                if glow > 0:
                    v.circle(c2, (tx, ty), tr + 10 + 20 * (1 - glow / 0.28), width=3)
                v.circle(c2, (tx, ty), tr)
                v.text(f"x{mult}", 44, (tx, ty), color=(25, 25, 35), outline=0)
            for body, _c, col in balls:
                v.circle(col, (body.position.x, body.position.y), br)
            for x, y, _vx, _vy, ang, _w, life in shards:
                c3 = mix((0, 0, 0), (215, 228, 255), min(1.0, life))
                pts_ = [(x + math.cos(ang + k * 2.1) * 8, y + math.sin(ang + k * 2.1) * 8) for k in range(3)]
                pygame.draw.polygon(v.surf, c3, pts_)
            parts.draw(v)
            # 砲台（撃つたびに少し下がる）
            dxa, dya = aim[0] - E[0], aim[1] - E[1] - 120
            da = math.hypot(dxa, dya)
            want_u = (dxa / da, dya / da)
            barrel = (barrel[0] + (want_u[0] - barrel[0]) * 0.12, barrel[1] + (want_u[1] - barrel[1]) * 0.12)
            bl = math.hypot(*barrel) or 1.0                     # 砲身はねらいをなめらかに追う
            ux, uy = barrel[0] / bl, barrel[1] / bl
            back = 14 * recoil / 0.09
            base = (E[0] - ux * back, E[1] - uy * back)
            tip = (base[0] + ux * 62, base[1] + uy * 62)
            pygame.draw.line(v.surf, (70, 74, 86), base, tip, 40)
            pygame.draw.line(v.surf, mix((150, 154, 168), (255, 255, 255), recoil / 0.09), base, tip, 30)
            v.circle((150, 154, 168), base, 26)
            v.circle((60, 64, 76), base, 12)
            if queue:
                v.text(f"+{len(queue)}", 46, (E[0] - 10, E[1] + 62), color=ring, outline=3)
            v.text(f"Glass {pct:.0f}%" if broke_at is None else "Glass broken", 96, (CX, 250))
        v.end(glow=0.3)
        if broke_at is not None and v.t - broke_at > 2.8:
            break
        if v.t > 80:
            break
    return {"result": f"glass broke at {broke_at:.1f}s after {hits} hits, {fired} shots" if broke_at
            else f"glass did not break ({pct:.0f}% left, {hits} hits, {fired} shots)", "marks": trace, "used": used}


# ============================================================ gear: 輪に閉じ込めると 4 倍
VIVID = [(45, 150, 235), (190, 232, 30), (172, 30, 222), (40, 222, 110), (228, 26, 62), (50, 70, 235),
         (238, 34, 200), (40, 222, 222), (242, 182, 40), (242, 112, 30), (40, 232, 170), (96, 44, 232)]
_SPRITES = {}


def _ball_sprite(col, r):
    """立体っぽい陰影つきの球（色と半径ごとに 1 回だけ作って使い回す）。"""
    key = (col, int(round(r * 2)))
    if key not in _SPRITES:
        r = key[1] / 2.0
        n = int(math.ceil(r * 2 + 2)) * 4
        yy, xx = np.mgrid[0:n, 0:n].astype(float)
        c = (n - 1) / 2.0
        d = np.hypot(xx - c, yy - c) / (r * 4)
        shade = np.clip(1.08 - 0.55 * d ** 2, 0, 1.1)
        hl = np.exp(-(((xx - c + r * 1.3) ** 2 + (yy - c + r * 1.5) ** 2) / (2 * (r * 1.1) ** 2)))
        rgb = np.clip(np.array(col)[None, None, :] * shade[..., None] + 215 * hl[..., None], 0, 255)
        alpha = np.clip((1.0 - d) * r * 4, 0, 1) * 255
        big = pygame.Surface((n, n), pygame.SRCALPHA)
        pygame.surfarray.pixels3d(big)[:] = rgb.transpose(1, 0, 2).astype(np.uint8)
        pygame.surfarray.pixels_alpha(big)[:] = alpha.T.astype(np.uint8)
        _SPRITES[key] = pygame.transform.smoothscale(big, (n // 4, n // 4))
    return _SPRITES[key]


def _glow_sprite(size=256):
    if "glow" not in _SPRITES:
        yy, xx = np.mgrid[0:size, 0:size].astype(float)
        d = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
        a = np.clip(1 - d, 0, 1) ** 1.6 * 255
        s = pygame.Surface((size, size))
        pygame.surfarray.pixels3d(s)[:] = np.repeat(a.T[..., None], 3, axis=2).astype(np.uint8)
        _SPRITES["glow"] = s
    return _SPRITES["glow"]


def run_gear2(v, rng):
    """歯車の別バージョン: アームが 4 本（2 本ずつ逆向き）。すれ違う回数が倍になる。"""
    return run_gear(v, rng, pairs=2, rho=135.0, slow=0.5, cap=2000)


def run_gear(v, rng, pairs=1, rho=150.0, slow=1.0, cap=1000):
    """円の中心の歯車に、半円のアームが 2 本付いて逆向きに回る。2 本のアームがすれ違うときに
    あいだに挟まれて潰されたボールは 2 個に増える。増えるほど粒が小さくなり、最後は円が割れる。"""
    R = 470.0
    C = (CX, CY)
    r0 = 14.0
    thick, span, n_seg = 9.0, 3.6, 18
    fill = 0.80
    sp = _space(gravity=0.0)
    sp.iterations = 10
    sp.damping = 0.93
    ring = _ring(sp, C, R, n=140, thick=5.0, elasticity=1.0, friction=0.0)

    A0, phi0 = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
    dA, dphi = rng.choice((-1, 1)) * rng.uniform(0.25, 0.4) * slow, rng.uniform(2.2, 2.5) * slow
    arms = []                                   # (回転体, 描く用の点, 線分の始点, 線分の終点)
    for s_, turn in [(s_, k * math.tau / pairs) for k in range(pairs) for s_ in (1, -1)]:
        rotor = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        rotor.position = C
        rotor.angle = A0 + s_ * phi0 + turn
        rotor.angular_velocity = dA + s_ * dphi
        pts = [(rho + math.cos(math.pi + s_ * span * k / n_seg) * rho, math.sin(math.pi + s_ * span * k / n_seg) * rho)
               for k in range(n_seg + 1)]
        sp.add(rotor)
        for p_, q_ in zip(pts[:-1], pts[1:]):
            seg = pymunk.Segment(rotor, p_, q_, thick)
            seg.elasticity, seg.friction = 0.9, 0.1
            sp.add(seg)
        arms.append((rotor, pts, np.array(pts[:-1], dtype=float), np.array(pts[1:], dtype=float)))

    order = VIVID[:]
    rng.shuffle(order)
    balls = []                                  # [body, shape, 色, 次に増えてよい時刻]
    rad = r0

    def add(pos, vel, col, t_next):
        b, c = _ball(sp, pos, rad, vel=vel, elasticity=0.9, friction=0.05)
        balls.append([b, c, col, t_next])

    a = rng.uniform(0, math.tau)
    add((CX + math.cos(a) * 170, CY + math.sin(a) * 170), (-math.sin(a) * 260, math.cos(a) * 260), order[0], 0.4)
    rings = []                                  # 増えた瞬間の輪 [x, y, 色, 経過]
    n_steps, dt = _steps(v)
    target_rad = rad
    done_at = full_at = None
    seq, splits = 0, 0
    marks = []                                  # 10・100・500・1000 個に達した時刻（長さの調整用）
    while True:
        for _ in range(n_steps):
            sp.step(dt)
        t = v.t
        if done_at is None and full_at is None:
            P = np.array([[b_[0].position.x, b_[0].position.y] for b_ in balls])
            dists, aways = [], []                     # それぞれのアームまでの距離と、アームからボールへ向かう向き
            idx = np.arange(len(P))
            for rotor, _pts, A_loc, B_loc in arms:
                ca, sa = math.cos(rotor.angle), math.sin(rotor.angle)
                rot = np.array([[ca, sa], [-sa, ca]])
                A = A_loc @ rot + np.array(C)
                AB = B_loc @ rot + np.array(C) - A
                AP = P[:, None, :] - A[None, :, :]
                tt = np.clip((AP * AB[None]).sum(-1) / (AB * AB).sum(-1)[None], 0.0, 1.0)
                vec = AP - tt[..., None] * AB[None]
                dall = np.hypot(vec[..., 0], vec[..., 1])
                k_min = dall.argmin(axis=1)
                dists.append(dall[idx, k_min])
                aways.append(vec[idx, k_min] / (dall[idx, k_min][:, None] + 1e-9))
            # 潰された = 逆向きに回る 2 本のアームがボールをはさんで向かい合い、すき間がボールの直径より狭い
            squeezed = np.zeros(len(P), dtype=bool)
            side = np.zeros(len(P), dtype=int)        # どのアームにはさまれたか（弾ける向きに使う）
            for i_ in range(0, len(arms), 2):
                for j_ in range(1, len(arms), 2):
                    gap = (dists[i_] - thick) + (dists[j_] - thick)
                    hit = (gap < 2 * rad + GEAR_PINCH) & ((aways[i_] * aways[j_]).sum(axis=1) < -0.4)
                    side[hit & ~squeezed] = i_
                    squeezed |= hit
            col = order[int(t / 2.4) % len(order)]
            born, limit = 0, max(3, len(balls) // 14)
            for i in np.nonzero(squeezed)[0]:
                item = balls[int(i)]
                if t < item[3] or born >= limit:
                    continue
                body = item[0]
                x, y = body.position.x, body.position.y
                # その場で 2 つに割れ、アームのすき間に沿って反対向きに弾け飛ぶ
                ax_, ay_ = float(aways[side[i]][i][0]), float(aways[side[i]][i][1])
                tx_, ty_ = -ay_, ax_
                k = rng.uniform(520, 700)
                body.velocity = (tx_ * k, ty_ * k)
                body.position = (x + tx_ * 3, y + ty_ * 3)
                item[2], item[3] = col, t + rng.uniform(0.45, 0.7)
                add((x - tx_ * 3, y - ty_ * 3), (-tx_ * k, -ty_ * k), col, t + rng.uniform(0.45, 0.7))
                rings.append([x, y, col, 0.0])
                born += 1
            if born:
                splits += born
                for m_ in (10, 100, 500, 1000, 2000):
                    if len(balls) >= m_ > len(balls) - born:
                        marks.append((m_, round(t, 1)))
                if v.audio.note(t, ARP_PROG[(seq // 8) % 4][ARP_PAT[seq % 8]], 0.36, "marimba", channel="s", min_gap=0.07):
                    seq += 1
                target_rad = min(r0, (R - 6) * math.sqrt(fill / len(balls)))
                if len(balls) >= cap:
                    full_at = t
        # ---- 粒をなめらかに小さくする
        if rad > target_rad + 0.01:
            rad = max(target_rad, rad - 0.03 * (60 / v.fps) * max(1.0, (rad - target_rad) * 2))
            for item in balls:
                item[1].unsafe_set_radius(rad)
        # ---- 円が割れる
        if full_at is not None and done_at is None and t - full_at > 1.2:
            done_at = t
            for seg in ring:
                sp.remove(seg)
            if pairs > 1:                       # 4 本版はアームが輪になって粒を抱え込むので、円と一緒にアームも砕ける
                for rotor, _pts, _a, _b in arms:
                    sp.remove(*rotor.shapes)
            for body, _c, _col, _n in balls:
                dx, dy = body.position.x - CX, body.position.y - CY
                d = math.hypot(dx, dy) or 1.0
                k = rng.uniform(300, 1000) * (0.4 + d / R)
                body.velocity = (dx / d * k, dy / d * k)
            v.audio.play(t, 80, 1.0, "thud")
            for i, m in enumerate((45, 52, 57, 61, 64, 69)):
                v.audio.note(t + 0.035 * i, m, 0.8, "piano")
        pos = []
        lim_r = R - 5 - rad
        lively = len(balls) < 500
        for body, _c, col, _n in balls:
            x, y = body.position.x, body.position.y
            if done_at is None:
                dx, dy = x - CX, y - CY
                d = math.hypot(dx, dy)
                if d > lim_r + 1.5:                                    # 押し出されかけた粒は内側へ戻す
                    x, y = CX + dx / d * lim_r, CY + dy / d * lim_r
                    body.position = (x, y)
                spd = body.velocity.length
                top = 950 if len(balls) >= 8 else 330          # 最初の数個はゆっくり動かす（アームに捕まりやすい）
                if spd > top:
                    body.velocity = body.velocity * (top / spd)
                elif lively and spd < 240:                             # 数が少ないうちは止まらせない
                    a = math.atan2(body.velocity.y, body.velocity.x) if spd > 1 else rng.uniform(0, math.tau)
                    k_ = 300 if len(balls) < 8 else 360
                    body.velocity = (math.cos(a) * k_, math.sin(a) * k_)
            pos.append((x, y, col))
        for r_ in rings:
            r_[3] += 1 / v.fps
        rings = [r_ for r_ in rings if r_[3] < 0.5][-60:]

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            for x, y, col in pos:
                if -20 < x < W + 20 and -20 < y < H + 20:
                    spr = _ball_sprite(col, rad)
                    v.surf.blit(spr, (x - spr.get_width() / 2, y - spr.get_height() / 2))
            for x, y, col, age in rings:
                k = age / 0.5
                v.circle(mix(mix(col, (255, 255, 255), 0.6), (0, 0, 0), k), (x, y), rad + 4 + 70 * k, width=3)
            if done_at is None:
                flash = 0.0 if full_at is None else min(1.0, (t - full_at) / 1.2)
                ring_col = mix((245, 245, 245), (255, 80, 80), flash * (0.5 + 0.5 * math.sin(t * 40)))
                pygame.draw.circle(v.surf, ring_col, (int(CX), int(CY)), int(R), 4)
                pygame.gfxdraw.aacircle(v.surf, int(CX), int(CY), int(R), ring_col)
            # 4 本版では、円が割れたあとアームは 0.3 秒で砕けて消える
            gone_k = min(1.0, (t - done_at) / 0.3) if (done_at is not None and pairs > 1) else 0.0
            for rotor, pts, _a, _b in arms:
                if gone_k >= 1.0:
                    break
                ca, sa = math.cos(rotor.angle), math.sin(rotor.angle)
                world = [(CX + x * ca - y * sa, CY + x * sa + y * ca) for x, y in pts]
                dark, light = mix((88, 88, 94), (0, 0, 0), gone_k), mix((158, 158, 164), (0, 0, 0), gone_k)
                pygame.draw.lines(v.surf, dark, False, world, 24)
                for p_ in world:
                    v.circle(dark, p_, 11)
                pygame.draw.lines(v.surf, light, False, world, 15)
                for p_ in world:
                    v.circle(light, p_, 7)
            ga = t * 1.6
            teeth = []
            for i in range(24):
                a = ga + i * math.tau / 24
                rr = 34 if i % 2 == 0 else 24
                for da in (-0.07, 0.07):
                    teeth.append((CX + math.cos(a + da) * rr, CY + math.sin(a + da) * rr))
            pygame.gfxdraw.filled_polygon(v.surf, teeth, (225, 225, 228))
            pygame.gfxdraw.aapolygon(v.surf, teeth, (225, 225, 228))
            v.circle((120, 120, 126), C, 14)
            v.circle((225, 225, 228), C, 9)
            v.circle((70, 70, 76), C, 4)
            v.text("Squeezed = x2", 100, (CX, 250))
            v.text(f"{len(balls)}", 150, (CX, CY + R + 180))
        v.end(glow=0.22)
        if done_at is not None and v.t - done_at > 2.6:
            break
        if v.t > 75:
            break
    return {"result": f"1 -> {len(balls)} balls ({splits} squeezes)", "marks": marks}
