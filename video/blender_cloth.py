"""blender_cloth.py — 「面の数が違う布」を順に落として比べる 3D 動画を Blender（bpy）で作る。

同じ大きさの布を、16 面 → 64 面 → 256 面 → 1024 面 → 4096 面の順に 2 つの球の上へ落とす。
面が少ないと板のように固く、多いほど布らしく垂れる。待っている布は上に重ねて見せておく。

  python video/blender_cloth.py --seed 3 --out DIR [--quality final|preview|none] [--step N]

出力: DIR/f_0001.png ... と DIR/cloth.json（それぞれの布が落ち始めるコマなど）。文字と音は sims_3d.py が重ねる。
"""

import argparse
import json
import math
import os
import random
import sys

import bpy

FPS = 30
GRIDS = [4, 8, 16, 32, 64]          # 一辺の分割数（面の数はその 2 乗）
SEG = 3.9                           # 1 枚あたりの秒数
SIZE = 2.7                          # 布の一辺


def material(name, color, rough=0.4, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


def collider(ob, friction=1.2):
    mod = ob.modifiers.new("collision", "COLLISION")
    ob.collision.thickness_outer = 0.03
    ob.collision.thickness_inner = 0.2
    ob.collision.cloth_friction = friction
    return mod


def build(seed):
    rng = random.Random(seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    seg = int(SEG * FPS)
    total = seg * len(GRIDS) + int(0.6 * FPS)
    sc.frame_start, sc.frame_end = 1, total

    hue = rng.choice([(1.0, 0.62, 0.10), (1.0, 0.45, 0.12), (0.95, 0.70, 0.18)])
    M = {"cloth": material("cloth", hue, 0.35, 0.9), "ball": material("ball", (0.55, 0.57, 0.62), 0.22, 1.0),
         "box": material("box", (0.42, 0.50, 0.62), 0.8), "floor": material("floor", (0.20, 0.24, 0.33), 0.9)}

    # ---- 2 つの球（布を受ける）と、下の箱
    gap = rng.uniform(0.52, 0.62)
    lift = rng.uniform(-0.05, 0.12)
    # 球を布の中心から少し奥へずらす。布は手前へ傾いて滑り落ち、箱のふちに掛かったり中へ落ちたりする
    off = (rng.uniform(-0.25, 0.25), rng.uniform(0.3, 0.5))
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.62, segments=48, ring_count=24,
                                             location=(sx * gap + off[0], off[1], 2.25 + (lift if sx > 0 else 0.0)))
        ball = bpy.context.object
        bpy.ops.object.shade_smooth()
        ball.data.materials.append(M["ball"])
        collider(ball)
    wall, half, top = 0.16, 1.15, 1.0
    for dx, dy, sx, sy in ((0, -half, 2 * half + wall, wall), (0, half, 2 * half + wall, wall),
                           (-half, 0, wall, 2 * half - wall), (half, 0, wall, 2 * half - wall)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(dx, dy, top - 1.6))
        w = bpy.context.object
        w.scale = (sx, sy, 3.2)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        w.data.materials.append(M["box"])
        collider(w, friction=2.0)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -2.2))
    bpy.context.object.data.materials.append(M["floor"])

    # ---- 布（上に重ねて待たせ、順番に落とす）
    cloths = []
    for k, n in enumerate(GRIDS):
        z0 = 3.95 + 0.17 * k
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=n, y_subdivisions=n, size=SIZE, location=(0.0, 0.0, z0),
                                        rotation=(0.0, 0.0, rng.uniform(-0.06, 0.06)))
        ob = bpy.context.object
        ob.name = f"cloth_{n * n}"
        ob.data.materials.append(M["cloth"])
        start = 1 + k * seg + int(0.5 * FPS)
        mod = ob.modifiers.new("cloth", "CLOTH")
        st = mod.settings
        st.quality = 10
        st.mass = 0.3
        st.tension_stiffness = st.compression_stiffness = 15
        st.shear_stiffness = 5
        st.bending_stiffness = 0.5
        st.air_damping = 1.0
        mod.collision_settings.collision_quality = 4
        mod.collision_settings.distance_min = 0.02
        mod.collision_settings.use_self_collision = False
        mod.point_cache.frame_start = start
        mod.point_cache.frame_end = start + seg + int(1.5 * FPS)
        wire = ob.modifiers.new("wire", "WIREFRAME")      # 面の境目が見えるよう、格子として描く
        wire.thickness = max(0.012, 0.055 - 0.0095 * k)
        wire.use_replace = n < 32                          # 面が多い布は、面も描いて布らしく見せる
        wire.use_even_offset = False
        cloths.append({"ob": ob, "faces": n * n, "start": start, "z0": z0})
    return sc, cloths, total


def setup_render(sc, quality):
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.use_adaptive_sampling = False
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 3, 1, 3
    c.transmission_bounces, c.transparent_max_bounces = 0, 2
    c.caustics_reflective = c.caustics_refractive = False
    c.use_denoising = False
    sc.render.use_persistent_data = False
    sc.view_settings.view_transform = "Standard"
    if quality == "final":
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 810, 1440, 8
    else:
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 360, 640, 4
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 15
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.23, 0.29, 0.40, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 2.6
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = (math.radians(48), 0.0, math.radians(30))
    bpy.ops.object.light_add(type="AREA", location=(-3.5, -4.0, 4.0))
    fill = bpy.context.object
    fill.data.energy = 160
    fill.data.size = 4
    fill.rotation_euler = (math.radians(60), 0.0, math.radians(-40))
    bpy.ops.object.camera_add(location=(0.0, -7.4, 4.5), rotation=(math.radians(72.5), 0.0, 0.0))
    cam = bpy.context.object
    cam.data.lens = 68
    cam.data.sensor_fit = "HORIZONTAL"
    sc.camera = cam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", default="preview", choices=["final", "preview", "none"])
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    os.makedirs(a.out, exist_ok=True)
    sc, cloths, total = build(a.seed)
    info = {"fps": FPS, "n_frames": total, "seed": a.seed,
            "cloths": [{"faces": c["faces"], "start": c["start"]} for c in cloths]}
    with open(os.path.join(a.out, "cloth.json"), "w") as f:
        json.dump(info, f)
    print("CLOTH", a.seed, "frames", total, "sec", round(total / FPS, 1), flush=True)
    if a.quality == "none":
        return
    setup_render(sc, a.quality)
    bpy.ops.ptcache.bake_all(bake=True)          # 布の動きを先に全部計算しておく（描くときにコマを飛ばしても狂わない）
    seg = int(SEG * FPS)
    for f in range(1, total + 1):                 # 布の計算はコマを順に進めないと進まないので、飛ばさず回す
        sc.frame_set(f)
        for k, c in enumerate(cloths):            # 次の布が落ち始めたら、前の布は片づける
            gone = f >= c["start"] + seg - 3
            c["ob"].hide_render = gone
            c["ob"].hide_viewport = gone
        if (f - 1) % a.step:
            continue
        sc.render.filepath = os.path.join(a.out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("RENDERED", flush=True)


if __name__ == "__main__":
    main()
