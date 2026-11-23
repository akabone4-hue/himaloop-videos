"""blender_chime.py — 鉄琴の上をボールが跳ねて曲を鳴らす 3D 動画を Blender（bpy）で描く。

経路（どの時刻にどこへ着地するか、板をどこに置くか）は sims_course.arc_layout が先に決めて、
layout.json として渡してくる。ここでは物理の計算はせず、その経路どおりにボールと鍵盤を置いて描くだけ。

  python video/blender_chime.py --layout layout.json --out DIR [--quality final|preview] [--step N]

鍵盤は音の高さで色と奥行きが変わる（低い音ほど長い）。ボールが当たった鍵盤は、少し沈んで光る。
"""

import argparse
import colorsys
import json
import math
import os
import sys

import bpy
from mathutils import Vector

SCALE = 0.01          # 経路の 1 ピクセル = 1 cm


def material(name, color, rough=0.3, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    b.inputs["Emission Strength"].default_value = 0.0
    return m


def linear(c):
    return tuple(x ** 2.2 for x in c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quality", default="preview", choices=["final", "preview", "none"])
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()
    with open(a.layout) as f:
        lay = json.load(f)
    os.makedirs(a.out, exist_ok=True)
    fps, total, g, br = lay["fps"], lay["total"], lay["g"], lay["br"]
    plats = lay["plats"]
    all_legs = lay.get("balls") or [lay["legs"]]               # ボールごとの経路（chime2 は 2 個）
    many = len(all_legs) > 1
    n_frames = int(total * fps)
    with open(os.path.join(a.out, "chime.json"), "w") as f:
        json.dump({"fps": fps, "n_frames": n_frames}, f)
    print("CHIME frames", n_frames, "bars", len(plats), flush=True)
    if a.quality == "none":
        return

    def to3d(x, y):
        return x * SCALE, -y * SCALE

    def ball_at(t, legs):
        k = 0
        for j in range(len(legs)):
            if legs[j][0] <= t:
                k = j
            else:
                break
        lt, lx, ly, lvx, lvy = legs[k]
        tau = max(0.0, t - lt)
        return lx + lvx * tau, ly + lvy * tau + 0.5 * g * tau * tau

    def ground_one(t, legs):                       # カメラが追う点（着地点から次の着地点へまっすぐ）
        k = 0
        for j in range(len(legs)):
            if legs[j][0] <= t:
                k = j
            else:
                break
        if k + 1 >= len(legs):
            return legs[k][1], legs[k][2]
        p, q = legs[k], legs[k + 1]
        u = min(1.0, max(0.0, (t - p[0]) / max(1e-6, q[0] - p[0])))
        return p[1] + (q[1] - p[1]) * u, p[2] + (q[2] - p[2]) * u

    def ground_at(t):                              # ボールが複数なら、その平均を追う
        pts = [ground_one(t, legs) for legs in all_legs]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps

    # ---- 鍵盤。見た目（色と奥行き）は音の高さだけで決める: 同じ音の鍵盤は必ず同じ色・同じ長さ、
    # 違う音の鍵盤は必ず違う見た目になる（「同じ鍵盤なのに音が違う」と見えないように）。
    # 低い音ほど長く、色は低い音の赤から高い音の紫へ順に変わる（本物の鉄琴と同じ並び）。
    # 幅はどの鍵盤も同じ（いちばん間隔の狭い所に合わせる）。
    lo = min(p[5] for p in plats)
    hi = max(p[5] for p in plats)
    width = max(34.0, min(60.0, min(p[4] for p in plats)))
    bars = []
    mats = {}
    for x, y, ang, t, _length, midi in plats:
        length = width
        X, Z = to3d(x, y)
        key = midi
        u = (midi - lo) / max(1, hi - lo)
        if key not in mats:
            col = colorsys.hsv_to_rgb(0.78 * u, 0.85, 1.0)
            mats[key] = linear(col)
        depth = 2.0 - 1.0 * u                       # 低い音ほど長い（本物の鉄琴と同じ）
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(X, 0.0, Z), rotation=(0.0, -ang, 0.0))
        ob = bpy.context.object
        ob.scale = (length * SCALE, depth, 0.16)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bev = ob.modifiers.new("bevel", "BEVEL")
        bev.width, bev.segments = 0.035, 3
        m = material(f"bar{len(bars)}", mats[key], 0.3, 0.25)
        ob.data.materials.append(m)
        nrm = Vector((math.sin(ang), 0.0, -math.cos(ang)))     # 板から見て「下」（沈む向き）
        bars.append({"ob": ob, "mat": m, "t": t, "home": Vector((X, 0.0, Z)), "down": nrm})
        for sy in (-1, 1):                          # 鍵盤を支える 2 本のピン
            bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.5, vertices=10,
                                                location=(X, sy * depth * 0.32, Z - 0.3))
            pin = bpy.context.object
            pin.data.materials.append(mats.setdefault("pin", None) or _pin_mat(mats))

    # ---- ボール
    balls = []
    looks = [(0.92, 0.92, 0.95), (1.0, 0.72, 0.25)]            # 銀と金
    for i, legs in enumerate(all_legs):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=br * SCALE, segments=32, ring_count=16)
        ob = bpy.context.object
        bpy.ops.object.shade_smooth()
        ob.data.materials.append(material(f"ball{i}", looks[i % 2], 0.12, 1.0))
        # 2 個のときは手前と奥に分ける（空中ですれ違っても、ぶつからない）
        balls.append((ob, legs, (-0.3 + 0.6 * i) if many else 0.0))

    # ---- 背景の板（影が落ちて奥行きが出る）
    xs = [p[0] for p in plats]
    ys = [p[1] for p in plats]
    cx, cz = to3d((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    w, h = (max(xs) - min(xs)) * SCALE + 30, (max(ys) - min(ys)) * SCALE + 40
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(cx, 1.3, cz), rotation=(math.pi / 2, 0.0, 0.0))
    back = bpy.context.object
    back.scale = (w, h, 1.0)
    back.data.materials.append(material("back", (0.05, 0.07, 0.13), 0.85))

    # ---- 描画の設定
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.use_adaptive_sampling = False
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 3, 1, 3
    c.transmission_bounces, c.transparent_max_bounces = 0, 2
    c.caustics_reflective = c.caustics_refractive = False
    c.use_denoising = False
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = "Standard"
    if a.quality == "final":
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 810, 1440, 8
    else:
        sc.render.resolution_x, sc.render.resolution_y, c.samples = 360, 640, 4
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 15
    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.80, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 3.6
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(55), 0.0, math.radians(-28))
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 50
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36
    sc.camera = cam

    camx = camz = None
    for f in range(1, n_frames + 1):
        t = (f - 1) / fps
        gx, gy = ground_at(t)
        tx, tz = to3d(gx, gy)
        camx = tx if camx is None else camx + (tx - camx) * 0.14
        camz = tz if camz is None else camz + (tz - camz) * 0.14
        if (f - 1) % a.step:
            continue
        sc.frame_set(f)
        for ob, legs, depth_y in balls:
            bx, by = ball_at(t, legs)
            X, Z = to3d(bx, by)
            ob.location = (X, depth_y, Z)
        for b in bars:                              # 当たった鍵盤は少し沈んで光り、すぐ戻る
            age = t - b["t"]
            dip = 0.07 * math.exp(-age / 0.07) * math.cos(age * 40) if age >= 0 else 0.0
            b["ob"].location = b["home"] + b["down"] * dip
            glow = 2.6 * math.exp(-age / 0.22) if age >= 0 else 0.0
            b["mat"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = glow
        cam.location = (camx, -6.0, camz + 3.2) if many else (camx, -5.4, camz + 2.9)   # 2 個のときは弧が高いので少し引く
        look = Vector((camx, 0.0, camz + (1.0 if many else 0.75))) - cam.location
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(a.out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("RENDERED", flush=True)


def _pin_mat(mats):
    mats["pin"] = material("pin", (0.25, 0.27, 0.32), 0.4, 1.0)
    return mats["pin"]


if __name__ == "__main__":
    main()
