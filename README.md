# mjsoul-analyzer

雀魂（じゃんたま）の牌譜URLを入力として、実際の打牌と最適手を比較・解析するツール（開発中）。

- 設計書: [`docs/DESIGN.md`](./docs/DESIGN.md)
- 開発ルール・雀魂利用規約の遵守事項: [`CLAUDE.md`](./CLAUDE.md)

## 現在の実装状況(v1 MVP)

牌効率(シャンテン数・受け入れ枚数)ベースの最適手判定、実際の打牌との差分ラベリング、
統計集計、Markdown/JSONレポート出力までを実装済み。**雀魂サーバーへの直接通信(牌譜取得)は
未実装**であり、事前に取得済みの牌譜データ(`RawGameRecord` JSON、`docs/DESIGN.md` 参照)を
ローカルディレクトリに配置して解析する形になっている(理由は `docs/DESIGN.md` 3.2節、
`src/mjsoul_analyzer/fetcher/record_fetcher.py` を参照)。

## セットアップ

```bash
pip install -e ".[dev]"
pytest
```

## 使い方

`cache/<対局ID>.json` に `RawGameRecord` 形式の牌譜データを配置した上で:

```bash
mjsoul-analyzer analyze "https://game.mahjongsoul.com/?paipu=<対局ID>_a<アカウントID>" \
    --records-dir cache --out reports
```

URL末尾の `_a<N>` は席番号(0-3)ではなく雀魂の**アカウントID**であり、牌譜内のプレイヤー
情報と突き合わせて席を解決する。アカウントIDでの自動解決がうまくいかない場合は
`--seat 0-3` で明示的に指定できる。

初回実行時は [CLAUDE.md](./CLAUDE.md) の利用規約遵守方針への同意プロンプトが表示される
(`--yes` でスキップ可能)。`reports/` にMarkdown/JSONレポートが出力される。

### 牌譜データ(RawGameRecord)の入手

雀魂サーバーへの直接通信は未実装のため、`RawGameRecord` JSON は別途用意する必要がある。
[`browser-extension/`](./browser-extension/) に、雀魂ブラウザ版の牌譜(リプレイ)画面を
開いている間だけ手動でWebSocket通信をキャプチャできる補助用Chrome拡張(非公式・個人利用専用)
を用意している。ただし出力は生データ(未デコード)であり、`RawGameRecord` への変換は今後の課題。
詳細は拡張機能の README を参照。