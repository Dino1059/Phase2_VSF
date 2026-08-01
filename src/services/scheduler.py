import uuid
import datetime
import logging
from typing import Dict, List, Optional, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service to schedule dataset profiling and quality checks via APScheduler."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._is_started = False

    def start(self) -> None:
        """Start the background scheduler if not already running."""
        if not self._is_started:
            try:
                self.scheduler.start()
                self._is_started = True
                logger.info("APScheduler BackgroundScheduler started successfully.")
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

    def add_schedule(
        self,
        name: str,
        dataset_name: str = "raw_taxi_trips.csv",
        schedule_type: str = "interval",
        interval_seconds: Optional[int] = 3600,
        cron_expression: Optional[str] = None,
        action: str = "profile",
    ) -> Dict[str, Any]:
        """
        Add a new profiling/quality check schedule.

        Args:
            name: Human readable name for the schedule.
            dataset_name: Target dataset filename or table.
            schedule_type: "interval" or "cron".
            interval_seconds: Seconds between runs if schedule_type is "interval".
            cron_expression: Cron string (e.g., "*/5 * * * *") if schedule_type is "cron".
            action: Action to perform, e.g., "profile", "quality_check", or "full".
        """
        schedule_id = f"sched_{uuid.uuid4().hex[:8]}"
        created_at = datetime.datetime.now().isoformat()

        if schedule_type == "cron":
            if not cron_expression:
                cron_expression = "0 * * * *"  # Default every hour
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            schedule_type = "interval"
            if not interval_seconds or interval_seconds < 1:
                interval_seconds = 3600
            trigger = IntervalTrigger(seconds=interval_seconds)

        # Make sure scheduler is running when schedule is added
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

        schedule_data = {
            "schedule_id": schedule_id,
            "id": schedule_id,
            "name": name,
            "dataset_name": dataset_name,
            "schedule_type": schedule_type,
            "interval_seconds": interval_seconds if schedule_type == "interval" else None,
            "cron_expression": cron_expression if schedule_type == "cron" else None,
            "action": action,
            "status": "active",
            "created_at": created_at,
            "last_run": None,
            "next_run": next_run_str,
            "run_count": 0,
        }

        self._schedules[schedule_id] = schedule_data
        logger.info(f"Schedule '{name}' ({schedule_id}) added successfully.")
        return schedule_data

    def get_schedules(self) -> List[Dict[str, Any]]:
        """Return all registered schedules."""
        # Update next_run_time dynamically from APScheduler jobs
        for sched_id, data in self._schedules.items():
            job = self.scheduler.get_job(sched_id)
            if job and job.next_run_time:
                data["next_run"] = job.next_run_time.isoformat()
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific schedule by ID."""
        data = self._schedules.get(schedule_id)
        if data:
            job = self.scheduler.get_job(schedule_id)
            if job and job.next_run_time:
                data["next_run"] = job.next_run_time.isoformat()
        return data

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        if schedule_id in self._schedules:
            try:
                if self.scheduler.get_job(schedule_id):
                    self.scheduler.remove_job(schedule_id)
            except Exception as e:
                logger.warning(f"Failed to remove APScheduler job {schedule_id}: {e}")
            del self._schedules[schedule_id]
            logger.info(f"Schedule {schedule_id} deleted successfully.")
            return True
        return False

    def trigger_now(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Manually trigger a schedule immediately."""
        if schedule_id in self._schedules:
            self._run_job(schedule_id)
            return self.get_schedule(schedule_id)
        return None

    def _run_job(self, schedule_id: str) -> None:
        """Internal execution method called by APScheduler when job fires."""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return

        now_str = datetime.datetime.now().isoformat()
        schedule["last_run"] = now_str
        schedule["run_count"] = schedule.get("run_count", 0) + 1

        dataset_name = schedule.get("dataset_name", "raw_taxi_trips.csv")
        action = schedule.get("action", "profile")

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
                    "schedule_name": schedule.get("name"),
                    "dataset": dataset_name,
                    "row_count": profile.get("total_rows", 0),
                    "anomalies": profile.get("total_anomalies", 0),
                    "health_score": profile.get("data_health_score", 100.0),
                },
            )
            logger.info(f"Executed scheduled task '{schedule.get('name')}' ({schedule_id}): {profile.get('summary')}")
        except Exception as e:
            logger.error(f"Error running scheduled task {schedule_id}: {e}")


# Global singleton instance
scheduler_service = SchedulerService()
