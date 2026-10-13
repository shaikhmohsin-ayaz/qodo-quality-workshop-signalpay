# Workshop Payment Workflow Build-Session Plan: Refund

## Summary
One short build session to add the refund endpoint under the repo quality gates.

## Implementation Skill Handoff
- Planning skill completed: `workshop-plan-from-task`
- First implementation skill to run: `workshop-tdd-bdd`
- Required implementation prompt:
  ```text
  Use the workshop TDD/BDD skill.

  Use the plan files just created.
  Write the smallest failing tests first for the selected payment workflow path.
  Cover one happy path and at least one failure path.
  Do not implement production code until the failing tests prove the behavior gap.
  ```
- Conditional skills kept active:
  - `payment-idempotency` for key, scope-before-mutation, event shape, retry behavior.
  - `workshop-failure-path-testing` for missing-key, missing-scope, unknown-payment, invalid-state, duplicate-event gates.
- Review/remediation skills:
  - `workshop-guidelines-audit` before committing or opening the PR.
  - optional `workshop-pythonic-review` for changed Python.
  - optional `qodo-review-resolver` after Qodo posts findings.

## Execution Steps
1. `make doctor` and `make verify` on the clean starter (baseline: 13 tests pass).
2. Re-read `AGENTS.md` and `rules/README.md`; selected rules are in `plan.md`.
3. Optional Qodo rules comparison: skipped (Qodo CLI not installed).
4. Run the `workshop-tdd-bdd` prompt above.
5. Add failing tests for scenarios 1-9 to `tests/test_payments_api.py`; confirm they fail because the endpoint is missing (404/405), not because of an import error.
6. Implement the minimal handler in `src/signalpay_api/app.py`, in this order: `require_principal(required_scope="payments:refund")`, key check, 404, idempotency lookup, status check (409), mutate, `build_payment_event`, cache a deepcopy.
7. Run the targeted tests, then `make verify`.
8. Run `workshop-guidelines-audit`.
9. Commit with Conventional Commits and the Copilot co-author trailer.
10. Push, open a PR, inspect Qodo findings, fix them, re-run `make verify`.

## Test Plan
- Success: one `payment.refunded` event, camelCase body, status `refunded`.
- Retry: same key returns the same body, no new event.
- Failure: missing key (400), wrong scope (403), no token (401), unknown payment (404), non-captured (409), double refund with a new key (409).
- Capture tests keep passing; capture and refund results do not collide.

## Risk Checks
- No state mutation before auth, key and state checks.
- No duplicate event for a retried key.
- No changed event field names.
- No committed secrets.

## Completion Notes
- Local verification:
- Repo rules applied:
- Qodo review:
- Remediation:
