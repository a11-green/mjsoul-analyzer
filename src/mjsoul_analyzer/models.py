"""牌譜解析ツールの共通データモデル。

設計の詳細は docs/DESIGN.md の「4. データモデル」を参照。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class Suit(Enum):
    MAN = "m"
    PIN = "p"
    SOU = "s"
    HONOR = "z"


# 34種類の牌インデックス順（0-8: 萬子1-9, 9-17: 筒子1-9, 18-26: 索子1-9, 27-33: 東南西北白發中）
HONOR_NAMES = ["East", "South", "West", "North", "Haku", "Hatsu", "Chun"]


@dataclass(frozen=True, order=True)
class Tile:
    """1枚の牌を表す。赤ドラは is_red_dora=True で表現する（比較・カウント上は通常の5と同種）。"""

    suit: Suit
    rank: int  # 数牌: 1-9 / 字牌: 1-7 (East,South,West,North,Haku,Hatsu,Chun)
    is_red_dora: bool = field(default=False, compare=False)

    def __post_init__(self) -> None:
        if self.suit == Suit.HONOR:
            if not (1 <= self.rank <= 7):
                raise ValueError(f"字牌のrankは1-7である必要があります: {self.rank}")
        else:
            if not (1 <= self.rank <= 9):
                raise ValueError(f"数牌のrankは1-9である必要があります: {self.rank}")
            if self.is_red_dora and self.rank != 5:
                raise ValueError("赤ドラは5のみ有効です")

    @property
    def index34(self) -> int:
        """34種類の牌を0-33のインデックスに変換する（シャンテン計算等で使用）。"""
        base = {Suit.MAN: 0, Suit.PIN: 9, Suit.SOU: 18, Suit.HONOR: 27}[self.suit]
        return base + (self.rank - 1)

    @classmethod
    def from_index34(cls, index: int) -> "Tile":
        if not (0 <= index <= 33):
            raise ValueError(f"index34は0-33である必要があります: {index}")
        if index < 9:
            return cls(Suit.MAN, index + 1)
        if index < 18:
            return cls(Suit.PIN, index - 9 + 1)
        if index < 27:
            return cls(Suit.SOU, index - 18 + 1)
        return cls(Suit.HONOR, index - 27 + 1)

    @classmethod
    def parse(cls, text: str) -> "Tile":
        """"1m" "5p" "0s"(赤5索) "3z"(西) のような短縮表記をパースする。"""
        text = text.strip()
        if len(text) != 2:
            raise ValueError(f"不正な牌表記です: {text!r}")
        rank_char, suit_char = text[0], text[1]
        if not rank_char.isdigit():
            raise ValueError(f"不正な牌表記です: {text!r}")
        rank = int(rank_char)
        try:
            suit = Suit(suit_char)
        except ValueError as exc:
            raise ValueError(f"不正な牌表記です: {text!r}") from exc

        is_red = False
        if rank == 0:
            if suit == Suit.HONOR:
                raise ValueError(f"字牌に赤ドラ表記(0)は使用できません: {text!r}")
            rank = 5
            is_red = True
        return cls(suit, rank, is_red_dora=is_red)

    def __str__(self) -> str:  # pragma: no cover - 表示用
        rank_char = "0" if self.is_red_dora else str(self.rank)
        return f"{rank_char}{self.suit.value}"


@dataclass
class Meld:
    kind: Literal["chi", "pon", "kan_open", "kan_closed", "kan_added"]
    tiles: list[Tile]  # 面子を構成する牌すべて(チー/ポンは3枚、カンは4枚)
    called_tile: Optional[Tile] = None  # 他家から鳴いた牌(暗槓・加槓の追加牌は対象外でNone)
    called_from_seat: Optional[int] = None  # 暗槓の場合は None


@dataclass
class Action:
    """牌譜イベント。手牌の状態遷移(自摸・打牌・鳴き・リーチ宣言)のみを表す。
    和了・流局は局の結果(RoundResult)として別に表現する。
    """

    seat: int
    kind: Literal["draw", "discard", "chi", "pon", "kan", "riichi"]
    tile: Optional[Tile] = None
    meld: Optional[Meld] = None
    is_tsumogiri: bool = False


@dataclass
class PlayerInfo:
    seat: int
    name: str = ""
    rank: str = ""


@dataclass
class RoundResult:
    kind: Literal["hora", "ryuukyoku"]
    winner_seats: list[int] = field(default_factory=list)
    houjuu_seat: Optional[int] = None  # ロン放銃した打ち手（ツモの場合None）
    is_tsumo: bool = False
    han: int = 0
    fu: int = 0
    points: int = 0
    yaku: list[str] = field(default_factory=list)
    tenpai_seats: list[int] = field(default_factory=list)  # 流局時の形式テンパイ者


@dataclass
class RoundRecord:
    round_name: str  # 例: "East-1-0"
    dora_indicators: list[Tile]
    initial_hands: dict[int, list[Tile]]  # 配牌(席番号 -> 13枚)
    events: list[Action]
    result: Optional[RoundResult] = None


@dataclass
class GameRecord:
    game_uuid: str
    players: list[PlayerInfo]
    rounds: list[RoundRecord]


@dataclass
class DecisionPoint:
    """ある打ち手が打牌を選択する直前の局面を表す。"""

    round_name: str
    turn: int
    seat: int
    hand: list[Tile]  # 打牌選択直前の手牌(自摸後14枚、または副露直後)
    melds: list[Meld]  # 打ち手自身の副露
    all_melds: dict[int, list[Meld]]  # 全員分の副露(受け入れ計算での見えている牌の判定に使用)
    discards_by_seat: dict[int, list[Tile]]
    dora_indicators: list[Tile]
    riichi_seats: set[int]
    remaining_tiles: int
    action_type: Literal["discard"] = "discard"
    actual_action: Optional[Action] = None


@dataclass
class RankedMove:
    action: Action
    shanten_after: int
    ukeire_count: int
    ukeire_tiles: list[Tile]
    est_value: float
    danger_score: float
    total_score: float


@dataclass
class MoveDiff:
    decision: DecisionPoint
    ranked_moves: list[RankedMove]
    best_move: RankedMove
    actual_move: Optional[RankedMove]
    actual_rank: Optional[int]  # 候補内での順位(1始まり)。見つからない場合None
    label: Literal["OPTIMAL", "ACCEPTABLE", "SUBOPTIMAL", "MISTAKE", "UNKNOWN"]
    shanten_delta: int
    ukeire_delta: int
    value_delta: float
