"""sims_squeeze.py — 「潰されると 2 倍」の仲間（arms を基準にした型）

  hammer  箱の左右の壁を、2 本のピストンが 上・中・下 の順に交互に叩く。ピストンと壁にはさまれたボールが 2 つに割れる
  cam     円の中心から伸びた 3 本の腕の先で、ローラーが壁すれすれを回る。ローラーと壁にはさまれたボールが 2 つに割れる

どれも同じ土台（_run）を使う。重力なし、1 個から始まり、上限に達すると枠が外れて弾ける。
増えた時刻で色が変わるので、世代ごとに色の波ができる。

「潰された」の判定は物理エンジンの接触から取る: ボールが 2 つの物（そのうち少なくとも 1 つは動く部品）に
同時に触れていて、その 2 つがボールをはさんで向かい合っているとき。形が変わっても同じ判定がそのまま使える。
新しい仕掛けを足すときは、_mech_○○ を 1 つ書いて run_○○ から渡すだけでよい。
"""

import math

import pygame
import pymunk

from engine import CX, CY, hsv, mix, penta
from sims_pack import _ball, _ring, _space, _steps

GREY_DARK, GREY = (95, 95, 100), (150, 150, 156)
BEAM_RED = 0.42       # beams: 赤い光線の長さ（円の半径に対する割合）。長いほど消えやすく、増えるのが遅くなる


def _box(sp, half):
    corners = [(CX - half, CY - half), (CX + half, CY - half), (CX + half, CY + half), (CX - half, CY + half)]
    segs = []
    for p, q in zip(corners, corners[1:] + corners[:1]):
        seg = pymunk.Segment(sp.static_body, p, q, 4)
        seg.elasticity, seg.friction = 1.0, 0.0
        sp.add(seg)
        segs.append(seg)
    return segs


def _box_clamp(half, br):
    lim = half - 4 - br
    return lambda x, y: (min(max(x, CX - lim), CX + lim), min(max(y, CY - lim), CY + lim))


def _circle_clamp(R, br):
    lim = R - 5 - br

    def clamp(x, y):
        d = math.hypot(x - CX, y - CY)
        return (x, y) if d <= lim else (CX + (x - CX) / d * lim, CY + (y - CY) / d * lim)
    return clamp


def _follow(body, target, fdt, angle=None):
    """動く部品を、次のコマで target（と angle）に来るように動かす（速度で動かすので、ボールを正しく押す）。"""
    body.velocity = ((target[0] - body.position.x) / fdt, (target[1] - body.position.y) / fdt)
    if angle is not None:
        body.angular_velocity = (angle - body.angle) / fdt


def _smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


