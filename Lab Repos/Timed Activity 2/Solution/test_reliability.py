import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

import main
from rate_limiter import RateLimiter

MAX_REQUESTS = 100
WINDOW_SECONDS = 10
MAX_TEXT_BYTES = 100_000


def _consume_shared_quota(shared_requests, results):
    import main as worker_main

    limiter = RateLimiter(max_requests=1)
    limiter.requests = shared_requests
    worker_main.rate_limiter = limiter
    response = TestClient(worker_main.app).post(
        "/analyze",
        json={"text": "request"},
    )
    results.put(response.status_code)


class ConcurrentReadDict(dict):
    def __init__(self):
        super().__init__()
        self.read_barrier = Barrier(2)

    def get(self, key, default=None):
        value = super().get(key, default)
        try:
            self.read_barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass
        return value


def test_rate_limit_is_enforced_atomically_under_concurrency():
    limiter = RateLimiter(max_requests=1)
    limiter.requests = ConcurrentReadDict()
    start = Barrier(2)

    def attempt():
        start.wait()
        return limiter.allow_request("198.51.100.10")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))

    assert sum(results) == 1


def test_separate_processes_consume_the_same_shared_quota():
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager:
        shared_requests = manager.dict()
        results = manager.Queue()
        processes = [
            context.Process(
                target=_consume_shared_quota,
                args=(shared_requests, results),
            )
            for _ in range(2)
        ]

        for process in processes:
            process.start()
            process.join(timeout=5)
            assert process.exitcode == 0

        assert sorted([results.get(timeout=1), results.get(timeout=1)]) == [200, 429]


def test_rate_limit_rejects_requests_until_the_window_expires():
    limiter = RateLimiter(
        max_requests=MAX_REQUESTS,
        window_seconds=WINDOW_SECONDS,
    )

    for _ in range(MAX_REQUESTS):
        assert limiter.allow_request("198.51.100.10")

    assert not limiter.allow_request("198.51.100.10")
    time.sleep(WINDOW_SECONDS + 0.05)

    assert limiter.allow_request("198.51.100.10")


def test_api_allows_100_requests_per_client_then_throttles(monkeypatch):
    limiter = RateLimiter(max_requests=MAX_REQUESTS)
    monkeypatch.setattr(main, "rate_limiter", limiter)
    client = TestClient(main.app)

    responses = [
        client.post("/analyze", json={"text": "request"})
        for _ in range(MAX_REQUESTS + 1)
    ]

    assert all(response.status_code == 200 for response in responses[:MAX_REQUESTS])
    assert responses[MAX_REQUESTS].status_code == 429


def test_expired_client_entries_are_removed_from_limiter_state():
    limiter = RateLimiter(
        max_requests=MAX_REQUESTS,
        window_seconds=WINDOW_SECONDS,
    )

    for index in range(256):
        assert limiter.allow_request(f"198.51.100.{index}")

    time.sleep(WINDOW_SECONDS + 0.05)
    assert limiter.allow_request("203.0.113.1")

    assert len(limiter.requests) <= 1


def test_api_accepts_text_at_the_limit_and_rejects_text_over_it(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1000))
    client = TestClient(main.app)

    accepted = client.post(
        "/analyze",
        json={"text": "a" * MAX_TEXT_BYTES},
    )
    rejected = client.post(
        "/analyze",
        json={"text": "a" * (MAX_TEXT_BYTES + 1)},
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 413


def test_api_rejects_oversized_raw_request_body():
    client = TestClient(main.app)
    body = b'{"text":"' + b"a" * (MAX_TEXT_BYTES * 6 + 1024) + b'"}'

    response = client.post(
        "/analyze",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


@pytest.mark.parametrize("text", [" ", "\t", "\n", " \t\n "])
def test_api_rejects_whitespace_only_text(monkeypatch, text):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1000))
    client = TestClient(main.app)

    response = client.post("/analyze", json={"text": text})

    assert response.status_code == 422


def test_rate_limit_response_includes_retry_after(monkeypatch):
    monkeypatch.setattr(
        main,
        "rate_limiter",
        RateLimiter(
            max_requests=MAX_REQUESTS,
            window_seconds=WINDOW_SECONDS,
        ),
    )
    client = TestClient(main.app)

    for _ in range(MAX_REQUESTS):
        assert client.post("/analyze", json={"text": "request"}).status_code == 200

    response = client.post("/analyze", json={"text": "over the limit"})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_rate_limit_uses_asgi_client_not_forwarded_headers(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1))
    first_client = TestClient(
        main.app,
        client=("198.51.100.10", 1234),
    )
    second_client = TestClient(
        main.app,
        client=("198.51.100.20", 1234),
    )

    first = first_client.post(
        "/analyze",
        json={"text": "first"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    second = second_client.post(
        "/analyze",
        json={"text": "second"},
    )
    repeated_first = first_client.post(
        "/analyze",
        json={"text": "third"},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert repeated_first.status_code == 429


def test_rate_limit_returns_a_client_error_when_client_is_missing(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1))
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/analyze",
            "raw_path": b"/analyze",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
        }
    )

    with pytest.raises(HTTPException) as error:
        main.enforce_rate_limit(request)

    assert error.value.status_code == 400
