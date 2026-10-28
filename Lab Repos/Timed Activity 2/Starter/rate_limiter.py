from datetime import datetime
 
class RateLimiter:
    def __init__(self, max_requests=100):
        self.max_requests = max_requests
        self.requests = {}
    
    def allow_request(self, user_id):
        count = self.requests.get(user_id, 0)
      
        if count >= self.max_requests:
            return False
        
        self.requests[user_id] = count + 1
        return True
