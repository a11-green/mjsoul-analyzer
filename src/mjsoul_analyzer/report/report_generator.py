"""解析結果をMarkdown/JSONレポートとして出力する(docs/DESIGN.md 3.8節)。

v1のスコープではMarkdownとJSONのみを対象とし、HTML出力はv2以降で検討する
(docs/DESIGN.md 8節「開発フェーズ」参照)。牌譜表示には雀魂の著作物(牌画像等)を
一切使用せず、テキスト表記(例: "3s", "0m"=赤5萬)に限定する(CLAUDE.md遵守)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mjsoul_analyzer.aggregator import SummaryStats
from mjsoul_analyzer.models import GameRecord, MoveDiff, PlayerInfo

_LABEL_JA = {
    "OPTIMAL": "最適",
    "ACCEPTABLE": "許容範囲",
    "SUBOPTIMAL": "やや損",
    "MISTAKE": "ミス",
    "UNKNOWN": "判定不能",
}


def build_report_dict(
    game_record: GameRecord,
    seat: int,
    move_diffs: list[MoveDiff],
    stats: SummaryStats,
) -> dict[str, Any]:
    """JSON出力用の辞書を組み立てる。"""
    player = _find_player(game_record, seat)
    return {
        "game_uuid": game_record.game_uuid,
        "seat": seat,
        "player_name": player.name if player else "",
        "summary": {
            "total_decisions": stats.total_decisions,
            "label_counts": stats.label_counts,
            "optimal_rate": stats.optimal_rate,
            "acceptable_or_better_rate": stats.acceptable_or_better_rate,
            "avg_shanten_loss": stats.avg_shanten_loss,
            "avg_value_loss": stats.avg_value_loss,
            "hora_count": stats.hora_count,
            "houjuu_count": stats.houjuu_count,
            "riichi_count": stats.riichi_count,
            "call_count": stats.call_count,
            "avg_hora_points": stats.avg_hora_points,
        },
        "decisions": [_move_diff_to_dict(d) for d in move_diffs],
    }


def _move_diff_to_dict(diff: MoveDiff) -> dict[str, Any]:
    decision = diff.decision
    return {
        "round_name": decision.round_name,
        "turn": decision.turn,
        "hand": [str(t) for t in decision.hand],
        "actual_discard": str(decision.actual_action.tile) if decision.actual_action and decision.actual_action.tile else None,
        "best_discard": str(diff.best_move.action.tile) if diff.best_move.action.tile else None,
        "actual_rank": diff.actual_rank,
        "label": diff.label,
        "shanten_delta": diff.shanten_delta,
        "ukeire_delta": diff.ukeire_delta,
        "value_delta": diff.value_delta,
    }


def write_json_report(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def render_markdown_report(
    game_record: GameRecord,
    seat: int,
    move_diffs: list[MoveDiff],
    stats: SummaryStats,
) -> str:
    player = _find_player(game_record, seat)
    player_label = f"{player.name} (seat {seat})" if player and player.name else f"seat {seat}"

    lines: list[str] = []
    lines.append(f"# 牌譜解析レポート: {game_record.game_uuid}")
    lines.append("")
    lines.append(f"対象プレイヤー: {player_label}")
    lines.append("")
    lines.append("## サマリ")
    lines.append("")
    lines.append(f"- 打牌選択数: {stats.total_decisions}")
    lines.append(f"- 最適手一致率: {stats.optimal_rate:.1%}")
    lines.append(f"- 許容範囲以上率(最適+許容): {stats.acceptable_or_better_rate:.1%}")
    lines.append(f"- 平均シャンテン損失: {stats.avg_shanten_loss:.2f}")
    lines.append(f"- 平均期待値損失: {stats.avg_value_loss:.2f}")
    lines.append(f"- 和了回数: {stats.hora_count} (平均打点 {stats.avg_hora_points:.0f})")
    lines.append(f"- 放銃回数: {stats.houjuu_count}")
    lines.append(f"- リーチ回数: {stats.riichi_count}")
    lines.append(f"- 副露回数: {stats.call_count}")
    lines.append("")
    lines.append("### ラベル別内訳")
    lines.append("")
    lines.append("| ラベル | 件数 | 割合 |")
    lines.append("|---|---|---|")
    total = stats.total_decisions or 1
    for label in ("OPTIMAL", "ACCEPTABLE", "SUBOPTIMAL", "MISTAKE", "UNKNOWN"):
        count = stats.label_counts.get(label, 0)
        lines.append(f"| {_LABEL_JA[label]} | {count} | {count / total:.1%} |")
    lines.append("")

    if stats.mistake_highlights:
        lines.append("## ミス局面ハイライト")
        lines.append("")
        for diff in stats.mistake_highlights:
            d = diff.decision
            actual_tile = d.actual_action.tile if d.actual_action else None
            best_tile = diff.best_move.action.tile
            lines.append(
                f"- **{d.round_name} 巡目{d.turn}**: "
                f"実際の打牌 `{actual_tile}` (シャンテン+{diff.shanten_delta}, "
                f"期待値損失{diff.value_delta:.1f}) / 推奨打牌 `{best_tile}`"
            )
        lines.append("")

    lines.append(
        "> 本レポートの「最適手」は本ツールの簡易効率エンジンによる推定であり、"
        "絶対的な正解を保証するものではありません。"
    )
    return "\n".join(lines)


def write_markdown_report(content: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


def _find_player(game_record: GameRecord, seat: int) -> PlayerInfo | None:
    for player in game_record.players:
        if player.seat == seat:
            return player
    return None
