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


@pytest.mark.asyncio
async def test_upload_batch_deduplicates_and_enqueues(monkeypatch):
    import io
    from fastapi import UploadFile
    from api.routes import leads as leads_route

    enqueued = []

    async def fake_enqueue(lead):
        enqueued.append(lead)

    monkeypatch.setattr(leads_route, "enqueue_lead", fake_enqueue)

    class FakeDB:
        def __init__(self):
            self.added = []
            self.committed = False
            self._next_id = 1

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            obj.id = f"lead-{self._next_id}"
            self._next_id += 1

    csv_text = (
        " name , email , company , property_address , city , state , country \n"
        "Alice Smith, alice@example.com , Acme Residential , 100 Main St , Austin , TX , US \n"
        " , , , , , , \n"
        "Incomplete Row, , Acme Residential , 100 Main St , Austin , TX , US \n"
        "Alice Duplicate, ALICE@example.com , acme residential , 100 main st , Austin , TX , US \n"
        "Bob Jones, bob@example.com , Beta Living , 200 Oak Ave , Dallas , TX , \n"
    )
    upload = UploadFile(filename="leads.csv", file=io.BytesIO(csv_text.encode("utf-8")))
    db = FakeDB()

    res = await leads_route.upload_batch(file=upload, db=db)

    assert res["accepted"] is True
    assert res["count"] == 2
    assert res["skipped_duplicates"] == 1
    assert res["skipped_invalid"] == 1
    assert res["lead_ids"] == ["lead-1", "lead-2"]
    assert len(enqueued) == 2
    assert enqueued[0].email == "alice@example.com"
    assert enqueued[0].company == "Acme Residential"
    assert enqueued[1].country == "US"


@pytest.mark.asyncio
async def test_upload_batch_rejects_missing_columns():
    import io
    from fastapi import HTTPException, UploadFile
    from api.routes.leads import upload_batch

    csv_text = "name,email,company\nAlice,alice@example.com,Acme\n"
    upload = UploadFile(filename="bad.csv", file=io.BytesIO(csv_text.encode("utf-8")))

    with pytest.raises(HTTPException) as exc_info:
        await upload_batch(file=upload, db=None)

    assert exc_info.value.status_code == 400
    assert "CSV missing required columns" in exc_info.value.detail


@pytest.mark.asyncio
async def test_recover_stalled_leads_requeues_and_fails(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from db.models import Lead, LeadStatus
    from services import pipeline_queue

    old_ts = datetime.now(timezone.utc) - timedelta(minutes=60)
    lead_retry = Lead(
        id="lead-retry",
        name="Retry Lead",
        email="r@example.com",
        company="Retry Co",
        property_address="1 St",
        city="Boston",
        state="MA",
        status=LeadStatus.processing,
        attempt_count=1,
        updated_at=old_ts,
    )
    lead_fail = Lead(
        id="lead-fail",
        name="Fail Lead",
        email="f@example.com",
        company="Fail Co",
        property_address="2 St",
        city="Boston",
        state="MA",
        status=LeadStatus.processing,
        attempt_count=pipeline_queue.MAX_PIPELINE_ATTEMPTS,
        updated_at=old_ts,
    )

    class FakeScalars:
        def all(self):
            return [lead_retry, lead_fail]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeSession:
        def __init__(self):
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            return FakeResult()

        async def commit(self):
            self.committed = True

    emitted = []

    async def fake_emit(lead_id, event_type, **kwargs):
        emitted.append((lead_id, event_type, kwargs))

    monkeypatch.setattr(pipeline_queue, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(pipeline_queue.event_bus, "emit", fake_emit)

    recovered = await pipeline_queue.recover_stalled_leads()
    assert recovered == 2
    assert lead_retry.status == LeadStatus.queued
    assert lead_retry.updated_at > old_ts
    assert lead_fail.status == LeadStatus.failed
    assert lead_fail.updated_at > old_ts
    assert [e[1] for e in emitted] == ["pipeline_requeued", "pipeline_failed"]

from backend.api.routes.leads import compute_batch_ingestion_summary


def test_compute_batch_ingestion_summary():
    summary = compute_batch_ingestion_summary(total_rows=10, accepted=7, skipped_empty=2, duplicates=1)
    assert summary["acceptance_ratio"] == 0.7
    assert summary["invariants_ok"] is True
