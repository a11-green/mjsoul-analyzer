import pytest

from mjsoul_analyzer.url_parser import (
    InvalidPaipuUrlError,
    PaipuRef,
    parse_paipu_url,
    parse_paipu_value,
)


def test_parse_query_url_with_seat_suffix():
    url = "https://game.mahjongsoul.com/?paipu=230101-90a2bcde-1234-5678-9abc-def012345678_a3"
    ref = parse_paipu_url(url)
    assert ref == PaipuRef(
        game_uuid="230101-90a2bcde-1234-5678-9abc-def012345678",
        focus_seat=3,
    )


def test_parse_query_url_without_seat_suffix():
    url = "https://game.mahjongsoul.com/?paipu=230101-90a2bcde-1234-5678-9abc-def012345678"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "230101-90a2bcde-1234-5678-9abc-def012345678"
    assert ref.focus_seat is None


def test_parse_url_with_extra_query_params():
    url = "https://game.mahjongsoul.com/?lang=ja&paipu=abc-123_a0&foo=bar"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "abc-123"
    assert ref.focus_seat == 0


def test_parse_fragment_based_url():
    url = "https://game.mahjongsoul.com/#/mjhome?paipu=abc-123_a2"
    ref = parse_paipu_url(url)
    assert ref.game_uuid == "abc-123"
    assert ref.focus_seat == 2


def test_parse_raw_value_directly():
    ref = parse_paipu_value("abc-123_a1")
    assert ref.game_uuid == "abc-123"
    assert ref.focus_seat == 1


def test_missing_paipu_param_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_url("https://game.mahjongsoul.com/?lang=ja")


def test_empty_url_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_url("")


def test_invalid_seat_number_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_value("abc-123_a9")


def test_invalid_characters_in_uuid_raises():
    with pytest.raises(InvalidPaipuUrlError):
        parse_paipu_value("abc/123;drop")
