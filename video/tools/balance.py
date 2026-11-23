#!/usr/bin/env python3
"""balance.py — 絵を描かずに何十回も回して、長さと勝ち方のかたよりを調べる

  python video/tools/balance.py survive2                 シード 1〜32 で回す
  python video/tools/balance.py cannons --seeds 1-80     シードの範囲を指定
  python video/tools/balance.py merge --seeds 31-50 --each   1 回ごとの結果も出す

出るもの:
  長さ（最短・中央・最長）と、registry.py の目標の長さに入った回数
  勝ち方の内訳（型が結果に "winner" を返す場合）。条件の違うレースは、ここがほぼ均等になるまで数字を直す
  途中で落ちたシード

注意: 物理は 60 コマ/秒で回す（本番と同じ）。--preview（30 コマ/秒）で書き出した動画とは結果が変わる型がある。
"""

import argparse
import collections
import multiprocessing as mp
import os
import random
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def one(job):
    name, seed = job
    import engine
    import registry
    try:
        v = engine.Video("", dry=True)
        meta = registry.SIMS[name]["run"](v, random.Random(seed)) or {}
        result = str(meta.get("result", ""))
        win = meta.get("winner")
        if win is None:                          # "winner" を返さない型は、結果の文から拾う（かっこの中の条件、なければ色）
            m = re.search(r"\(([^)]*)\) wins", result) or re.search(r"(\w+) wins", result)
            win = m.group(1) if m else None
        return seed, round(v.finish(), 1), win, result[:70], None
    except Exception as e:                       # 1 回落ちても、ほかのシードは続ける
        return seed, None, None, "", repr(e)[:160]


def parse_seeds(text):
    out = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def run(name, seeds, jobs=4):
    with mp.Pool(jobs) as pool:
        return pool.map(one, [(name, s) for s in seeds], chunksize=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("type")
    ap.add_argument("--seeds", default="1-32")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--each", action="store_true", help="1 回ごとの結果も出す")
    args = ap.parse_args()
    import registry
    if args.type not in registry.SIMS:
        print(f"種類 {args.type} はない。python video/make.py list で一覧が出る")
        return 2
    spec = registry.SIMS[args.type]
    if spec.get("heavy"):
        print("3D の型は対象外（1 回に時間がかかりすぎる）")
        return 2
    res = run(args.type, parse_seeds(args.seeds), args.jobs)
    ok = [r for r in res if r[4] is None]
    lens = [r[1] for r in ok]
    lo, hi = spec["length"]
    if args.each:
        for seed, d, win, result, err in res:
            print(f"  {seed:4d}  {d if d is not None else 'ERR':>5}  {err or result}")
    if lens:
        inside = sum(lo <= d <= hi for d in lens)
        print(f"{args.type}: {len(lens)} 回  長さ 最短 {min(lens)} / 中央 {statistics.median(lens):.1f} / 最長 {max(lens)} 秒"
              f"  目標 {lo}〜{hi} 秒に入った回数 {inside}/{len(lens)}")
    wins = collections.Counter(r[2] for r in ok if r[2] is not None)
    if wins:
        total = sum(wins.values())
        print("勝ち方の内訳: " + "  ".join(f"{k} {n}（{n * 100 // total}%）" for k, n in wins.most_common()))
    for seed, _d, _w, _r, err in res:
        if err:
            print(f"落ちたシード {seed}: {err}")
    return 1 if len(ok) < len(res) else 0


if __name__ == "__main__":
    sys.exit(main())
