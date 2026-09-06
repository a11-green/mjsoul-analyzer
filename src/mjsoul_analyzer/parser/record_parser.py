"""正規化された牌譜JSON(RawGameRecord)を内部データモデル(GameRecord)へ変換する。

RawGameRecordのスキーマ:

```json
{
  "game_uuid": "230101-90a2bcde-1234-5678-9abc-def012345678",
  "players": [{"seat": 0, "name": "Alice", "rank": "...", "account_id": 430980121}, ...],
  "rounds": [
    {
      "round_name": "East-1-0",
      "dora_indicators": ["5z"],
      "initial_hands": {"0": ["1m", "2m", ...13枚], "1": [...], "2": [...], "3": [...]},
      "events": [
        {"type": "draw", "seat": 0, "tile": "3p"},
        {"type": "discard", "seat": 0, "tile": "3p", "tsumogiri": true},
        {"type": "riichi", "seat": 0},
        {"type": "chi", "seat": 1, "tiles": ["4p", "5p", "6p"], "called_tile": "5p", "from_seat": 0},
        {"type": "pon", "seat": 2, "tiles": ["7z", "7z", "7z"], "called_tile": "7z", "from_seat": 1},
        {"type": "kan_open", "seat": 2, "tiles": [...4枚...], "called_tile": "...", "from_seat": 1},
        {"type": "kan_closed", "seat": 0, "tiles": [...4枚...]},
        {"type": "kan_added", "seat": 2, "tile": "..."}
      ],
      "result": {
        "kind": "hora",
        "winner_seats": [0],
        "houjuu_seat": null,
        "is_tsumo": true,
        "han": 3, "fu": 40, "points": 5800,
        "yaku": ["riichi", "menzen_tsumo"]
      }
    }
  ]
}
```

このモジュールは「取得済みの牌譜データ」を対象とする。実際の雀魂サーバーからどのようにこの形式の
データを得るかは `mjsoul_analyzer.fetcher` の責務であり、本モジュールは通信を一切行わない。
"""
from __future__ import annotations

from typing import Any

from mjsoul_analyzer.models import (
    Action,
    GameRecord,
    Meld,
    PlayerInfo,
    RoundRecord,
    RoundResult,
    Tile,
)


class InvalidRecordError(ValueError):
    """RawGameRecordの形式が不正な場合に送出される。"""


def parse_raw_game_record(raw: dict[str, Any]) -> GameRecord:
    try:
        game_uuid = raw["game_uuid"]
        players_raw = raw["players"]
        rounds_raw = raw["rounds"]
    except KeyError as exc:
        raise InvalidRecordError(f"必須フィールドが不足しています: {exc}") from exc

    players = [
        PlayerInfo(
            seat=p["seat"],
            name=p.get("name", ""),
            rank=p.get("rank", ""),
            account_id=p.get("account_id"),
        )
        for p in players_raw
    ]
    rounds = [_parse_round(r) for r in rounds_raw]
    return GameRecord(game_uuid=game_uuid, players=players, rounds=rounds)


def _parse_round(raw_round: dict[str, Any]) -> RoundRecord:
    round_name = raw_round["round_name"]
    dora_indicators = [Tile.parse(t) for t in raw_round.get("dora_indicators", [])]
    initial_hands = {
        int(seat): [Tile.parse(t) for t in tiles]
        for seat, tiles in raw_round.get("initial_hands", {}).items()
    }
    events = [_parse_event(e) for e in raw_round.get("events", [])]
    result = _parse_result(raw_round.get("result"))
    return RoundRecord(
        round_name=round_name,
        dora_indicators=dora_indicators,
        initial_hands=initial_hands,
        events=events,
        result=result,
    )


def _parse_event(raw_event: dict[str, Any]) -> Action:
    event_type = raw_event["type"]
    seat = raw_event["seat"]

    if event_type == "draw":
        return Action(seat=seat, kind="draw", tile=Tile.parse(raw_event["tile"]))

    if event_type == "discard":
        return Action(
            seat=seat,
            kind="discard",
            tile=Tile.parse(raw_event["tile"]),
            is_tsumogiri=bool(raw_event.get("tsumogiri", False)),
        )

    if event_type == "riichi":
        return Action(seat=seat, kind="riichi")

    if event_type in ("chi", "pon", "kan_open"):
        tiles = [Tile.parse(t) for t in raw_event["tiles"]]
        called_tile = Tile.parse(raw_event["called_tile"]) if raw_event.get("called_tile") else None
        meld = Meld(
            kind=event_type,
            tiles=tiles,
            called_tile=called_tile,
            called_from_seat=raw_event.get("from_seat"),
        )
        action_kind = "kan" if event_type == "kan_open" else event_type
        return Action(seat=seat, kind=action_kind, meld=meld)

    if event_type == "kan_closed":
        tiles = [Tile.parse(t) for t in raw_event["tiles"]]
        meld = Meld(kind="kan_closed", tiles=tiles, called_tile=None, called_from_seat=None)
        return Action(seat=seat, kind="kan", meld=meld)

    if event_type == "kan_added":
        added_tile = Tile.parse(raw_event["tile"])
        # kan_addedは既存のポン面子に4枚目を足す形なので、tilesは追加牌のみを保持し、
        # 既存ポン面子とのマージはhand_state側で行う。
        meld = Meld(kind="kan_added", tiles=[added_tile], called_tile=None, called_from_seat=None)
        return Action(seat=seat, kind="kan", meld=meld)

    raise InvalidRecordError(f"未知のイベント種別です: {event_type!r}")


def _parse_result(raw_result: dict[str, Any] | None) -> RoundResult | None:
    if raw_result is None:
        return None
    kind = raw_result["kind"]
    if kind == "hora":
        return RoundResult(
            kind="hora",
            winner_seats=list(raw_result.get("winner_seats", [])),
            houjuu_seat=raw_result.get("houjuu_seat"),
            is_tsumo=bool(raw_result.get("is_tsumo", False)),
            han=int(raw_result.get("han", 0)),
            fu=int(raw_result.get("fu", 0)),
            points=int(raw_result.get("points", 0)),
            yaku=list(raw_result.get("yaku", [])),
        )
    if kind == "ryuukyoku":
        return RoundResult(
            kind="ryuukyoku",
            tenpai_seats=list(raw_result.get("tenpai_seats", [])),
        )
    raise InvalidRecordError(f"未知の局結果種別です: {kind!r}")
