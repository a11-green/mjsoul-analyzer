import json
from pathlib import Path

import pytest

from mjsoul_analyzer.compliance.credential_store import (
    Credentials,
    CredentialError,
    load_credentials_from_env,
    load_credentials_from_file,
)
from mjsoul_analyzer.compliance.rate_limiter import RateLimiter
from mjsoul_analyzer.fetcher.record_fetcher import (
    LiveMahjongSoulRecordFetcher,
    LocalFileRecordFetcher,
    RecordFetchError,
)
from mjsoul_analyzer.url_parser import PaipuRef


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_rate_limiter_enforces_min_interval_via_sleep():
    clock = FakeClock()
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock.advance(seconds)

    limiter = RateLimiter(
        min_interval_seconds=3.0,
        max_requests_per_window=100,
        window_seconds=60.0,
        clock=clock,
        sleep=fake_sleep,
    )
    limiter.acquire()
    assert sleep_calls == []  # 初回は待たない

    clock.advance(1.0)
    limiter.acquire()
    assert sleep_calls == [2.0]  # 3秒間隔を保つため2秒待つ


def test_rate_limiter_enforces_window_limit():
    clock = FakeClock()
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock.advance(seconds)

    limiter = RateLimiter(
        min_interval_seconds=0.0,
        max_requests_per_window=2,
        window_seconds=10.0,
        clock=clock,
        sleep=fake_sleep,
    )
    limiter.acquire()
    clock.advance(1.0)
    limiter.acquire()
    clock.advance(1.0)
    limiter.acquire()  # 3件目、直近10秒以内に既に2件あるため待たされる
    assert sleep_calls  # 何かしら待機が発生している
    assert sum(sleep_calls) >= 7.9  # 10秒窓を満たすまで待つはず(誤差許容)


def test_credentials_repr_and_str_do_not_leak_secrets():
    creds = Credentials(username="alice", password="super-secret")
    assert "super-secret" not in repr(creds)
    assert "super-secret" not in str(creds)


def test_load_credentials_from_env(monkeypatch):
    monkeypatch.setenv("MJSOUL_USERNAME", "alice")
    monkeypatch.setenv("MJSOUL_PASSWORD", "pw")
    creds = load_credentials_from_env()
    assert creds.username == "alice"
    assert creds.password == "pw"


def test_load_credentials_from_env_missing_raises(monkeypatch):
    monkeypatch.delenv("MJSOUL_USERNAME", raising=False)
    monkeypatch.delenv("MJSOUL_PASSWORD", raising=False)
    with pytest.raises(CredentialError):
        load_credentials_from_env()


def test_load_credentials_from_file(tmp_path: Path):
    cred_file = tmp_path / "creds.json"
    cred_file.write_text(json.dumps({"username": "bob", "password": "pw2"}), encoding="utf-8")
    creds = load_credentials_from_file(cred_file)
    assert creds.username == "bob"


def test_load_credentials_from_file_missing_raises(tmp_path: Path):
    with pytest.raises(CredentialError):
        load_credentials_from_file(tmp_path / "not_found.json")


def test_local_file_record_fetcher_reads_json(tmp_path: Path):
    record_path = tmp_path / "abc-123.json"
    record_path.write_text(json.dumps({"game_uuid": "abc-123", "players": [], "rounds": []}), encoding="utf-8")
    fetcher = LocalFileRecordFetcher(tmp_path)
    raw = fetcher.fetch(PaipuRef(game_uuid="abc-123", viewer_account_id=None))
    assert raw["game_uuid"] == "abc-123"


def test_local_file_record_fetcher_missing_file_raises(tmp_path: Path):
    fetcher = LocalFileRecordFetcher(tmp_path)
    with pytest.raises(RecordFetchError):
        fetcher.fetch(PaipuRef(game_uuid="missing", viewer_account_id=None))


def test_live_fetcher_is_not_implemented():
    creds = Credentials(username="alice", password="pw")
    fetcher = LiveMahjongSoulRecordFetcher(creds)
    with pytest.raises(NotImplementedError):
        fetcher.fetch(PaipuRef(game_uuid="abc-123", viewer_account_id=None))
