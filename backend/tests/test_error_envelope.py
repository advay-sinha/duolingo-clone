"""Every error response has one shape, and none of them leak internals.

Phase 8's review found three different error shapes reaching the client:
``{"error": {...}}`` from domain errors, ``{"detail": [...]}`` with pydantic
internals from validation failures, and ``{"detail": "Not Found"}`` from an
unmatched route. These tests pin the single envelope in place.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _envelope(response) -> dict:
    body = response.json()
    assert "detail" not in body, f"un-enveloped error body: {body}"
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message"}, body
    assert isinstance(body["error"]["message"], str)
    return body["error"]


def test_a_domain_error_uses_the_envelope(client: TestClient) -> None:
    error = _envelope(client.get("/api/v1/lessons/999999"))
    assert error["code"] == "not_found"


def test_a_validation_error_uses_the_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/lessons/not-a-number")

    assert response.status_code == 422
    error = _envelope(response)
    assert error["code"] == "invalid_request"
    # The field that failed is named, because that is the part a client can act
    # on.
    assert "lesson_id" in error["message"]


def test_a_validation_error_does_not_echo_the_submitted_input(
    client: TestClient,
) -> None:
    """A payload must not be reflected back inside an error body.

    FastAPI's default handler includes the offending `input` verbatim. Echoing
    request content into a response is the kind of thing that is harmless until
    the payload contains something that should not be repeated.
    """
    response = client.post(
        "/api/v1/lessons/1/answer",
        json={"attempt_id": "not-an-int", "exercise_id": 1, "answer": {}},
    )

    assert response.status_code == 422
    assert "not-an-int" not in response.text


def test_an_unmatched_route_uses_the_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert _envelope(response)["code"] == "http_error"


def test_no_error_body_contains_a_traceback(client: TestClient) -> None:
    """Raw exception text must never reach a client."""
    for response in (
        client.get("/api/v1/lessons/999999"),
        client.get("/api/v1/lessons/not-a-number"),
        client.get("/api/v1/does-not-exist"),
        client.post("/api/v1/lessons/1/complete", json={"attempt_id": 999999}),
    ):
        text = response.text
        for marker in ("Traceback", "File \"", "app/services", "sqlalchemy"):
            assert marker not in text, f"{marker!r} leaked in: {text}"
