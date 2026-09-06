"""牌譜イベント列を先頭から再生し、各打牌選択直前の局面(DecisionPoint)を復元する。

既知の簡略化(docs/DESIGN.md 参照):
- ドラ表示牌は局開始時点で分かっている分のみを扱う。カンドラ(新ドラ)は
  RawGameRecord生成時点で判明している最終的な `dora_indicators` をその局の全ての
  DecisionPointに一律で見せている(実際のゲームではカンの瞬間まで新ドラは見えない)。
  これは実装を単純化するためのMVP時点の割り切りであり、将来的にはカン発生イベントに
  合わせて逐次追加する形に改善する。
- 山の残り枚数は「配牌後の残り牌数(70) - これまでの自摸回数」という近似値であり、
  カンによる王牌からの補充などは厳密には反映していない。
"""
from __future__ import annotations

from mjsoul_analyzer.models import Action, DecisionPoint, GameRecord, Meld, RoundRecord, Tile

# 4人打ち: 136枚 - 王牌14枚 - 配牌13枚*4 = 70枚
_INITIAL_LIVE_WALL = 70


def reconstruct_decision_points(
    record: GameRecord,
    focus_seats: set[int] | None = None,
) -> list[DecisionPoint]:
    """牌譜全体からDecisionPointの列を復元する。

    Args:
        record: 解析対象の牌譜。
        focus_seats: 解析したい席番号の集合。Noneの場合は全員分を対象とする。
    """
    decision_points: list[DecisionPoint] = []
    for round_record in record.rounds:
        decision_points.extend(_reconstruct_round(round_record, focus_seats))
    return decision_points


def _remove_tile(hand: list[Tile], tile: Tile) -> None:
    for i, t in enumerate(hand):
        if t.suit == tile.suit and t.rank == tile.rank:
            del hand[i]
            return
    raise ValueError(f"手牌に存在しない牌を取り除こうとしました: {tile}")


def _apply_meld_to_hand(hand: list[Tile], meld: Meld) -> None:
    """鳴き面子の構成牌のうち、自分の手牌から出た分だけを取り除く。"""
    skip_one_of_called = meld.called_tile is not None
    for t in meld.tiles:
        if skip_one_of_called and t.suit == meld.called_tile.suit and t.rank == meld.called_tile.rank:
            skip_one_of_called = False
            continue
        _remove_tile(hand, t)


def _reconstruct_round(
    round_record: RoundRecord,
    focus_seats: set[int] | None,
) -> list[DecisionPoint]:
    hands: dict[int, list[Tile]] = {
        seat: list(tiles) for seat, tiles in round_record.initial_hands.items()
    }
    melds: dict[int, list[Meld]] = {seat: [] for seat in hands}
    discards: dict[int, list[Tile]] = {seat: [] for seat in hands}
    riichi_seats: set[int] = set()
    remaining_tiles = _INITIAL_LIVE_WALL
    turn_counters: dict[int, int] = {seat: 0 for seat in hands}
    decision_points: list[DecisionPoint] = []

    for event in round_record.events:
        _handle_event(
            event,
            round_record=round_record,
            hands=hands,
            melds=melds,
            discards=discards,
            riichi_seats=riichi_seats,
            turn_counters=turn_counters,
            focus_seats=focus_seats,
            decision_points=decision_points,
            remaining_tiles=remaining_tiles,
        )
        if event.kind == "draw":
            remaining_tiles -= 1

    return decision_points


def _handle_event(
    event: Action,
    *,
    round_record: RoundRecord,
    hands: dict[int, list[Tile]],
    melds: dict[int, list[Meld]],
    discards: dict[int, list[Tile]],
    riichi_seats: set[int],
    turn_counters: dict[int, int],
    focus_seats: set[int] | None,
    decision_points: list[DecisionPoint],
    remaining_tiles: int,
) -> None:
    seat = event.seat

    if event.kind == "draw":
        hands[seat].append(event.tile)
        turn_counters[seat] += 1
        return

    if event.kind == "discard":
        if focus_seats is None or seat in focus_seats:
            decision_points.append(
                DecisionPoint(
                    round_name=round_record.round_name,
                    turn=turn_counters[seat],
                    seat=seat,
                    hand=list(hands[seat]),
                    melds=list(melds[seat]),
                    all_melds={s: list(m) for s, m in melds.items()},
                    discards_by_seat={s: list(d) for s, d in discards.items()},
                    dora_indicators=list(round_record.dora_indicators),
                    riichi_seats=set(riichi_seats),
                    remaining_tiles=remaining_tiles,
                    actual_action=event,
                )
            )
        _remove_tile(hands[seat], event.tile)
        discards[seat].append(event.tile)
        return

    if event.kind == "riichi":
        riichi_seats.add(seat)
        return

    if event.kind in ("chi", "pon"):
        assert event.meld is not None
        _apply_meld_to_hand(hands[seat], event.meld)
        melds[seat].append(event.meld)
        return

    if event.kind == "kan":
        assert event.meld is not None
        if event.meld.kind == "kan_added":
            _apply_added_kan(hands[seat], melds[seat], event.meld)
        else:
            _apply_meld_to_hand(hands[seat], event.meld)
            melds[seat].append(event.meld)
        return

    raise ValueError(f"未対応のイベント種別です: {event.kind!r}")


def _apply_added_kan(hand: list[Tile], seat_melds: list[Meld], added_meld: Meld) -> None:
    """加槓(既存のポンに4枚目を足す)を適用する。"""
    added_tile = added_meld.tiles[0]
    for i, existing in enumerate(seat_melds):
        if existing.kind == "pon" and existing.tiles[0].rank == added_tile.rank and existing.tiles[0].suit == added_tile.suit:
            _remove_tile(hand, added_tile)
            seat_melds[i] = Meld(
                kind="kan_added",
                tiles=list(existing.tiles) + [added_tile],
                called_tile=existing.called_tile,
                called_from_seat=existing.called_from_seat,
            )
            return
    raise ValueError(f"加槓対象のポン面子が見つかりません: {added_tile}")