# ------------------------------------------------------------------ 土台
def _run(v, rng, mech, caption, cap=320, br=10.0, bottom=CY + 580):
    sp = _space(gravity=0.0)
    sp.iterations = 12
    m = mech(sp, rng, br)
    hue0 = rng.random()

    def colour(t):
        return hsv(hue0 + t * 0.055 + rng.uniform(-0.02, 0.02), 1.0, 1.0)

    balls = []                                 # [body, shape, 色, 次に増えてよい時刻]
    a0 = rng.uniform(0, math.tau)
    b, c = _ball(sp, m["start"], br, vel=(math.cos(a0) * 430, math.sin(a0) * 430), elasticity=1.0, friction=0.0)
    balls.append([b, c, colour(0.0), 0.3])
    rings = []                                 # 増えた瞬間に広がる輪 [x, y, 色, 経過時間]
    gone = []                                  # 消えた瞬間のしるし [x, y, 経過時間]
    peak = 1
    n_steps, dt = _steps(v)
    done_at = None
    lo, hi = m.get("speed", (320.0, 780.0))
    wait = m.get("wait", (0.6, 1.0))
    while True:
        t = v.t
        m["update"](t, 1.0 / v.fps)
        if "sound" in m and done_at is None:
            m["sound"](v, t)
        for _ in range(n_steps):
            sp.step(dt)
        if done_at is None:
            born = 0
            if "kill" in m:                    # 仕掛けによっては、触れたボールが消える（最後の 1 個は消えない）
                for item in list(balls):
                    if len(balls) <= 1:
                        break
                    x, y = item[0].position.x, item[0].position.y
                    if m["kill"](x, y):
                        sp.remove(item[0], item[1])
                        balls.remove(item)
                        gone.append([x, y, 0.0])
                        v.audio.play(t, 180, 0.3, "pop", channel="k", min_gap=0.06)
            for item in list(balls):
                if len(balls) >= cap or born >= m.get("per_frame", 6):
                    break
                if t < item[3]:
                    continue
                body = item[0]
                touch = []                     # ボールに触れている「ボール以外の物」: (向き x, 向き y, 動く部品か)
                body.each_arbiter(lambda arb, touch=touch: touch.append(
                    (arb.normal.x, arb.normal.y, arb.shapes[1].body.body_type == pymunk.Body.KINEMATIC))
                    if arb.shapes[1].body.body_type != pymunk.Body.DYNAMIC else None)
                pinch = None
                for i in range(len(touch)):
                    for j in range(i + 1, len(touch)):
                        p, q = touch[i], touch[j]
                        if (p[2] or q[2]) and p[0] * q[0] + p[1] * q[1] < -0.45:
                            pinch = (p[0] - q[0], p[1] - q[1])
                if pinch is None and "pinched" in m:           # 仕掛けごとの判定（形から決める）
                    pinch = m["pinched"](body.position.x, body.position.y)
                if pinch is None:
                    continue
                d = math.hypot(*pinch) or 1.0
                n = (pinch[0] / d, pinch[1] / d)               # はさまれている向き
                x, y = body.position.x, body.position.y
                if "split" in m:
                    p1, v1, p2, v2 = m["split"](x, y, n, body.velocity, rng)
                else:                                          # その場で 2 つに割れ、はさむ向きと直角に左右へ飛ぶ
                    tx, ty = -n[1], n[0]
                    p1, v1 = (x + tx * 3, y + ty * 3), (tx * 520, ty * 520)
                    p2, v2 = (x - tx * 3, y - ty * 3), (-tx * 520, -ty * 520)
                col = colour(t)
                body.position, body.velocity = p1, v1
                item[2], item[3] = col, t + rng.uniform(*wait)
                nb, nc = _ball(sp, p2, br, vel=v2, elasticity=1.0, friction=0.0)
                balls.append([nb, nc, col, t + rng.uniform(*wait)])
                rings.append([x, y, col, 0.0])
                born += 1
            if born:
                v.audio.note(t, penta(min(int(math.log2(len(balls)) * 2), 18), 57), 0.3, "pluck", channel="s", min_gap=0.045)
            for body, _c, _col, _n in balls:
                x, y = body.position.x, body.position.y
                nx_, ny_ = m["clamp"](x, y)                    # 部品に押されて枠の外へ出かけた球は、その場で内側へ戻す
                if nx_ != x or ny_ != y:
                    vx_, vy_ = body.velocity
                    if (x - nx_) * vx_ > 0:
                        vx_ = -vx_
                    if (y - ny_) * vy_ > 0:
                        vy_ = -vy_
                    body.position, body.velocity = (nx_, ny_), (vx_, vy_)
                if "pull" in m:
                    m["pull"](body)
                spd = body.velocity.length
                if spd > hi:
                    body.velocity = body.velocity * (hi / spd)
                elif spd < lo:
                    a = rng.uniform(0, math.tau)
                    body.velocity = (math.cos(a) * (lo + 60), math.sin(a) * (lo + 60))
            if len(balls) >= cap:
                done_at = t
                for seg in m["walls"]:
                    sp.remove(seg)
                for body, _c, _col, _n in balls:
                    dx, dy = body.position.x - CX, body.position.y - CY
                    d = math.hypot(dx, dy) or 1.0
                    k = rng.uniform(700, 1500)
                    body.velocity = (dx / d * k, dy / d * k)
                v.audio.play(t, 90, 1.0, "thud")
                for i, mm in enumerate((48, 55, 60, 64, 67, 72)):
                    v.audio.note(t + 0.03 * i, mm, 0.8, "piano")
        for r in rings:
            r[3] += 1 / v.fps
        rings = [r for r in rings if r[3] < 0.6][-40:]
        for g_ in gone:
            g_[2] += 1 / v.fps
        gone = [g_ for g_ in gone if g_[2] < 0.35][-40:]
        peak = max(peak, len(balls))

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            for x, y, col, age in rings:
                v.circle(mix((0, 0, 0), col, 0.5 * (1 - age / 0.6)), (x, y), 14 + 110 * age / 0.6, width=2)
            for x, y, age in gone:                             # 消えた所に、小さな赤いばつ印
                c_ = mix((255, 70, 70), (0, 0, 0), age / 0.35)
                d_ = 9 + 30 * age
                pygame.draw.line(v.surf, c_, (x - d_, y - d_), (x + d_, y + d_), 3)
                pygame.draw.line(v.surf, c_, (x - d_, y + d_), (x + d_, y - d_), 3)
            if done_at is None:
                m["frame"](v)
            for body, _c, col, _n in balls:
                x, y = body.position.x, body.position.y
                if -30 < x < 1110 and -30 < y < 1950:
                    v.circle(col, (x, y), br)
                    v.circle(mix(col, (255, 255, 255), 0.6), (x - 3, y - 3), 3)
            m["draw"](v, t)
            v.text(caption, 100, (CX, 250))
            v.text(f"{len(balls)}", 150, (CX, bottom))
        v.end(glow=0.28)
        if done_at is not None and v.t - done_at > 2.3:
            break
        if v.t > 80:
            break
    return {"result": f"1 -> {len(balls)} balls"}


