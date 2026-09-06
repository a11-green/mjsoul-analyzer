"""牌譜データの取得層(Compliance Layerに包まれる取得インターフェース)。

docs/DESIGN.md 3.2節を参照。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from mjsoul_analyzer.compliance.credential_store import Credentials
from mjsoul_analyzer.compliance.rate_limiter import RateLimiter
from mjsoul_analyzer.url_parser import PaipuRef


class RecordFetchError(Exception):
    """牌譜の取得に失敗した場合に送出される。"""


class RecordFetcher(Protocol):
    """`mjsoul_analyzer.parser.record_parser` が読み込めるRawGameRecord(dict)を返す取得手段。"""

    def fetch(self, ref: PaipuRef) -> dict[str, Any]: ...


class LocalFileRecordFetcher:
    """あらかじめ用意された RawGameRecord (JSON) をローカルディレクトリから読み込むフェッチャー。

    自分が正当にアクセスできる牌譜データを何らかの手段でJSON化し、`cache/` 等の
    ローカルディレクトリに配置している場合に使用する。雀魂サーバーへの通信は一切行わない。
    ファイル名は `<game_uuid>.json` を想定する。
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def fetch(self, ref: PaipuRef) -> dict[str, Any]:
        path = self._directory / f"{ref.game_uuid}.json"
        if not path.exists():
            raise RecordFetchError(f"牌譜ファイルが見つかりません: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecordFetchError(f"牌譜ファイルの形式が不正です: {path}") from exc


class LiveMahjongSoulRecordFetcher:
    """雀魂サーバーから本人アカウントで牌譜を直接取得するフェッチャー(未実装スタブ)。

    実装時に満たすべき要件(CLAUDE.md参照):

    - 認証は利用者本人のアカウントでのみ行う(第三者アカウントの代行ログイン禁止)。
    - 通信プロトコルは、非改変クライアントと同一の通信仕様に外部から準拠する形で実装し、
      雀魂クライアント自体の逆アセンブル・逆コンパイル・改変は行わない。
    - 実際の通信を行う前に必ず `RateLimiter.acquire()` を呼び出し、短時間の大量アクセスを防ぐ。

    本開発・レビュー環境はネットワーク的にサンドボックス化されており、実際の雀魂サーバーとの
    認証・牌譜取得プロトコルを検証する手段がない。検証されていないプロトコル実装を
    そのまま組み込むことは、動作不良や意図しない過剰アクセスにつながりうるため、
    ここでは意図的に未実装(NotImplementedError)としている。実装する際は、
    必ず開発者自身のアカウント・少数の手動テストで検証してから利用すること。
    """

    def __init__(self, credentials: Credentials, rate_limiter: RateLimiter | None = None) -> None:
        self._credentials = credentials
        self._rate_limiter = rate_limiter or RateLimiter()

    def fetch(self, ref: PaipuRef) -> dict[str, Any]:
        raise NotImplementedError(
            "雀魂サーバーとの実通信は未実装です。CLAUDE.md および "
            "docs/DESIGN.md 3.2節、本クラスのdocstringを参照のうえ、"
            "検証済みの通信プロトコルが確立してから実装してください。"
        )
