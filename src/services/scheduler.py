import uuid
import datetime
import json
import logging
from typing import Dict, List, Optional, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.db.connection import get_db

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service to schedule dataset profiling and quality checks via APScheduler backed by DuckDB."""

    def __init__(self, db=None):
        self.scheduler = BackgroundScheduler()
        self._db = db
        self._is_started = False

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def start(self) -> None:
        """Start the background scheduler and reload active schedules from DuckDB."""
        if not self._is_started:
            try:
                self.scheduler.start()
                self._is_started = True
                logger.info("APScheduler BackgroundScheduler started successfully.")
                self._reload_schedules_from_db()
            except Exception as e:
                logger.error(f"Failed to start APScheduler: {e}")

    def shutdown(self, wait: bool = False) -> None:
        """Shutdown the scheduler."""
        if self._is_started:
            try:
                self.scheduler.shutdown(wait=wait)
                self._is_started = False
                logger.info("APScheduler stopped.")
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {e}")

    def _reload_schedules_from_db(self) -> None:
        """Reload all active schedules from DuckDB `schedules` table into APScheduler."""
        try:
            conn = self.db.get_connection()
            rows = conn.execute("""
                SELECT id, dataset_key, cron_expression, is_active, created_at, next_run_at, name, schedule_type, interval_seconds, action
                FROM schedules
                WHERE is_active = true
            """).fetchall()

            for row in rows:
                sched_id = row[0]
                dataset_key = row[1]
                cron_expr = row[2]
                is_active = row[3]
                created_at = row[4]
                next_run_at = row[5]
                name = row[6] or f"Schedule-{sched_id}"
                schedule_type = row[7] or ("cron" if cron_expr else "interval")
                interval_seconds = row[8]
                action = row[9] or "profile"

                if not is_active:
                    continue

                if schedule_type == "cron" and cron_expr:
                    trigger = CronTrigger.from_crontab(cron_expr)
                else:
                    sec = interval_seconds if (interval_seconds and interval_seconds > 0) else 3600
                    trigger = IntervalTrigger(seconds=sec)

                if not self.scheduler.get_job(sched_id):
                    job = self.scheduler.add_job(
                        func=self._run_job,
                        trigger=trigger,
                        id=sched_id,
                        name=name,
                        args=[sched_id],
                        replace_existing=True,
                    )
                    next_run_str = job.next_run_time.isoformat() if job.next_run_time else None
                    conn.execute("UPDATE schedules SET next_run_at = ? WHERE id = ?", [next_run_str, sched_id])
            logger.info(f"Reloaded {len(rows)} active schedules from DuckDB.")
        except Exception as e:
            logger.error(f"Failed to reload schedules from DuckDB: {e}")

    def add_schedule(
        self,
        name: str,
        dataset_name: str = "raw_taxi_trips.csv",
        schedule_type: str = "interval",
        interval_seconds: Optional[int] = 3600,
        cron_expression: Optional[str] = None,
        action: str = "profile",
        schedule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a new profiling/quality check schedule and persist to DuckDB."""
        if not schedule_id:
            schedule_id = f"sched_{uuid.uuid4().hex[:8]}"

        created_at_dt = datetime.datetime.now()

        if schedule_type == "cron":
            if not cron_expression:
                cron_expression = "0 * * * *"
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            schedule_type = "interval"
            if not interval_seconds or interval_seconds < 1:
                interval_seconds = 3600
            trigger = IntervalTrigger(seconds=interval_seconds)

        if not self._is_started:
            self.start()

        job = self.scheduler.add_job(
            func=self._run_job,
            trigger=trigger,
            id=schedule_id,
            name=name,
            args=[schedule_id],
            replace_existing=True,
        )

        next_run_str = job.next_run_time.isoformat() if job.next_run_time else None

        conn = self.db.get_connection()
        conn.execute("DELETE FROM schedules WHERE id = ?", [schedule_id])
        conn.execute("""
            INSERT INTO schedules (id, dataset_key, cron_expression, is_active, created_at, next_run_at, name, schedule_type, interval_seconds, action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            schedule_id,
            dataset_name,
            cron_expression if schedule_type == "cron" else None,
            True,
            created_at_dt,
            next_run_str,
            name,
            schedule_type,
            interval_seconds if schedule_type == "interval" else None,
            action,
        ])

        sched_dict = self.get_schedule(schedule_id)
        logger.info(f"Schedule '{name}' ({schedule_id}) added and persisted to DuckDB successfully.")
        return sched_dict

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Return all registered active schedules from DuckDB."""
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT id, dataset_key, cron_expression, is_active, created_at, next_run_at, name, schedule_type, interval_seconds, action
            FROM schedules
            WHERE is_active = true
            ORDER BY created_at DESC
        """).fetchall()

        schedules = []
        for r in rows:
            sched_dict = self._row_to_schedule_dict(r)
            schedules.append(sched_dict)
        return schedules

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific schedule by ID from DuckDB."""
        conn = self.db.get_connection()
        row = conn.execute("""
            SELECT id, dataset_key, cron_expression, is_active, created_at, next_run_at, name, schedule_type, interval_seconds, action
            FROM schedules
            WHERE id = ?
        """, [schedule_id]).fetchone()

        if not row:
            return None
        return self._row_to_schedule_dict(row)

    def _row_to_schedule_dict(self, row) -> Dict[str, Any]:
        sched_id = row[0]
        dataset_key = row[1]
        cron_expr = row[2]
        is_active = row[3]
        created_at = row[4]
        next_run_at = row[5]
        name = row[6]
        schedule_type = row[7] or ("cron" if cron_expr else "interval")
        interval_seconds = row[8]
        action = row[9] or "profile"

        job = self.scheduler.get_job(sched_id) if self._is_started else None
        next_run_str = job.next_run_time.isoformat() if (job and job.next_run_time) else (str(next_run_at) if next_run_at else None)

        conn = self.db.get_connection()
        run_count_row = conn.execute("SELECT COUNT(*), MAX(completed_at) FROM job_runs WHERE schedule_id = ?", [sched_id]).fetchone()
        run_count = run_count_row[0] if run_count_row else 0
        last_run = str(run_count_row[1]) if (run_count_row and run_count_row[1]) else None

        created_at_str = str(created_at) if created_at else datetime.datetime.now().isoformat()

        return {
            "schedule_id": sched_id,
            "id": sched_id,
            "name": name or f"Schedule-{sched_id}",
            "dataset_name": dataset_key or "raw_taxi_trips.csv",
            "dataset_key": dataset_key or "raw_taxi_trips.csv",
            "schedule_type": schedule_type,
            "interval_seconds": interval_seconds,
            "cron_expression": cron_expr,
            "action": action,
            "status": "active" if is_active else "inactive",
            "is_active": bool(is_active),
            "created_at": created_at_str,
            "last_run": last_run,
            "next_run": next_run_str,
            "next_run_at": next_run_str,
            "run_count": run_count,
        }

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule by ID from DuckDB and APScheduler."""
        conn = self.db.get_connection()
        row = conn.execute("SELECT id FROM schedules WHERE id = ?", [schedule_id]).fetchone()
        if not row:
            return False

        try:
            if self.scheduler.get_job(schedule_id):
                self.scheduler.remove_job(schedule_id)
        except Exception as e:
            logger.warning(f"Failed to remove APScheduler job {schedule_id}: {e}")

        conn.execute("DELETE FROM schedules WHERE id = ?", [schedule_id])
        logger.info(f"Schedule {schedule_id} deleted successfully from DuckDB.")
        return True

    def trigger_now(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Manually trigger a schedule immediately."""
        sched = self.get_schedule(schedule_id)
        if sched:
            self._run_job(schedule_id)
            return self.get_schedule(schedule_id)
        return None

    def _run_job(self, schedule_id: str) -> None:
        """Internal execution method called by APScheduler when job fires."""
        sched = self.get_schedule(schedule_id)
        if not sched:
            return

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        dataset_key = sched.get("dataset_key") or sched.get("dataset_name") or "raw_taxi_trips.csv"
        action = sched.get("action", "profile")
        started_at_dt = datetime.datetime.now()

        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO job_runs (id, schedule_id, dataset_key, status, result_summary, started_at)
            VALUES (?, ?, ?, 'RUNNING', '{}', ?)
        """, [run_id, schedule_id, dataset_key, started_at_dt])

        try:
            from src.services.dataset_engine import load_dataset_rows, profile_rows
            from src.api.audit_store import AuditStore

            rows = load_dataset_rows()
            profile = profile_rows(rows)

            audit_store = AuditStore()
            audit_store.record_event(
                f"scheduled_{action}",
                {
                    "schedule_id": schedule_id,
                    "schedule_name": sched.get("name"),
                    "dataset": dataset_key,
                    "row_count": profile.get("total_rows", 0),
                    "anomalies": profile.get("total_anomalies", 0),
                    "health_score": profile.get("data_health_score", 100.0),
                },
            )

            completed_at_dt = datetime.datetime.now()
            summary_dict = {
                "total_rows": profile.get("total_rows", 0),
                "total_anomalies": profile.get("total_anomalies", 0),
                "data_health_score": profile.get("data_health_score", 100.0),
                "summary": profile.get("summary", ""),
            }
            summary_json = json.dumps(summary_dict)

            conn.execute("""
                UPDATE job_runs
                SET status = 'COMPLETED', result_summary = ?, completed_at = ?
                WHERE id = ?
            """, [summary_json, completed_at_dt, run_id])

            logger.info(f"Executed scheduled task '{sched.get('name')}' ({schedule_id}): {profile.get('summary')}")
        except Exception as e:
            completed_at_dt = datetime.datetime.now()
            error_json = json.dumps({"error": str(e)})
            conn.execute("""
                UPDATE job_runs
                SET status = 'FAILED', result_summary = ?, completed_at = ?
                WHERE id = ?
            """, [error_json, completed_at_dt, run_id])
            logger.error(f"Error running scheduled task {schedule_id}: {e}")

    def get_job_runs(self, schedule_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get job execution history from DuckDB `job_runs` table."""
        conn = self.db.get_connection()
        if schedule_id:
            rows = conn.execute("""
                SELECT id, schedule_id, dataset_key, status, result_summary, started_at, completed_at
                FROM job_runs
                WHERE schedule_id = ?
                ORDER BY started_at DESC
            """, [schedule_id]).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, schedule_id, dataset_key, status, result_summary, started_at, completed_at
                FROM job_runs
                ORDER BY started_at DESC
            """).fetchall()

        runs = []
        for r in rows:
            summary = {}
            if r[4]:
                try:
                    summary = json.loads(r[4]) if isinstance(r[4], str) else r[4]
                except Exception:
                    summary = {}
            runs.append({
                "id": r[0],
                "schedule_id": r[1],
                "dataset_key": r[2],
                "status": r[3],
                "result_summary": summary,
                "started_at": str(r[5]) if r[5] else None,
                "completed_at": str(r[6]) if r[6] else None,
            })
        return runs


scheduler_service = SchedulerService()
