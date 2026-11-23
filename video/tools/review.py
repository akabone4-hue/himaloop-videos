#!/usr/bin/env python3
"""review.py — できあがった動画を、送る前に機械で点検する

  python video/tools/review.py video/out/gear2_2.mp4            1 本を点検（コマの一覧画像も作る）
  python video/tools/review.py video/out/*.mp4 --out DIR        まとめて点検し、DIR に一覧画像と review.md を書く
  python video/tools/review.py FILE.mp4 --close 12.5            12.5 秒からの 2.4 秒間を細かいコマ送りの画像にする
  python video/tools/review.py FILE.mp4 --gate                  自動投稿の直前の関門。壊れた動画のときだけ失敗で終わる

調べること（基準は video/QUALITY.md の「機械で調べる項目」と同じ）:
  長さ・大きさ・音量 / 最初の音までの時間 / 無音が続く区間 / 動きが止まって見える区間 /
  画面の端に文字や絵がかかっていないか

人が見ないと分からないこと（増える理由が見えるか、決着が読めてしまわないか など）は調べられない。
一覧画像を開いて、QUALITY.md の「目で見る項目」を自分で確かめること。
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

# 基準（変えるときは QUALITY.md も直す）
LEN_MIN, LEN_MAX = 20.0, 45.0        # 秒
FIRST_SOUND_MAX = 1.2                # 最初の音までの秒数
SILENCE_MAX = 2.0                    # これ以上の無音は注意
MEAN_DB_MIN, MEAN_DB_MAX = -27.0, -14.0
LULL_MIN = 4.0                       # 動きがほとんどない時間がこれ以上続いたら注意
STALE_MIN = 8.0                      # 動いてはいるが、画面全体の様子が変わらない時間がこれ以上続いたら注意
STALE_LEVEL = 2.2                    # 5 秒離れた画面どうしの差（0〜255 の明るさ）。陣取りで勢力が動かなかった例が 1.6〜2.2
SIZE_MAX_MB = 70


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=width,height,r_frame_rate:format=duration,size", "-of", "json", path])
    j = json.loads(r.stdout)
    st, fm = j["streams"][0], j["format"]
    num, den = st["r_frame_rate"].split("/")
    return {"width": st["width"], "height": st["height"], "fps": round(int(num) / int(den), 2),
            "duration": float(fm["duration"]), "size_mb": int(fm["size"]) / 1e6}


def audio(path):
    r = _run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect,silencedetect=noise=-38dB:d=0.4",
              "-vn", "-f", "null", "-"])
    out = r.stderr
    mean = re.search(r"mean_volume: (-?[\d.]+)", out)
    peak = re.search(r"max_volume: (-?[\d.]+)", out)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", out)]
    sil = list(zip(starts, durs))
    first = 0.0
    if sil and sil[0][0] <= 0.05:
        first = sil[0][1]
    total = probe(path)["duration"]
    # 途中の無音だけを数える（最後の余韻のあとの無音は、どの動画にもある）
    mid = [(round(s, 1), round(d, 1)) for s, d in sil if d >= SILENCE_MAX and s > 0.05 and s + d < total - 0.3]
    return {"mean_db": float(mean.group(1)) if mean else None, "max_db": float(peak.group(1)) if peak else None,
            "first_sound": first, "silences": mid}


def frames_small(path, fps=5, w=54, h=96):
    """動画を小さな白黒のコマの並びにして返す（動き・端の点検用）。"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h}", "-pix_fmt", "gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(a) // (w * h)
    return a[: n * w * h].reshape(n, h, w).astype(np.float32), fps


