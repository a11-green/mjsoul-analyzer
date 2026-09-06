"""雀魂の牌譜URLから対局ID・観戦席を抽出する。

雀魂の対局結果画面「牌譜を見る」で共有される牌譜URLは、一般に以下のような形式を取る
（コミュニティで広く観測されている公開情報に基づく。運営による表記変更の可能性はある）。

    https://game.mahjongsoul.com/?paipu=230101-90a2bcde-1234-5678-9abc-def012345678_a3

`paipu` クエリパラメータの値が「対局ID」であり、末尾の `_a<N>` は「どの席(0-3)を主観視点として
開くか」を表すサフィックスである（無い場合は視点指定なし）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

_PAIPU_ID_PATTERN = re.compile(r"^[0-9A-Za-z-]+$")
_SEAT_SUFFIX_PATTERN = re.compile(r"^(?P<uuid>.+)_a(?P<seat>\d+)$")


class InvalidPaipuUrlError(ValueError):
    """牌譜URLの形式が不正、または対局IDを抽出できない場合に送出される。"""


@dataclass(frozen=True)
class PaipuRef:
    game_uuid: str
    focus_seat: Optional[int]  # 0-3。URLに視点指定が無ければNone


def parse_paipu_url(url: str) -> PaipuRef:
    """牌譜URL文字列を解析し、対局IDと観戦席番号を取得する。

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
    """`paipu=` の値そのもの（例: "230101-xxxx..._a3"）を解析する。"""
    raw_value = raw_value.strip()
    if not raw_value:
        raise InvalidPaipuUrlError("paipuパラメータの値が空です")

    match = _SEAT_SUFFIX_PATTERN.match(raw_value)
    if match:
        game_uuid = match.group("uuid")
        focus_seat = int(match.group("seat"))
        if not (0 <= focus_seat <= 3):
            raise InvalidPaipuUrlError(f"席番号は0-3である必要があります: {focus_seat}")
    else:
        game_uuid = raw_value
        focus_seat = None

    if not game_uuid or not _PAIPU_ID_PATTERN.match(game_uuid):
        raise InvalidPaipuUrlError(f"対局IDの形式が不正です: {game_uuid!r}")

    return PaipuRef(game_uuid=game_uuid, focus_seat=focus_seat)


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
