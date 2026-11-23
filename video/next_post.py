#!/usr/bin/env python3
"""next_post.py — 次に投稿する動画（種類とシード）を決める

  python video/next_post.py             次の 1 本を「種類 シード 出どころ」で表示
  python video/next_post.py --pop       投稿が成功したあと、予約リストの先頭を消す

video/post_queue.txt に「種類 シード」を 1 行ずつ書いておくと、上から順に 1 日 1 本ずつ投稿されます。
リストが空になったら、種類を日替わりで回しながら新しいシードで作ります。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "post_queue.txt")
# 自動投稿で回す型。確認が済んだものだけを入れる。
# 入れていないもの: fill（参考動画なしで保留）、marble・faces・chime（3D。自動投稿に入れるかは検討中）
ROTATION = ["towers", "colorwar", "walls", "gear", "weapon", "glass", "bricks", "battle", "rings", "arms",
            "multiply", "hammer", "music", "rays", "cam", "grow",
            # 2026-11-23 に「合格」と言われた型
            "cannons", "merge", "bomb", "towers2", "blackhole", "bricks2", "rps", "gear2", "beams"]


def read_queue():
    if not os.path.exists(QUEUE):
        return [], []
    with open(QUEUE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    entries = [(i, ln.split()) for i, ln in enumerate(lines) if ln.strip() and not ln.strip().startswith("#")]
    return lines, entries


JST = timezone(timedelta(hours=9))
# 自動投稿の時刻（日本時間）。1 日 2 回。外部の呼び出し（cron-job.org）の時刻と合わせる
POST_TIMES = [(7, 10), (23, 10)]
POST_TIME = POST_TIMES[-1]    # 古い呼び出し元のために残してある（1 つだけ使う所は夜の時刻を使う）
EARLY = 3                     # 枠の切り替えは投稿時刻の 3 分前（時計のずれで呼び出しが少し早く来ても、次の枠に入るように）
POSTS = os.path.join(HERE, "posts.json")


def slot(when):
    """その時刻が「どの投稿枠」か。(日付, 何番目) を返す。枠は投稿時刻に始まり、次の投稿時刻の直前まで続く。
    いちばん早い投稿時刻より前の時間は、前日の最後の枠に入る。"""
    local = when.astimezone(JST)
    minutes = local.hour * 60 + local.minute
    starts = [h * 60 + m - EARLY for h, m in POST_TIMES]
    idx = max((i for i, st in enumerate(starts) if minutes >= st), default=None)
    if idx is None:
        return (local.date() - timedelta(days=1), len(POST_TIMES) - 1)
    return (local.date(), idx)


def on_hold(now=None):
    """自動投稿を止めている時間か（video/post_config.json の hold_until より前）。"""
    cfg = os.path.join(HERE, "post_config.json")
    if not os.path.exists(cfg):
        return False
    with open(cfg, "r", encoding="utf-8") as f:
        until = (json.load(f).get("hold_until") or "").strip()
    if not until:
        return False
    return (now or datetime.now(timezone.utc)) < datetime.fromisoformat(until)


def already_posted(now=None):
    """いまの枠の動画をもう投稿したか（遅れて届いた自動実行で 2 本目を出さないための確認）。
    自動投稿を止めている時間も「投稿しない」と答える。"""
    if on_hold(now):
        return True
    if not os.path.exists(POSTS):
        return False
    with open(POSTS, "r", encoding="utf-8") as f:
        posts = json.load(f)
    stamps = [p.get("posted_at") for p in posts if p.get("posted_at")]
    if not stamps:
        return False
    last = datetime.fromisoformat(max(stamps))
    return slot(last) >= slot(now or datetime.now(timezone.utc))


def rotation_pick(day, idx):
    """予約リストが空のときに作る動画（種類, シード）。枠ごとに種類もシードも変わる（同じ日に同じ動画を 2 回出さない）。"""
    n = day.toordinal() * len(POST_TIMES) + idx
    return ROTATION[n % len(ROTATION)], int(day.strftime("%Y%m%d")) * 10 + idx


def upcoming(n, now=None):
    """これから投稿される n 本を [(種類, シード, 投稿予定日)] で返す（予約リスト → 日替わりの順）。"""
    now = (now or datetime.now(timezone.utc)).astimezone(JST)
    day, idx = slot(now)
    _, entries = read_queue()
    out = []
    for i in range(n):
        idx += 1                                   # 次の枠へ
        if idx >= len(POST_TIMES):
            day, idx = day + timedelta(days=1), 0
        if i < len(entries):
            parts = entries[i][1]
            out.append((parts[0], int(parts[1]) if len(parts) > 1 else 1, day))
        else:
            out.append((*rotation_pick(day, idx), day))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", action="store_true")
    ap.add_argument("--already-posted", action="store_true",
                    help="いまの枠の動画を投稿済みなら終了コード 0（まだなら 1）")
    args = ap.parse_args()
    if args.already_posted:
        return 0 if already_posted() else 1
    lines, entries = read_queue()
    if args.pop:
        if entries:
            del lines[entries[0][0]]
            with open(QUEUE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        return 0
    if entries:
        parts = entries[0][1]
        print(parts[0], parts[1] if len(parts) > 1 else "1", "queue")
        return 0
    day, idx = slot(datetime.now(timezone.utc))
    kind, seed = rotation_pick(day, idx)
    print(kind, seed, "rotation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
