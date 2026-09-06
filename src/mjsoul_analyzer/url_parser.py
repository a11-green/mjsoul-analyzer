"""雀魂の牌譜URLから対局ID・観戦視点(アカウントID)を抽出する。

雀魂の対局結果画面「牌譜を見る」で共有される牌譜URLは、一般に以下のような形式を取る
（実際に観測されたURL例に基づく。運営による表記変更の可能性はある）。

    https://game.mahjongsoul.com/?paipu=260906-3de0ca77-72f2-4450-b09a-a9521b37c142_a430980121

`paipu` クエリパラメータの値が「対局ID」であり、末尾の `_a<N>` はビューアがどのプレイヤー視点で
開くかを指定する **観戦者のアカウントID**（雀魂内部の数値ID。0-3の席番号ではない）である。

このアカウントIDから「どの席(0-3)か」を知るには、牌譜データ本体に含まれる各プレイヤーの
アカウントID一覧と突き合わせる必要がある（`resolve_focus_seat` 参照）。URL単体からは
席番号を直接特定できない点に注意すること。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from mjsoul_analyzer.models import GameRecord

_PAIPU_ID_PATTERN = re.compile(r"^[0-9A-Za-z-]+$")
_ACCOUNT_SUFFIX_PATTERN = re.compile(r"^(?P<uuid>.+)_a(?P<account_id>\d+)$")


class InvalidPaipuUrlError(ValueError):
    """牌譜URLの形式が不正、または対局IDを抽出できない場合に送出される。"""


@dataclass(frozen=True)
class PaipuRef:
    game_uuid: str
    viewer_account_id: Optional[int]  # URLに視点指定(_a<アカウントID>)が無ければNone


def parse_paipu_url(url: str) -> PaipuRef:
    """牌譜URL文字列を解析し、対局IDと観戦者アカウントIDを取得する。

    Raises:
        InvalidPaipuUrlError: URLから有効な `paipu` パラメータを取得できない場合。
    """
    url = url.strip()
    if not url:
        raise InvalidPaipuUrlError("空のURLが指定されました")

    parsed = urlparse(url)
    raw_value = _extract_paipu_param(parsed.query) or _extract_paipu_param(parsed.fragment)
    if raw_value is None:
        raise InvalidPaipuUrlError(f"URLに 'paipu' パラメータが見つかりません: {url!r}")

    return parse_paipu_value(raw_value)


def parse_paipu_value(raw_value: str) -> PaipuRef:
    """`paipu=` の値そのもの（例: "260906-xxxx..._a430980121"）を解析する。"""
    raw_value = raw_value.strip()
    if not raw_value:
        raise InvalidPaipuUrlError("paipuパラメータの値が空です")

    match = _ACCOUNT_SUFFIX_PATTERN.match(raw_value)
    if match:
        game_uuid = match.group("uuid")
        viewer_account_id = int(match.group("account_id"))
    else:
        game_uuid = raw_value
        viewer_account_id = None

    if not game_uuid or not _PAIPU_ID_PATTERN.match(game_uuid):
        raise InvalidPaipuUrlError(f"対局IDの形式が不正です: {game_uuid!r}")

    return PaipuRef(game_uuid=game_uuid, viewer_account_id=viewer_account_id)


def resolve_focus_seat(ref: PaipuRef, record: "GameRecord") -> Optional[int]:
    """PaipuRefのアカウントIDを、牌譜データ内のプレイヤー一覧と突き合わせて席番号(0-3)に解決する。

    Returns:
        該当する席番号。アカウントID指定が無い場合、または牌譜内に一致するプレイヤーが
        見つからない場合はNone。
    """
    if ref.viewer_account_id is None:
        return None
    for player in record.players:
        if player.account_id == ref.viewer_account_id:
            return player.seat
    return None


def _extract_paipu_param(query_or_fragment: str) -> Optional[str]:
    if not query_or_fragment:
        return None
    # フラグメントが "/mjhome?paipu=..." のようにパスを含む場合に備え、
    # '?' 以降だけをクエリ文字列として扱う。
    if "?" in query_or_fragment:
        query_or_fragment = query_or_fragment.split("?", 1)[1]
    params = parse_qs(query_or_fragment)
    values = params.get("paipu")
    if not values:
        return None
    return values[0]
