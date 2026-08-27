"""Tests for the Multi-tier User Memory module (src/memory/).

Covers, per workstream/tier of the plan confirmed in implementation-notes.md:
  Workstream A — identity binding/resolution
  Workstream B — step tracking, resumability, timeout sweep
  Tầng 2        — deterministic session compression
  Tầng 3         — incremental consolidation + context injection
  Workstream C  — transparency & control API (auth, view, edit, delete)
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.memory.context_provider import MemoryContextProvider
from src.memory.identity import SessionIdentityRegistry
from src.memory.routes import memory_router
from src.memory.schemas import SessionStep
from src.memory.session_summarizer import SessionSummarizer
from src.memory.state_tracker import SessionStateTracker
from src.memory.store import MemoryStore
from src.memory.user_memory import UserMemoryConsolidator


def _fresh_stack():
    """Purpose: give every test its own MemoryStore-backed object graph, but
    on the shared test DuckDB file (`tests/conftest.py` already redirects
    DUCKDB_PATH), and with globally-unique user/session ids so parallel table
    rows never collide across tests.
    """
    store = MemoryStore()
    identity = SessionIdentityRegistry(store)
    summarizer = SessionSummarizer()
    tracker = SessionStateTracker(store, identity, summarizer)
    consolidator = UserMemoryConsolidator(store)
    provider = MemoryContextProvider(store, consolidator)
    return store, identity, tracker, consolidator, provider


def _uid() -> str:
    return f"usr_test_{uuid.uuid4().hex[:10]}"


def _sid() -> str:
    return f"sess_test_{uuid.uuid4().hex[:10]}"


class TestIdentity:
    def test_bind_and_resolve(self):
        _, identity, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        identity.bind(sid, uid, role="Analyst")
        assert identity.resolve(sid) == (uid, "Analyst")

    def test_resolve_unknown_session_returns_none(self):
        _, identity, *_ = _fresh_stack()
        assert identity.resolve("sess_never_bound_xyz") is None

    def test_bind_requires_user_id(self):
        _, identity, *_ = _fresh_stack()
        with pytest.raises(ValueError):
            identity.bind(_sid(), "")


class TestStateTracker:
    def test_start_session_is_idempotent(self):
        _, _, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        first = tracker.start_session(sid, uid)
        tracker.record_step(sid, SessionStep.PROFILE)
        second = tracker.start_session(sid, uid)
        assert second.session_id == first.session_id
        assert second.current_step == SessionStep.PROFILE

    def test_record_step_without_start_resolves_owner_from_identity(self):
        store, identity, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        identity.bind(sid, uid)
        state = tracker.record_step(sid, SessionStep.PROFILE)
        assert state.user_id == uid
        assert state.current_step == SessionStep.PROFILE

    def test_record_step_unknown_session_raises(self):
        _, _, tracker, *_ = _fresh_stack()
        with pytest.raises(LookupError):
            tracker.record_step(_sid(), SessionStep.PROFILE)

    def test_close_session_produces_summary_and_marks_state_closed(self):
        _, _, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid, dataset_key="vinfast_ev_telemetry_dirty")
        tracker.record_step(sid, SessionStep.PROFILE)
        tracker.record_step(sid, SessionStep.PROPOSE_RULE, {"rule_count": 2})
        summary = tracker.close_session(sid)

        assert summary is not None
        assert summary.session_id == sid
        assert summary.rules_proposed == 2
        assert summary.dataset_keys == ["vinfast_ev_telemetry_dirty"]

        state = tracker.get_state(sid)
        assert state.status.value == "closed"
        assert state.ended_at is not None

    def test_close_session_unknown_session_returns_none(self):
        _, _, tracker, *_ = _fresh_stack()
        assert tracker.close_session(_sid()) is None

    def test_sweep_idle_sessions_closes_only_stale_active_sessions(self):
        store, _, tracker, *_ = _fresh_stack()
        uid, sid_fresh, sid_stale = _uid(), _sid(), _sid()
        tracker.start_session(sid_fresh, uid)
        tracker.start_session(sid_stale, uid)

        stale_state = store.get_state(sid_stale)
        stale_state.updated_at = "2000-01-01T00:00:00+00:00"
        store.upsert_state(stale_state)

        swept = tracker.sweep_idle_sessions(idle_minutes=30)
        swept_ids = {s.session_id for s in swept}

        assert sid_stale in swept_ids
        assert sid_fresh not in swept_ids
        assert store.get_state(sid_stale).status.value == "timed_out"
        assert store.get_state(sid_fresh).status.value == "active"


class TestSessionSummarizer:
    def test_outcome_labels_are_deterministic(self):
        _, _, tracker, *_ = _fresh_stack()

        uid_a, sid_a = _uid(), _sid()
        tracker.start_session(sid_a, uid_a)
        tracker.record_step(sid_a, SessionStep.PROPOSE_RULE)
        tracker.record_step(sid_a, SessionStep.RULE_REJECTED)
        assert tracker.close_session(sid_a).outcome == "rejected"

        uid_b, sid_b = _uid(), _sid()
        tracker.start_session(sid_b, uid_b)
        tracker.record_step(sid_b, SessionStep.DETECT)
        assert tracker.close_session(sid_b).outcome == "investigated_only"

        uid_c, sid_c = _uid(), _sid()
        tracker.start_session(sid_c, uid_c)
        assert tracker.close_session(sid_c).outcome == "incomplete"


class TestUserMemoryConsolidation:
    def test_consolidate_merges_incrementally_across_sessions(self):
        _, _, tracker, consolidator, _ = _fresh_stack()
        uid = _uid()

        sid1 = _sid()
        tracker.start_session(sid1, uid, dataset_key="vinfast_ev_telemetry_dirty")
        tracker.record_step(sid1, SessionStep.RULE_APPROVED)
        tracker.close_session(sid1)

        profile1 = consolidator.consolidate(uid)
        assert profile1.sessions_observed == 1
        assert profile1.rule_decision_pattern["approved"] == 1

        sid2 = _sid()
        tracker.start_session(sid2, uid, dataset_key="vinfast_ev_telemetry_dirty")
        tracker.record_step(sid2, SessionStep.RULE_REJECTED)
        tracker.close_session(sid2)

        profile2 = consolidator.consolidate(uid)
        assert profile2.sessions_observed == 2
        assert profile2.rule_decision_pattern == {"approved": 1, "rejected": 1, "edited": 0}
        assert profile2.approval_rate == 0.5
        assert profile2.top_datasets[0]["dataset_key"] == "vinfast_ev_telemetry_dirty"
        assert profile2.top_datasets[0]["count"] == 2

    def test_consolidate_with_no_new_summaries_is_a_no_op(self):
        _, _, tracker, consolidator, _ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid)
        tracker.close_session(sid)

        first = consolidator.consolidate(uid)
        second = consolidator.consolidate(uid)
        assert second.updated_at == first.updated_at

    def test_consolidate_new_user_returns_empty_baseline(self):
        _, _, _, consolidator, _ = _fresh_stack()
        profile = consolidator.consolidate(_uid())
        assert profile.sessions_observed == 0


class TestMemoryContextProvider:
    def test_new_user_yields_empty_context(self):
        _, _, _, _, provider = _fresh_stack()
        assert provider.build_user_memory_context(_uid()) == ""

    def test_context_includes_narrative_after_a_closed_session(self):
        _, _, tracker, _, provider = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid, dataset_key="xanh_sm_trips_dirty")
        tracker.record_step(sid, SessionStep.RULE_APPROVED)
        tracker.close_session(sid)

        ctx = provider.build_user_memory_context(uid)
        assert "USER MEMORY CONTEXT" in ctx
        assert "SECURITY NOTICE" in ctx
        assert "xanh_sm_trips_dirty" in ctx

    def test_context_never_leaks_raw_row_shaped_keys(self):
        """No raw_rows/samples/records key can appear — the model is typed and
        aggregation-only by construction, so this guards the contract itself."""
        _, _, tracker, _, provider = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid, dataset_key="d")
        tracker.close_session(sid)
        ctx = provider.build_user_memory_context(uid)
        for forbidden in ("raw_rows", "sample_rows", "raw_data"):
            assert forbidden not in ctx


@pytest.fixture()
def memory_client():
    app = FastAPI()
    app.include_router(memory_router, prefix="/api/v1")

    @app.middleware("http")
    async def _inject_test_identity(request, call_next):
        request.state.user_id = request.headers.get("X-Test-User-Id", "usr_anonymous")
        request.state.user_role = request.headers.get("X-Test-User-Role", "Analyst")
        return await call_next(request)

    return TestClient(app)


class TestWorkstreamCRoutes:
    def test_view_own_profile_after_a_closed_session(self, memory_client):
        _, _, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid, dataset_key="vgreen_charging_stations_dirty")
        tracker.record_step(sid, SessionStep.RULE_APPROVED)
        tracker.close_session(sid)

        resp = memory_client.get(
            f"/api/v1/memory/{uid}/profile", headers={"X-Test-User-Id": uid}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sessions_observed"] == 1

    def test_cannot_view_someone_elses_memory(self, memory_client):
        target_uid = _uid()
        resp = memory_client.get(
            f"/api/v1/memory/{target_uid}/profile",
            headers={"X-Test-User-Id": _uid(), "X-Test-User-Role": "Analyst"},
        )
        assert resp.status_code == 403

    def test_admin_can_view_any_users_memory(self, memory_client):
        target_uid = _uid()
        resp = memory_client.get(
            f"/api/v1/memory/{target_uid}/profile",
            headers={"X-Test-User-Id": _uid(), "X-Test-User-Role": "Admin"},
        )
        assert resp.status_code == 200

    def test_edit_own_narrative(self, memory_client):
        _, _, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid)
        tracker.record_step(sid, SessionStep.RULE_APPROVED)
        tracker.close_session(sid)
        memory_client.get(f"/api/v1/memory/{uid}/profile", headers={"X-Test-User-Id": uid})

        resp = memory_client.patch(
            f"/api/v1/memory/{uid}/profile",
            json={"narrative": "Corrected by user"},
            headers={"X-Test-User-Id": uid},
        )
        assert resp.status_code == 200
        assert resp.json()["narrative"] == "Corrected by user"

    def test_edit_nonexistent_profile_returns_404(self, memory_client):
        uid = _uid()
        resp = memory_client.patch(
            f"/api/v1/memory/{uid}/profile",
            json={"narrative": "x"},
            headers={"X-Test-User-Id": uid},
        )
        assert resp.status_code == 404

    def test_delete_one_session_summary(self, memory_client):
        _, _, tracker, *_ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid)
        summary = tracker.close_session(sid)

        resp = memory_client.delete(
            f"/api/v1/memory/{uid}/sessions/{summary.summary_id}",
            headers={"X-Test-User-Id": uid},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        again = memory_client.delete(
            f"/api/v1/memory/{uid}/sessions/{summary.summary_id}",
            headers={"X-Test-User-Id": uid},
        )
        assert again.status_code == 404

    def test_delete_all_memory_for_self(self, memory_client):
        _, _, tracker, consolidator, _ = _fresh_stack()
        uid, sid = _uid(), _sid()
        tracker.start_session(sid, uid)
        tracker.close_session(sid)
        consolidator.consolidate(uid)

        resp = memory_client.delete(
            f"/api/v1/memory/{uid}", headers={"X-Test-User-Id": uid}
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        follow_up = memory_client.get(
            f"/api/v1/memory/{uid}/profile?refresh=false", headers={"X-Test-User-Id": uid}
        )
        assert follow_up.json() is None

    def test_get_memory_index_and_stats(self, memory_client):
        uid = _uid()
        idx = memory_client.get("/api/v1/memory", headers={"X-Test-User-Id": uid})
        assert idx.status_code == 200
        body = idx.json()
        assert body["module"] == "memory"
        assert body["user_id"] == uid
        assert body["session_count"] == 0
        stats = memory_client.get("/api/v1/memory/stats", headers={"X-Test-User-Id": uid})
        assert stats.status_code == 200
        assert stats.json()["user_id"] == uid
        assert stats.json()["sessions"] == 0
