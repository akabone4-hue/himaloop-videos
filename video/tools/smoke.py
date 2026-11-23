#!/usr/bin/env python3
"""smoke.py — コードを直したあと、何も壊していないかを確かめる

  python video/tools/smoke.py              全部の型を 1 回ずつ、絵を描かずに回す（落ちないか・長さが極端でないか）
  python video/tools/smoke.py --golden     それに加えて、投稿の順番に入っている型の結果が前と同じかを比べる
  python video/tools/smoke.py --update     いまの結果を「正しい結果」として golden.json に書き直す

--golden が大事な理由:
  自動投稿は「型の名前 + シード」で動画を作る。共通の部品を直したとき、順番待ちの動画の中身が
  知らないうちに変わると、確認していない動画が投稿されてしまう。直したあとは必ず --golden で確かめ、
  変えるつもりで変えたときだけ --update する（そのときは作り直して目で確認する）。

  golden.json の結果は、この作業環境で作ったもの。GitHub 側の機械では計算の細かい違いで
  ずれることがあるので、GitHub 側（.github/workflows/check.yml）では「落ちないか」だけを確かめる。
"""

import argparse
import json
import multiprocessing as mp
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
sys.path.insert(0, VIDEO)
GOLDEN = os.path.join(HERE, "golden.json")


def one(job):
    name, seed = job
    import engine
    import registry
    try:
        v = engine.Video("", dry=True)
        meta = registry.SIMS[name]["run"](v, random.Random(seed)) or {}
        return name, seed, round(v.finish(), 2), str(meta.get("result", ""))[:80], None
    except Exception as e:
        return name, seed, None, "", repr(e)[:200]


def one_post(job):
    """自動投稿が実際に作る 1 本と同じ手順（make.py と同じく、長さが合うシードを探してから回す）。"""
    name, seed = job
    import make
    import registry
    try:
        spec = registry.SIMS[name]
        if spec.get("search", True):
            seed2, _d = make.find_seed(spec, seed)
        else:
            seed2 = seed
        _n, _s, d, result, err = one((name, seed2))
        return name, seed, d, f"seed {seed2}: {result}", err
    except Exception as e:
        return name, seed, None, "", repr(e)[:200]


def queued():
    """投稿の順番に入っている (型, シード)。順番待ちの一覧と、そのあとに回る型の最初の何本か。"""
    import next_post
    out = []
    path = os.path.join(VIDEO, "post_queue.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            parts = line.split("#")[0].split()
            if len(parts) >= 2 and parts[1].isdigit():
                out.append((parts[0], int(parts[1])))
    try:
        for item in next_post.upcoming(24):
            name, seed = item[0], item[1]
            if isinstance(name, str) and isinstance(seed, int) and (name, seed) not in out:
                out.append((name, seed))
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--golden", action="store_true", help="順番待ちの型の結果を golden.json と比べる")
    ap.add_argument("--update", action="store_true", help="golden.json を、いまの結果で書き直す")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    import registry
    bad = 0
    light = [n for n, s in registry.SIMS.items() if not s.get("heavy")]
    with mp.Pool(args.jobs) as pool:
        res = pool.map(one, [(n, 1) for n in light], chunksize=1)
        for name, seed, d, result, err in res:
            if err:
                print(f"NG   {name}: 落ちた {err}")
                bad += 1
            elif not 8 <= d <= 79:
                print(f"NG   {name}: 長さ {d} 秒（決着がつかない、またはすぐ終わる）")
                bad += 1
            else:
                print(f"ok   {name:10} {d:6.1f}s  {result}")
        if args.golden or args.update:
            jobs = [(n, s) for n, s in queued() if n in registry.SIMS and not registry.SIMS[n].get("heavy")]
            now = {f"{n} {s}": [d, r if not err else "ERR " + err] for n, s, d, r, err in pool.map(one_post, jobs, chunksize=1)}
            if args.update:
                with open(GOLDEN, "w", encoding="utf-8") as f:
                    json.dump(now, f, ensure_ascii=False, indent=1, sort_keys=True)
                print(f"golden.json を書き直した（{len(now)} 件）")
            else:
                old = json.load(open(GOLDEN, encoding="utf-8")) if os.path.exists(GOLDEN) else {}
                for key, val in now.items():
                    if key not in old:
                        print(f"new  {key}: golden.json にまだない（--update で足す）")
                    elif old[key] != val:
                        print(f"DIFF {key}: 前 {old[key]} → いま {val}")
                        bad += 1
                same = sum(1 for k, v_ in now.items() if old.get(k) == v_)
                print(f"順番待ちの型: {same}/{len(now)} 件が前と同じ結果")
    print("問題なし" if not bad else f"問題 {bad} 件")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
