"""sims_3d.py — Blender で作る 3D の型

  marble  壁掛けコースの 3D マーブルレース（ギミックの順番と配置は毎回変わる）
  faces   面の数が違う布（16 → 4096 面）を順に球の上へ落として比べる
  chime   鉄琴の上をボールが跳ねて曲を鳴らす（1 バウンド = 1 音）

絵は blender_marble.py / blender_cloth.py が別プロセスで描く（Blender の Python モジュール bpy が必要:
pip install bpy）。ここではその結果（コマ画像と race.json）を読み、文字と音を重ねる。
"""

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import pygame

import melodies
import sims_course
from engine import ARP_PAT, ARP_PROG, CX, H, W, mix

HERE = os.path.dirname(os.path.abspath(__file__))
GRAVITY = 9.81


def _hits(info):
    """記録した位置から「何かに当たった瞬間」を拾う。[(コマ, 玉の番号, 強さ, 高さ z)]"""
    fps, frames = info["fps"], info["frames"]
    out = []
    for i in range(len(frames[0])):
        prev_v = None
        for f in range(1, len(frames)):
            p, q = frames[f][i], frames[f - 1][i]
            vel = ((p[0] - q[0]) * fps, (p[2] - q[2]) * fps)
            if prev_v is not None:
                dvx = vel[0] - prev_v[0]
                dvz = vel[1] - prev_v[1] + GRAVITY / fps          # 重力による変化は除く
                jolt = math.hypot(dvx, dvz)
                if jolt > 1.6:
                    out.append((f, i, jolt, p[2]))
            prev_v = vel
    out.sort()
    return out


def _blender(script, data_name, v, rng, setup=None):
    """Blender のスクリプトを別プロセスで走らせ、(作業フォルダ, 記録データ) を返す。
    setup(work) を渡すと、走らせる前に作業フォルダへ入力ファイルを書き、追加の引数の一覧を返してもらう。"""
    seed = rng.randrange(1, 10 ** 6)
    keep = os.environ.get("KEEP_BLENDER_FRAMES")        # 文字や音だけ直したいとき用: コマ画像を残して使い回す
    work = (os.path.join(tempfile.gettempdir(), f"blender_keep_{script[:-3]}_{seed}_{int(v.fps)}") if keep
            else tempfile.mkdtemp(prefix="blender_"))
    if keep and os.path.exists(os.path.join(work, "done")):
        with open(os.path.join(work, data_name)) as f:
            return work, json.load(f)
    quality = "none" if v.dry else ("preview" if v.fps < 60 else "final")
    os.makedirs(work, exist_ok=True)
    cmd = [sys.executable, os.path.join(HERE, script), "--seed", str(seed), "--out", work, "--quality", quality]
    if setup:
        cmd += setup(work)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(os.path.join(work, data_name)):
        raise RuntimeError(f"{script} failed:\n" + res.stdout[-1500:] + res.stderr[-1500:])
    if keep:
        open(os.path.join(work, "done"), "w").close()
    with open(os.path.join(work, data_name)) as f:
        return work, json.load(f)


def _cleanup(work):
    if not os.environ.get("KEEP_BLENDER_FRAMES"):
        shutil.rmtree(work, ignore_errors=True)


def _frame(work, f):
    img = pygame.image.load(os.path.join(work, f"f_{f:04d}.png"))
    return img if img.get_size() == (W, H) else pygame.transform.smoothscale(img, (W, H))


def _top_band(height=330):
    band = pygame.Surface((W, height), pygame.SRCALPHA)
    for y in range(height):
        pygame.draw.line(band, (8, 10, 18, int(190 * (1 - y / height) ** 1.3)), (0, y), (W, y))
    return band


