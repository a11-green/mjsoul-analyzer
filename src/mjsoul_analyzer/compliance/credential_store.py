"""雀魂アカウントの認証情報を安全に取り扱うためのモジュール。

CLAUDE.md「認証情報の安全な取り扱い」を実装レベルで担保する:
- 認証情報はリポジトリにコミットしない(環境変数 or `.gitignore` 対象のローカルファイルから読む)
- ログ出力・例外メッセージ・reprに平文を含めない
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class CredentialError(Exception):
    """認証情報の取得に失敗した場合に送出される。"""


@dataclass(frozen=True, repr=False)
class Credentials:
    username: str
    password: str

    def __repr__(self) -> str:  # 誤ってログに平文が出力されるのを防ぐ
        return "Credentials(username='***', password='***')"

    __str__ = __repr__


def load_credentials_from_env(prefix: str = "MJSOUL_") -> Credentials:
    """環境変数 `{prefix}USERNAME` / `{prefix}PASSWORD` から認証情報を読み込む。"""
    username = os.environ.get(f"{prefix}USERNAME")
    password = os.environ.get(f"{prefix}PASSWORD")
    if not username or not password:
        raise CredentialError(
            f"{prefix}USERNAME / {prefix}PASSWORD 環境変数が設定されていません。"
            "認証情報は本人アカウントのものを、環境変数かローカル設定ファイル"
            "(.gitignore対象)からのみ読み込むこと。"
        )
    return Credentials(username=username, password=password)


def load_credentials_from_file(path: Path) -> Credentials:
    """ローカルのJSON設定ファイル({"username": ..., "password": ...})から読み込む。

    このファイルは絶対にリポジトリにコミットしないこと(.gitignoreで除外済み)。
    """
    if not path.exists():
        raise CredentialError(f"認証情報ファイルが見つかりません: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Credentials(username=data["username"], password=data["password"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise CredentialError(f"認証情報ファイルの形式が不正です: {path}") from exc
