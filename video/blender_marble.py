"""blender_marble.py — 3D マーブルレースを Blender（bpy）で作る。

壁掛けのコースを上から下へ転がる。ギミック（ジグザグ坂・釘の板・回る羽根・じょうご・階段・
振り子ハンマー・水車）の順番と細かい配置はシードごとに変わる。

  python video/blender_marble.py --seed 3 --out DIR [--quality final|preview|none] [--step N]

出力: DIR/f_0001.png ...（コマ画像）と DIR/race.json（各コマのビー玉の位置・順位・当たりの強さ）。
文字や音は入れない。あとで sims_3d.py が race.json を読んで、文字と音を重ねて動画にする。
"""

import argparse
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

FPS = 30
HALF = 4.0            # コースの内側の半分の幅
DEPTH = 1.05          # 奥行き（手前の見えないガラスと奥の板のあいだ）
MR = 0.24             # ビー玉の半径
# 画面で見せたい色（0〜255）。順位表示の丸も同じ色を使うので、ビー玉と丸の色がずれない
NAMES = [("RED", (228, 32, 44)), ("BLUE", (44, 104, 236)), ("GREEN", (46, 190, 84)),
         ("YELLOW", (250, 208, 44)), ("PURPLE", (150, 74, 232)), ("ORANGE", (250, 132, 30)),
         ("CYAN", (40, 200, 226)), ("PINK", (250, 118, 186))]


def linear(c):
    """画面の色（0〜255）を、Blender の材質に渡す値へ直す。"""
    return tuple((x / 255.0) ** 2.2 for x in c)


# ------------------------------------------------------------------ 部品づくり
def material(name, color, rough=0.4, metallic=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1.0)
        b.inputs["Emission Strength"].default_value = emit
    return m


def rigid(ob, kind="PASSIVE", shape="BOX", friction=0.5, bounce=0.6, mass=1.0, kinematic=False):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.rigidbody.object_add(type=kind)
    rb = ob.rigid_body
    rb.collision_shape = shape
    rb.friction, rb.restitution = friction, bounce
    rb.collision_margin = 0.01 if kind == "PASSIVE" else 0.02
    if kind == "ACTIVE":
        rb.mass = mass
        rb.linear_damping, rb.angular_damping = 0.02, 0.05
        rb.use_deactivation = False
    if kinematic:
        rb.kinematic = True
    ob.select_set(False)
    return ob


def box(name, loc, size, mat, rot_y=0.0, solid=True, hide=False, kinematic=False, bounce=0.6, friction=0.5):
    """size は (x 幅, y 奥行き, z 高さ)。rot_y が正だと右下がり。"""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=(0.0, rot_y, 0.0))
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat is not None:
        ob.data.materials.append(mat)
    if hide:
        ob.hide_render = True
    if solid:
        rigid(ob, kinematic=kinematic, bounce=bounce, friction=friction)
    return ob


def bevel(ob, width=0.04):
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width, mod.segments = width, 2
    return ob


def peg(loc, mat, radius=0.11):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=DEPTH, vertices=20, location=loc,
                                        rotation=(math.pi / 2, 0.0, 0.0))
    ob = bpy.context.object
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    rigid(ob, shape="CONVEX_HULL", bounce=0.85, friction=0.3)
    return ob


def drive(ob, path, index, expr):
    """コマ番号 frame だけで決まる動き（回転・往復）。キーを打たずに式で動かす。"""
    fc = ob.driver_add(path, index)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = expr


def ramp(x0, x1, z_at_x0, angle, mat, thick=0.22, name="ramp", bounce=0.5):
    """x0 から x1 までの坂。angle が正だと右下がり。上の面が (x0, z_at_x0) を通る。"""
    length = (x1 - x0) / math.cos(angle)
    cx = (x0 + x1) / 2
    cz = z_at_x0 - math.tan(angle) * (cx - x0) - thick / 2 / math.cos(angle)
    return bevel(box(name, (cx, 0.0, cz), (length, DEPTH, thick), mat, rot_y=angle, bounce=bounce))