def run_faces(v, rng):
    work, info = _blender("blender_cloth.py", "cloth.json", v, rng)
    fps, total, cloths = info["fps"], info["n_frames"], info["cloths"]
    lead = int(0.5 * fps)
    for k, c in enumerate(cloths):
        t0 = (c["start"] - lead - 1) / fps
        v.audio.note(t0 + 0.05, 60 + 4 * k, 0.5, "marimba")           # 枚数が進むごとに音が上がる
        v.audio.play((c["start"] - 1) / fps + 0.62, 150 - 12 * k, 0.5 - 0.06 * k, "thud")      # 球に当たる音
        v.audio.play((c["start"] - 1) / fps + 0.66, 700, 0.12, "wood")
    rep = max(1, round(v.fps / fps))
    band = None if v.dry else _top_band(300)
    for f in range(1, total + 1):
        if not v.dry:
            img = _frame(work, f)
            k = max(i for i, c in enumerate(cloths) if f >= c["start"] - lead or i == 0)
            age = (f - (cloths[k]["start"] - lead)) / fps
        for _ in range(rep):
            if not v.dry:
                v.surf.blit(img, (0, 0))
                v.surf.blit(band, (0, 0))
                size = 132 + int(26 * max(0.0, 1 - age / 0.18)) if k else 132        # 切り替わる瞬間だけ少し大きく
                v.text(f"{cloths[k]['faces']} Faces", size, (CX, 170), outline=6)
            v.end(glow=0.0)
    _cleanup(work)
    return {"result": " > ".join(str(c["faces"]) for c in cloths) + " faces"}


def run_chime(v, rng):
    """鉄琴の上をボールが跳ねて曲を鳴らす。経路は 2D で先に決め、絵だけ Blender で描く。"""
    song = rng.choice(melodies.ALL)
    notes, end_t, legs, plats, _vx = sims_course.arc_layout(rng, song)
    lift = 12 if min(m for _t, m in notes) < 57 else 0
    fps3d = 30
    total = end_t + 1.4

    def setup(work):
        path = os.path.join(work, "layout.json")
        with open(path, "w") as f:
            json.dump({"fps": fps3d, "total": total, "g": sims_course.MUSIC_G, "br": 22.0, "legs": legs,
                       "plats": [list(p) + [m] for p, (_t, m) in zip(plats, notes)]}, f)
        return ["--layout", path]

    work, info = _blender("blender_chime.py", "chime.json", v, rng, setup=setup)
    for i, (t, midi) in enumerate(notes):
        gap_t = (notes[i + 1][0] - t) if i + 1 < len(notes) else 1.5
        v.audio.note(t, midi + lift + 12, 0.55, "glock", dur=gap_t + 0.35)      # 鉄琴らしく 1 オクターブ上で鳴らす
    rep = max(1, round(v.fps / fps3d))
    band = None if v.dry else _top_band(320)
    for f in range(1, info["n_frames"] + 1):
        if not v.dry:
            img = _frame(work, f)
        for _ in range(rep):
            if not v.dry:
                v.surf.blit(img, (0, 0))
                v.surf.blit(band, (0, 0))
                v.text(song["title"], 100 if len(song["title"]) < 16 else 64, (CX, 170))
                v.text("every bounce = 1 note", 60, (CX, 258), color=(215, 218, 230), outline=3)
            v.end(glow=0.0)
    _cleanup(work)
    return {"song": song, "result": f"{len(notes)} notes"}


def run_chime2(v, rng):
    """鉄琴の 2 個版。銀と金のボールが鍵盤を 1 枚おきに踏み、追い越し合いながら曲を鳴らす。
    1 個あたりの間隔が倍になるので弧が高く、動きが大きい。"""
    songs = melodies.ALL[:]
    rng.shuffle(songs)
    for song in songs:                          # ゆっくりした曲は弧が高くなりすぎるので、置ける曲を選ぶ
        got = sims_course.arc_layout2(rng, song)
        if got:
            break
    else:
        raise RuntimeError("chime2: no song could be laid out for two balls")
    notes, end_t, two, plats, _vx = got
    lift = 12 if min(m for _t, m in notes) < 57 else 0
    fps3d = 30
    total = end_t + 1.4

    def setup(work):
        path = os.path.join(work, "layout.json")
        with open(path, "w") as f:
            json.dump({"fps": fps3d, "total": total, "g": sims_course.MUSIC_G2, "br": 22.0, "balls": two,
                       "plats": [list(p) + [m] for p, (_t, m) in zip(plats, notes)]}, f)
        return ["--layout", path]

    work, info = _blender("blender_chime.py", "chime.json", v, rng, setup=setup)
    for i, (t, midi) in enumerate(notes):
        gap_t = (notes[i + 1][0] - t) if i + 1 < len(notes) else 1.5
        v.audio.note(t, midi + lift + 12, 0.55, "glock", dur=gap_t + 0.35)
    rep = max(1, round(v.fps / fps3d))
    band = None if v.dry else _top_band(320)
    for f in range(1, info["n_frames"] + 1):
        if not v.dry:
            img = _frame(work, f)
        for _ in range(rep):
            if not v.dry:
                v.surf.blit(img, (0, 0))
                v.surf.blit(band, (0, 0))
                v.text(song["title"], 100 if len(song["title"]) < 16 else 64, (CX, 170))
                v.text("2 balls take turns", 60, (CX, 258), color=(215, 218, 230), outline=3)
            v.end(glow=0.0)
    _cleanup(work)
    return {"song": song, "result": f"{len(notes)} notes, 2 balls"}