# ------------------------------------------------------------------ hammer: ピストンが壁を叩く
def _mech_hammer(sp, rng, br):
    half = 390.0
    walls = _box(sp, half)
    hw, hd = 330.0, 76.0                       # ピストンの頭の幅（壁沿い）と厚み
    d_min, d_max = hd / 2 + 2 * br - 5, 245.0  # 頭の中心から壁までの距離（叩いたときは、すき間がボールの直径より少し狭い）
    inward = [(0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)]      # 上・右・下・左の壁から箱の内側へ向かう向き
    T = rng.uniform(1.05, 1.2)                 # 1 回叩く周期。左右とも同じで、半拍ずらして交互に叩く
    spots = [-(half - hw / 2 - 6), 0.0, half - hw / 2 - 6]            # 叩く場所は 上・中・下 の 3 か所
    order = [0, 1, 2, 1]                       # 上 → 中 → 下 → 中 → … と順番に動く
    heads = []
    for i, k in enumerate((1, 3)):             # 左右の壁に 1 本ずつ（4 本にすると、引いたときに中央で重なって見づらい）
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        shape = pymunk.Poly.create_box(body, (hd, hw))
        shape.elasticity, shape.friction = 1.0, 0.0
        sp.add(body, shape)
        heads.append({"body": body, "n": inward[k], "phase": i * T / 2, "shift": i * 2, "d": d_max, "hit": -1})

    def spot(h, cyc):
        return spots[order[(cyc + h["shift"]) % len(order)]]

    def place(h, t):
        u_all = (t + h["phase"]) / T
        cyc, u = int(u_all), u_all % 1.0
        s0, s1 = spot(h, cyc - 1), spot(h, cyc)
        if u < 0.5:                            # 引いた位置で、次の場所へ横に動く
            d, s_ = d_max, s0 + (s1 - s0) * _smooth(u / 0.5)
        elif u < 0.68:                         # 叩く（だんだん速く）
            d, s_ = d_max - (d_max - d_min) * ((u - 0.5) / 0.18) ** 2, s1
        elif u < 0.8:                          # 押しつけたまま少し止まる
            d, s_ = d_min, s1
        else:                                  # 引く
            d, s_ = d_min + (d_max - d_min) * _smooth((u - 0.8) / 0.2), s1
        nx, ny = h["n"]
        h["d"] = d
        return (CX - nx * (half - d) - ny * s_, CY - ny * (half - d) + nx * s_)

    def sound(v, t):
        for h in heads:                        # 壁を叩いた瞬間に、低い音を 1 つ（左右で高さを変える）
            cyc = int((t + h["phase"]) / T - 0.68)
            if (t + h["phase"]) / T >= 0.68 and cyc != h["hit"]:
                h["hit"] = cyc
                v.audio.play(t, 96 if h["n"][0] > 0 else 128, 0.5, "thud")

    def update(t, fdt):
        for h in heads:
            _follow(h["body"], place(h, t + fdt), fdt)

    def frame(v):
        pygame.draw.rect(v.surf, (245, 245, 245), (CX - half - 3, CY - half - 3, 2 * half + 6, 2 * half + 6), 5)

    def draw(v, t):
        for h in heads:
            x, y = h["body"].position
            nx, ny = h["n"]
            pygame.draw.line(v.surf, GREY_DARK, (x, y), (x + nx * 118, y + ny * 118), 26)       # 柄
            pygame.draw.line(v.surf, GREY, (x, y), (x + nx * 118, y + ny * 118), 14)
            w, d = hd, hw
            flash = max(0.0, 1 - (h["d"] - d_min) / 60)                                          # 壁に近いほど明るい
            pygame.draw.rect(v.surf, GREY_DARK, (int(x - w / 2), int(y - d / 2), int(w), int(d)), border_radius=12)
            pygame.draw.rect(v.surf, mix(GREY, (255, 255, 255), 0.5 * flash),
                             (int(x - w / 2 + 6), int(y - d / 2 + 6), int(w - 12), int(d - 12)), border_radius=8)

    return {"walls": walls, "clamp": _box_clamp(half, br), "update": update, "frame": frame, "draw": draw,
            "sound": sound, "start": (CX + rng.uniform(-80, 80), CY + rng.uniform(-80, 80))}


