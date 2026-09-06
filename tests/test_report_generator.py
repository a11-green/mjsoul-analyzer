import json
from pathlib import Path

from mjsoul_analyzer.aggregator import aggregate
from mjsoul_analyzer.report.report_generator import (
    build_report_dict,
    render_markdown_report,
    write_json_report,
    write_markdown_report,
)
from tests.test_aggregator import make_game_record, make_move_diff


def test_build_report_dict_and_json_roundtrip(tmp_path: Path):
    record = make_game_record()
    diffs = [make_move_diff("OPTIMAL"), make_move_diff("MISTAKE", shanten_delta=1, value_delta=2.0)]
    stats = aggregate(record, seat=0, move_diffs=diffs)
    report = build_report_dict(record, seat=0, move_diffs=diffs, stats=stats)

    out_path = tmp_path / "report.json"
    write_json_report(report, out_path)

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["game_uuid"] == "g1"
    assert loaded["seat"] == 0
    assert loaded["summary"]["total_decisions"] == 2
    assert len(loaded["decisions"]) == 2


def test_render_markdown_report_contains_key_sections(tmp_path: Path):
    record = make_game_record()
    diffs = [make_move_diff("MISTAKE", shanten_delta=1, value_delta=2.0)]
    stats = aggregate(record, seat=0, move_diffs=diffs)
    markdown = render_markdown_report(record, seat=0, move_diffs=diffs, stats=stats)

    assert "牌譜解析レポート" in markdown
    assert "最適手一致率" in markdown
    assert "ミス局面ハイライト" in markdown

    out_path = tmp_path / "report.md"
    write_markdown_report(markdown, out_path)
    assert out_path.read_text(encoding="utf-8") == markdown
