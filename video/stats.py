#!/usr/bin/env python3
"""stats.py — 投稿した動画の数字を集めて、一覧ページを作る

  python video/stats.py

video/posts.json にある YouTube の動画について、次を取得します。
  ・再生数、高評価、コメント数（YouTube Data API。ほぼリアルタイム）
  ・平均視聴率、平均視聴時間、共有数、登録者の増減（YouTube Analytics API。1〜3 日遅れ）
結果は docs/stats/README.md に表として書き出し、日ごとの記録を video/stats.json に残します。

必要な権限（リフレッシュトークン取得時のスコープ）:
  https://www.googleapis.com/auth/youtube.readonly
  https://www.googleapis.com/auth/yt-analytics.readonly
権限が足りない場合は、取れた範囲だけで表を作り、足りないものをページに書きます。
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

import next_post
import post_buffer
import post_log
from upload_youtube import access_token

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(HERE, "posts.json")
HISTORY = os.path.join(HERE, "stats.json")
OTHER = os.path.join(HERE, "other_stats.json")     # TikTok・X の数字（手入力。API では取っていない）
PAGE = os.path.join(os.path.dirname(HERE), "docs", "stats", "README.md")
DATA_URL = os.environ.get("YT_DATA_URL", "https://www.googleapis.com/youtube/v3/videos")
ANALYTICS_URL = os.environ.get("YT_ANALYTICS_URL", "https://youtubeanalytics.googleapis.com/v2/reports")
JST = timezone(timedelta(hours=9))


def video_id(url):
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{6,})", url or "")
    return m.group(1) if m else ""


def fetch_countries(token, start):
    """どの国から見られているか（チャンネル全体、再生数の多い順）。戻り値: ([(国コード, 再生数)], エラー文)"""
    r = requests.get(ANALYTICS_URL, timeout=30, headers={"Authorization": f"Bearer {token}"}, params={
        "ids": "channel==MINE", "startDate": start, "endDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "metrics": "views", "dimensions": "country", "sort": "-views", "maxResults": 25})
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}: {r.text[:300]}"
    return [(row[0], int(row[1])) for row in r.json().get("rows", []) or []], ""


# 国コード → (表示名, 協定世界時との差の目安)。投稿時刻を考えるための大まかな値（夏時間は見ていない）
COUNTRY = {"US": ("アメリカ", -6), "IN": ("インド", 5.5), "GB": ("イギリス", 0), "JP": ("日本", 9), "BR": ("ブラジル", -3),
           "ID": ("インドネシア", 7), "PH": ("フィリピン", 8), "MX": ("メキシコ", -6), "DE": ("ドイツ", 1), "FR": ("フランス", 1),
           "CA": ("カナダ", -5), "VN": ("ベトナム", 7), "TH": ("タイ", 7), "TR": ("トルコ", 3), "RU": ("ロシア", 3),
           "PK": ("パキスタン", 5), "BD": ("バングラデシュ", 6), "KR": ("韓国", 9), "ES": ("スペイン", 1), "IT": ("イタリア", 1),
           "AU": ("オーストラリア", 10), "EG": ("エジプト", 2), "SA": ("サウジアラビア", 3), "NG": ("ナイジェリア", 1),
           "AR": ("アルゼンチン", -3), "CO": ("コロンビア", -5), "PL": ("ポーランド", 1), "MY": ("マレーシア", 8),
           "IQ": ("イラク", 3), "DZ": ("アルジェリア", 1), "MA": ("モロッコ", 1), "UA": ("ウクライナ", 2), "NL": ("オランダ", 1)}


COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def fetch_comments(token, ids, per_video=5):
    """動画ごとの新しいコメント（本文と日付だけ。書いた人の名前は記録しない）。戻り値: {id: [(日付, 本文)]}
    403 が返るのは、認証のときに「コメントを読む許可」（youtube.force-ssl）を付けていないため。
    その場合は 1 回であきらめ、{"blocked": True} を返す（ページには数だけ出る）。"""
    out = {}
    for vid in ids:
        r = requests.get(COMMENTS_URL, timeout=30, headers={"Authorization": f"Bearer {token}"}, params={
            "part": "snippet", "videoId": vid, "maxResults": per_video, "order": "time", "textFormat": "plainText"})
        if r.status_code == 403:
            print("comments: not permitted with the current YouTube authorization (needs youtube.force-ssl); skipped")
            return {"blocked": True}
        if r.status_code != 200:
            print(f"comments failed for {vid}: HTTP {r.status_code}")
            continue
        rows = []
        for it in r.json().get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            text = " ".join((sn.get("textDisplay") or "").split())[:200]
            rows.append((sn.get("publishedAt", "")[:10], text, int(sn.get("likeCount", 0))))
        if rows:
            out[vid] = rows
    return out


def fetch_public(token, ids):
    """再生数・高評価・コメント数・公開設定。戻り値: ({id: {...}}, エラー文)"""
    out = {}
    for i in range(0, len(ids), 50):
        r = requests.get(DATA_URL, timeout=30, headers={"Authorization": f"Bearer {token}"},
                         params={"part": "statistics,status", "id": ",".join(ids[i:i + 50]), "maxResults": 50})
        if r.status_code != 200:
            return out, f"HTTP {r.status_code}: {r.text[:300]}"
        for it in r.json().get("items", []):
            st = it.get("statistics", {})
            out[it["id"]] = {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                             "comments": int(st.get("commentCount", 0)),
                             "privacy": it.get("status", {}).get("privacyStatus", "")}
    return out, ""


def fetch_analytics(token, ids, start):
    """平均視聴率など。戻り値: ({id: {...}}, エラー文)"""
    metrics = "views,averageViewPercentage,averageViewDuration,shares,subscribersGained,subscribersLost"
    r = requests.get(ANALYTICS_URL, timeout=30, headers={"Authorization": f"Bearer {token}"}, params={
        "ids": "channel==MINE", "startDate": start, "endDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "metrics": metrics, "dimensions": "video", "filters": "video==" + ",".join(ids[:200]),
        "sort": "-views", "maxResults": 200})
    if r.status_code != 200:
        return {}, f"HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    cols = [c["name"] for c in data.get("columnHeaders", [])]
    out = {}
    for row in data.get("rows", []) or []:
        rec = dict(zip(cols, row))
        out[rec["video"]] = {"a_views": int(rec.get("views", 0)),
                             "avg_pct": float(rec.get("averageViewPercentage", 0)),
                             "avg_sec": float(rec.get("averageViewDuration", 0)),
                             "shares": int(rec.get("shares", 0)),
                             "subs": int(rec.get("subscribersGained", 0)) - int(rec.get("subscribersLost", 0))}
    return out, ""


BUFFER_POSTS = """
query($input: PostsInput!, $first: Int!, $after: String) {
  posts(first: $first, after: $after, input: $input) {
    edges { cursor node { id channelService text sentAt externalLink metrics { type value } } }
  }
}
"""


def fetch_buffer_posts():
    """Buffer 経由で公開した投稿と、その数字（再生数など）を取得する。戻り値: ([投稿], エラー文)"""
    orgs = post_buffer.gql("query { account { organizations { id } } }")
    if orgs.get("errors"):
        return [], json.dumps(orgs["errors"], ensure_ascii=False)[:300]
    out = []
    for org in ((orgs.get("data") or {}).get("account") or {}).get("organizations") or []:
        after = None
        for _ in range(5):                      # 多くても 5 ページ（500 件）まで
            res = post_buffer.gql(BUFFER_POSTS, {"input": {"organizationId": org["id"], "filter": {"status": ["sent"]}},
                                                 "first": 100, "after": after})
            if res.get("errors"):
                return out, json.dumps(res["errors"], ensure_ascii=False)[:300]
            edges = ((res.get("data") or {}).get("posts") or {}).get("edges") or []
            for e in edges:
                n = e["node"]
                out.append({"service": (n.get("channelService") or "").lower(),
                            "first_line": (n.get("text") or "").split("\n")[0].strip(),
                            "sent_at": n.get("sentAt") or "", "link": n.get("externalLink") or "",
                            "metrics": {m["type"]: m["value"] for m in n.get("metrics") or []}})
            if len(edges) < 100:
                break
            after = edges[-1]["cursor"]
    return out, ""


def match_buffer(posts, buffer_posts):
    """投稿記録（posts.json）の各動画に、同じタイトルで前後 36 時間以内に出た Buffer の投稿を対応づける。
    戻り値: {ファイル名: {"tiktok": {...}, "x": {...}}}"""
    out = {}
    for p in posts:
        try:
            base = datetime.fromisoformat(p["posted_at"])
        except (KeyError, ValueError):
            continue
        for bp in buffer_posts:
            if bp["first_line"] != p.get("title") or not bp["sent_at"]:
                continue
            try:
                sent = datetime.fromisoformat(bp["sent_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            gap = abs((sent - base).total_seconds())
            if gap > 36 * 3600:
                continue
            key = "tiktok" if bp["service"] == "tiktok" else "x" if bp["service"] in ("twitter", "x") else None
            if not key:
                continue
            cur = out.setdefault(p.get("file", ""), {}).get(key)
            if cur is None or gap < cur["_gap"]:
                out[p.get("file", "")][key] = {"_gap": gap, "link": bp["link"], **bp["metrics"]}
    return out


def load_other():
    if os.path.exists(OTHER):
        with open(OTHER, "r", encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    return {}


def render(posts, pub, ana, notes, now=None, other=None, buf=None, countries=None, comments=None):
    now = now or datetime.now(JST)
    other = other or {}
    buf = buf or {}
    countries = countries or []
    comments = comments or {}
    out = ["# 動画の数字", "",
           f"最終更新: {now.strftime('%Y-%m-%d %H:%M')} JST ／ 1 日 1 回、自動で更新されます", ""]
    out += [f"> {n}" for n in notes]
    if notes:
        out.append("")
    out += ["## 見方", "",
            "- **平均視聴率**: 動画の長さに対して平均で何 % まで見られたか。ショートでは 100% を超えると繰り返し見られている",
            "- **再生数**はほぼリアルタイム。平均視聴率などは YouTube 側の集計に 1〜3 日かかるため、新しい動画は「—」になる",
            "- **TikTok・X** の列は、Buffer 経由で自動投稿した動画は Buffer から取得した数字。"
            "手動で投稿した動画は、記録した時点の数字（`video/other_stats.json`、日付は記録日）",
            ""]
    rows = []
    for p in posts:
        vid = video_id(p.get("youtube_url"))
        if not vid:
            continue
        d = datetime.fromisoformat(p["posted_at"]).astimezone(JST)
        rows.append((p, vid, d, pub.get(vid, {}), ana.get(vid, {})))

    def num(v, fmt="{:,}"):
        return fmt.format(v) if v not in (None, "") else "—"

    def manual(p, key):
        service, metric_names = ("tiktok", ("views",)) if key == "tiktok_views" else ("x", ("impressions", "views"))
        got = (buf.get(p.get("file", ""), {}) or {}).get(service) or {}
        # Buffer は、数字を持っていない投稿にも全項目 0 を返す。全部 0 のときは「取れていない」として扱う
        if any(v for k, v in got.items() if not k.startswith("_") and isinstance(v, (int, float))):
            for m in metric_names:
                if got.get(m) is not None:
                    return f"{got[m]:,.0f}"
        rec = other.get(p.get("file", ""), {})
        if rec.get(key) in (None, ""):
            return "—"
        day = str(rec.get("as_of", ""))[5:].replace("-", "/")
        return f"{rec[key]:,}" + (f"（{day}）" if day else "")

    out += ["## 動画ごと", "",
            "| 投稿日時 | 種類 | タイトル | YouTube 再生数 | 高評価 | コメント | 平均視聴率 | 平均視聴時間 | 共有 | 登録者 "
            "| TikTok 再生数 | X 表示回数 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for p, vid, d, a, b in rows:
        title = p["title"].replace("|", "\\|")
        mark = "" if a.get("privacy", "public") == "public" else f"（{a.get('privacy')}）"
        out.append(f"| {d.month}/{d.day} {d.hour}:{d.minute:02d} | {p['type']} | [{title}]({p['youtube_url']}){mark} | "
                   f"{num(a.get('views'))} | {num(a.get('likes'))} | {num(a.get('comments'))} | "
                   f"{num(b.get('avg_pct'), '{:.0f}%')} | {num(b.get('avg_sec'), '{:.1f}秒')} | "
                   f"{num(b.get('shares'))} | {num(b.get('subs'), '{:+,}')} | "
                   f"{manual(p, 'tiktok_views')} | {manual(p, 'x_views')} |")
    if not rows:
        out.append("| — | — | まだ投稿がありません | — | — | — | — | — | — | — | — | — |")

    # 種類ごとの平均（どの型を増やすかの判断材料）
    by = {}
    for p, vid, d, a, b in rows:
        if "views" not in a:
            continue
        g = by.setdefault(p["type"], {"n": 0, "views": 0, "pct": [], "label": p.get("label_ja", p["type"])})
        g["n"] += 1
        g["views"] += a["views"]
        if "avg_pct" in b:
            g["pct"].append(b["avg_pct"])
    if by:
        out += ["", "## 種類ごとの平均", "",
                "| 種類 | 内容 | 本数 | 1 本あたりの再生数 | 平均視聴率 |", "|---|---|---:|---:|---:|"]
        for t, g in sorted(by.items(), key=lambda kv: -kv[1]["views"] / kv[1]["n"]):
            pct = f"{sum(g['pct']) / len(g['pct']):.0f}%" if g["pct"] else "—"
            out.append(f"| {t} | {g['label']} | {g['n']} | {g['views'] / g['n']:,.0f} | {pct} |")
        out += ["", "本数が少ないうちは、1 本の当たり外れで平均が大きく動きます。各種類 3 本以上たまってから比べてください。"]
        # ---- 朝と夜の比較（1 日 2 回の投稿で、どちらの時間帯が伸びるかを見る）
        slots = {}
        for p, vid, d, a, an in rows:
            if "views" not in a:
                continue
            key = "朝（7:10 ごろ）" if 3 <= d.hour < 15 else "夜（23:10 ごろ）"
            g = slots.setdefault(key, {"views": [], "pct": []})
            g["views"].append(a["views"])
            if an.get("avg_pct"):
                g["pct"].append(an["avg_pct"])
        out += ["", "## 投稿した時間帯ごと", "",
                "2026-11-23 の夜から 1 日 2 回（7:10 と 23:10）に変えた。それより前の投稿は、すべて朝（5:30〜11:00）に出ている。",
                "「まん中の値」は、再生数を順に並べたときの中央の 1 本。飛び抜けて伸びた 1 本に引っぱられないので、比べるときはこちらを見る。",
                "", "| 時間帯 | 本数 | 1 本あたりの再生数 | まん中の値 | 平均視聴率 |", "|---|---:|---:|---:|---:|"]
        for key in ("朝（7:10 ごろ）", "夜（23:10 ごろ）"):
            g = slots.get(key)
            if not g:
                out.append(f"| {key} | 0 | — | — | — |")
                continue
            vs = sorted(g["views"])
            mid = vs[len(vs) // 2] if len(vs) % 2 else (vs[len(vs) // 2 - 1] + vs[len(vs) // 2]) / 2
            pct = f"{sum(g['pct']) / len(g['pct']):.0f}%" if g["pct"] else "—"
            out.append(f"| {key} | {len(vs)} | {sum(vs) / len(vs):,.0f} | {mid:,.0f} | {pct} |")
    if comments.get("blocked"):
        out += ["", "## 新しいコメント（YouTube）", "",
                "コメントの本文は、いまの YouTube の許可では読めません（上の表には数だけ出ます）。"
                "本文もここに並べたい場合は、認証をやり直して「コメントの管理」の許可を足す必要があります（任意）。"]
    elif comments:
        out += ["", "## 新しいコメント（YouTube）", "",
                "動画ごとに新しい順で 5 件まで。次に作る動画の手がかりにする。", ""]
        for p, vid, d, a, an in rows:
            if vid not in comments:
                continue
            out.append(f"**{p['type']}**（{d.month}/{d.day}）: [{p.get('title', '')}]({p['youtube_url']})")
            out.append("")
            for day, text, likes in comments[vid]:
                safe = text.replace("|", "/").replace("<", "＜").replace(">", "＞")
                out.append(f"- {day[5:].replace('-', '/')} 「{safe}」" + (f"（高評価 {likes}）" if likes else ""))
            out.append("")
    if countries:
        total = sum(n for _c, n in countries) or 1
        times = next_post.POST_TIMES
        head = " | ".join(f"{h}:{m:02d} の投稿は現地で" for h, m in times)
        out += ["", "## どの国から見られているか（YouTube）", "",
                "投稿時刻を決める材料です。右の列は、日本時間の投稿時刻がその国で何時ごろにあたるか（夏時間は見ていない目安）。",
                "", f"| 国 | 再生数 | 割合 | {head} |", "|---|---:|---:|" + "---|" * len(times)]
        for code, n in countries[:12]:
            name, off = COUNTRY.get(code, (code, None))
            local = " | ".join("—" if off is None else f"{int((h + m / 60 - 9 + off) % 24):02d} 時ごろ" for h, m in times)
            out.append(f"| {name} | {n:,} | {100 * n / total:.0f}% | {local} |")
    return "\n".join(out) + "\n"


def main():
    posts = []
    if os.path.exists(POSTS):
        with open(POSTS, "r", encoding="utf-8") as f:
            posts = json.load(f)
    ids = [v for v in (video_id(p.get("youtube_url")) for p in posts) if v]
    notes, pub, ana, countries, comments = [], {}, {}, [], {}
    if ids:
        token = access_token()
        pub, err = fetch_public(token, ids)
        if err:
            print(f"public stats failed: {err}")
            notes.append("再生数を取得できませんでした。リフレッシュトークンに youtube.readonly の権限が必要です"
                         "（video/POSTING.md の「数字を自動で集める」を参照）。")
        # 公開設定が変わっていたら（手動で公開した等）、投稿一覧ページにも反映する
        changed = False
        for p in posts:
            now_privacy = pub.get(video_id(p.get("youtube_url")), {}).get("privacy")
            if now_privacy and p.get("privacy") != now_privacy:
                p["privacy"] = now_privacy
                changed = True
        if changed:
            with open(POSTS, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=1)
            with open(post_log.PAGE, "w", encoding="utf-8") as f:
                f.write(post_log.render(posts))
        first = min(datetime.fromisoformat(p["posted_at"]) for p in posts if video_id(p.get("youtube_url")))
        comments = fetch_comments(token, [v for v in ids if pub.get(v, {}).get("comments")])
        countries, c_err = fetch_countries(token, (first - timedelta(days=1)).strftime("%Y-%m-%d"))
        if c_err:
            print(f"country stats failed: {c_err}")
        ana, err = fetch_analytics(token, ids, (first - timedelta(days=1)).strftime("%Y-%m-%d"))
        if err:
            print(f"analytics failed: {err}")
            notes.append("平均視聴率などを取得できませんでした。YouTube Analytics API の有効化と、"
                         "yt-analytics.readonly の権限が必要です（video/POSTING.md の「数字を自動で集める」を参照）。")
    buf = {}
    if os.environ.get("BUFFER_API_KEY") and posts:
        buffer_posts, err = fetch_buffer_posts()
        if err:
            print(f"buffer stats failed: {err}")
        buf = match_buffer(posts, buffer_posts)
        print(f"buffer posts: {len(buffer_posts)} fetched, matched to {len(buf)} videos")
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(render(posts, pub, ana, notes, other=load_other(), buf=buf, countries=countries, comments=comments))

    if pub:                                 # 日ごとの記録（伸び方をあとで見られるように）
        history = []
        if os.path.exists(HISTORY):
            with open(HISTORY, "r", encoding="utf-8") as f:
                history = json.load(f)
        today = datetime.now(JST).strftime("%Y-%m-%d")
        history = [h for h in history if h["date"] != today]
        by_id = {video_id(p.get("youtube_url")): p.get("file", "") for p in posts}
        history.append({"date": today, "videos": {
            v: {**pub.get(v, {}), **ana.get(v, {}),
                **{f"{svc}_{k}": val for svc, rec in (buf.get(by_id.get(v, ""), {}) or {}).items()
                   for k, val in rec.items() if not k.startswith("_") and k != "link"}}
            for v in ids}})
        with open(HISTORY, "w", encoding="utf-8") as f:
            json.dump(history[-400:], f, ensure_ascii=False, indent=1)
    print(f"stats updated: {len(ids)} videos, public={len(pub)}, analytics={len(ana)}, notes={len(notes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
