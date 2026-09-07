"""ブラウザ拡張(`browser-extension/`)でキャプチャしたWebSocket生フレームJSONを、
`mjsoul_analyzer.parser.record_parser` が読める RawGameRecord 形式のJSONへ変換する。

雀魂の通信プロトコル(liqi/protobuf)は非公開である。本モジュールは、実際に
キャプチャした通信データをprotobufワイヤーフォーマット(タグ+長さのみ)レベルで
手動解析し、各フィールドの意味を実データの挙動から逆算したものである
(例: あるseatが直前に自摸した牌と同じ牌を打牌した場合にのみ特定のフィールドが
1になる、といった実測による対応付け)。メッセージ名(".lq.RecordDealTile"等)は
メッセージ内に平文の文字列として埋め込まれているため確実だが、和了時の役・翻・符
などIDテーブルが必要な情報は未対応(役IDの列挙定義が非公開のため)。

CLAUDE.mdの「通信プロトコルは、コミュニティで公開されている非改変クライアント
同士の通信仕様の観察・公開情報に基づき実装し、クライアント自体の改造は伴わない」
という方針の範囲内で実装している。雀魂クライアントやサーバーには一切アクセスせず、
既にローカルに保存された(ユーザー自身のブラウザ拡張によるキャプチャ済みの)JSON
ファイルを読むだけであり、本モジュール自体は通信を一切行わない。
"""
from __future__ import annotations

import base64
from typing import Any, Optional

_WIND_NAMES = {0: "East", 1: "South", 2: "West", 3: "North"}


class CaptureDecodeError(ValueError):
    """キャプチャJSONから牌譜データを復元できない場合に送出される。"""


# ---------------------------------------------------------------------------
# 汎用protobufワイヤーフォーマット読み取り(タグ+長さのみ。スキーマは持たない)
# ---------------------------------------------------------------------------