# ------------------------------------------------------------------ ギミック（上端 z を受け取り、下端 z を返す）
def mod_zigzag(z, rng, M):
    n = rng.choice([2, 3])
    side = rng.choice([-1, 1])
    ang = math.radians(rng.uniform(11, 15))
    for _ in range(n):
        gap = rng.uniform(1.1, 1.5)
        if side < 0:      # 左の壁から右下がり
            ramp(-HALF, HALF - gap, z - 0.6, ang, M["white"])
        else:             # 右の壁から左下がり
            ramp(-HALF + gap, HALF, z - 0.6 - math.tan(ang) * (2 * HALF - gap), -ang, M["white"])
        z -= 0.6 + math.tan(ang) * (2 * HALF - gap) + 0.95
        side = -side
    return z - 0.3


def mod_plinko(z, rng, M):
    rows = rng.choice([5, 6, 7])
    sx, sz = 1.0, 0.82
    z -= 0.9
    for r in range(rows):
        if r % 2 == 0:
            xs = [-3.0 + sx * k for k in range(7)]
        else:                       # 壁ぎわは釘の代わりに小さな斜面（釘と壁のあいだにはさまらないように）
            xs = [-2.5 + sx * k for k in range(6)]
            ramp(-HALF, -HALF + 0.55, z + 0.35, math.radians(38), M["gold"], thick=0.12)
            ramp(HALF - 0.55, HALF, z + 0.35 - math.tan(math.radians(38)) * 0.55, -math.radians(38), M["gold"], thick=0.12)
        for x in xs:
            peg((x, 0.0, z), M["gold"])
        z -= sz
    return z - 0.2


def mod_spinners(z, rng, M):
    z -= 2.3
    w = rng.uniform(1.6, 2.3)
    for sx in (-1, 1):
        a0 = rng.uniform(0, math.pi)
        for k in range(2):
            bar = bevel(box("spinner", (sx * 2.0, 0.0, z), (2.8, DEPTH * 0.9, 0.2), M["red"], kinematic=True,
                            bounce=0.4))
            drive(bar, "rotation_euler", 1, f"{a0 + k * math.pi / 2:.4f} + {sx * w:.4f} * frame / {FPS}")
        hub = peg((sx * 2.0, -0.02, z), M["dark"], radius=0.22)
        hub.scale = (1.0, 1.0, 1.06)
    return z - 2.3


def mod_funnel(z, rng, M):
    ang = math.radians(rng.uniform(19, 24))
    gap = rng.uniform(1.25, 1.4)                # ビー玉 2.6〜2.9 個ぶん。これより狭いと詰まる
    c = rng.uniform(-1.2, 1.2)
    tan = math.tan(ang)
    z_lip = z - 0.5 - tan * max(c - gap / 2 + HALF, HALF - c - gap / 2)      # すき間のふちの高さ（左右同じ）
    ramp(-HALF, c - gap / 2, z_lip + tan * (c - gap / 2 + HALF), ang, M["blue"])
    ramp(c + gap / 2, HALF, z_lip, -ang, M["blue"])
    peg((c + rng.uniform(-0.12, 0.12), 0.0, z_lip - 1.5), M["gold"], radius=0.3)      # 落ちてきた玉を左右に散らす
    return z_lip - 2.6


def mod_stairs(z, rng, M):
    side = rng.choice([-1, 1])
    n, sw, sh = 8, 0.84, 0.42
    z -= 0.7
    tilt = math.radians(6)
    for i in range(n):
        x0 = -HALF + i * sw
        zz = z - i * sh
        if side < 0:
            ramp(x0, x0 + sw + 0.02, zz, tilt, M["green"], thick=0.3, bounce=0.35)
        else:
            ramp(-x0 - sw - 0.02, -x0, zz - math.tan(tilt) * 0, -tilt, M["green"], thick=0.3, bounce=0.35)
    return z - n * sh - 0.9


