from math import ceil

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from rate_limiter import RateLimiter

MAX_REQUESTS = 2
WORDS_PER_MINUTE = 200

rate_limiter = RateLimiter(max_requests=MAX_REQUESTS)

app = FastAPI(
    title="Text Utility API",
    description="Analyze text and estimate its reading time.",
)


class TextRequest(BaseModel):
    text: str = Field(min_length=1)


class TextAnalysis(BaseModel):
    word_count: int
    estimated_reading_minutes: int


def enforce_rate_limit(request: Request) -> None:
    if request.client is None:
        raise HTTPException(status_code=400, detail="Unable to identify request client.")

    if not rate_limiter.allow_request(request.client.host):
        raise HTTPException(status_code=429, detail="Request limit exceeded.")


@app.post(
    "/analyze",
    response_model=TextAnalysis,
    dependencies=[Depends(enforce_rate_limit)],
)
def analyze_text(payload: TextRequest) -> TextAnalysis:
    word_count = len(payload.text.split())
    reading_minutes = max(1, ceil(word_count / WORDS_PER_MINUTE))
    return TextAnalysis(
        word_count=word_count,
        estimated_reading_minutes=reading_minutes,
    )
