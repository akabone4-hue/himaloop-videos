# himaloop-videos

物理シミュレーションの短い縦動画（1080×1920、20〜45 秒）をプログラムで作り、毎日決まった時刻に投稿する仕組みです。

| 場所 | 中身 |
|---|---|
| [`video/README.md`](video/README.md) | 動画の種類の一覧と、作り方・試し方 |
| [`video/QUALITY.md`](video/QUALITY.md) | 良い動画の基準と、作るときの手順・点検の項目 |
| [`video/FEEDBACK.md`](video/FEEDBACK.md) | 型ごとの、これまでの評価と指摘 |
| [`video/IDEAS.md`](video/IDEAS.md) | これから作る型の候補と、直したい点 |
| [`video/POSTING.md`](video/POSTING.md) | 投稿の準備と、自動投稿の設定手順 |
| [`video/KNOWHOW_3D.md`](video/KNOWHOW_3D.md) | 3D の動画（Blender）を作るときのメモ |
| [`docs/posts/README.md`](docs/posts/README.md) | 投稿した動画の一覧 |
| [`docs/stats/README.md`](docs/stats/README.md) | 再生数などの数字（1 日 1 回更新） |
| `video/post_queue.txt` | これから投稿する順番 |

## 手元で 1 本作る

```
pip install -r video/requirements.txt
python video/make.py list                     # 種類の一覧
python video/make.py towers --seed 7          # video/out/ に mp4 ができる
python video/make.py towers --seed 7 --preview   # 低画質で手早く確認
```

ffmpeg が必要です。3D の種類（marble・faces・chime）は追加で `pip install -r video/requirements-3d.txt` が要ります。

## 自動で動いているもの

| 処理 | いつ | 内容 |
|---|---|---|
| Post Video | 毎日 7:10 と 23:10（日本時間） | 次の 1 本を作って投稿し、記録を更新する |
| Video Stats | 1 日 1 回 | 再生数などを集めて `docs/stats/` を更新する |

時刻どおりに動かすために、外部のサービスから Post Video を呼んでいます（手順は `video/POSTING.md` の「時刻どおりに投稿する」）。
認証に使う値はすべてリポジトリの Secrets に入っていて、ファイルには書いていません。
