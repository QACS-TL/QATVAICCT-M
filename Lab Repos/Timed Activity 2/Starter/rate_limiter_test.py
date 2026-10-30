from rate_limiter import RateLimiter

def test_limit_not_reached():
    limiter = RateLimiter(2)
    
    assert limiter.allow_request("A")
    assert limiter.allow_request("A")
 
 
def test_limit_reached():
    limiter = RateLimiter(2)
    
    limiter.allow_request("A")
    limiter.allow_request("A")
    
    assert (limiter.allow_request("A") is False)
