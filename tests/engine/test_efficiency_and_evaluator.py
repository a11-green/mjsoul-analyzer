from mjsoul_analyzer.engine.efficiency_engine import rank_moves
from mjsoul_analyzer.engine.move_evaluator import EvaluatorConfig, evaluate
from mjsoul_analyzer.models import Action, DecisionPoint, RankedMove, Tile


def tiles(text: str) -> list[Tile]:
    result: list[Tile] = []
    buffer: list[str] = []
    for ch in text:
        if ch.isdigit():
            buffer.append(ch)
        else:
            for rank in buffer:
                result.append(Tile.parse(rank + ch))
            buffer = []
    return result


def make_decision(
    hand_text: str,
    actual_discard: str,
    *,
    seat: int = 0,
    discards_by_seat: dict[int, str] | None = None,
    riichi_seats: set[int] | None = None,
    dora_indicators: str = "",
) -> DecisionPoint:
    hand = tiles(hand_text)
    discards_by_seat = discards_by_seat or {}
    return DecisionPoint(
        round_name="East-1-0",
        turn=5,
        seat=seat,
        hand=hand,
        melds=[],
        all_melds={0: [], 1: [], 2: [], 3: []},
        discards_by_seat={s: tiles(t) for s, t in discards_by_seat.items()},
        dora_indicators=tiles(dora_indicators),
        riichi_seats=riichi_seats or set(),
        remaining_tiles=50,
        actual_action=Action(seat=seat, kind="discard", tile=Tile.parse(actual_discard)),
    )


def fake_move(tile_text: str, *, shanten_after: int, ukeire_count: int, danger_score: float = 0.0, est_value: float = 5.0) -> RankedMove:
    return RankedMove(
        action=Action(seat=0, kind="discard", tile=Tile.parse(tile_text)),
        shanten_after=shanten_after,
        ukeire_count=ukeire_count,
        ukeire_tiles=[],
        est_value=est_value,
        danger_score=danger_score,
        total_score=0.0,
    )


# --- rank_moves (efficiency_engine) ---


def test_rank_moves_prefers_tsumogiri_isolated_honor_over_breaking_a_set():
    # 123m 456p 789s 11z 45s + 浮き牌9m(14枚) を想定し、9mを切るのが最善のはず
    decision = make_decision("123m456p789s11z45s9m", "9m")
    ranked = rank_moves(decision)
    assert ranked[0].action.tile == Tile.parse("9m")
    assert ranked[0].shanten_after == 0  # 9mを切れば聴牌


def test_evaluate_labels_optimal_when_actual_matches_best():
    decision = make_decision("123m456p789s11z45s9m", "9m")
    ranked = rank_moves(decision)
    diff = evaluate(decision, ranked)
    assert diff.label == "OPTIMAL"
    assert diff.actual_rank == 1
    assert diff.shanten_delta == 0


def test_evaluate_labels_mistake_when_shanten_worsens():
    # 9mではなく聴牌を崩す牌(1z)を切ってしまったケース
    decision = make_decision("123m456p789s11z45s9m", "1z")
    ranked = rank_moves(decision)
    diff = evaluate(decision, ranked)
    assert diff.label == "MISTAKE"
    assert diff.shanten_delta >= 1


def test_evaluate_returns_unknown_when_actual_tile_not_in_hand():
    decision = make_decision("123m456p789s11z45s9m", "9m")
    ranked = rank_moves(decision)
    decision.actual_action.tile = Tile.parse("9p")
    diff = evaluate(decision, ranked)
    assert diff.label == "UNKNOWN"
    assert diff.actual_rank is None


# --- move_evaluator のラベリング分岐を直接検証 ---
# (現実的な牌姿からシャンテン・受け入れが完全に同点の局面を作るのは難しいため、
#  RankedMoveを直接組み立てて分岐条件そのものを検証する)


def test_label_mistake_due_to_danger_when_shanten_is_equal():
    decision = make_decision("123m456p789s11z45s", "5s", riichi_seats={1})
    best = fake_move("3s", shanten_after=0, ukeire_count=8, danger_score=0.0)
    risky_same_shanten = fake_move("5s", shanten_after=0, ukeire_count=8, danger_score=0.6)
    decision.actual_action.tile = Tile.parse("5s")
    diff = evaluate(decision, [best, risky_same_shanten])
    assert diff.label == "MISTAKE"
    assert diff.shanten_delta == 0


def test_label_acceptable_within_threshold():
    decision = make_decision("123m456p789s11z45s", "6s")
    best = fake_move("3s", shanten_after=0, ukeire_count=8)
    acceptable = fake_move("6s", shanten_after=0, ukeire_count=6)  # ukeire差2 <= 既定閾値3
    decision.actual_action.tile = Tile.parse("6s")
    diff = evaluate(decision, [best, acceptable], EvaluatorConfig(acceptable_rank=3, ukeire_threshold=3))
    assert diff.label == "ACCEPTABLE"
    assert diff.actual_rank == 2


def test_label_suboptimal_when_beyond_acceptable_threshold():
    decision = make_decision("123m456p789s11z45s", "7z")
    best = fake_move("3s", shanten_after=0, ukeire_count=8)
    poor = fake_move("7z", shanten_after=0, ukeire_count=1)  # ukeire差7 > 既定閾値3
    decision.actual_action.tile = Tile.parse("7z")
    diff = evaluate(decision, [best, poor], EvaluatorConfig(acceptable_rank=3, ukeire_threshold=3))
    assert diff.label == "SUBOPTIMAL"
