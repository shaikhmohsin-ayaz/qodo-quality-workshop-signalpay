# Workshop Payment Workflow Plan: Refund

## Summary
Add `POST /payments/{payment_id}/refund` to the SignalPay API, mirroring `capture_payment` in `src/signalpay_api/app.py`. The refund scope (`payments:refund`), the `sp_live_payments_refund` token, the `payment.refunded` event type and the `refunded` status already exist in `contracts.py`. Refund is full-amount only and allowed only from `captured`.

## Skill Routing
- Selected repo-local rules: `PAY-001`, `PAY-002`, `PAY-003`, `PAY-004`, `PAY-005`, `PAY-006`, `PAY-007`, `PAY-009`, `PAY-010` (`PAY-008` is already satisfied: the Qodo key lives in `~/.qodo/config.json`).
- Optional Qodo rules: not loaded. The Qodo CLI is not installed, so there is no `qodo-get-rules` comparison. Repo-local rules are the baseline.
- Planning skill used: `workshop-plan-from-task`
- Implementation entry skill: `workshop-tdd-bdd`
- Conditional implementation skills:
  - `payment-idempotency` (idempotency key, scope before mutation, event contract, retry behavior)
  - `workshop-failure-path-testing` (missing key, missing scope, unknown payment, invalid state)
- Pre-PR review skills: `workshop-guidelines-audit`, optional `workshop-pythonic-review`
- Post-review skill: optional `qodo-review-resolver` after Qodo posts PR findings.
- Exact next prompt after planning:
  ```text
  Use the workshop TDD/BDD skill.

  Use the plan files just created.
  Write the smallest failing tests first for the selected payment workflow path.
  Cover one happy path and at least one failure path.
  Do not implement production code until the failing tests prove the behavior gap.
  ```
- Local verification gates: `make test`, `make lint`, `make typecheck`, `make security`, `make semgrep`, `make verify`

## Selected Repo Rules and Why
- `PAY-001`: refund moves money, so it requires `Idempotency-Key`; missing key returns 400.
- `PAY-002`: auth and `payments:refund` scope are checked before any mutation.
- `PAY-003`: cache key is `("refund", payment_id, key)`, so it cannot collide with capture.
- `PAY-004`: retry returns the original response and emits no second event.
- `PAY-005`: response reuses the `Payment` model with camelCase aliases.
- `PAY-006`: event built with `build_payment_event(event_type="payment.refunded", ...)`.
- `PAY-007`: success and failure-path tests are written first.
- `PAY-009`: no gate is weakened.
- `PAY-010`: `captured -> refunded` is the only allowed transition; others return 409.

## Scope
- One refund endpoint in `app.py` plus tests in `tests/test_payments_api.py`.
- Preserve existing capture behavior.

Out of scope:
- database persistence, partial refunds, frontend, external processor, Docker or deployment

## Behavior Scenarios
1. Given a captured payment and a refund-scoped token, when refund runs with a new key, then 200, status `refunded`, camelCase body, and exactly one `payment.refunded` event.
2. Given the same key is retried, then the identical body is returned and no second event is emitted.
3. Given a missing `Idempotency-Key`, then 400 and no state change.
4. Given a capture-only or read-only token, then 403, status unchanged, no event.
5. Given no token or a wrong-audience token, then 401.
6. Given an unknown payment, then 404.
7. Given a payment that is not `captured`, then 409, no mutation, no event.
8. Given a new key on an already refunded payment, then 409 (no double refund).
9. Given the same key used for capture and refund, then results do not collide.

## Verification Gates
- `make test`, `make lint`, `make typecheck`, `make security`, `make semgrep`, `make verify`
- repo-local rules audit (`workshop-guidelines-audit`)
- Qodo PR review

## Failure and Recovery
- If a new test passes before implementation, the test is wrong; tighten it.
- If a gate fails, fix the code, never the gate.
- If Semgrep flags mutation before auth or idempotency, reorder the handler.
- On Windows, `make` needs Git's `usr\bin` on PATH.

## Commit Plan
1. `test: add failing refund workflow tests`
2. `feat: add idempotent refund endpoint`

## Definition of Done
- Scenarios 1-9 are covered by passing tests.
- `make verify` is green.
- Audit finds no `PAY-*` violations.
- PR is open with verification evidence; Qodo findings fixed or deferred with rationale.
- No secrets in the diff.

## Assumptions
- Refund is full-amount only, from `captured` only, and returns the updated `Payment` with 200.
- `.agents/` and `.claude/` skill folders are not committed unless requested.
