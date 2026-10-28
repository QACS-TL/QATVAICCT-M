# Production Deployment Evidence

## Current Evidence

- `pytest -vv --cov=order_processor --cov-report=term-missing order_processor_tests.py`: 25 tests passed; `order_processor.py` reported 100% statement coverage.
- This is unit-test evidence only. Repository and payment services are mocked; it does not establish authorization, trusted pricing, or real-provider behavior.

## Required Before Approval

The following evidence is not present in this workspace. Attach results from the application and deployment environment before approving production release.

| Gate | Evidence to attach | Acceptance criteria |
| --- | --- | --- |
| Customer authorization | API/integration tests and relevant authorization design | User A cannot process user B's order or substitute `customer_id`; rejected requests cause no repository access to another tenant and no charge. |
| Trusted pricing | Integration tests plus the server-side pricing source | Client-supplied price, tax, and discount changes cannot reduce or alter the payable amount. The processor receives server-derived order values. |
| Currency and amount rules | Supported-currency policy, provider requirements, boundary tests | Unsupported currencies and invalid precision/amounts are rejected or normalized according to documented rules; provider receives the expected amount for each supported currency. |
| Provider idempotency | Sandbox test report and provider idempotency documentation | Concurrent requests and retry-after-timeout produce at most one charge; changed payloads and cross-tenant key collisions are handled safely; key scope and retention cover the retry window. |
| Failure recovery | Fault-injection/integration test report and reconciliation runbook | Repository and payment timeouts, provider errors, and ambiguous outcomes do not mark unpaid orders as paid; retries are bounded and ambiguous charges can be reconciled without duplicate charging. |
| Input and resource limits | API validation tests and load/abuse test results | Maximum order size, line count, quantity, and amount are enforced; malformed or oversized requests fail within resource limits and never trigger a charge. |
| Production controls | Deployment configuration review and operational sign-off | Payment credentials are held in the approved secret store; access is least-privilege; transport is protected; logs exclude sensitive payment/customer data; alerts and rollback/reconciliation procedures are verified. |

## Evidence Record

For each gate, record the build/commit, test environment, execution date, report or artifact location, result, and reviewer. Any failed or unavailable gate remains a release blocker until resolved or explicitly accepted by the designated risk owner.