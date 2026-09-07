from mjsoul_analyzer.engine.shanten import calculate_shanten, calculate_ukeire
from mjsoul_analyzer.models import Tile


def tiles(text: str) -> list[Tile]:
    """"123m456p789s11z" のような連続表記をTileのリストに変換するテスト用ヘルパー。"""
    result: list[Tile] = []
    buffer: list[str] = []
    for ch in text:
        if ch.isdigit():
            buffer.append(ch)
        else:
            for rank in buffer:
                result.append(Tile.parse(rank + ch))
            buffer = []
    assert not buffer, f"末尾に牌種が続かない数字が残っています: {text}"
    return result


def test_agari_standard_hand_is_minus_one():
    hand = tiles("123m456p789s111z22z")
    assert len(hand) == 14
    assert calculate_shanten(hand) == -1


def test_tenpai_standard_hand_is_zero():
    hand = tiles("123m456p789s11z45s")
    assert len(hand) == 13
    assert calculate_shanten(hand) == 0


def test_one_shanten_standard_hand():
    hand = tiles("1239m456p789s4s11z")
    assert len(hand) == 13
    assert calculate_shanten(hand) == 1


def test_agari_with_melds():
    # 2副露(既に2面子完成)+ 残り手牌 で 2面子+雀頭 が揃っていれば和了形
    hand = tiles("123m456p11z")
    assert len(hand) == 8
    assert calculate_shanten(hand, melds_count=2) == -1


def test_chiitoitsu_agari():
    hand = tiles("11m22m33m44p55p66s11z")
    assert len(hand) == 14
    assert calculate_shanten(hand) == -1


def test_chiitoitsu_tenpai():
    hand = tiles("11m22m33m44p55p66p7z")
    assert len(hand) == 13
    assert calculate_shanten(hand) == 0


def test_kokushi_agari():
    hand = tiles("19m19p19s1234567z1m")
    assert len(hand) == 14
    assert calculate_shanten(hand) == -1


def test_kokushi_tenpai():
    hand = tiles("19m19p19s123456z7z")
    # 13種類の么九牌が1枚ずつ(対子なし) -> 国士無双13面待ちで聴牌
    assert len(hand) == 13
    assert calculate_shanten(hand) == 0


def test_ukeire_for_tenpai_ryanmen():
    hand = tiles("123m456p789s11z45s")
    visible = [0] * 34
    total, ukeire_tiles = calculate_ukeire(hand, melds_count=0, visible_counts=visible)
    ukeire_strs = sorted(str(t) for t in ukeire_tiles)
    assert ukeire_strs == ["3s", "6s"]
    assert total == 8  # 3s, 6sそれぞれ4枚ずつ見えていない
