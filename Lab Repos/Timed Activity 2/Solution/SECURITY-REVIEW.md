# API Security Review

Review scope: `rate_limiter.py` considered as a component used by a web app.

## Findings

| # | Severity | Lines | Finding | Confidence |
|---|---|---:|---|---:|
| 1 | MEDIUM | 9–14 | The check and counter update are not atomic. Concurrent calls for the same key can both pass the threshold check and exceed the configured limit when the limiter is shared across concurrent handlers. | 8/10 |
| 2 | MEDIUM | 9–14 | Counts never expire or reset. Once a key reaches `max_requests`, all later requests using that key are denied for the lifetime of the stored state, which can permanently lock out a user instead of enforcing a time-based limit. | 8/10 |
| 3 | MEDIUM | 6, 9, 14 | State is held in an in-memory dictionary on this object. If a deployment uses multiple limiter instances, each instance has an independent quota; distributing requests can exceed the intended limit. Restarting an instance also clears its counts. | 8/10 |
| 4 | MEDIUM | 8–14 | The quota key is taken directly from `user_id`. If a web handler supplies a client-controlled value instead of a trusted authenticated identity, a caller may vary the value to obtain separate counters and bypass the intended per-user limit. | 8/10 |

## Scope and assumptions

Findings 3 and 4 depend on how the web application instantiates the limiter and derives `user_id`; those integration details are not present in the reviewed file. This review does not establish that the application uses multiple instances or accepts a client-controlled key.
