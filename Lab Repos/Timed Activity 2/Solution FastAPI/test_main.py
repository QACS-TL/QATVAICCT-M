from fastapi.testclient import TestClient

import main
from rate_limiter import RateLimiter


def test_analyze_text_returns_word_count_and_reading_time(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=2))
    client = TestClient(main.app)

    response = client.post("/analyze", json={"text": "One two three"})

    assert response.status_code == 200
    assert response.json() == {
        "word_count": 3,
        "estimated_reading_minutes": 1,
    }


def test_analyze_text_rejects_requests_over_limit(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1))
    client = TestClient(main.app)

    assert client.post("/analyze", json={"text": "First request"}).status_code == 200

    response = client.post("/analyze", json={"text": "Second request"})

    assert response.status_code == 429
    assert response.json() == {"detail": "Request limit exceeded."}


def test_analyze_text_rejects_empty_text(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(max_requests=1))
    client = TestClient(main.app)

    response = client.post("/analyze", json={"text": ""})

    assert response.status_code == 422
