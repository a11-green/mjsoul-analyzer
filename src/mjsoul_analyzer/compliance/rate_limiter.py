"""牌譜取得のアクセス頻度を制御するレートリミッタ。

CLAUDE.md「サーバーへの負荷・アクセス頻度に配慮する」を実装レベルで担保するためのモジュール。
`RecordFetcher` の実装は、実際のサーバー通信を行う直前に必ず `acquire()` を呼び出すこと。
"""
from __future__ import annotations

import time
from typing import Callable


class RateLimiter:
    """最小リクエスト間隔と、一定時間窓あたりの最大リクエスト数の両方を強制する。"""

    def __init__(
        self,
        min_interval_seconds: float = 3.0,
        max_requests_per_window: int = 10,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if min_interval_seconds < 0 or max_requests_per_window <= 0 or window_seconds <= 0:
            raise ValueError("レート制限パラメータは正の値である必要があります")
        self._min_interval = min_interval_seconds
        self._max_requests = max_requests_per_window
        self._window = window_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None
        self._request_times: list[float] = []

    def acquire(self) -> None:
        """次のリクエストを送信してよいタイミングまで待機する。"""
        now = self._clock()

        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self._min_interval:
                self._sleep(self._min_interval - elapsed)
                now = self._clock()

        self._request_times = [t for t in self._request_times if now - t < self._window]
        if len(self._request_times) >= self._max_requests:
            oldest = self._request_times[0]
            wait = self._window - (now - oldest)
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
            self._request_times = [t for t in self._request_times if now - t < self._window]

        self._request_times.append(now)
        self._last_request_at = now