def run_hammer(v, rng):
    return _run(v, rng, _mech_hammer, "Smashed = x2")


# ------------------------------------------------------------------ cam: 3 つのローラーが壁ぎわを回る
def _mech_cam(sp, rng, br):
    """円の中心から 3 本の腕が伸び、先のローラーが壁すれすれを回る。ローラーと壁にはさまれたボールが割れる。
    壁ぎわにいないボールは逃げられるので、増えるかどうかは決まっていない。回転はだんだん速くなる。"""
    R = 430.0
    walls = _ring(sp, (CX, CY), R, n=160, thick=5.0, elasticity=1.0, friction=0.0)
    rr = 92.0                                   # ローラーの半径
    orbit = R - 5 - rr - (2 * br - 5)           # ローラーの中心が回る半径（壁とのすき間はボールの直径より少し狭い）
    sign = rng.choice((-1, 1))
    w0, w1, ramp = 1.5, 2.6, 30.0  # 回る速さ（ラジアン/秒）: 最初 → 最後、何秒かけて上げるか
    state = {"a": rng.uniform(0, math.tau), "w": w0, "flash": [0.0, 0.0, 0.0]}
    rollers = []
    for k in range(3):
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        shape = pymunk.Circle(body, rr)
        shape.elasticity, shape.friction = 1.0, 0.0
        sp.add(body, shape)
        rollers.append(body)

    def centre(k, a):
        aa = a + k * math.tau / 3
        return (CX + math.cos(aa) * orbit, CY + math.sin(aa) * orbit)

    def update(t, fdt):
        state["w"] = w0 + (w1 - w0) * min(1.0, t / ramp)
        nxt = state["a"] + sign * state["w"] * fdt
        for k, body in enumerate(rollers):
            body.position = centre(k, state["a"])              # 位置は毎コマ合わせ直し、次のコマへの動きは速度で与える
            _follow(body, centre(k, nxt), fdt)
            body.angular_velocity = -sign * state["w"] * orbit / rr      # 壁の上を転がっているように回す
        state["a"] = nxt
        state["flash"] = [max(0.0, f - fdt) for f in state["flash"]]

    def split(x, y, n, vel, rng_):
        # ローラーの後ろ側（通り過ぎた側）へ 2 つとも飛ばす。前へ飛ばすと、すぐ追いつかれてまた潰される
        a = math.atan2(y - CY, x - CX)
        k = min(range(3), key=lambda i: math.hypot(x - rollers[i].position.x, y - rollers[i].position.y))
        state["flash"][k] = 0.18
        back = (math.sin(a) * sign, -math.cos(a) * sign)       # 回る向きと逆
        inward = (-math.cos(a), -math.sin(a))
        out = []
        for mix_in in (0.15, 0.75):
            dx, dy = back[0] + inward[0] * mix_in, back[1] + inward[1] * mix_in
            d = math.hypot(dx, dy)
            out += [(x + back[0] * 14 + inward[0] * 4, y + back[1] * 14 + inward[1] * 4),
                    (dx / d * 560, dy / d * 560)]
        return tuple(out)

    def frame(v):
        v.circle((245, 245, 245), (CX, CY), R + 3, width=5)

    def draw(v, t):
        for body in rollers:
            pygame.draw.line(v.surf, GREY_DARK, (CX, CY), body.position, 30)
        for body in rollers:
            pygame.draw.line(v.surf, GREY, (CX, CY), body.position, 16)
        for k, body in enumerate(rollers):
            x, y = body.position
            lit = state["flash"][k] / 0.18
            v.circle(GREY_DARK, (x, y), rr)
            v.circle(mix(GREY, (255, 255, 255), 0.6 * lit), (x, y), rr - 8)
            v.circle(GREY_DARK, (x, y), rr - 34)
            for i in range(4):                  # 転がっているのが分かる模様
                a = body.angle + i * math.tau / 4
                v.circle((0, 0, 0), (x + math.cos(a) * (rr - 58), y + math.sin(a) * (rr - 58)), 11)
            v.circle(GREY, (x, y), 13)
        v.circle((225, 225, 228), (CX, CY), 34)
        v.circle((60, 60, 66), (CX, CY), 13)

    return {"walls": walls, "clamp": _circle_clamp(R, br), "update": update, "frame": frame, "draw": draw,
            "split": split, "start": (CX + rng.uniform(-40, 40), CY + rng.uniform(-40, 40)),
            "speed": (300.0, 600.0), "wait": (0.55, 0.85), "per_frame": 14}