def motion(path):
    fr, fps = frames_small(path)
    if len(fr) < 3:
        return {"lulls": [], "edge": [], "stale": []}
    diff = np.abs(fr[1:] - fr[:-1]).mean(axis=(1, 2))
    ref = float(np.median(diff)) or 1e-6
    quiet = diff < max(0.02, 0.12 * ref)             # ふだんの動きの 1 割ちょっと以下 = ほぼ止まっている
    lulls, start = [], None
    for i, q in enumerate(list(quiet) + [False]):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) / fps >= LULL_MIN and start / fps > 0.5:
                lulls.append((round(start / fps, 1), round((i - start) / fps, 1)))
            start = None
    # 端: 上 4%・下 3%・左右 2% に、明るい絵（文字など）が長い時間かかっていないか
    h, w = fr.shape[1:]
    bright = fr > 150
    edge = []
    zones = {"上端": bright[:, : max(1, int(h * 0.04)), :], "下端": bright[:, -max(1, int(h * 0.03)):, :],
             "左端": bright[:, :, : max(1, int(w * 0.02))], "右端": bright[:, :, -max(1, int(w * 0.02)):]}
    last = max(1, int(len(fr) * 0.88))               # 最後の弾ける場面は端まで飛ぶので除く
    for name, z in zones.items():
        share = float(z[:last].any(axis=(1, 2)).mean())
        if share > 0.5:
            edge.append((name, round(share * 100)))
    # 停滞: 小さな玉は動いていても、5 秒前と比べて画面全体の様子が変わっていない（勢力が動かない、など）。
    # 1 秒ごとの平均の絵どうしを比べる。最初の 5 秒は、まだ物が少なくて差が出ないので見ない。
    n = len(fr) // fps
    stale = []
    if n > 12:
        sec = fr[: n * fps].reshape(n, fps, h, w).mean(axis=1)
        d = np.abs(sec[5:] - sec[:-5]).mean(axis=(1, 2))
        start = None
        for i, low in enumerate(list(d < STALE_LEVEL) + [False]):
            if i < 5:
                continue
            if low and start is None:
                start = i
            elif not low and start is not None:
                if i - start >= STALE_MIN:
                    stale.append((start, i - start + 5))
                start = None
    return {"lulls": lulls, "edge": edge, "stale": stale}


def sheet(path, out_png, n=8, duration=None):
    duration = duration or probe(path)["duration"]
    _run(["ffmpeg", "-y", "-v", "error", "-i", path, "-vf", f"fps={n}/{duration},scale=270:-1,tile={n}x1",
          "-frames:v", "1", out_png])


def close_up(path, out_png, at, span=2.4):
    _run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", path, "-vf", f"fps={16 / span},scale=270:-1,tile=8x2",
          "-frames:v", "1", out_png])


def gate(path):
    """自動投稿の直前の関門。「出来が良いか」ではなく「壊れていないか」だけを見る。
    ここで止めるのは、投稿したら明らかに困るものだけ（音がない、長さが極端、大きさが違う、中身がほぼ空）。"""
    problems = []
    try:
        p = probe(path)
        a = audio(path)
    except Exception as e:
        return [f"読めない: {e!r}"]
    if not 10.0 <= p["duration"] <= 60.0:
        problems.append(f"長さ {p['duration']:.1f} 秒（10〜60 秒の外）")
    if (p["width"], p["height"]) != (1080, 1920):
        problems.append(f"大きさ {p['width']}x{p['height']}（1080x1920 でない）")
    if p["size_mb"] < 0.3:
        problems.append(f"ファイルが小さすぎる（{p['size_mb']:.2f}MB）")
    if a["mean_db"] is None or a["mean_db"] < -45.0:
        problems.append(f"音がない、または小さすぎる（平均 {a['mean_db']} dB）")
    return problems


