"""シャンテン数計算。

シャンテン数 = あと何回の有効な牌交換で聴牌（テンパイ）になるかを表す数値。
- -1: 和了形（アガリ）
-  0: 聴牌
-  1以上: 聴牌までの残り手数

通常形（4面子+1雀頭）・七対子・国士無双の3形について計算し、最小値を採用する。
副露（チー・ポン・カン）がある場合は、副露の数だけ「既に完成した面子」として扱い、
通常形の計算のみを対象とする（七対子・国士無双は副露では成立しないため）。

アルゴリズムは、34種類の牌カウント配列に対して「面子・対子・搭子(塔子)をどう組み合わせるのが
最も聴牌に近いか」を再帰的に全探索する、広く知られた手法（いわゆる shanten calculator の
素朴な実装）を採用している。牌の種類数(34)・各種類の最大枚数(4)が小さいため、
1手あたりの探索量は実用上十分高速。
"""
from __future__ import annotations

from mjsoul_analyzer.models import Suit, Tile


def tiles_to_counts(tiles: list[Tile]) -> list[int]:
    """Tileのリストを34種類の枚数配列に変換する。"""
    counts = [0] * 34
    for tile in tiles:
        counts[tile.index34] += 1
    return counts


def calculate_shanten(tiles: list[Tile], melds_count: int = 0) -> int:
    """手牌のシャンテン数を計算する。

    Args:
        tiles: 副露を除いた手牌(通常13枚、打牌前の自摸直後は14枚で呼ぶ想定だが、
            本関数は「打牌後」つまり13-3*melds_count枚を渡すことを想定している)。
        melds_count: 既に副露している面子の数(0-4)。
    """
    counts = tiles_to_counts(tiles)
    best = _standard_shanten(counts, melds_count)
    if melds_count == 0:
        best = min(best, _chiitoitsu_shanten(counts))
        best = min(best, _kokushi_shanten(counts))
    return best


def _standard_shanten(counts: list[int], melds_count: int) -> int:
    need_sets = 4 - melds_count
    counts = list(counts)  # 破壊的に使うのでコピー
    best = [8]

    def finalize(sets: int, partials: int, has_pair: bool) -> None:
        # 面子+搭子の合計はneed_setsを超えても意味がないので切り詰める
        if sets + partials > need_sets:
            partials = need_sets - sets
        shanten = (need_sets - sets) * 2 - partials - (1 if has_pair else 0)
        # 雀頭が無いまま面子+搭子でneed_setsを使い切っている場合、
        # どこかを崩して雀頭を作る必要があるため+1する
        if not has_pair and sets + partials >= need_sets and need_sets > 0:
            shanten += 1
        if shanten < best[0]:
            best[0] = shanten

    def recurse(i: int, sets: int, partials: int, has_pair: bool) -> None:
        if i >= 34:
            finalize(sets, partials, has_pair)
            return

        c = counts[i]
        if c == 0:
            recurse(i + 1, sets, partials, has_pair)
            return

        suit_pos = i % 9
        is_number = i < 27

        # 刻子(同じ牌3枚)
        if c >= 3:
            counts[i] -= 3
            recurse(i, sets + 1, partials, has_pair)
            counts[i] += 3

        # 順子(連続3枚、数牌のみ)
        if is_number and suit_pos <= 6 and counts[i] >= 1 and counts[i + 1] >= 1 and counts[i + 2] >= 1:
            counts[i] -= 1
            counts[i + 1] -= 1
            counts[i + 2] -= 1
            recurse(i, sets + 1, partials, has_pair)
            counts[i] += 1
            counts[i + 1] += 1
            counts[i + 2] += 1

        # 対子を雀頭として使う
        if c >= 2 and not has_pair:
            counts[i] -= 2
            recurse(i, sets, partials, True)
            counts[i] += 2

        # 対子を搭子(暗刻/明刻候補やシャンポン)として使う
        if c >= 2:
            counts[i] -= 2
            recurse(i, sets, partials + 1, has_pair)
            counts[i] += 2

        # 両面/辺張搭子 (i, i+1)
        if is_number and suit_pos <= 7 and counts[i] >= 1 and counts[i + 1] >= 1:
            counts[i] -= 1
            counts[i + 1] -= 1
            recurse(i, sets, partials + 1, has_pair)
            counts[i] += 1
            counts[i + 1] += 1

        # 嵌張搭子 (i, i+2)
        if is_number and suit_pos <= 6 and counts[i] >= 1 and counts[i + 2] >= 1:
            counts[i] -= 1
            counts[i + 2] -= 1
            recurse(i, sets, partials + 1, has_pair)
            counts[i] += 1
            counts[i + 2] += 1

        # この牌種はこれ以上使わず次へ進む(余り牌として浮かせる)
        recurse(i + 1, sets, partials, has_pair)

    recurse(0, 0, 0, False)
    return best[0]


def _chiitoitsu_shanten(counts: list[int]) -> int:
    pairs = sum(1 for c in counts if c >= 2)
    kinds = sum(1 for c in counts if c >= 1)
    # 七対子は7種の対子が必要。牌種が7未満の場合、種類不足分だけ余分にペナルティが乗る。
    shanten = 6 - pairs
    if kinds < 7:
        shanten += 7 - kinds
    return shanten


def _kokushi_shanten(counts: list[int]) -> int:
    terminal_honor_indices = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    kinds = sum(1 for i in terminal_honor_indices if counts[i] >= 1)
    has_pair = any(counts[i] >= 2 for i in terminal_honor_indices)
    return 13 - kinds - (1 if has_pair else 0)


def calculate_ukeire(
    tiles: list[Tile],
    melds_count: int,
    visible_counts: list[int],
) -> tuple[int, list[Tile]]:
    """現在のシャンテン数を1つ進める(シャンテンを減らす)受け入れ牌を計算する。

    Args:
        tiles: 判定対象の手牌(打牌後の状態)。
        melds_count: 副露面子数。
        visible_counts: 34種類それぞれについて、既に見えている(手牌以外の)枚数。
            自分の手牌分は含めないこと。受け入れ枚数 = 4 - visible_counts[i] - own_hand_counts[i]。

    Returns:
        (受け入れ総枚数, 受け入れ牌種のリスト)
    """
    base_shanten = calculate_shanten(tiles, melds_count)
    own_counts = tiles_to_counts(tiles)
    ukeire_tiles: list[Tile] = []
    total = 0
    for idx in range(34):
        if own_counts[idx] >= 4:
            continue  # これ以上増やせない
        candidate_tiles = list(tiles) + [Tile.from_index34(idx)]
        if calculate_shanten(candidate_tiles, melds_count) < base_shanten:
            remaining = 4 - visible_counts[idx] - own_counts[idx]
            if remaining > 0:
                ukeire_tiles.append(Tile.from_index34(idx))
                total += remaining
    return total, ukeire_tiles