def run_cam(v, rng):
    return _run(v, rng, _mech_cam, "Pinched = x2", cap=320, bottom=CY + 620)


# ------------------------------------------------------------------ survive: 潰されたらライフが減る生き残り戦
SURVIVORS = [("RED", (255, 77, 90)), ("BLUE", (61, 139, 255)), ("GREEN", (61, 220, 132)), ("YELLOW", (255, 201, 60)),
             ("PURPLE", (178, 102, 255)), ("ORANGE", (255, 140, 50))]


def _run_survive(v, rng, mech, lives=3, br=26.0, bottom=CY + 640, caption="Squeezed = -1 life"):
    """6 色のボールが同じ仕掛けの中を逃げ回る。はさまれて潰されるたびにライフが 1 減り、0 になると消える。
    最後まで残った 1 個が勝ち。潰された判定は増える型（_run）と同じ。"""
    sp = _space(gravity=0.0)
    sp.iterations = 12
    m = mech(sp, rng, br)
    names = SURVIVORS[:]
    rng.shuffle(names)
    lo, hi = m.get("speed", (300.0, 600.0))
    balls = []                                 # [body, shape, 番号, ライフ, 次に潰されてよい時刻]
    for i in range(len(names)):
        a = i * math.tau / len(names) + rng.uniform(-0.2, 0.2)
        d = rng.uniform(40, 120)
        va = rng.uniform(0, math.tau)
        b, c = _ball(sp, (CX + math.cos(a) * d, CY + math.sin(a) * d), br,
                     vel=(math.cos(va) * 420, math.sin(va) * 420), elasticity=1.0, friction=0.0)
        balls.append([b, c, i, lives, 1.5])
    hp = [lives] * len(names)
    out_order = []                             # 脱落した順
    pops = []                                  # 潰された瞬間の輪 [x, y, 色, 経過, 脱落か]
    n_steps, dt = _steps(v)
    done_at = None
    while True:
        t = v.t
        m["update"](t, 1.0 / v.fps)
        if "sound" in m and done_at is None:
            m["sound"](v, t)
        for _ in range(n_steps):
            sp.step(dt)
        if done_at is None:
            for item in list(balls):
                body = item[0]
                if t >= item[4]:
                    touch = []
                    body.each_arbiter(lambda arb, touch=touch: touch.append(
                        (arb.normal.x, arb.normal.y, arb.shapes[1].body.body_type == pymunk.Body.KINEMATIC))
                        if arb.shapes[1].body.body_type != pymunk.Body.DYNAMIC else None)
                    pinch = None
                    for i in range(len(touch)):
                        for j in range(i + 1, len(touch)):
                            p, q = touch[i], touch[j]
                            if (p[2] or q[2]) and p[0] * q[0] + p[1] * q[1] < -0.45:
                                pinch = (p[0] - q[0], p[1] - q[1])
                    if pinch is not None:
                        d = math.hypot(*pinch) or 1.0
                        n = (pinch[0] / d, pinch[1] / d)
                        x, y = body.position.x, body.position.y
                        if "split" in m:
                            p1, v1, _p2, _v2 = m["split"](x, y, n, body.velocity, rng)
                        else:
                            tx, ty = -n[1], n[0]
                            s_ = rng.choice((-1, 1))
                            p1, v1 = (x + s_ * tx * 6, y + s_ * ty * 6), (s_ * tx * 560, s_ * ty * 560)
                        item[3] -= 1
                        hp[item[2]] = item[3]
                        item[4] = t + 1.2
                        col = names[item[2]][1]
                        if item[3] <= 0:
                            pops.append([x, y, col, 0.0, True])
                            sp.remove(body, item[1])
                            balls.remove(item)
                            out_order.append(item[2])
                            v.audio.play(t, 300, 0.7, "pop")
                            v.audio.note(t, 45 + 2 * len(out_order), 0.6, "piano", dur=0.6)
                        else:
                            pops.append([x, y, col, 0.0, False])
                            body.position, body.velocity = p1, v1
                            v.audio.play(t, 150, 0.55, "thud", channel="h", min_gap=0.05)
            for item in balls:
                body = item[0]
                x, y = body.position.x, body.position.y
                nx_, ny_ = m["clamp"](x, y)
                if nx_ != x or ny_ != y:
                    vx_, vy_ = body.velocity
                    if (x - nx_) * vx_ > 0:
                        vx_ = -vx_
                    if (y - ny_) * vy_ > 0:
                        vy_ = -vy_
                    body.position, body.velocity = (nx_, ny_), (vx_, vy_)
                spd = body.velocity.length
                if spd > hi:
                    body.velocity = body.velocity * (hi / spd)
                elif spd < lo:
                    a = rng.uniform(0, math.tau)
                    body.velocity = (math.cos(a) * (lo + 60), math.sin(a) * (lo + 60))
            if len(balls) <= 1:
                done_at = t
                for i, mm in enumerate((60, 64, 67, 72, 76)):
                    v.audio.note(t + 0.07 * i, mm, 0.8, "piano")
        for p_ in pops:
            p_[3] += 1 / v.fps
        pops = [p_ for p_ in pops if p_[3] < 0.6]

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            m["frame"](v)
            for x, y, col, age, dead in pops:
                k = age / 0.6
                v.circle(mix(col, (0, 0, 0), k), (x, y), br + (220 if dead else 110) * k, width=5 if dead else 3)
            for body, _c, idx, life, cool in balls:
                x, y = body.position.x, body.position.y
                col = names[idx][1]
                blink = t < cool and int(t * 14) % 2 == 0      # 潰された直後は点滅（この間はもう一度潰されない）
                v.circle((255, 255, 255), (x, y), br + 3)
                v.circle(mix(col, (255, 255, 255), 0.55) if blink else col, (x, y), br)
                v.text(str(life), 40, (x, y + 1), outline=3)
            m["draw"](v, t)
            v.text(caption, 92, (CX, 170))
            # 上の一覧: 色ごとの残りライフ（脱落した色は暗くなる）
            for i, (name, col) in enumerate(names):
                px = CX - (len(names) - 1) * 80 + i * 160
                alive = hp[i] > 0
                v.circle(col if alive else mix((0, 0, 0), col, 0.25), (px, 272), 24)
                for k in range(lives):
                    c2 = col if k < hp[i] else (46, 48, 58)
                    wd = 110 / lives
                    pygame.draw.rect(v.surf, c2, (int(px - 55 + k * wd), 308, int(wd - 5), 9), border_radius=3)
            if done_at is not None and balls:
                w = balls[0][2]
                v.text(f"{names[w][0]} WINS", 150, (CX, bottom - 30), color=names[w][1], outline=7)
            else:
                v.text(f"{len(balls)} left", 110, (CX, bottom))
        v.end(glow=0.28)
        if done_at is not None and v.t - done_at > 2.6:
            break
        if v.t > 80:
            break
    winner = names[balls[0][2]][0] if balls else "nobody"
    return {"result": f"{winner} wins, {len(out_order)} out", "winner": winner}


