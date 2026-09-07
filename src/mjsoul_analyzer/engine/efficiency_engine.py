"""牌効率・簡易期待値に基づく候補手(打牌)のランキング算出。

docs/DESIGN.md 3.5節のMVP方針に対応する、決定論的な効率ベースのエンジン。
機械学習等を用いた高精度モデルへの差し替えは MoveRankingProvider として将来拡張する
(docs/DESIGN.md 8節)。
"""
from __future__ import annotations

from dataclasses import dataclass

from mjsoul_analyzer.engine.shanten import calculate_shanten, calculate_ukeire
from mjsoul_analyzer.models import Action, DecisionPoint, RankedMove, Suit, Tile


@dataclass(frozen=True)
class EngineConfig:
    """効率エンジンの挙動を調整するパラメータ。既定値はいずれも簡易ヒューリスティック。"""

    danger_weight: float = 5.0  # 相手リーチ時、危険度スコアに掛ける減点係数
    value_weight: float = 1.0


def rank_moves(decision: DecisionPoint, config: EngineConfig | None = None) -> list[RankedMove]:
    """DecisionPointにおける打牌候補を、効率(シャンテン->受け入れ->期待値->安全度)の
    優先順位でランキングする。
    """
    config = config or EngineConfig()
    melds_count = len(decision.melds)
    visible_counts = _compute_visible_counts(decision)
    opponents_in_riichi = bool(decision.riichi_seats - {decision.seat})
    dora_tile_kinds = _dora_tile_kinds(decision.dora_indicators)

    candidates: list[RankedMove] = []
    seen_tile_kinds: set[tuple[str, int]] = set()
    for tile in decision.hand:
        key = (tile.suit.value, tile.rank)
        if key in seen_tile_kinds:
            continue  # 同種の牌は1候補として扱う(赤ドラは別枚として個別評価する)
        seen_tile_kinds.add(key)

        remaining_hand = list(decision.hand)
        _remove_one(remaining_hand, tile)

        shanten_after = calculate_shanten(remaining_hand, melds_count)
        ukeire_count, ukeire_tiles = calculate_ukeire(remaining_hand, melds_count, visible_counts)
        est_value = _estimate_value(remaining_hand, shanten_after, dora_tile_kinds)
        danger_score = _estimate_danger(tile, decision)

        total_score = (
            -shanten_after * 1000.0
            + ukeire_count * 10.0
            + est_value * config.value_weight
            - (danger_score * config.danger_weight if opponents_in_riichi else 0.0)
        )

        candidates.append(
            RankedMove(
                action=Action(seat=decision.seat, kind="discard", tile=tile),
                shanten_after=shanten_after,
                ukeire_count=ukeire_count,
                ukeire_tiles=ukeire_tiles,
                est_value=est_value,
                danger_score=danger_score,
                total_score=total_score,
            )
        )

    candidates.sort(key=lambda m: m.total_score, reverse=True)
    return candidates


def _remove_one(hand: list[Tile], tile: Tile) -> None:
    for i, t in enumerate(hand):
        if t.suit == tile.suit and t.rank == tile.rank:
            del hand[i]
            return
    raise ValueError(f"手牌に存在しない牌です: {tile}")


def _compute_visible_counts(decision: DecisionPoint) -> list[int]:
    """自分の手牌を除く、場に見えている(捨て牌・全員の副露・ドラ表示牌)牌の枚数を34種で集計する。"""
    counts = [0] * 34
    for tiles in decision.discards_by_seat.values():
        for t in tiles:
            counts[t.index34] += 1
    for melds in decision.all_melds.values():
        for meld in melds:
            for t in meld.tiles:
                counts[t.index34] += 1
    for t in decision.dora_indicators:
        counts[t.index34] += 1
    return counts


def _dora_tile_kinds(dora_indicators: list[Tile]) -> set[int]:
    """ドラ表示牌から、ドラそのものの牌種(34インデックス)集合を求める。"""
    kinds: set[int] = set()
    for indicator in dora_indicators:
        if indicator.suit == Suit.HONOR:
            # 東南西北: 4種循環, 白發中: 3種循環
            if indicator.rank <= 4:
                next_rank = indicator.rank % 4 + 1
            else:
                next_rank = (indicator.rank - 5 + 1) % 3 + 5
            kinds.add(Tile(indicator.suit, next_rank).index34)
        else:
            next_rank = indicator.rank % 9 + 1
            kinds.add(Tile(indicator.suit, next_rank).index34)
    return kinds


def _estimate_value(hand_after: list[Tile], shanten_after: int, dora_kinds: set[int]) -> float:
    """期待打点の概算。役の複合や裏ドラは考慮しない簡易ヒューリスティック
    (docs/DESIGN.md 3.5節「打点期待値の概算」)。
    """
    dora_count = sum(1 for t in hand_after if t.index34 in dora_kinds) + sum(
        1 for t in hand_after if t.is_red_dora
    )
    shanten_bonus = max(0, 3 - max(shanten_after, 0)) * 2.0
    return shanten_bonus + dora_count * 1.0


def _estimate_danger(tile: Tile, decision: DecisionPoint) -> float:
    """放銃リスクの簡易概算(0.0=安全 ～ 1.0=高リスク)。

    現物(genbutsu)・スジ・場に見えている枚数によるヒューリスティックであり、
    正確な待ち読みを行うものではない(docs/DESIGN.md 3.5節)。
    """
    riichi_opponents = decision.riichi_seats - {decision.seat}
    if not riichi_opponents:
        return 0.0

    opponent_discards: set[tuple[str, int]] = set()
    for seat in riichi_opponents:
        for t in decision.discards_by_seat.get(seat, []):
            opponent_discards.add((t.suit.value, t.rank))

    key = (tile.suit.value, tile.rank)
    if key in opponent_discards:
        return 0.0  # 現物

    if tile.suit.value != "z":
        suji_low = (tile.suit.value, tile.rank - 3)
        suji_high = (tile.suit.value, tile.rank + 3)
        has_low = tile.rank - 3 >= 1 and suji_low in opponent_discards
        has_high = tile.rank + 3 <= 9 and suji_high in opponent_discards
        if has_low and has_high:
            return 0.2
        if has_low or has_high:
            return 0.35
        return 0.5

    # 字牌: 場に見えている枚数が多いほど(残り枚数が少ないほど)リスクは下がる
    visible = sum(1 for t in _all_visible_tiles(decision) if t.suit == tile.suit and t.rank == tile.rank)
    return max(0.1, 0.5 - visible * 0.15)


def _all_visible_tiles(decision: DecisionPoint):
    for tiles in decision.discards_by_seat.values():
        yield from tiles
    for melds in decision.all_melds.values():
        for meld in melds:
            yield from meld.tiles
