#!/usr/bin/env python3
"""upload_youtube.py — 作った動画を YouTube にアップロードする

  python video/upload_youtube.py video/out/weapon_21.mp4 --privacy public
  python video/upload_youtube.py --check          投稿せず、認証情報が通るかだけ確かめる

同じ名前の .json（make.py が書き出す）からタイトル・説明文・タグを読みます。
認証情報は環境変数で渡します（GitHub の Secrets に登録。ファイルやチャットには書かない）:
  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN

縦型で 3 分以内の動画は、YouTube 側で自動的にショートとして扱われます。
"""

import argparse
import json
import os
import sys

import requests

TOKEN_URL = os.environ.get("YT_TOKEN_URL", "https://oauth2.googleapis.com/token")
UPLOAD_URL = os.environ.get("YT_UPLOAD_URL", "https://www.googleapis.com/upload/youtube/v3/videos")


def fail(msg, resp=None):
    print(f"ERROR: {msg}", file=sys.stderr)
    if resp is not None:
        print(f"  HTTP {resp.status_code}: {resp.text[:800]}", file=sys.stderr)
    sys.exit(1)


SCOPES = {
    "https://www.googleapis.com/auth/youtube.upload": "動画のアップロード（自動投稿に必須）",
    "https://www.googleapis.com/auth/youtube.readonly": "再生数・高評価・コメント数の読み取り",
    "https://www.googleapis.com/auth/yt-analytics.readonly": "平均視聴率などの読み取り",
}


def access_token(with_scopes=False):
    need = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        fail(f"環境変数が未設定です: {', '.join(missing)}")
    r = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        fail("アクセストークンを取得できません。リフレッシュトークンが失効したか、ID/シークレットが違います", r)
    if with_scopes:
        return r.json()["access_token"], r.json().get("scope", "").split()
    return r.json()["access_token"]


def _start(token, size, body, parts):
    return requests.post(UPLOAD_URL, timeout=60, params={"uploadType": "resumable", "part": parts},
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                                  "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                         data=json.dumps(body).encode("utf-8"))


def upload(path, info, privacy):
    token = access_token()
    size = os.path.getsize(path)
    body = {
        "snippet": {"title": info["title"][:100], "description": info.get("description", "")[:4900],
                    "tags": info.get("tags", []), "categoryId": "24"},        # 24 = エンターテインメント
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    r = None
    if info.get("title_ja"):
        # 日本語のタイトル・説明文を「翻訳」として付ける。日本語設定の視聴者にはこちらが表示される
        localized = json.loads(json.dumps(body))
        localized["snippet"]["defaultLanguage"] = "en"
        localized["localizations"] = {"ja": {"title": info["title_ja"][:100],
                                             "description": info.get("description_ja", "")[:4900]}}
        r = _start(token, size, localized, "snippet,status,localizations")
        if r.status_code != 200 or "Location" not in r.headers:
            print(f"NOTE: 日本語版つきの登録が通らなかったので、英語のみで登録し直します (HTTP {r.status_code})")
            r = None
    if r is None:
        r = _start(token, size, body, "snippet,status")
    if r.status_code != 200 or "Location" not in r.headers:
        fail("アップロードを開始できません", r)
    with open(path, "rb") as f:
        r2 = requests.put(r.headers["Location"], timeout=900, data=f,
                          headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if r2.status_code not in (200, 201):
        fail("動画の送信に失敗しました", r2)
    return r2.json()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public")
    ap.add_argument("--check", action="store_true", help="投稿はせず、認証情報が通るかだけ確かめる")
    args = ap.parse_args()
    if args.check:
        _, granted = access_token(with_scopes=True)
        print("OK: 認証情報は有効です（アクセストークンを取得できました）")
        lines = ["### YouTube の権限"]
        for scope, label in SCOPES.items():
            mark = "あり" if scope in granted else "なし"
            print(f"  [{mark}] {label}")
            lines.append(f"- {mark}: {label}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        if "https://www.googleapis.com/auth/youtube.upload" not in granted:
            fail("アップロードの権限がありません。このままでは自動投稿が失敗します")
        return 0
    if not args.video:
        fail("動画ファイルを指定してください")
    meta_path = os.path.splitext(args.video)[0] + ".json"
    with open(meta_path, "r", encoding="utf-8") as f:
        info = json.load(f)
    res = upload(args.video, info, args.privacy)
    vid = res.get("id", "")
    got = (res.get("status") or {}).get("privacyStatus", "?")
    url = f"https://www.youtube.com/shorts/{vid}"
    print(f"uploaded: {url}  title={info['title']!r}  privacy={got}")
    with open(os.path.splitext(args.video)[0] + ".posted.json", "w", encoding="utf-8") as f:
        json.dump({"id": vid, "url": url, "privacy": got}, f)       # 投稿一覧ページ用
    lines = [f"### 投稿しました", f"- {info['title']}", f"- {url}", f"- 公開設定: {got}"]
    if got != args.privacy:
        note = (f"指定は {args.privacy} でしたが、YouTube 側で {got} になりました。"
                "未審査の API プロジェクトは非公開に固定されることがあります。YouTube Studio で公開設定を変更してください。")
        print("NOTE: " + note)
        lines.append(f"- 注意: {note}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
