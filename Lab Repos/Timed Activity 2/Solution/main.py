from math import ceil

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from rate_limiter import RateLimiter

MAX_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 10
MAX_TEXT_BYTES = 100_000
MAX_REQUEST_BODY_BYTES = MAX_TEXT_BYTES * 6 + 1024
WORDS_PER_MINUTE = 200

rate_limiter = RateLimiter(
    max_requests=MAX_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)

app = FastAPI(
    title="Text Utility API",
    description="Analyze text and estimate its reading time.",
)


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body_messages: list[Message] = []
        body_size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                body_messages.append(message)
                break

            body_size += len(message.get("body", b""))
            if body_size > self.max_body_bytes:
                body = b'{"detail":"Request body is too large."}'
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return

            body_messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay_body() -> Message:
            if body_messages:
                return body_messages.pop(0)
            return await receive()

        await self.app(scope, replay_body, send)


app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=MAX_REQUEST_BODY_BYTES,
)


class TextRequest(BaseModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def reject_whitespace_only_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must contain at least one non-whitespace character.")
        return value


class TextAnalysis(BaseModel):
    word_count: int
    estimated_reading_minutes: int


def enforce_rate_limit(request: Request) -> None:
    if request.client is None:
        raise HTTPException(status_code=400, detail="Unable to identify request client.")

    client_host = request.client.host
    if not rate_limiter.allow_request(client_host):
        retry_after = rate_limiter.retry_after(client_host)
        raise HTTPException(
            status_code=429,
            detail="Request limit exceeded.",
            headers={"Retry-After": str(retry_after)},
        )


def enforce_text_size(payload: TextRequest) -> None:
    if len(payload.text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Text must not exceed {MAX_TEXT_BYTES} UTF-8 bytes.",
        )


@app.post(
    "/analyze",
    response_model=TextAnalysis,
    dependencies=[Depends(enforce_rate_limit), Depends(enforce_text_size)],
)
def analyze_text(payload: TextRequest) -> TextAnalysis:
    word_count = len(payload.text.split())
    reading_minutes = max(1, ceil(word_count / WORDS_PER_MINUTE))
    return TextAnalysis(
        word_count=word_count,
        estimated_reading_minutes=reading_minutes,
    )
