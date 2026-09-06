"""実際の打牌と、効率エンジンが算出した候補手ランキングとの差分を評価する。

docs/DESIGN.md 3.6節のラベリング方針:
- OPTIMAL: 最上位候補と一致
- ACCEPTABLE: 上位N(既定3)以内で、シャンテン差・受け入れ差が閾値以下
- MISTAKE: シャンテンを後退させる、または相手リーチ時に明確な危険牌を選んでいる
- SUBOPTIMAL: 上記のいずれにも該当しないが和了に向かう手ではある
"""
from __future__ import annotations

from dataclasses import dataclass

from mjsoul_analyzer.models import DecisionPoint, MoveDiff, RankedMove


@dataclass(frozen=True)
class EvaluatorConfig:
    acceptable_rank: int = 3
    ukeire_threshold: int = 3
    danger_mistake_threshold: float = 0.4


def evaluate(
    decision: DecisionPoint,
    ranked_moves: list[RankedMove],
    config: EvaluatorConfig | None = None,
) -> MoveDiff:
    config = config or EvaluatorConfig()
    if not ranked_moves:
        raise ValueError("ranked_movesが空です")
    if decision.actual_action is None or decision.actual_action.tile is None:
        raise ValueError("actual_actionに打牌情報がありません")

    actual_tile = decision.actual_action.tile
    best = ranked_moves[0]

    actual_move: RankedMove | None = None
    actual_rank: int | None = None
    for idx, move in enumerate(ranked_moves, start=1):
        move_tile = move.action.tile
        if move_tile is not None and move_tile.suit == actual_tile.suit and move_tile.rank == actual_tile.rank:
            actual_move = move
            actual_rank = idx
            break

    if actual_move is None:
        return MoveDiff(
            decision=decision,
            ranked_moves=ranked_moves,
            best_move=best,
            actual_move=None,
            actual_rank=None,
            label="UNKNOWN",
            shanten_delta=0,
            ukeire_delta=0,
            value_delta=0.0,
        )

    shanten_delta = actual_move.shanten_after - best.shanten_after
    ukeire_delta = best.ukeire_count - actual_move.ukeire_count
    value_delta = best.est_value - actual_move.est_value

    label = _label_move(decision, ranked_moves, best, actual_move, actual_rank, shanten_delta, ukeire_delta, config)

    return MoveDiff(
        decision=decision,
        ranked_moves=ranked_moves,
        best_move=best,
        actual_move=actual_move,
        actual_rank=actual_rank,
        label=label,
        shanten_delta=shanten_delta,
        ukeire_delta=ukeire_delta,
        value_delta=value_delta,
    )


def _label_move(
    decision: DecisionPoint,
    ranked_moves: list[RankedMove],
    best: RankedMove,
    actual_move: RankedMove,
    actual_rank: int,
    shanten_delta: int,
    ukeire_delta: int,
    config: EvaluatorConfig,
) -> str:
    if actual_rank == 1:
        return "OPTIMAL"

    if shanten_delta >= 1:
        return "MISTAKE"

    opponents_in_riichi = bool(decision.riichi_seats - {decision.seat})
    if opponents_in_riichi:
        best_tier_danger = min(
            m.danger_score for m in ranked_moves if m.shanten_after == best.shanten_after
        )
        if actual_move.danger_score - best_tier_danger >= config.danger_mistake_threshold:
            return "MISTAKE"

    if actual_rank <= config.acceptable_rank and ukeire_delta <= config.ukeire_threshold:
        return "ACCEPTABLE"

    return "SUBOPTIMAL"
