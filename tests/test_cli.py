import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from mjsoul_analyzer.cli import main

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_round.json"


def test_analyze_end_to_end(tmp_path: Path, monkeypatch):
    # ホームディレクトリをtmp_pathに向け、ToS同意マーカーが実環境を汚さないようにする
    monkeypatch.setenv("HOME", str(tmp_path))

    records_dir = tmp_path / "cache"
    records_dir.mkdir()
    shutil.copy(FIXTURE_PATH, records_dir / "test-uuid-0001.json")

    out_dir = tmp_path / "reports"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "analyze",
            "test-uuid-0001_a111111111",
            "--records-dir",
            str(records_dir),
            "--out",
            str(out_dir),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "最適手一致率" in result.output

    json_path = out_dir / "test-uuid-0001_seat0.json"
    md_path = out_dir / "test-uuid-0001_seat0.md"
    assert json_path.exists()
    assert md_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["game_uuid"] == "test-uuid-0001"
    assert report["seat"] == 0
    assert report["summary"]["total_decisions"] == 2  # seat0の打牌は2回


def test_analyze_missing_seat_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    records_dir = tmp_path / "cache"
    records_dir.mkdir()
    shutil.copy(FIXTURE_PATH, records_dir / "test-uuid-0001.json")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "test-uuid-0001", "--records-dir", str(records_dir), "--yes"],
    )
    assert result.exit_code != 0
    assert "席番号" in result.output


def test_analyze_missing_record_file_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    records_dir = tmp_path / "cache"
    records_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "no-such-uuid_a0", "--records-dir", str(records_dir), "--yes"],
    )
    assert result.exit_code != 0
    assert "未実装" in result.output


def test_tos_prompt_declined_aborts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    records_dir = tmp_path / "cache"
    records_dir.mkdir()
    shutil.copy(FIXTURE_PATH, records_dir / "test-uuid-0001.json")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["analyze", "test-uuid-0001_a111111111", "--records-dir", str(records_dir)],
        input="n\n",
    )
    assert result.exit_code != 0
    assert "同意" in result.output
