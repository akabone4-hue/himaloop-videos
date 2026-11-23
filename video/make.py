#!/usr/bin/env python3
"""make.py — 物理シミュレーション動画を作る

  python video/make.py list                       種類の一覧
  python video/make.py grow                       1 本作る（video/out/ に mp4 と投稿用テキスト）
  python video/make.py all --count 2              全種類を 2 本ずつ
  python video/make.py rings --seed 7 --preview   低画質・30fps で手早く確認

長さが決まっていない種類（脱出・バトルなど）は、先に物理だけを高速で回して
ちょうどよい長さ（種類ごとの目標秒数）になる乱数シードを探してから書き出します。
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine          # noqa: E402
import registry        # noqa: E402


def measure(spec, seed):
    v = engine.Video("", dry=True)
    spec["run"](v, random.Random(seed))
    return v.finish()


def find_seed(spec, start_seed, tries=60):
    lo, hi = spec["length"]
    best = None
    for i in range(tries):
        seed = start_seed + i
        d = measure(spec, seed)
        if lo <= d <= hi:
            return seed, d
        miss = min(abs(d - lo), abs(d - hi))
        if best is None or miss < best[2]:
            best = (seed, d, miss)
    return best[0], best[1]


def make_one(name, seed, out_dir, preview=False):
    spec = registry.SIMS[name]
    t0 = time.time()
    seed, expect = find_seed(spec, seed) if spec.get("search", True) else (seed, None)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{name}_{seed}")
    v = engine.Video(base + ".mp4", fps=30 if preview else 60, preview=preview)
    meta = spec["run"](v, random.Random(seed)) or {}
    duration = v.finish()
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(registry.post_text(name, meta, duration, seed))
    info = registry.post_meta(name, meta, seed)
    info.update({"seed": seed, "duration": round(duration, 1), "result": meta.get("result", "")})
    with open(base + ".json", "w", encoding="utf-8") as f:      # 自動投稿用
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"{name}: seed={seed} {duration:.1f}s -> {base}.mp4 ({time.time() - t0:.0f}s) {meta.get('result', '')}",
          flush=True)
    return base + ".mp4"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("type", help="種類名 / all / list")
    ap.add_argument("--seed", type=int, default=None, help="乱数シード（省略時は時刻から決める）")
    ap.add_argument("--count", type=int, default=1, help="種類ごとの本数")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--preview", action="store_true", help="540x960・30fps で手早く書き出す")
    args = ap.parse_args()

    if args.type == "list":
        for name, spec in registry.SIMS.items():
            print(f"{name:10} {spec['ja']}")
        return 0
    # all には 3D の型（Blender が必要で 1 本に 1 時間以上かかる）を含めない。作るときは名前で指定する
    names = ([n for n, s in registry.SIMS.items() if not s.get("heavy")] if args.type == "all"
             else [n.strip() for n in args.type.split(",")])
    for n in names:
        if n not in registry.SIMS:
            print(f"unknown type: {n}  (python video/make.py list)")
            return 2
    seed = args.seed if args.seed is not None else int(time.time()) % 1_000_000
    for name in names:
        for i in range(args.count):
            make_one(name, seed + i * 1000, args.out, args.preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
