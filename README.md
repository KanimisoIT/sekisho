# 関所(sekisho)

AI に書かせるアプリのための、機械の検査の本体。各アプリは `caller/sekisho-call.yml` を置いて、ここを main で呼ぶ。main に入るのは、最後の段 `sekisho / verdict` が緑のときだけ。

判定に使う台本と設定(zizmor・actionlint)は、いつも本体の物を使う。本体の main は、ルールセットと自己試験で守る。自己試験は「わざと誤りを入れた見本」を変えたあとの台本にかけ、抜け道の封じは取り込み先の版の台本で判定する(同じ変更の中で判定役を弱められないように)。

## ループ

1. かにみそが言葉で頼む・直しを言う
2. AI が枝で作り、PR を出す
3. 関所が走る。赤なら AI が `gh run view --log-failed` で理由を読んで直す
4. 緑なら自動で取り込む(auto-merge)
5. 3回で緑にならない・PR が24時間開いたまま・main が赤、のどれかは報せ便がメールで知らせる

## 段

| 段 | 検査 | 中身 |
| --- | --- | --- |
| secrets | 秘密の混入 | gitleaks |
| workflows | 自動検査の手順そのもの | actionlint・zizmor |
| deps | 依存の既知の脆弱性 | osv-scanner |
| guard | 抜け道の封じ | 黙らせる書き込みの新顔・許しの期限と上限・足すだけの所(`.sekisho/checks/`・`tests/spec/`)の変更・試験の数の減り・守りの設定の弱め |
| guard | 経緯の注釈 | 「以前は」「修正」「〜のため追加」・日付の入った注釈 |
| guard | 版の一致 | `.sekisho/config.json` の `version_sync` |
| guard | 指摘の束 | `.sekisho/checks/` の台本(頭に `由来: #番号 日付`) |
| lang | 言語の検査 | JS・TS: `npm run lint`・`tsc --noEmit`・`npm test`。Python: ruff・pyright・pytest |
| verdict | 判定 | 上の段のどれか一つでも成功以外なら赤。飛ばし・取消も赤 |

## 指摘の束の書き方

かにみその直しが一つ来たら、`.sekisho/checks/` に今の誤りで落ちる台本を一本足し、直して通す。一度入れた台本は変えない・消さない。引退させるときは、新しい台本の頭に `退く: <古い台本の道筋>` と書く。公開のリポジトリでは、頭に言葉を引かない(番号と日付だけ。言葉は非公開の所)。

```python
# 由来: #12 2026-11-26
# R3 のフラッシュは150点
import json, sys
rules = json.load(open('rules.json', encoding='utf-8'))
sys.exit(0 if rules['R3']['flush'] == 150 else 1)
```

## 一度きりの準備(かにみその手)

1. GitHub Pro にする(非公開のリポジトリにも守りと自動の取り込みを掛けるため)
2. `setup/1_setup.cmd` を押す。本体と書庫の検査のリポジトリを作り、守りを掛け、最後にログアウトする。PC の Git の資格情報には何も書かない
3. AI 用の鍵を一本作る(Settings → Developer settings → Fine-grained tokens)
   - 持ち主 KanimisoIT・All repositories・Contents 読み書き・Pull requests 読み書き・Actions 読み取り
   - Administration と Workflows は付けない(付けると AI が守りと手順を書き換えられる)
   - 期限は366日。残りの日数は報せ便が数える
   - PC の利用者の環境変数に `GH_TOKEN` として置き、`gh auth setup-git` を一度押す
4. アプリのリポジトリを作ったら `setup/2_add_repo.cmd` を押す

本体の手順(`.github/workflows/`)を変えるときだけ、かにみその手が要る(AI の鍵では変えられない)。台本(`scripts/`)と見本(`tests/spec/`)の変更は、AI が PR で出し、自己試験が緑なら自動で入る。

## 自己試験

`tests/spec/` は検査の検査。わざと誤りを入れた見本が全部赤のままかを試す。見本は足すだけで、新しい見本は新しいファイルに書く。

```
python -m pytest -q tests
```