def run_marble(v, rng):
    work, info = _blender("blender_marble.py", "race.json", v, rng)
    names, colors = info["names"], [tuple(c) for c in info["colors"]]
    frames, fps = info["frames"], info["fps"]
    finish = {int(k): val for k, val in info["finish"].items()}
    podium = sorted(finish, key=lambda i: finish[i])
    winner = podium[0]
    win_frame = finish[winner]
    zones = {name: (top, bottom) for name, top, bottom in info["layout"]}
    pegs = [(top, bottom) for name, top, bottom in info["layout"] if name == "plinko"]

    # ---- 音: 釘に当たると木琴、そのほかは木の「コツッ」。強く当たるほど大きい
    seq = 0
    for f, i, jolt, z in _hits(info):
        t = (f - 1) / fps
        vol = min(0.55, 0.10 + jolt / 16)
        if any(bottom < z < top for top, bottom in pegs):
            if v.audio.note(t, ARP_PROG[(seq // 8) % 4][ARP_PAT[seq % 8]] + 12, vol, "marimba",
                            channel="peg", min_gap=0.06):
                seq += 1
        else:
            v.audio.play(t, 520 + 60 * (i % 5), vol, "wood", channel=f"w{i % 3}", min_gap=0.05)
    v.audio.note(1.0, 72, 0.5, "piano")                       # ゲートが上がる合図
    for k, (i, m) in enumerate(zip(podium[:3], (72, 67, 64))):
        v.audio.note((finish[i] - 1) / fps, m + 12 if k == 0 else m, 0.8 if k == 0 else 0.5, "piano")
    for k, m in enumerate((60, 64, 67, 72)):
        v.audio.note((win_frame - 1) / fps + 0.12 + 0.07 * k, m, 0.7, "piano")

    rep = max(1, round(v.fps / fps))                          # 30 コマ/秒の絵を、動画のコマ数に合わせて繰り返す
    band = None
    for f in range(1, len(frames) + 1):
        if not v.dry:
            img = _frame(work, f)
            # ゴール済みの玉はゴールした順、まだ走っている玉は低い位置にいる順。
            # （ゴールの記録は「このコマまでにゴールした玉」だけを使う。先の結果で並べない）
            order = sorted(range(len(names)),
                           key=lambda i: (finish[i] if finish.get(i, 10 ** 9) <= f else 10 ** 9, frames[f - 1][i][2]))
            if band is None:
                band = _top_band()
        for _ in range(rep):
            if not v.dry:
                v.surf.blit(img, (0, 0))
                v.surf.blit(band, (0, 0))
                v.text("Pick a color!", 96, (CX, 150))
                x0 = CX - (len(order) - 1) * 52
                for rank, i in enumerate(order):                  # いまの順位（左が先頭）
                    x = x0 + rank * 104
                    r = 34 if rank == 0 else 28
                    v.circle((250, 250, 250), (x, 262), r + 5)
                    v.circle(colors[i], (x, 262), r)
                    if rank < 3:
                        v.text(str(rank + 1), 44, (x, 263), outline=3)
                if f >= win_frame:
                    age = (f - win_frame) / fps
                    al = int(255 * min(1.0, age / 0.25))
                    v.text(f"{names[winner]} WINS", 150, (CX, 800), color=mix(colors[winner], (255, 255, 255), 0.25),
                           outline=8, alpha=al)
                    for k, i in enumerate(podium[1:3]):
                        if f >= finish[i]:
                            v.text(f"{k + 2}. {names[i]}", 76, (CX, 930 + 90 * k), color=mix(colors[i], (255, 255, 255), 0.3),
                                   outline=5)
            v.end(glow=0.0)
    _cleanup(work)
    gimmicks = [name for name, _t, _b in info["layout"]]
    return {"result": f"{names[winner]} wins; course: {' > '.join(gimmicks)}", "winner": names[winner]}