def run_survive(v, rng):
    return _run_survive(v, rng, _mech_cam, lives=5)


def run_smash(v, rng):
    return _run_survive(v, rng, _mech_hammer, lives=4, caption="Smashed = -1 life")


# ------------------------------------------------------------------ hexarms: 六角形の中で 3 本のアームが回る
def _mech_hexarms(sp, rng, br):
    """arms の別バージョン。六角形の角 3 つに C 字のアームが付いて回る。アームと壁にはさまれたボールが割れる。"""
    Rh = 450.0
    verts = [(CX + math.cos(math.radians(-90 + 60 * i)) * Rh, CY + math.sin(math.radians(-90 + 60 * i)) * Rh)
             for i in range(6)]
    walls = []
    for p, q in zip(verts, verts[1:] + verts[:1]):
        seg = pymunk.Segment(sp.static_body, p, q, 4)
        seg.elasticity, seg.friction = 1.0, 0.0
        sp.add(seg)
        walls.append(seg)
    # 各辺の「内向きの向き」と辺上の 1 点（枠の外へ出かけた球を戻すのに使う）
    edges = []
    for p, q in zip(verts, verts[1:] + verts[:1]):
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        d = math.hypot(CX - mx, CY - my)
        edges.append((mx, my, (CX - mx) / d, (CY - my) / d))

    def clamp(x, y):
        for mx, my, nx, ny in edges:
            depth = (x - mx) * nx + (y - my) * ny - (4 + br)
            if depth < 0:
                x, y = x - nx * depth, y - ny * depth
        return x, y

    rho, span, n_seg = 190.0, 3.5, 16
    arms = []
    for k, i in enumerate((0, 2, 4)):
        turn = 1 if k % 2 == 0 else -1
        rotor = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        rotor.position = verts[i]
        rotor.angle = rng.uniform(0, math.tau)
        rotor.angular_velocity = turn * rng.uniform(2.6, 3.2)
        # 逆回りのアームは形も鏡写しにする（どのアームも、回る向きに対して同じ側ですくう）
        pts = [(rho + math.cos(math.pi + turn * span * j / n_seg) * rho, math.sin(math.pi + turn * span * j / n_seg) * rho)
               for j in range(n_seg + 1)]
        sp.add(rotor)
        for p, q in zip(pts[:-1], pts[1:]):
            seg = pymunk.Segment(rotor, p, q, 8)
            seg.elasticity, seg.friction = 1.0, 0.0
            sp.add(seg)
        arms.append((rotor, pts))

    def update(t, fdt):
        pass                                    # アームは一定の速さで回り続ける

    def frame(v):
        pygame.draw.lines(v.surf, (245, 245, 245), True, verts, 5)

    def draw(v, t):
        for rotor, pts in arms:
            ca, sa = math.cos(rotor.angle), math.sin(rotor.angle)
            px, py = rotor.position
            world = [(px + x * ca - y * sa, py + x * sa + y * ca) for x, y in pts]
            pygame.draw.lines(v.surf, GREY_DARK, False, world, 20)
            pygame.draw.lines(v.surf, GREY, False, world, 12)
            v.circle(GREY, (px, py), 16)
            v.circle((60, 60, 66), (px, py), 7)

    return {"walls": walls, "clamp": clamp, "update": update, "frame": frame, "draw": draw,
            "start": (CX + rng.uniform(-60, 60), CY + rng.uniform(-60, 60))}


