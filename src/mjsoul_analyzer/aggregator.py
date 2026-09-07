"""対局単位・プレイヤー単位の統計集計(docs/DESIGN.md 3.7節)。"""
from __future__ import annotations

from dataclasses import dataclass, field

from mjsoul_analyzer.models import GameRecord, MoveDiff

_LABELS = ("OPTIMAL", "ACCEPTABLE", "SUBOPTIMAL", "MISTAKE", "UNKNOWN")


@dataclass
class SummaryStats:
    seat: int
    total_decisions: int
    label_counts: dict[str, int]
    optimal_rate: float
    acceptable_or_better_rate: float
    avg_shanten_loss: float
    avg_value_loss: float
    hora_count: int
    houjuu_count: int
    riichi_count: int
    call_count: int
    avg_hora_points: float
    mistake_highlights: list[MoveDiff] = field(default_factory=list)


def aggregate(
    game_record: GameRecord,
    seat: int,
    move_diffs: list[MoveDiff],
    highlight_limit: int = 10,
) -> SummaryStats:
    """指定した席のプレイヤーについて、打牌の一致率と実績統計をまとめる。"""
    label_counts = {label: 0 for label in _LABELS}
    shanten_losses: list[int] = []
    value_losses: list[float] = []
    for diff in move_diffs:
        label_counts[diff.label] = label_counts.get(diff.label, 0) + 1
        if diff.label != "UNKNOWN":
            shanten_losses.append(max(0, diff.shanten_delta))
            value_losses.append(max(0.0, diff.value_delta))

    total = len(move_diffs)
    optimal_rate = label_counts["OPTIMAL"] / total if total else 0.0
    acceptable_or_better_rate = (
        (label_counts["OPTIMAL"] + label_counts["ACCEPTABLE"]) / total if total else 0.0
    )
    avg_shanten_loss = sum(shanten_losses) / len(shanten_losses) if shanten_losses else 0.0
    avg_value_loss = sum(value_losses) / len(value_losses) if value_losses else 0.0

    hora_count = 0
    houjuu_count = 0
    riichi_count = 0
    call_count = 0
    hora_points: list[int] = []
    for round_record in game_record.rounds:
        for event in round_record.events:
            if event.seat != seat:
                continue
            if event.kind == "riichi":
                riichi_count += 1
            elif event.kind in ("chi", "pon", "kan"):
                call_count += 1

        result = round_record.result
        if result is None or result.kind != "hora":
            continue
        if seat in result.winner_seats:
            hora_count += 1
            hora_points.append(result.points)
        if result.houjuu_seat == seat:
            houjuu_count += 1

    avg_hora_points = sum(hora_points) / len(hora_points) if hora_points else 0.0

    mistakes = [d for d in move_diffs if d.label == "MISTAKE"]
    mistakes.sort(key=lambda d: (d.shanten_delta, d.value_delta), reverse=True)

    return SummaryStats(
        seat=seat,
        total_decisions=total,
        label_counts=label_counts,
        optimal_rate=optimal_rate,
        acceptable_or_better_rate=acceptable_or_better_rate,
        avg_shanten_loss=avg_shanten_loss,
        avg_value_loss=avg_value_loss,
        hora_count=hora_count,
        houjuu_count=houjuu_count,
        riichi_count=riichi_count,
        call_count=call_count,
        avg_hora_points=avg_hora_points,
        mistake_highlights=mistakes[:highlight_limit],
    )