def _read_varint(b: bytes, i: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = b[i]
        result |= (byte & 0x7F) << shift
        i += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, i


def _read_field(b: bytes, i: int) -> tuple[int, int, Any, int]:
    tag, i = _read_varint(b, i)
    field_no = tag >> 3
    wire_type = tag & 7
    if wire_type == 0:
        val, i = _read_varint(b, i)
        return field_no, wire_type, val, i
    if wire_type == 2:
        length, i = _read_varint(b, i)
        val = b[i : i + length]
        i += length
        return field_no, wire_type, val, i
    if wire_type == 5:
        return field_no, wire_type, b[i : i + 4], i + 4
    if wire_type == 1:
        return field_no, wire_type, b[i : i + 8], i + 8
    raise CaptureDecodeError(f"未対応のwire type: {wire_type} (offset={i})")


def _read_all(b: bytes) -> list[tuple[int, int, Any]]:
    i = 0
    out = []
    while i < len(b):
        fno, wt, val, i = _read_field(b, i)
        out.append((fno, wt, val))
    return out


def _group(fields: list[tuple[int, int, Any]]) -> dict[int, list[Any]]:
    d: dict[int, list[Any]] = {}
    for fno, _wt, val in fields:
        d.setdefault(fno, []).append(val)
    return d


def _to_signed64(v: int) -> int:
    if v >= 2**63:
        v -= 2**64
    return v


def _decode_tile(raw: bytes) -> str:
    return raw.decode("ascii")


# ---------------------------------------------------------------------------
# キャプチャJSON -> fetchGameRecordのレスポンス(GameDetailRecords)を取り出す
# ---------------------------------------------------------------------------


def _extract_game_detail_records(capture: dict) -> tuple[bytes, bytes]:
    """キャプチャJSON中の `.lq.Lobby.fetchGameRecord` レスポンスフレームを探し、
    (head_bytes, game_detail_records_payload_bytes) を返す。
    """
    frames = capture.get("frames", [])
    for frame in frames:
        if frame.get("direction") != "recv":
            continue
        try:
            raw = base64.b64decode(frame["data"])
        except Exception:
            continue
        if len(raw) < 3 or raw[0] != 3:  # 3 = RESPONSE
            continue
        body = raw[3:]
        try:
            outer = _read_all(body)
        except Exception:
            continue
        outer_g = _group(outer)
        if 2 not in outer_g:
            continue
        resgame_bytes = outer_g[2][0]
        if not isinstance(resgame_bytes, bytes):
            continue
        try:
            resgame_fields = _group(_read_all(resgame_bytes))
        except Exception:
            continue
        if 3 not in resgame_fields or 4 not in resgame_fields:
            continue
        head_bytes = resgame_fields[3][0]
        data_wrapper_bytes = resgame_fields[4][0]
        try:
            dw = _group(_read_all(data_wrapper_bytes))
        except Exception:
            continue
        name = dw.get(1, [b""])[0]
        if name != b".lq.GameDetailRecords":
            continue
        payload_bytes = dw.get(2, [None])[0]
        if isinstance(payload_bytes, bytes):
            return head_bytes, payload_bytes
    raise CaptureDecodeError(
        "キャプチャ内に .lq.Lobby.fetchGameRecord のレスポンス"
        "(.lq.GameDetailRecords)が見つかりませんでした。"
        "牌譜画面を開いた直後から最後までキャプチャできているか確認してください。"
    )


def _decode_players(head_bytes: bytes) -> list[dict[str, Any]]:
    players = []
    for fno, wt, val in _read_all(head_bytes):
        if fno != 11 or not isinstance(val, bytes):
            continue
        pf = _group(_read_all(val))
        account_id = pf.get(1, [None])[0]
        seat = pf.get(2, [None])[0]
        name_raw = pf.get(3, [b""])[0]
        name = name_raw.decode("utf-8", errors="replace") if isinstance(name_raw, bytes) else ""
        players.append({"seat": seat, "account_id": account_id, "name": name})
    players.sort(key=lambda p: p["seat"])
    return players


def _decode_uuid(head_bytes: bytes) -> str:
    g = _group(_read_all(head_bytes))
    uuid_bytes = g.get(1, [b""])[0]
    return uuid_bytes.decode("utf-8", errors="replace") if isinstance(uuid_bytes, bytes) else ""


def _decode_named_action_entries(payload_bytes: bytes) -> list[dict[str, Any]]:
    """GameDetailRecords中の「名前付き(type=1)」アクションのみを、出現順で返す。

    type=2/3/4のエントリは実測上すべて短い(4バイト程度の)補助情報のみで、
    手牌状態を変化させる実際のアクション(自摸・打牌・鳴き・和了など)は
    必ずtype=1のエントリとして ".lq.RecordXxx" という名前付きで格納されている
    ことを実データで確認済み。
    """
    top = _read_all(payload_bytes)
    out = []
    for fno, wt, val in top:
        if fno != 3 or not isinstance(val, bytes):
            continue
        entry = _group(_read_all(val))
        wrapper = entry.get(3)
        if not wrapper:
            continue
        wdict = _group(_read_all(wrapper[0]))
        name = wdict.get(1, [b""])[0].decode("utf-8", errors="replace")
        data = wdict.get(2, [b""])[0]
        out.append({"name": name, "data": data})
    return out


# ---------------------------------------------------------------------------
# 個別アクションのデコード
# ---------------------------------------------------------------------------


def _decode_new_round(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    chang = g.get(1, [0])[0]
    ju = g.get(2, [0])[0]
    ben = g.get(3, [0])[0]
    hands: dict[int, list[str]] = {}
    for seat, field_no in ((0, 7), (1, 8), (2, 9), (3, 10)):
        if field_no in g:
            hands[seat] = [_decode_tile(t) for t in g[field_no]]
    dora_indicator = g.get(16, [None])[0]
    dora_indicators = [_decode_tile(dora_indicator)] if isinstance(dora_indicator, bytes) else []
    return {
        "chang": chang,
        "ju": ju,
        "ben": ben,
        "hands": hands,
        "dora_indicators": dora_indicators,
    }


def _decode_deal_tile(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    return {"seat": g.get(1, [0])[0], "tile": _decode_tile(g.get(2, [b""])[0])}


def _decode_discard_tile(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    return {
        "seat": g.get(1, [0])[0],
        "tile": _decode_tile(g.get(2, [b""])[0]),
        "is_riichi": bool(g.get(3, [0])[0]),
        "is_tsumogiri": bool(g.get(5, [0])[0]),
    }


def _decode_chi_peng_gang(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    seat = g.get(1, [0])[0]
    call_type = g.get(2, [0])[0]
    tiles = [_decode_tile(t) for t in g.get(3, [])]
    froms = list(g.get(4, [b""])[0]) if 4 in g else []
    called_tile = None
    from_seat = None
    for tile_str, origin_seat in zip(tiles, froms):
        if origin_seat != seat:
            called_tile = tile_str
            from_seat = origin_seat
            break
    if len(tiles) == 4:
        kind = "kan_open"
    elif call_type == 0:
        kind = "chi"
    else:
        kind = "pon"
    return {
        "seat": seat,
        "kind": kind,
        "tiles": tiles,
        "called_tile": called_tile,
        "from_seat": from_seat,
    }


def _decode_an_gang_add_gang(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    seat = g.get(1, [0])[0]
    call_type = g.get(2, [0])[0]
    tiles = [_decode_tile(t) for t in g.get(3, [])]
    # field2(type): 2=加槓(既存のポンに1枚追加), 3=暗槓(手牌のみで完結、代表牌1枚のみ
    # 送られてくるため4枚に複製する)。実データでtype=3(暗槓)を確認済み。
    if call_type == 2:
        kind = "kan_added"
    else:
        kind = "kan_closed"
        if len(tiles) == 1:
            tiles = tiles * 4
    return {"seat": seat, "kind": kind, "tiles": tiles}


def _decode_ba_bei(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    return {"seat": g.get(1, [0])[0]}


def _decode_hule(data: bytes) -> dict[str, Any]:
    g = _group(_read_all(data))
    delta_bytes = g.get(3, [b""])[0]
    deltas = []
    if isinstance(delta_bytes, bytes):
        i = 0
        while i < len(delta_bytes):
            v, i = _read_varint(delta_bytes, i)
            deltas.append(_to_signed64(v))
    winner_seats = [seat for seat, delta in enumerate(deltas) if delta > 0]
    points = sum(delta for delta in deltas if delta > 0)
    return {"winner_seats": winner_seats, "points": points, "deltas": deltas}


# ---------------------------------------------------------------------------
# RawGameRecord組み立て
# ---------------------------------------------------------------------------


def _round_name(chang: int, ju: int, ben: int) -> str:
    wind = _WIND_NAMES.get(chang, str(chang))
    return f"{wind}-{ju + 1}-{ben}"


def capture_to_raw_game_record(capture: dict) -> dict[str, Any]:
    """ブラウザ拡張のキャプチャJSON(1個)から RawGameRecord 形式のdictを組み立てる。

    han・fu・役名は雀魂側の役ID列挙が非公開のため未対応(result.yakuは常に空、
    result.han/result.fuは0)。winner_seats・is_tsumo・houjuu_seat・points
    (和了者の純増点)は実データで検証済みのため対応している。
    """
    head_bytes, payload_bytes = _extract_game_detail_records(capture)
    game_uuid = _decode_uuid(head_bytes)
    players_raw = _decode_players(head_bytes)
    players = [
        {"seat": p["seat"], "name": p["name"], "account_id": p["account_id"]}
        for p in players_raw
    ]

    entries = _decode_named_action_entries(payload_bytes)

    rounds: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    last_draw_seat: Optional[int] = None
    saw_discard_since_last_draw = True

    def finish_round(result: Optional[dict[str, Any]]) -> None:
        if current is not None:
            current["result"] = result
            rounds.append(current)

    for entry in entries:
        name = entry["name"]
        data = entry["data"]

        if name == ".lq.RecordNewRound":
            finish_round({"kind": "ryuukyoku", "tenpai_seats": []})
            nr = _decode_new_round(data)
            current = {
                "round_name": _round_name(nr["chang"], nr["ju"], nr["ben"]),
                "dora_indicators": nr["dora_indicators"],
                "initial_hands": {str(seat): tiles for seat, tiles in nr["hands"].items()},
                "events": [],
            }
            last_draw_seat = None
            saw_discard_since_last_draw = True
            continue

        if current is None:
            continue  # NewRoundより前のイベントは無視する

        if name == ".lq.RecordDealTile":
            dt = _decode_deal_tile(data)
            current["events"].append({"type": "draw", "seat": dt["seat"], "tile": dt["tile"]})
            last_draw_seat = dt["seat"]
            saw_discard_since_last_draw = False

        elif name == ".lq.RecordDiscardTile":
            dst = _decode_discard_tile(data)
            if dst["is_riichi"]:
                current["events"].append({"type": "riichi", "seat": dst["seat"]})
            current["events"].append(
                {
                    "type": "discard",
                    "seat": dst["seat"],
                    "tile": dst["tile"],
                    "tsumogiri": dst["is_tsumogiri"],
                }
            )
            saw_discard_since_last_draw = True

        elif name == ".lq.RecordChiPengGang":
            call = _decode_chi_peng_gang(data)
            event: dict[str, Any] = {
                "type": call["kind"],
                "seat": call["seat"],
                "tiles": call["tiles"],
            }
            if call["called_tile"] is not None:
                event["called_tile"] = call["called_tile"]
                event["from_seat"] = call["from_seat"]
            current["events"].append(event)
            saw_discard_since_last_draw = True

        elif name == ".lq.RecordAnGangAddGang":
            gang = _decode_an_gang_add_gang(data)
            if gang["kind"] == "kan_added":
                current["events"].append(
                    {"type": "kan_added", "seat": gang["seat"], "tile": gang["tiles"][0]}
                )
            else:
                current["events"].append(
                    {"type": "kan_closed", "seat": gang["seat"], "tiles": gang["tiles"]}
                )
            saw_discard_since_last_draw = True

        elif name == ".lq.RecordBaBei":
            bb = _decode_ba_bei(data)
            current["events"].append({"type": "kita", "seat": bb["seat"]})

        elif name == ".lq.RecordHule":
            hule = _decode_hule(data)
            is_tsumo = not saw_discard_since_last_draw and last_draw_seat in hule["winner_seats"]
            houjuu_seat = None
            if not is_tsumo and current["events"]:
                last_event = current["events"][-1]
                if last_event.get("type") == "discard":
                    houjuu_seat = last_event["seat"]
            finish_round(
                {
                    "kind": "hora",
                    "winner_seats": hule["winner_seats"],
                    "houjuu_seat": houjuu_seat,
                    "is_tsumo": is_tsumo,
                    "han": 0,
                    "fu": 0,
                    "points": hule["points"],
                    "yaku": [],
                }
            )
            current = None

    finish_round({"kind": "ryuukyoku", "tenpai_seats": []})

    return {"game_uuid": game_uuid, "players": players, "rounds": rounds}