def run_hexarms(v, rng):
    return _run(v, rng, _mech_hexarms, "Squeezed = x2", bottom=CY + 640)


# ------------------------------------------------------------------ beams: 緑の光線で 2 倍、赤の光線で消える
def _mech_beams(sp, rng, br):
    """円の中心から 2 本の光線が伸びて、別々の速さで回る。緑に触れたボールは 2 つに割れ、赤に触れたボールは消える。
    赤は緑より短いので、全体としては増えていく（増えたり減ったりしながら上限へ向かう）。"""
    R = 440.0
    walls = _ring(sp, (CX, CY), R, n=140, thick=5.0, elasticity=1.0, friction=0.0)
    wg = rng.choice((-1, 1)) * rng.uniform(1.5, 1.8)            # 緑が回る速さ（ラジアン/秒）
    wr = -math.copysign(rng.uniform(0.8, 1.0), wg)              # 赤は逆向きに回る
    ag0, ar0 = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
    len_g, len_r = R - 8, R * BEAM_RED                          # 緑は端から端まで（中心の両側）、赤は片側だけで短い
    state = {"t": 0.0}

    def tip(a0, w, length, t):
        a = a0 + w * t
        return (CX + math.cos(a) * length, CY + math.sin(a) * length), (math.cos(a), math.sin(a))

    def near(x, y, a0, w, length, t, width, both=False):
        _p, (ux, uy) = tip(a0, w, length, t)
        rx, ry = x - CX, y - CY
        along = rx * ux + ry * uy
        if both:
            along = abs(along)
        return 26 < along < length and abs(rx * uy - ry * ux) < width

    def update(t, fdt):
        state["t"] = t

    def pinched(x, y):
        if near(x, y, ag0, wg, len_g, state["t"], br + 5, both=True):
            _p, (ux, uy) = tip(ag0, wg, len_g, state["t"])
            return (-uy, ux)                    # 光線と直角の向き（2 つに割れて、光線に沿って前後へ飛ぶ）
        return None

    def kill(x, y):
        return near(x, y, ar0, wr, len_r, state["t"], br + 4)

    def frame(v):
        v.circle((245, 245, 245), (CX, CY), R + 3, width=5)

    def draw(v, t):
        for a0, w, length, col, both in ((ag0, wg, len_g, (60, 255, 120), True), (ar0, wr, len_r, (255, 60, 70), False)):
            p, _u = tip(a0, w, length, t)
            q = (2 * CX - p[0], 2 * CY - p[1]) if both else (CX, CY)
            pygame.draw.line(v.surf, mix((0, 0, 0), col, 0.35), q, p, 18)
            pygame.draw.line(v.surf, col, q, p, 8)
            pygame.draw.line(v.surf, (255, 255, 255), q, p, 2)
            v.circle(col, p, 9)
            if both:
                v.circle(col, q, 9)
        v.circle((225, 225, 228), (CX, CY), 22)
        v.circle((60, 60, 66), (CX, CY), 9)

    a = rng.uniform(0, math.tau)
    return {"walls": walls, "clamp": _circle_clamp(R, br), "update": update, "frame": frame, "draw": draw,
            "pinched": pinched, "kill": kill, "start": (CX + math.cos(a) * 300, CY + math.sin(a) * 300),
            "speed": (300.0, 560.0), "wait": (0.55, 0.85), "per_frame": 16}


def run_beams(v, rng):
    return _run(v, rng, _mech_beams, "GREEN = x2   RED = gone", cap=300, bottom=CY + 640)
