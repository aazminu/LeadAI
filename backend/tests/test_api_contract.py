import pytest


def test_app_registers_required_routes():
    from main import app

    routes = {route.path for route in app.routes}

    assert "/api/leads" in routes
    assert "/api/leads/{lead_id}" in routes
    assert "/api/leads/{lead_id}/stream" in routes
    assert "/api/leads/batch" in routes
    assert "/api/scheduler" in routes
    assert "/api/scheduler/toggle" in routes
    assert "/api/scheduler/run-now" in routes
    assert "/health" in routes


def test_error_payload_shape():
    from api.errors import error_payload

    payload = error_payload(
        code="validation_error",
        message="Request validation failed",
        request_id="req-123",
        details=[{"field": "email"}],
    )

    assert payload == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "request_id": "req-123",
            "details": [{"field": "email"}],
        }
    }


@pytest.mark.asyncio
async def test_scheduler_status_shape():
    from services.pipeline_queue import scheduler_status

    status = scheduler_status()

    assert "enabled" in status
    assert "worker_running" in status
    assert "max_pipeline_attempts" in status
    assert "stalled_after_minutes" in status
