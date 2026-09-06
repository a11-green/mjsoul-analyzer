from mjsoul_analyzer.aggregator import aggregate
from mjsoul_analyzer.models import (
    Action,
    DecisionPoint,
    GameRecord,
    MoveDiff,
    PlayerInfo,
    RankedMove,
    RoundRecord,
    RoundResult,
    Tile,
)


def make_move_diff(label: str, shanten_delta: int = 0, value_delta: float = 0.0) -> MoveDiff:
    decision = DecisionPoint(
        round_name="East-1-0",
        turn=1,
        seat=0,
        hand=[],
        melds=[],
        all_melds={0: [], 1: [], 2: [], 3: []},
        discards_by_seat={0: [], 1: [], 2: [], 3: []},
        dora_indicators=[],
        riichi_seats=set(),
        remaining_tiles=50,
        actual_action=Action(seat=0, kind="discard", tile=Tile.parse("1m")),
    )
    best = RankedMove(
        action=Action(seat=0, kind="discard", tile=Tile.parse("1m")),
        shanten_after=0,
        ukeire_count=8,
        ukeire_tiles=[],
        est_value=5.0,
        danger_score=0.0,
        total_score=0.0,
    )
    return MoveDiff(
        decision=decision,
        ranked_moves=[best],
        best_move=best,
        actual_move=best,
        actual_rank=1,
        label=label,
        shanten_delta=shanten_delta,
        ukeire_delta=0,
        value_delta=value_delta,
    )


def make_game_record() -> GameRecord:
    rounds = [
        RoundRecord(
            round_name="East-1-0",
            dora_indicators=[],
            initial_hands={},
            events=[
                Action(seat=0, kind="riichi"),
            ],
            result=RoundResult(kind="hora", winner_seats=[0], is_tsumo=True, han=3, fu=40, points=5800),
        ),
        RoundRecord(
            round_name="East-2-0",
            dora_indicators=[],
            initial_hands={},
            events=[
                Action(seat=1, kind="pon"),
            ],
            result=RoundResult(kind="hora", winner_seats=[1], houjuu_seat=0, points=3900),
        ),
        RoundRecord(
            round_name="East-3-0",
            dora_indicators=[],
            initial_hands={},
            events=[],
            result=RoundResult(kind="ryuukyoku", tenpai_seats=[0]),
        ),
    ]
    players = [PlayerInfo(seat=i) for i in range(4)]
    return GameRecord(game_uuid="g1", players=players, rounds=rounds)


def test_aggregate_label_counts_and_rates():
    diffs = [
        make_move_diff("OPTIMAL"),
        make_move_diff("OPTIMAL"),
        make_move_diff("ACCEPTABLE", shanten_delta=0, value_delta=1.0),
        make_move_diff("MISTAKE", shanten_delta=1, value_delta=3.0),
    ]
    record = make_game_record()
    stats = aggregate(record, seat=0, move_diffs=diffs)

    assert stats.total_decisions == 4
    assert stats.label_counts["OPTIMAL"] == 2
    assert stats.label_counts["MISTAKE"] == 1
    assert stats.optimal_rate == 0.5
    assert stats.acceptable_or_better_rate == 0.75
    assert stats.avg_shanten_loss == (0 + 0 + 0 + 1) / 4
    assert stats.avg_value_loss == (0 + 0 + 1.0 + 3.0) / 4


def test_aggregate_game_result_stats_for_seat0():
    record = make_game_record()
    stats = aggregate(record, seat=0, move_diffs=[])
    assert stats.hora_count == 1
    assert stats.houjuu_count == 1  # 2局目でseat0が放銃
    assert stats.riichi_count == 1
    assert stats.call_count == 0
    assert stats.avg_hora_points == 5800


def test_aggregate_game_result_stats_for_seat1():
    record = make_game_record()
    stats = aggregate(record, seat=1, move_diffs=[])
    assert stats.hora_count == 1
    assert stats.houjuu_count == 0
    assert stats.call_count == 1
    assert stats.avg_hora_points == 3900


def test_mistake_highlights_sorted_by_severity():
    diffs = [
        make_move_diff("MISTAKE", shanten_delta=1, value_delta=1.0),
        make_move_diff("MISTAKE", shanten_delta=2, value_delta=0.5),
        make_move_diff("OPTIMAL"),
    ]
    record = make_game_record()
    stats = aggregate(record, seat=0, move_diffs=diffs, highlight_limit=1)
    assert len(stats.mistake_highlights) == 1
    assert stats.mistake_highlights[0].shanten_delta == 2
