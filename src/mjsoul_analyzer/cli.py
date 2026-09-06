"""CLIエントリポイント(docs/DESIGN.md 3.9節)。"""
from __future__ import annotations

from pathlib import Path

import click

from mjsoul_analyzer.aggregator import aggregate
from mjsoul_analyzer.engine.efficiency_engine import rank_moves
from mjsoul_analyzer.engine.hand_state import reconstruct_decision_points
from mjsoul_analyzer.engine.move_evaluator import EvaluatorConfig, evaluate
from mjsoul_analyzer.fetcher.record_fetcher import LocalFileRecordFetcher, RecordFetchError
from mjsoul_analyzer.parser.record_parser import InvalidRecordError, parse_raw_game_record
from mjsoul_analyzer.report.report_generator import (
    build_report_dict,
    render_markdown_report,
    write_json_report,
    write_markdown_report,
)
from mjsoul_analyzer.url_parser import InvalidPaipuUrlError, parse_paipu_url, parse_paipu_value

_ACK_MARKER_PATH = Path.home() / ".mjsoul-analyzer" / "tos_ack"

_TOS_NOTICE = (
    "本ツールは、雀魂の対局終了後の牌譜を、あなた自身のアカウントで正当にアクセスできる範囲で\n"
    "オフライン解析するためのものです。対局中のリアルタイムアシスト・自動打牌・他者牌譜の無断収集\n"
    "などには使用しないでください(詳細は CLAUDE.md を参照)。\n\n"
    "上記の方針に同意しますか?"
)


def _ensure_tos_ack(assume_yes: bool) -> None:
    if assume_yes or _ACK_MARKER_PATH.exists():
        return
    if not click.confirm(_TOS_NOTICE, default=False):
        raise click.ClickException("利用規約遵守方針への同意が得られなかったため終了します。")
    _ACK_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ACK_MARKER_PATH.write_text("ack\n", encoding="utf-8")


@click.group()
def main() -> None:
    """雀魂 牌譜解析ツール: 実際の打牌と最適手を比較・解析する。"""


@main.command()
@click.argument("paipu")
@click.option(
    "--seat",
    type=click.IntRange(0, 3),
    default=None,
    help="解析対象の席番号(0-3)。牌譜URLに視点指定(例: ..._a0)があれば省略可。",
)
@click.option(
    "--records-dir",
    type=click.Path(path_type=Path),
    default=Path("cache"),
    show_default=True,
    help="取得済みのRawGameRecord(JSON)を格納したディレクトリ。",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    default=Path("reports"),
    show_default=True,
    help="レポート出力先ディレクトリ。",
)
@click.option(
    "--format",
    "formats",
    default="md,json",
    show_default=True,
    help="出力フォーマット(カンマ区切り: md,json)。",
)
@click.option("--acceptable-rank", type=int, default=3, show_default=True)
@click.option("--ukeire-threshold", type=int, default=3, show_default=True)
@click.option("--yes", "assume_yes", is_flag=True, help="利用規約遵守方針の確認プロンプトをスキップする。")
def analyze(
    paipu: str,
    seat: int | None,
    records_dir: Path,
    out_dir: Path,
    formats: str,
    acceptable_rank: int,
    ukeire_threshold: int,
    assume_yes: bool,
) -> None:
    """牌譜URL(または牌譜ID)を解析し、最適手との一致率レポートを生成する。

    現時点では雀魂サーバーへの直接通信は未実装のため、事前に取得済みの
    RawGameRecord(JSON、docs/DESIGN.md 参照)を --records-dir に配置しておく必要がある。
    """
    _ensure_tos_ack(assume_yes)

    try:
        ref = parse_paipu_url(paipu) if "://" in paipu else parse_paipu_value(paipu)
    except InvalidPaipuUrlError as exc:
        raise click.ClickException(str(exc)) from exc

    target_seat = seat if seat is not None else ref.focus_seat
    if target_seat is None:
        raise click.ClickException(
            "解析対象の席番号を特定できません。--seat を指定するか、"
            "視点指定付きの牌譜URL/ID(例: ..._a0)を使用してください。"
        )

    fetcher = LocalFileRecordFetcher(records_dir)
    try:
        raw = fetcher.fetch(ref)
    except RecordFetchError as exc:
        raise click.ClickException(
            f"{exc}\n"
            "雀魂サーバーへの直接アクセスは未実装です。事前に取得済みのRawGameRecord(JSON)を "
            f"{records_dir}/{ref.game_uuid}.json として配置してください(docs/DESIGN.md 3.2節参照)。"
        ) from exc

    try:
        record = parse_raw_game_record(raw)
    except InvalidRecordError as exc:
        raise click.ClickException(str(exc)) from exc

    decisions = reconstruct_decision_points(record, focus_seats={target_seat})
    if not decisions:
        raise click.ClickException(f"seat={target_seat} の打牌選択が牌譜内に見つかりませんでした。")

    evaluator_config = EvaluatorConfig(acceptable_rank=acceptable_rank, ukeire_threshold=ukeire_threshold)
    diffs = [evaluate(decision, rank_moves(decision), evaluator_config) for decision in decisions]

    stats = aggregate(record, target_seat, diffs)

    format_list = {f.strip().lower() for f in formats.split(",") if f.strip()}
    out_dir.mkdir(parents=True, exist_ok=True)

    if "json" in format_list:
        report = build_report_dict(record, target_seat, diffs, stats)
        json_path = out_dir / f"{record.game_uuid}_seat{target_seat}.json"
        write_json_report(report, json_path)
        click.echo(f"JSONレポートを出力しました: {json_path}")

    if "md" in format_list:
        markdown = render_markdown_report(record, target_seat, diffs, stats)
        md_path = out_dir / f"{record.game_uuid}_seat{target_seat}.md"
        write_markdown_report(markdown, md_path)
        click.echo(f"Markdownレポートを出力しました: {md_path}")

    click.echo("")
    click.echo(
        f"最適手一致率: {stats.optimal_rate:.1%} "
        f"({stats.label_counts['OPTIMAL']}/{stats.total_decisions})"
    )


if __name__ == "__main__":
    main()
