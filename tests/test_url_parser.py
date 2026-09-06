import pytest

from mjsoul_analyzer.models import GameRecord, PlayerInfo
from mjsoul_analyzer.url_parser import (
    InvalidPaipuUrlError,
    PaipuRef,
    parse_paipu_url,
    parse_paipu_value,
    resolve_focus_seat,
)


def test_parse_query_url_with_account_suffix():
    url = "https://game.mahjongsoul.com/?paipu=260906-3de0ca77-72f2-4450-b09a-a9521b37c142_a430980121"
    ref = parse_paipu_url(url)
    assert ref == PaipuRef(
        game_uuid="260906-3de0ca77-72f2-4450-b09a-a9521b37c142",
        viewer_account_id=430980121,
    )


def test_parse_query_url_without_account_suffix():
    url = "https://game.mahjongsoul.com/?paipu=230101-90a2bcde-1234-5678-9abc-def012345678"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "230101-90a2bcde-1234-5678-9abc-def012345678"
    assert ref.viewer_account_id is None


def test_parse_url_with_extra_query_params():
    url = "https://game.mahjongsoul.com/?lang=ja&paipu=abc-123_a555&foo=bar"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "abc-123"
    assert ref.viewer_account_id == 555


def test_parse_fragment_based_url():
    url = "https://game.mahjongsoul.com/#/mjhome?paipu=abc-123_a999"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "abc-123"
    assert ref.viewer_account_id == 999


def test_parse_raw_value_directly():
    ref = parse_paipu_value("abc-123_a12345678")
    assert ref.game_uuid == "abc-123"
    assert ref.viewer_account_id == 12345678


def test_missing_paipu_param_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_url("https://game.mahjongsoul.com/?lang=ja")


def test_empty_url_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_url("")


def test_invalid_characters_in_uuid_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_value("abc/123;drop")


def test_resolve_focus_seat_matches_account_id():
    ref = PaipuRef(game_uuid="abc-123", viewer_account_id=430980121)
    record = GameRecord(
        game_uuid="abc-123",
        players=[
            PlayerInfo(seat=0, name="Alice", account_id=111),
            PlayerInfo(seat=1, name="Bob", account_id=430980121),
            PlayerInfo(seat=2, name="Carol", account_id=222),
            PlayerInfo(seat=3, name="Dave", account_id=333),
        ],
        rounds=[],
    )
    assert resolve_focus_seat(ref, record) == 1


def test_resolve_focus_seat_returns_none_when_no_match():
    ref = PaipuRef(game_uuid="abc-123", viewer_account_id=999999999)
    record = GameRecord(
        game_uuid="abc-123",
        players=[PlayerInfo(seat=0, name="Alice", account_id=111)],
        rounds=[],
    )
    assert resolve_focus_seat(ref, record) is None


def test_resolve_focus_seat_returns_none_when_no_account_id_in_url():
    ref = PaipuRef(game_uuid="abc-123", viewer_account_id=None)
    record = GameRecord(game_uuid="abc-123", players=[], rounds=[])
    assert resolve_focus_seat(ref, record) is None
