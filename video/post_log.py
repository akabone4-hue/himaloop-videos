#!/usr/bin/env python3
"""post_log.py — 投稿した動画を記録し、TikTok・X 用のコピペ一覧ページを作り直す

  python video/post_log.py video/out/weapon_21.mp4 --asset-url <動画ファイルのURL>

記録は video/posts.json、一覧ページは docs/posts/README.md。
ページは GitHub 上で開くと、文面の右上にコピーボタンが付きます。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "posts.json")
PAGE = os.path.join(os.path.dirname(HERE), "docs", "posts", "README.md")
JST = timezone(timedelta(hours=9))
WEEKDAYS = "月火水木金土日"
FENCE = "````"
MAX_ON_PAGE = 60


def load():
    if os.path.exists(LOG):
        with open(LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def render(entries, now=None):
    now = now or datetime.now(JST)
    out = [
        "# 投稿一覧",
        "",
        f"最終更新: {now.strftime('%Y-%m-%d %H:%M')} JST ／ 新しい動画が上に並びます",
        "",
        "YouTube・TikTok・X へは自動で投稿されます（TikTok と X は、YouTube の約 10 分後に Buffer 経由）。",
        "下のリンクと文面は、手で投稿し直したいとき用です。",
        "",
        "## 手で投稿するとき",
        "",
        "1. 「動画をダウンロード」を押して mp4 を保存する",
        "2. 「TikTok の投稿画面を開く」を押し、保存した mp4 を選ぶ",
        "3. 下の文面の右上にあるコピーボタンを押し、説明欄に貼って投稿する",
        "4. X も同じ手順で、X 用の文面を貼る",
        "",
    ]
    if not entries:
        out.append("まだ投稿した動画はありません。")
    for e in entries[:MAX_ON_PAGE]:
        d = datetime.fromisoformat(e["posted_at"]).astimezone(JST)
        out += [
            "---",
            "",
            f"## {d.month}/{d.day}（{WEEKDAYS[d.weekday()]}） {e['title']}",
            "",
            f"- 種類: {e.get('label_ja', e['type'])} ／ 長さ: {e.get('duration', '?')}秒",
            f"- **[動画をダウンロード]({e['asset_url']})**（{e['file']}）",
        ]
        if e.get("youtube_url"):
            note = ""
            if e.get("privacy") and e["privacy"] != "public":
                note = f"（公開設定: {e['privacy']}。公開するには YouTube Studio で変更）"
            out.append(f"- YouTube: {e['youtube_url']}{note}")
        out += [
            "",
            "**TikTok** ／ [TikTok の投稿画面を開く](https://www.tiktok.com/tiktokstudio/upload)",
            "",
            f"{FENCE}text", e["tiktok_caption"], FENCE,
            "",
            "**X** ／ [X の投稿画面を開く](https://x.com/compose/post)",
            "",
            f"{FENCE}text", e["x_post"], FENCE,
            "",
        ]
    if len(entries) > MAX_ON_PAGE:
        out.append(f"これより古い {len(entries) - MAX_ON_PAGE} 件は `video/posts.json` に残っています。")
    return "\n".join(out).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?", help="mp4 のパス（同名の .json が必要）。省略するとページの作り直しだけ行う")
    ap.add_argument("--asset-url", help="一覧ページからダウンロードさせる動画ファイルの URL")
    ap.add_argument("--youtube-url", default="", help="すでに YouTube に上げてある場合の URL")
    ap.add_argument("--privacy", default="")
    args = ap.parse_args()

    entries = load()
    if args.video:
        base = os.path.splitext(args.video)[0]
        with open(base + ".json", "r", encoding="utf-8") as f:
            info = json.load(f)
        yt = {"url": args.youtube_url, "privacy": args.privacy}
        if not args.youtube_url and os.path.exists(base + ".posted.json"):
            with open(base + ".posted.json", "r", encoding="utf-8") as f:
                yt = json.load(f)
        entry = {
            "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "type": info["type"], "seed": info.get("seed"), "label_ja": info.get("label_ja", info["type"]),
            "file": os.path.basename(args.video), "duration": info.get("duration"),
            "title": info["title"], "title_ja": info["title_ja"],
            "tiktok_caption": info["tiktok_caption"], "x_post": info["x_post"],
            "asset_url": args.asset_url or "", "youtube_url": yt.get("url", ""), "privacy": yt.get("privacy", ""),
        }
        entries = [e for e in entries if e["file"] != entry["file"]]     # 同じ動画の記録は上書き
        entries.insert(0, entry)
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(render(entries))
    print(f"post list updated: {len(entries)} entries -> docs/posts/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
