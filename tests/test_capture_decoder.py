import json
from pathlib import Path

import pytest

from mjsoul_analyzer.engine.efficiency_engine import rank_moves
from mjsoul_analyzer.engine.hand_state import reconstruct_decision_points
from mjsoul_analyzer.engine.move_evaluator import evaluate
from mjsoul_analyzer.fetcher.capture_decoder import (
    CaptureDecodeError,
    capture_to_raw_game_record,
)
from mjsoul_analyzer.parser.record_parser import parse_raw_game_record

_PAIPU_DIR = Path(__file__).parent / "paipu"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_full_game_record(path: Path) -> bool:
    """初期のデバッグ用キャプチャ(heartbeatのみで牌譜データを含まない)を除外する。"""
    return _load(path).get("frame_count", 0) > 10


_REAL_CAPTURES = sorted(p for p in _PAIPU_DIR.glob("mjsoul_capture_*.json") if _has_full_game_record(p))


@pytest.mark.parametrize("capture_path", _REAL_CAPTURES, ids=lambda p: p.name)
def test_capture_to_raw_game_record_roundtrips_through_full_pipeline(capture_path: Path) -> None:
    """browser-extensionで実際にキャプチャした生データを、記録破損なく
    RawGameRecord化し、DecisionPoint復元・効率エンジンまで通せることを確認する。"""
    capture = _load(capture_path)

    raw = capture_to_raw_game_record(capture)

    assert raw["game_uuid"]
    assert len(raw["players"]) in (3, 4)
    assert raw["rounds"], "少なくとも1局は含まれているはず"

    record = parse_raw_game_record(raw)
    decision_points = reconstruct_decision_points(record)
    assert decision_points, "打牌選択が1つも復元できないのはおかしい"

    # 全ての局・全ての打牌選択点で効率エンジン・評価器がエラーなく完走することを確認する
    # (=手牌復元が矛盾なく最後まで行えている、という強い整合性チェックになる)。
    for dp in decision_points:
        ranked = rank_moves(dp)
        assert ranked
        diff = evaluate(dp, ranked)
        assert diff.label in ("OPTIMAL", "ACCEPTABLE", "SUBOPTIMAL", "MISTAKE", "UNKNOWN")


def test_capture_to_raw_game_record_decodes_known_first_round() -> None:
    capture_path = _PAIPU_DIR / "mjsoul_capture_1788786202091.json"
    if not capture_path.exists():
        pytest.skip("実キャプチャサンプルが見つかりません")
    capture = _load(capture_path)

    raw = capture_to_raw_game_record(capture)

    assert raw["game_uuid"] == "260907-f2e1581b-212e-42fd-b2ed-ff06b4037517"
    names = {p["name"] for p in raw["players"]}
    assert names == {"とろきょうへい", "アマテラス0909", "咲ch"}

    round1 = raw["rounds"][0]
    assert round1["round_name"] == "East-1-0"
    assert round1["dora_indicators"] == ["2s"]
    assert len(round1["initial_hands"]["0"]) == 14  # 親は配牌+第1自摸で14枚
    assert len(round1["initial_hands"]["1"]) == 13
    assert len(round1["initial_hands"]["2"]) == 13

    result = round1["result"]
    assert result["kind"] == "hora"
    assert result["winner_seats"] == [2]
    assert result["is_tsumo"] is True
    assert result["points"] == 6000


def test_capture_to_raw_game_record_raises_on_capture_without_fetch_game_record() -> None:
    empty_capture = {"frames": []}
    with pytest.raises(CaptureDecodeError):
        capture_to_raw_game_record(empty_capture)


def test_capture_to_raw_game_record_raises_on_heartbeat_only_capture() -> None:
    """記録開始が遅すぎてheartbeatしか捕まえられなかった初期の実キャプチャでも、
    (誤った空データを返さず)明確なエラーになることを確認する。"""
    heartbeat_only_path = _PAIPU_DIR / "mjsoul_capture_1788781787552.json"
    if not heartbeat_only_path.exists():
        pytest.skip("該当のキャプチャサンプルが見つかりません")
    capture = _load(heartbeat_only_path)
    with pytest.raises(CaptureDecodeError):
        capture_to_raw_game_record(capture)
