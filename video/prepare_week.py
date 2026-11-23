#!/usr/bin/env python3
"""prepare_week.py — これから 1 週間分の動画を先に作り、まとめて予約投稿するためのページを作る

  python video/prepare_week.py --days 7

TikTok と X は、公式の投稿画面に「予約投稿」があります。1 週間分を一度に予約しておけば、
毎日の手作業がなくなります。このスクリプトは、YouTube の自動投稿でこれから出る予定の動画を
同じ順番・同じ内容で先に書き出し、ダウンロードリンクと文面を docs/posts/week.md に並べます。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make          # noqa: E402
import next_post     # noqa: E402

PAGE = os.path.join(os.path.dirname(HERE), "docs", "posts", "week.md")
JST = timezone(timedelta(hours=9))
WEEKDAYS = "月火水木金土日"
FENCE = "````"


def render(items, repo, now=None):
    now = now or datetime.now(JST)
    hh, mm = next_post.POST_TIME
    out = [
        "# 今週の予約投稿用（TikTok・X）",
        "",
        f"作成: {now.strftime('%Y-%m-%d %H:%M')} JST ／ [投稿済みの一覧に戻る](README.md)",
        "",
        "これから 1 週間に YouTube へ自動投稿される予定の動画です。TikTok と X の予約投稿に使ってください。",
        "",
        "## 使い方（週に 1 回、10 分ほど）",
        "",
        "1. 下の動画を上から順にダウンロードする",
        "2. [TikTok の投稿画面](https://www.tiktok.com/tiktokstudio/upload) で動画を選び、文面を貼る。"
        "「Schedule（予約投稿）」を選んで、その動画の予定日時を入れて予約する",
        "3. [X の投稿画面](https://x.com/compose/post) で動画を付けて文面を貼る。"
        "カレンダーのアイコン（予約設定）を押して、同じ日時を入れて予約する",
        "4. これを動画の本数ぶん繰り返す",
        "",
        f"予約する時刻は、YouTube の自動投稿と同じ **{hh}:{mm:02d}（日本時間）** を目安にしています。"
        "予約できる期間の上限は各サービスの画面の表示に従ってください。",
        "",
    ]
    for it in items:
        d = it["date"]
        out += [
            "---",
            "",
            f"## {d.month}/{d.day}（{WEEKDAYS[d.weekday()]}） {it['title']}",
            "",
            f"- 予約する日時: **{d.month}/{d.day} {hh}:{mm:02d}**",
            f"- 種類: {it['label_ja']} ／ 長さ: {it['duration']}秒",
            f"- **[動画をダウンロード](https://github.com/{repo}/releases/download/videos/{it['file']})**（{it['file']}）",
            "",
            "**TikTok**",
            "",
            f"{FENCE}text", it["tiktok_caption"], FENCE,
            "",
            "**X**",
            "",
            f"{FENCE}text", it["x_post"], FENCE,
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--no-render", action="store_true", help="動画は作らず、予定の一覧だけ表示する")
    args = ap.parse_args()

    plan = next_post.upcoming(args.days)
    if args.no_render:
        for t, seed, d in plan:
            print(d.isoformat(), t, seed)
        return 0
    items = []
    for t, seed, d in plan:
        path = make.make_one(t, seed, args.out)
        with open(os.path.splitext(path)[0] + ".json", "r", encoding="utf-8") as f:
            info = json.load(f)
        info.update({"date": d, "file": os.path.basename(path)})
        items.append(info)
    repo = os.environ.get("GITHUB_REPOSITORY", "akabone4-hue/himaloop-videos")
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(render(items, repo))
    print(f"week page updated: {len(items)} videos -> docs/posts/week.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
