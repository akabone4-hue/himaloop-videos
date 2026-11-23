# himaloop-videos — 作業の案内

物理シミュレーションの縦動画（1080×1920、20〜45 秒）を作り、YouTube（主）・TikTok・X へ自動投稿するリポジトリです。
チャンネル名は HimaLoop。やりとりは日本語で、専門用語を避けて平易に書きます。

## 最初に読むもの

| ファイル | 中身 |
|---|---|
| `video/QUALITY.md` | **良い動画の基準と、作るときの手順。** 新しい型を作る前・直す前に必ず読む |
| `video/FEEDBACK.md` | 型ごとの、これまでの評価と指摘。もらった指摘はここへ足す |
| `video/IDEAS.md` | これから作る型の候補と、直したい点 |
| `video/README.md` | 型の一覧と、ファイルの役割 |
| `video/POSTING.md` | 自動投稿の仕組みと設定 |
| `video/KNOWHOW_3D.md` | 3D（Blender）の作り方 |
| `docs/stats/README.md` | 再生数（1 日 1 回、自動で更新） |

## 道具

```
python video/make.py 型 --seed 1 --preview     試し書き出し（30 コマ/秒）
python video/make.py 型 --seed 1               本番
python video/tools/balance.py 型 --seeds 1-64  絵なしで回して、長さと勝ち方のかたよりを見る
python video/tools/review.py 動画.mp4          機械で点検し、コマの一覧画像を作る
python video/tools/smoke.py --golden           直したあと: 落ちないか、順番待ちの動画が変わっていないか
```

新しい型は `video/tools/template_sim.py`（そのまま動く骨組み）を写して始める。本番の書き出しのあとは、点検結果が自動で出る。

入れておくもの: `pip install -r video/requirements.txt` と ffmpeg。3D の型だけ `video/requirements-3d.txt`（約 430MB、Python 3.13）。

## 守ること

- **新しい型は、持ち主が「良い」と言うまで投稿の順番（`post_queue.txt`・`ROTATION`）に入れない。**
- **順番待ちの動画の中身を、知らないうちに変えない。** 共通の部品を直したら `smoke.py --golden`。
- **自分で見直してから送る。** `review.py` と、`QUALITY.md` の「目で見る項目」。
- 鍵や合言葉（YouTube・Buffer など）は GitHub の Secrets にだけ置く。会話・ファイル・ログに書かない、表示しない。
- 他人の映像・音楽・キャラクター・ロゴ・実在の人物を使わない。
- TikTok・X を画面操作や読み取りで自動化しない（投稿は Buffer 経由だけ）。
- プルリクエストは、頼まれたときだけ作る。
- **このリポジトリは公開。** コミットに作業セッションの URL や共同作成者の行を入れない（持ち主の希望）。
  作者のアドレスは GitHub の匿名アドレス（`289170110+akabone4-hue@users.noreply.github.com`）を使う。
- 試し書き出し（30 コマ/秒）と本番（60 コマ/秒）は結果が変わる型がある。勝者や長さは本番で確かめる。
- 書き出しの途中で `git stash`・`git checkout` をしない（古いコードで動画ができる）。

## 投稿の仕組み（要点）

- 毎日 7:10 と 23:10（日本時間）に 1 本ずつ。外の時計（cron-job.org）が `post-video.yml` を呼ぶ。GitHub 自身の予定実行は数時間遅れるので、予備。
- YouTube に上げた 10 分後に、Buffer 経由で TikTok と X へ。
- 次に何が投稿されるか: `python video/next_post.py`。止めたいとき: `video/post_config.json` の `hold_until`。
- `.github/workflows/check.yml` が、コードを変えるたびに全部の型を絵なしで回す。失敗したら、その日の投稿の前に直す。
