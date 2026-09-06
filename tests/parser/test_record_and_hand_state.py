import json
from pathlib import Path

from mjsoul_analyzer.engine.hand_state import reconstruct_decision_points
from mjsoul_analyzer.models import Tile
from mjsoul_analyzer.parser.record_parser import parse_raw_game_record

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample_round.json"


def load_record():
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return parse_raw_game_record(raw)


def test_parse_raw_game_record_basic_structure():
    record = load_record()
    assert record.game_uuid == "test-uuid-0001"
    assert len(record.players) == 4
    assert len(record.rounds) == 1

    round_record = record.rounds[0]
    assert round_record.round_name == "East-1-0"
    assert round_record.dora_indicators == [Tile.parse("4s")]
    assert len(round_record.initial_hands[0]) == 13
    assert round_record.result is not None
    assert round_record.result.kind == "ryuukyoku"


def test_reconstruct_decision_points_count_and_order():
    record = load_record()
    decisions = reconstruct_decision_points(record)
    # discardイベントは6回(seat0*2, seat1*2, seat2*1, seat3*1)
    assert len(decisions) == 6
    assert [d.seat for d in decisions] == [0, 1, 2, 3, 0, 1]


def test_decision_point_hand_includes_drawn_tile():
    record = load_record()
    decisions = reconstruct_decision_points(record)
    first = decisions[0]
    assert first.seat == 0
    assert first.round_name == "East-1-0"
    # 配牌13枚 + 自摸1枚 = 14枚
    assert len(first.hand) == 14
    assert Tile.parse("9m") in first.hand
    assert first.actual_action is not None
    assert first.actual_action.tile == Tile.parse("9m")
    assert first.actual_action.is_tsumogiri is True


def test_decision_point_reflects_prior_discards_and_dora():
    record = load_record()
    decisions = reconstruct_decision_points(record)
    third = decisions[2]  # seat2の打牌
    assert third.seat == 2
    # seat0, seat1がそれぞれ1回ずつ捨てた後の状態が見えているはず
    assert third.discards_by_seat[0] == [Tile.parse("9m")]
    assert third.discards_by_seat[1] == [Tile.parse("9p")]
    assert third.dora_indicators == [Tile.parse("4s")]


def test_chi_updates_hand_and_meld_state():
    record = load_record()
    decisions = reconstruct_decision_points(record)
    # seat1の2回目の打牌(チー後)
    seat1_second = decisions[5]
    assert seat1_second.seat == 1
    assert len(seat1_second.melds) == 1
    meld = seat1_second.melds[0]
    assert meld.kind == "chi"
    assert sorted(str(t) for t in meld.tiles) == ["4p", "5p", "6p"]
    # 配牌13枚 -> 自摸9pをそのまま打牌(±0) -> チーで手牌から4p,5pを提供(-2) = 11枚
    assert len(seat1_second.hand) == 11


def test_focus_seats_filters_decision_points():
    record = load_record()
    decisions = reconstruct_decision_points(record, focus_seats={0})
    assert len(decisions) == 2
    assert all(d.seat == 0 for d in decisions)
