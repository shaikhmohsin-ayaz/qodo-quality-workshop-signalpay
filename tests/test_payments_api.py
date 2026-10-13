from fastapi.testclient import TestClient

from signalpay_api.app import app, payment_events, reset_state


def client() -> TestClient:
    reset_state()
    return TestClient(app)


def auth(token: str = "sp_live_payments_capture") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_get_payment_returns_contract_shape() -> None:
    response = client().get("/payments/pay_1001", headers=auth("sp_live_payments_reader"))

    assert response.status_code == 200
    assert response.json() == {
        "paymentId": "pay_1001",
        "customerId": "cus_9001",
        "amount": 12500,
        "currency": "USD",
        "status": "authorized",
    }


def test_capture_requires_an_idempotency_key() -> None:
    response = client().post("/payments/pay_1001/capture", headers=auth())

    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key header is required"


def test_capture_is_idempotent_and_emits_one_event() -> None:
    api = client()
    headers = auth() | {"Idempotency-Key": "cap-pay-1001-001"}

    first = api.post("/payments/pay_1001/capture", headers=headers)
    second = api.post("/payments/pay_1001/capture", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "captured"
    assert len(payment_events) == 1
    assert payment_events[0]["customerId"] == "cus_9001"
    assert payment_events[0]["type"] == "payment.captured"


def test_capture_requires_capture_scope() -> None:
    response = client().post(
        "/payments/pay_1001/capture",
        headers=auth("sp_live_payments_reader") | {"Idempotency-Key": "cap-denied-001"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "payments:capture scope is required"


def test_rejects_sessions_for_other_token_families() -> None:
    response = client().get(
        "/payments/pay_1001",
        headers=auth("sp_live_settlement_reader"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "session token is not valid for audience payments-api"


REFUND = "sp_live_payments_refund"


def captured_api() -> TestClient:
    api = client()
    capture = api.post(
        "/payments/pay_1001/capture",
        headers=auth() | {"Idempotency-Key": "cap-setup-001"},
    )
    assert capture.status_code == 200
    payment_events.clear()
    return api


def test_refund_captured_payment_emits_one_refunded_event() -> None:
    api = captured_api()

    response = api.post(
        "/payments/pay_1001/refund",
        headers=auth(REFUND) | {"Idempotency-Key": "ref-pay-1001-001"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "paymentId": "pay_1001",
        "customerId": "cus_9001",
        "amount": 12500,
        "currency": "USD",
        "status": "refunded",
    }
    assert payment_events == [
        {
            "eventId": "payment.refunded:pay_1001",
            "type": "payment.refunded",
            "paymentId": "pay_1001",
            "customerId": "cus_9001",
            "amount": 12500,
            "currency": "USD",
            "status": "refunded",
        }
    ]


def test_refund_retry_returns_original_response_without_new_event() -> None:
    api = captured_api()
    headers = auth(REFUND) | {"Idempotency-Key": "ref-pay-1001-002"}

    first = api.post("/payments/pay_1001/refund", headers=headers)
    second = api.post("/payments/pay_1001/refund", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(payment_events) == 1


def test_refund_requires_an_idempotency_key() -> None:
    api = captured_api()

    response = api.post("/payments/pay_1001/refund", headers=auth(REFUND))

    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key header is required"
    assert payment_events == []


def test_refund_requires_refund_scope_before_mutation() -> None:
    api = captured_api()

    response = api.post(
        "/payments/pay_1001/refund",
        headers=auth() | {"Idempotency-Key": "ref-denied-001"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "payments:refund scope is required"
    assert payment_events == []
    status = api.get("/payments/pay_1001", headers=auth("sp_live_payments_reader"))
    assert status.json()["status"] == "captured"


def test_refund_rejects_payment_that_was_not_captured() -> None:
    api = client()

    response = api.post(
        "/payments/pay_1001/refund",
        headers=auth(REFUND) | {"Idempotency-Key": "ref-uncaptured-001"},
    )

    assert response.status_code == 409
    assert payment_events == []
    status = api.get("/payments/pay_1001", headers=auth("sp_live_payments_reader"))
    assert status.json()["status"] == "authorized"


def test_refund_rejects_second_refund_with_new_key() -> None:
    api = captured_api()
    api.post(
        "/payments/pay_1001/refund",
        headers=auth(REFUND) | {"Idempotency-Key": "ref-first-001"},
    )

    response = api.post(
        "/payments/pay_1001/refund",
        headers=auth(REFUND) | {"Idempotency-Key": "ref-second-001"},
    )

    assert response.status_code == 409
    assert len(payment_events) == 1


def test_refund_requires_a_valid_token_and_known_payment() -> None:
    api = captured_api()
    key = {"Idempotency-Key": "ref-auth-001"}

    anonymous = api.post("/payments/pay_1001/refund", headers=key)
    wrong_audience = api.post(
        "/payments/pay_1001/refund",
        headers=auth("sp_live_settlement_reader") | key,
    )
    unknown = api.post("/payments/pay_404/refund", headers=auth(REFUND) | key)

    assert anonymous.status_code == 401
    assert wrong_audience.status_code == 401
    assert unknown.status_code == 404
    assert payment_events == []


def test_refund_and_capture_idempotency_keys_do_not_collide() -> None:
    api = client()
    shared = {"Idempotency-Key": "shared-key-001"}

    capture = api.post("/payments/pay_1001/capture", headers=auth() | shared)
    refund = api.post("/payments/pay_1001/refund", headers=auth(REFUND) | shared)

    assert capture.json()["status"] == "captured"
    assert refund.status_code == 200
    assert refund.json()["status"] == "refunded"
    assert [event["type"] for event in payment_events] == [
        "payment.captured",
        "payment.refunded",
    ]