def mod_hammer(z, rng, M):
    side = rng.choice([-1, 1])
    ang = math.radians(rng.uniform(9, 12))
    gap = 1.3
    top = z - 3.3
    if side < 0:
        ramp(-HALF, HALF - gap, top, ang, M["white"])
    else:
        ramp(-HALF + gap, HALF, top - math.tan(ang) * (2 * HALF - gap), -ang, M["white"])
    for k, px in enumerate((-1.9, 1.7)):
        pivot_z = z - 0.4
        length = 2.2
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px, 0.0, pivot_z))
        arm = bpy.context.object
        arm.name = "hammer"
        for vtx in arm.data.vertices:            # 原点（軸）から下へ伸びる棒にする
            vtx.co = Vector((vtx.co.x * 0.16, vtx.co.y * DEPTH * 0.8, vtx.co.z * length - length / 2))
        arm.data.materials.append(M["dark"])
        rigid(arm, shape="CONVEX_HULL", kinematic=True, bounce=0.3)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.36, depth=DEPTH * 0.8, vertices=24, location=(px, 0.0, pivot_z),
                                            rotation=(math.pi / 2, 0.0, 0.0))
        head = bpy.context.object
        head.name = "hammer_head"
        bpy.ops.object.shade_smooth()
        for vtx in head.data.vertices:
            vtx.co.y -= 0.0
        head.data.materials.append(M["red"])
        head.parent = arm
        head.location = (0.0, 0.0, -length)
        rigid(head, shape="CONVEX_HULL", kinematic=True, bounce=0.5)
        ph = rng.uniform(0, math.tau)
        drive(arm, "rotation_euler", 1, f"0.95 * sin({ph:.3f} + {rng.uniform(2.6, 3.3):.3f} * frame / {FPS})")
        peg((px, -0.02, pivot_z), M["gold"], radius=0.16)
    return top - math.tan(ang) * (2 * HALF - gap) - 1.4


def mod_wheel(z, rng, M):
    rad = 2.7
    z -= rad + 0.5
    w = rng.choice([-1, 1]) * rng.uniform(0.9, 1.2)
    a0 = rng.uniform(0, math.pi)
    for k in range(3):
        bar = bevel(box("wheel", (0.0, 0.0, z), (2 * rad, DEPTH * 0.9, 0.2), M["purple"], kinematic=True, bounce=0.3))
        drive(bar, "rotation_euler", 1, f"{a0 + k * math.pi / 3:.4f} + {w:.4f} * frame / {FPS}")
    hub = peg((0.0, -0.02, z), M["gold"], radius=0.34)
    hub.scale = (1.0, 1.0, 1.06)
    # 壁ぎわを素通りしないよう、左右に小さな出っ張り
    for sx in (-1, 1):
        ramp(sx * HALF if sx < 0 else HALF - 0.9, -HALF + 0.9 if sx < 0 else HALF, z + rad + 0.2 - (0 if sx < 0 else 0.4),
             sx * -math.radians(24), M["white"])
    return z - rad - 0.4


MODULES = {"zigzag": mod_zigzag, "plinko": mod_plinko, "spinners": mod_spinners, "funnel": mod_funnel,
           "stairs": mod_stairs, "hammer": mod_hammer, "wheel": mod_wheel}


# ------------------------------------------------------------------ 場面全体
def build(seed, n_marbles=8):
    rng = random.Random(seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world
    rw.substeps_per_frame = 24
    rw.solver_iterations = 24
    if rw.collection is None:
        rw.collection = bpy.data.collections.new("rigid")
        sc.collection.children.link(rw.collection)

    M = {"white": material("white", (0.92, 0.90, 0.86), 0.5), "gold": material("gold", (1.0, 0.72, 0.22), 0.25, 1.0),
         "red": material("red", (0.90, 0.12, 0.12), 0.35), "blue": material("blue", (0.15, 0.42, 0.90), 0.4),
         "green": material("green", (0.18, 0.68, 0.36), 0.45), "purple": material("purple", (0.55, 0.25, 0.85), 0.4),
         "dark": material("dark", (0.10, 0.11, 0.14), 0.4), "board": material("board", (0.16, 0.19, 0.27), 0.7),
         "wall": material("wall", (0.30, 0.34, 0.44), 0.6), "finish": material("finish", (1.0, 1.0, 1.0), 0.5, emit=0.6)}

    order = ["zigzag", "plinko", "spinners", "funnel", "stairs", "hammer", "wheel"]
    rng.shuffle(order)
    extra = rng.choice(["plinko", "zigzag", "spinners"])      # 7 種類ぜんぶ＋どれか 1 つをもう一度
    spot = rng.randrange(len(order) + 1)
    if (spot > 0 and order[spot - 1] == extra) or (spot < len(order) and order[spot] == extra):
        spot = (order.index(extra) + 3) % (len(order) + 1)
    order.insert(spot, extra)
    # ---- スタート台（ゲートが上がると一斉に転がり出す）
    z = 0.0
    start_ang = math.radians(14)
    side = rng.choice([-1, 1])
    if side < 0:
        ramp(-HALF, 1.2, z, start_ang, M["white"], name="start")
    else:
        ramp(-1.2, HALF, z - math.tan(start_ang) * (HALF + 1.2), -start_ang, M["white"], name="start")
    gate_x = side * -1.25 * -1                     # ゲートは坂の下端の手前
    gate_x = 0.95 * (1 if side < 0 else -1)
    gate_z = z - math.tan(start_ang) * (gate_x + HALF if side < 0 else HALF - gate_x) + 0.6
    gate = box("gate", (gate_x, 0.0, gate_z), (0.16, DEPTH, 1.3), M["red"], kinematic=True)
    drive(gate, "location", 2, f"{gate_z:.4f} + min(2.2, max(0.0, (frame - {FPS}) * 0.12))")
    names = NAMES[:n_marbles]
    slots = list(range(n_marbles))
    rng.shuffle(slots)
    marbles = []
    for i, (nm, col) in enumerate(names):
        s = slots[i]
        row, colm = s // 4, s % 4
        d = 0.5 + colm * 0.54 + (0.27 if row else 0.0)                 # ゲートからの距離
        x = gate_x - d if side < 0 else gate_x + d
        zz = z - math.tan(start_ang) * (x + HALF if side < 0 else HALF - x) + MR + 0.02 + row * 0.47
        bpy.ops.mesh.primitive_uv_sphere_add(radius=MR, segments=28, ring_count=14,
                                             location=(x, rng.uniform(-0.12, 0.12), zz))
        ob = bpy.context.object
        ob.name = nm
        bpy.ops.object.shade_smooth()
        ob.data.materials.append(material(nm, linear(col), 0.18))
        rigid(ob, "ACTIVE", "SPHERE", friction=0.45, bounce=0.5)
        marbles.append(ob)
    z -= math.tan(start_ang) * (HALF + 1.2) + 1.3
    layout = []
    for name in order:
        z_top = z
        z = MODULES[name](z, rng, M)
        layout.append((name, round(z_top, 2), round(z, 2)))
    # ---- ゴール（中央へ集めて、線を越えたら順位が決まる）
    ang = math.radians(20)
    z -= 0.4
    ramp(-HALF, -0.8, z, ang, M["white"])
    ramp(0.8, HALF, z - math.tan(ang) * (HALF - 0.8), -ang, M["white"])
    z_finish = z - math.tan(ang) * (HALF - 0.8) - 0.9
    box("finish_line", (0.0, DEPTH / 2 - 0.03, z_finish), (2 * HALF, 0.04, 0.22), M["finish"], solid=False)
    z_floor = z_finish - 3.2
    box("floor", (0.0, 0.0, z_floor), (2 * HALF + 1, DEPTH, 0.4), M["wall"], bounce=0.2)
    # ---- 壁・奥の板・手前の見えないガラス
    top, bottom = 3.5, z_floor - 1.0
    mid, height = (top + bottom) / 2, top - bottom
    for sx in (-1, 1):
        box("side", (sx * (HALF + 0.2), 0.0, mid), (0.4, DEPTH + 0.1, height), M["wall"], bounce=0.5)
    box("board", (0.0, DEPTH / 2 + 0.1, mid - 8), (2 * HALF + 6.0, 0.2, height + 22), M["board"], bounce=0.3)
    box("glass", (0.0, -DEPTH / 2 - 0.1, mid), (2 * HALF + 1.0, 0.2, height), None, hide=True, bounce=0.3, friction=0.1)
    return sc, marbles, {"layout": layout, "z_finish": z_finish, "z_floor": z_floor, "names": [n for n, _c in names],
                         "colors": [c for _n, c in names]}


def simulate(sc, marbles, info, max_seconds=75):
    """物理を最後まで回して、各コマの位置を記録する。"""
    rw = sc.rigidbody_world
    last = int(max_seconds * FPS)
    sc.frame_start, sc.frame_end = 1, last
    rw.point_cache.frame_start, rw.point_cache.frame_end = 1, last
    frames, finish = [], {}
    still = [0] * len(marbles)        # 止まったままのコマ数（どこかに引っかかったら、そのシードは使わない）
    stuck = False
    for f in range(1, last + 1):
        sc.frame_set(f)
        pos = [tuple(round(c, 4) for c in m.matrix_world.translation) for m in marbles]
        frames.append(pos)
        for i, p in enumerate(pos):
            if i not in finish and p[2] < info["z_finish"]:
                finish[i] = f
            if i not in finish and len(frames) > 1 and f > 2 * FPS:
                q = frames[-2][i]
                moved = abs(p[0] - q[0]) + abs(p[2] - q[2])
                still[i] = still[i] + 1 if moved < 0.004 else 0
                if still[i] > 2.5 * FPS:
                    stuck = True
        if stuck:
            break
        if len(finish) >= 3 and f > sorted(finish.values())[2] + int(1.2 * FPS):
            break
        if finish and f > min(finish.values()) + 6 * FPS:
            break
    info["stuck"] = stuck or len(finish) < 3
    return frames, finish


def camera_track(frames, info):
    """先頭の少し上を追うカメラの高さ（なめらかに）。"""
    zs, cur = [], None
    for pos in frames:
        order = sorted(p[2] for p in pos)
        lead = max(order[0], info["z_finish"] - 1.0)
        target = 0.65 * lead + 0.35 * order[min(2, len(order) - 1)]
        cur = target if cur is None else cur + (target - cur) * 0.07
        zs.append(cur)
    return zs


def setup_render(sc, quality):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.use_adaptive_sampling = False
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 2, 1, 2
    c.transmission_bounces, c.transparent_max_bounces = 0, 2
    c.caustics_reflective = c.caustics_refractive = False
    c.use_denoising = False
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = "Standard"
    if quality == "final":
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 810, 1440, 6
    else:
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 360, 640, 3
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 15
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.68, 0.80, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    bpy.ops.object.light_add(type="SUN", location=(0, -10, 10))
    sun = bpy.context.object
    sun.data.energy = 3.4
    sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(62), 0.0, math.radians(-24))
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 60
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    sc.camera = cam
    return cam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", default="preview", choices=["final", "preview", "none"])
    ap.add_argument("--step", type=int, default=1, help="何コマおきに描くか（確認用）")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    os.makedirs(a.out, exist_ok=True)
    seed = a.seed
    for _try in range(12):            # 引っかかりが出たコースは捨てて、次のシードで作り直す
        sc, marbles, info = build(seed)
        frames, finish = simulate(sc, marbles, info)
        if not info["stuck"]:
            break
        print("STUCK seed", seed, flush=True)
        seed += 1000
    info.update({"fps": FPS, "frames": frames, "finish": {str(k): v for k, v in finish.items()},
                 "seed": a.seed, "used_seed": seed, "n_frames": len(frames)})
    cam_dist, cam_up = 15.3, 2.4
    cam_z = camera_track(frames, info)
    info["cam"] = {"z": [round(z, 4) for z in cam_z], "dist": cam_dist, "up": cam_up, "lens": 60, "sensor": 36}
    with open(os.path.join(a.out, "race.json"), "w") as f:
        json.dump(info, f)
    order = sorted(finish, key=lambda i: finish[i])
    print("RACE", a.seed, "frames", len(frames), "sec", round(len(frames) / FPS, 1), "layout",
          [m[0] for m in info["layout"]], "finish", [(info["names"][i], finish[i]) for i in order], flush=True)
    if a.quality == "none":
        return
    # 描くときは物理をもう一度回さず、記録した位置にビー玉を置く（コマを飛ばしても同じ絵になる）
    bpy.ops.rigidbody.world_remove()
    cam = setup_render(sc, a.quality)
    for f in range(1, len(frames) + 1, a.step):
        sc.frame_set(f)
        for m, p in zip(marbles, frames[f - 1]):
            m.location = p
        tz = cam_z[f - 1]
        cam.location = (0.0, -cam_dist, tz + cam_up)
        direction = Vector((0.0, 0.0, tz - 0.6)) - cam.location
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(a.out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("RENDERED", len(range(1, len(frames) + 1, a.step)), flush=True)


if __name__ == "__main__":
    main()
