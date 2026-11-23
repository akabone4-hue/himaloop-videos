#!/usr/bin/env python3
"""post_buffer.py — Buffer 経由で TikTok と X に動画を投稿する

  python video/post_buffer.py --check
      接続中のチャンネル（TikTok・X など）と、投稿 API の書式を表示する。投稿はしない。
  python video/post_buffer.py video/out/weapon_21.mp4 --url <動画の公開URL>
      同じ名前の .json から文面を読み、TikTok と X のチャンネルにすぐ公開投稿する。
  python video/post_buffer.py video/out/weapon_21.mp4 --url <動画の公開URL> --draft-test
      公開せず Buffer の下書きとして登録し、通ったことを確認したら下書きを消す（動作確認用）。
  python video/post_buffer.py --is-enabled
      自動投稿の開始日（video/post_config.json の buffer_start）を過ぎていれば終了コード 0。

Buffer は TikTok と X の審査を通った投稿サービスで、自作アプリでは公開投稿できない TikTok にも
公開で投稿できます。動画は公開 URL で渡す必要があります。
認証は環境変数 BUFFER_API_KEY（GitHub の Secrets に登録）。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_URL = os.environ.get("BUFFER_API_URL", "https://api.buffer.com")
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_config.json")
JST = timezone(timedelta(hours=9))
# Buffer 側のサービス名 → 文面に使う項目（.json のキー）
TARGETS = {"tiktok": "tiktok_caption", "twitter": "x_post", "x": "x_post"}

TYPE_FRAGMENT = "fragment T on __Type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }"
INTROSPECTION = """
query {
  __schema {
    mutationType { fields { name args { name type { ...T } } } }
    types { kind name enumValues { name } inputFields { name type { ...T } } }
  }
}
""" + TYPE_FRAGMENT


def gql(query, variables=None):
    key = os.environ.get("BUFFER_API_KEY")
    if not key:
        print("ERROR: 環境変数 BUFFER_API_KEY が未設定です", file=sys.stderr)
        sys.exit(1)
    r = requests.post(API_URL, timeout=60, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"query": query, "variables": variables or {}})
    try:
        body = r.json()
    except ValueError:
        body = {"errors": [{"message": f"HTTP {r.status_code}: {r.text[:300]}"}]}
    if r.status_code != 200 and "errors" not in body:
        body["errors"] = [{"message": f"HTTP {r.status_code}: {r.text[:300]}"}]
    return body


def type_str(t):
    if not t:
        return "?"
    if t.get("kind") == "NON_NULL":
        return type_str(t.get("ofType")) + "!"
    if t.get("kind") == "LIST":
        return "[" + type_str(t.get("ofType")) + "]"
    return t.get("name") or "?"


def list_channels():
    """[(id, name, service)] を返す。API の形が違った場合はエラー文を表示して空を返す。"""
    orgs = gql("query { account { organizations { id name } } }")
    if orgs.get("errors"):
        print("account query errors:", json.dumps(orgs["errors"], ensure_ascii=False)[:600])
    out = []
    for org in ((orgs.get("data") or {}).get("account") or {}).get("organizations") or []:
        res = gql('query { channels(input: { organizationId: "%s" }) { id name service } }' % org["id"])
        if res.get("errors"):
            print("channels query errors:", json.dumps(res["errors"], ensure_ascii=False)[:600])
        for ch in (res.get("data") or {}).get("channels") or []:
            out.append((ch["id"], ch.get("name", ""), (ch.get("service") or "").lower()))
    if not out:
        res = gql("query { channels { id name service } }")
        if res.get("errors"):
            print("bare channels query errors:", json.dumps(res["errors"], ensure_ascii=False)[:600])
        for ch in (res.get("data") or {}).get("channels") or []:
            out.append((ch["id"], ch.get("name", ""), (ch.get("service") or "").lower()))
    return out


def check():
    channels = list_channels()
    print(f"channels: {len(channels)}")
    for cid, name, service in channels:
        print(f"  [{service}] {name}  id={cid}")
    wanted = {"tiktok": False, "x": False}
    for _, _, service in channels:
        if service == "tiktok":
            wanted["tiktok"] = True
        if service in ("twitter", "x"):
            wanted["x"] = True
    print(f"TikTok 接続: {'あり' if wanted['tiktok'] else 'なし'} / X 接続: {'あり' if wanted['x'] else 'なし'}")

    schema = gql(INTROSPECTION)
    if schema.get("errors"):
        print("introspection errors:", json.dumps(schema["errors"], ensure_ascii=False)[:600])
        return 0
    sch = schema["data"]["__schema"]
    print("--- mutations ---")
    for f in (sch.get("mutationType") or {}).get("fields") or []:
        args = ", ".join(f"{a['name']}: {type_str(a['type'])}" for a in f.get("args") or [])
        print(f"  {f['name']}({args})")
    print("--- input types / enums ---")
    for t in sch.get("types") or []:
        name = t.get("name") or ""
        if name.startswith("__"):
            continue
        if t["kind"] == "INPUT_OBJECT":
            fields = ", ".join(f"{f['name']}: {type_str(f['type'])}" for f in t.get("inputFields") or [])
            print(f"  input {name} {{ {fields} }}")
        elif t["kind"] == "ENUM":
            print(f"  enum {name} {{ {' | '.join(v['name'] for v in t.get('enumValues') or [])} }}")
    return 0


CREATE_POST = """
mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}
"""


DELETE_POST = """
mutation($input: DeletePostInput!) {
  deletePost(input: $input) { __typename ... on MutationError { message } }
}
"""


def wait_until_sent(posted, timeout=180, interval=30):
    """投稿が実際に公開されるまで待って、最終状態を表示する。posted: [(サービス, 投稿ID)]

    Buffer の API は 30 日で 2,000 回までなので、問い合わせは 30 秒おき・最長 3 分に抑える
    （1 回の投稿で多くても 12 回程度）。"""
    query = "query($id: PostId!) { post(input: { id: $id }) { id status externalLink sentAt } }"
    final = {}
    deadline = time.time() + timeout
    pending = dict(posted)
    while pending and time.time() < deadline:
        time.sleep(interval)
        for service, pid in list(pending.items()):
            res = gql(query, {"id": pid})
            node = (res.get("data") or {}).get("post") or {}
            if res.get("errors"):
                print(f"status query errors [{service}]: {json.dumps(res['errors'], ensure_ascii=False)[:400]}")
                pending.pop(service)
                final[service] = "unknown"
                continue
            status = node.get("status")
            if status in ("sent", "error"):
                print(f"RESULT [{service}] status={status} link={node.get('externalLink', '')}")
                final[service] = status
                pending.pop(service)
    for service in pending:
        print(f"RESULT [{service}] まだ公開が完了していません（Buffer 側で処理中）")
        final[service] = "pending"
    return final


def describe_type(name):
    """型の項目名と型名を返す（数字の取り出し方を調べるため）。"""
    res = gql('query { __type(name: "%s") { kind fields { name type { ...T } } enumValues { name } } }' % name
              + TYPE_FRAGMENT)
    t = (res.get("data") or {}).get("__type") or {}
    return [(f["name"], type_str(f["type"])) for f in t.get("fields") or []]


def describe(names):
    """型の中身（項目・引数・入力項目・列挙値）を表示する。API の書式を確かめるための開発用。"""
    q = ('query { __type(name: "%s") { kind fields { name args { name type { ...T } } type { ...T } } '
         'inputFields { name type { ...T } } enumValues { name } } }' + TYPE_FRAGMENT)
    for name in names:
        t = (gql(q % name).get("data") or {}).get("__type")
        if not t:
            print(f"type {name}: (not found)")
            continue
        parts = []
        for f in t.get("fields") or []:
            args = ", ".join(f"{a['name']}: {type_str(a['type'])}" for a in f.get("args") or [])
            parts.append(f"{f['name']}{'(' + args + ')' if args else ''}: {type_str(f['type'])}")
        parts += [f"{f['name']}: {type_str(f['type'])}" for f in t.get("inputFields") or []]
        parts += [v["name"] for v in t.get("enumValues") or []]
        print(f"{t['kind']} {name} {{ " + " | ".join(parts) + " }")
    return 0


def status(ids):
    """投稿 ID を指定して、公開の状態を表示する。posts:read の権限が入っているかの確認にも使う。"""
    query = "query($id: PostId!) { post(input: { id: $id }) { id status channelService externalLink sentAt } }"
    ok = True
    for pid in ids:
        res = gql(query, {"id": pid})
        if res.get("errors"):
            ok = False
            msg = res["errors"][0].get("message", "")
            print(f"post {pid}: 読み取れません -> {msg[:200]}")
        else:
            node = (res.get("data") or {}).get("post") or {}
            print(f"post {pid}: service={node.get('channelService')} status={node.get('status')} "
                  f"sentAt={node.get('sentAt')} link={node.get('externalLink')}")
    fields = dict(describe_type("Post"))
    print("Post.metrics type:", fields.get("metrics"), "/ Post.error type:", fields.get("error"))
    for tname in {(fields.get("metrics") or "").strip("[]!"), (fields.get("error") or "").strip("[]!")}:
        if tname:
            print(f"  type {tname}: " + ", ".join(f"{n}: {t}" for n, t in describe_type(tname)))
    return 0 if ok else 1


def is_enabled():
    """自動投稿の開始日を過ぎているか。手動で予約済みの期間と重ならないようにするための設定。"""
    start = ""
    if os.path.exists(CONFIG):
        with open(CONFIG, "r", encoding="utf-8") as f:
            start = (json.load(f).get("buffer_start") or "").strip()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    if not start:
        print("buffer_start が未設定のため、Buffer への投稿は行いません")
        return False
    if today < start:
        print(f"Buffer への自動投稿は {start} から開始します（今日は {today}）")
        return False
    return True


def post(video, url, draft=False, wait=False):
    with open(os.path.splitext(video)[0] + ".json", "r", encoding="utf-8") as f:
        info = json.load(f)
    channels = list_channels()
    done, failed, posted = [], [], []
    for cid, name, service in channels:
        if service not in TARGETS:
            continue
        # shareNow = すぐ公開。automatic = Buffer が直接投稿する（通知だけ送る notification ではない）
        payload = {"text": info[TARGETS[service]], "channelId": cid, "schedulingType": "automatic",
                   "mode": "shareNow", "needsApproval": False, "assets": [{"video": {"url": url}}]}
        if draft:
            payload["saveToDraft"] = True
        res = gql(CREATE_POST, {"input": payload})
        node = (res.get("data") or {}).get("createPost") or {}
        if res.get("errors") or node.get("__typename") != "PostActionSuccess":
            failed.append(service)
            print(f"FAILED [{service}] {name}: {json.dumps(res.get('errors') or node, ensure_ascii=False)[:600]}")
        else:
            done.append(service)
            pid = node["post"].get("id")
            print(f"OK [{service}] {name}: post id={pid} status={node['post'].get('status')}"
                  + (" (draft)" if draft else ""))
            if not draft and pid:
                posted.append((service, pid))
            if draft and pid:                      # 確認用の下書きは残さない
                rm = gql(DELETE_POST, {"input": {"id": pid}})
                state = "deleted" if not rm.get("errors") else json.dumps(rm["errors"], ensure_ascii=False)[:300]
                print(f"   draft cleanup: {state}")
    if not done and not failed:
        print("TikTok・X のチャンネルが Buffer に接続されていません")
        return 1
    if wait and posted:
        final = wait_until_sent(posted)
        if any(v == "error" for v in final.values()):
            return 1
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--url", help="動画の公開 URL")
    ap.add_argument("--draft-test", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--is-enabled", action="store_true")
    ap.add_argument("--wait", action="store_true", help="公開が完了するまで待って結果を表示する")
    ap.add_argument("--status", nargs="+", metavar="POST_ID", help="投稿 ID の状態を表示する")
    ap.add_argument("--describe", nargs="+", metavar="TYPE", help="API の型の中身を表示する（開発用）")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.is_enabled:
        return 0 if is_enabled() else 1
    if args.status:
        return status(args.status)
    if args.describe:
        return describe(args.describe)
    if not args.video or not args.url:
        ap.error("動画ファイルと --url が必要です")
    return post(args.video, args.url, args.draft_test, args.wait)


if __name__ == "__main__":
    sys.exit(main())