def review(path):
    p = probe(path)
    a = audio(path)
    m = motion(path)
    warn = []
    if not LEN_MIN <= p["duration"] <= LEN_MAX:
        warn.append(f"長さ {p['duration']:.1f} 秒（目安 {LEN_MIN:.0f}〜{LEN_MAX:.0f}）")
    if (p["width"], p["height"]) != (1080, 1920):
        warn.append(f"大きさ {p['width']}x{p['height']}（本番は 1080x1920）")
    if p["size_mb"] > SIZE_MAX_MB:
        warn.append(f"ファイル {p['size_mb']:.0f}MB（{SIZE_MAX_MB}MB 超）")
    if a["mean_db"] is None:
        warn.append("音がない")
    else:
        if not MEAN_DB_MIN <= a["mean_db"] <= MEAN_DB_MAX:
            warn.append(f"平均音量 {a['mean_db']:.1f} dB（目安 {MEAN_DB_MIN:.0f}〜{MEAN_DB_MAX:.0f}）")
        if a["first_sound"] > FIRST_SOUND_MAX:
            warn.append(f"最初の音まで {a['first_sound']:.1f} 秒（目安 {FIRST_SOUND_MAX} 秒以内）")
        for s, d in a["silences"]:
            warn.append(f"無音 {s} 秒から {d} 秒間")
    for s, d in m["lulls"]:
        warn.append(f"動きがほぼ止まる {s} 秒から {d} 秒間")
    for s_, d_ in m["stale"]:
        warn.append(f"画面全体の様子がほとんど変わらない {s_} 秒から約 {d_} 秒間（決着や変化が見えているか確認）")
    for name, pct in m["edge"]:
        warn.append(f"{name}に絵や文字がかかっている（全体の {pct}% の時間）")
    return {"file": os.path.basename(path), **p, **a, **m, "warn": warn}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default=None, help="一覧画像と review.md を書くフォルダ（省略時は動画と同じ場所の review/）")
    ap.add_argument("--close", type=float, default=None, help="この秒数からの細かいコマ送りも作る")
    ap.add_argument("--no-sheet", action="store_true", help="一覧画像を作らない（数字だけ）")
    ap.add_argument("--gate", action="store_true", help="壊れているときだけ失敗で終わる（自動投稿の直前用）")
    args = ap.parse_args()
    if args.gate:
        failed = 0
        for path in args.files:
            problems = gate(path) if os.path.exists(path) else ["ファイルがない"]
            print(f"{os.path.basename(path)}: " + ("OK" if not problems else " / ".join(problems)))
            failed += bool(problems)
        return 1 if failed else 0
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.files[0])), "review")
    os.makedirs(out, exist_ok=True)
    lines = ["# 動画の点検結果", "", "| 動画 | 長さ | 大きさ | 平均音量 | 最初の音 | 注意 |", "|---|---:|---:|---:|---:|---|"]
    bad = 0
    sheets = []
    for path in args.files:
        if not os.path.exists(path):
            print(f"{path}: ファイルがない")
            bad += 1
            continue
        r = review(path)
        name = os.path.splitext(r["file"])[0]
        if not args.no_sheet:
            png = os.path.join(out, name + ".png")
            sheet(path, png, duration=r["duration"])
            sheets.append(png)
            if args.close is not None:
                close_up(path, os.path.join(out, name + f"_close{args.close:g}.png"), args.close)
        mark = "OK" if not r["warn"] else "注意 " + str(len(r["warn"]))
        print(f"{name:16} {r['duration']:5.1f}s {r['size_mb']:5.1f}MB {r['mean_db']} dB 最初の音 {r['first_sound']:.1f}s  {mark}")
        for w in r["warn"]:
            print(f"    - {w}")
        bad += bool(r["warn"])
        lines.append(f"| {name} | {r['duration']:.1f} 秒 | {r['size_mb']:.0f}MB | {r['mean_db']} dB | {r['first_sound']:.1f} 秒 | "
                     + ("なし" if not r["warn"] else "<br>".join(r["warn"])) + " |")
    if len(sheets) > 1:                                # まとめて見られるよう、縦に並べた 1 枚も作る（6 本ずつ）
        for k in range(0, len(sheets), 6):
            part = sheets[k:k + 6]
            cmd = ["ffmpeg", "-y", "-v", "error"]
            for s in part:
                cmd += ["-i", s]
            cmd += ["-filter_complex", f"vstack=inputs={len(part)}", os.path.join(out, f"all_{k // 6 + 1}.png")]
            if len(part) > 1:
                _run(cmd)
    with open(os.path.join(out, "review.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"一覧画像と review.md: {out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
