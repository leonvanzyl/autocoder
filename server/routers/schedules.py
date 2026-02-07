"""
Schedules Router
================

API endpoints for managing agent schedules.
Provides CRUD operations for time-based schedule configuration.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Tuple

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import validate_project_not_detached

# Schedule limits to prevent resource exhaustion
MAX_SCHEDULES_PER_PROJECT = 50

from ..schemas import (
    NextRunResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name

if TYPE_CHECKING:
    from api.database import Schedule as ScheduleModel


def _schedule_to_response(schedule: "ScheduleModel") -> ScheduleResponse:
    """Convert a Schedule ORM object to a ScheduleResponse Pydantic model.

    SQLAlchemy Column descriptors resolve to Python types at instance access time,
    but mypy sees the Column[T] descriptor type. Using model_validate with
    from_attributes handles this conversion correctly.
    """
    return ScheduleResponse.model_validate(schedule, from_attributes=True)

router = APIRouter(
    prefix="/api/projects/{project_name}/schedules",
    tags=["schedules"]
)


@contextmanager
def _get_db_session(project_name: str) -> Generator[Tuple[Session, Path], None, None]:
    """Get database session for a project as a context manager.

    Usage:
        with _get_db_session(project_name) as (db, project_path):
            # ... use db ...
        # db is automatically closed

    Raises:
        HTTPException 404: If project not found
        HTTPException 409: If project is detached
    """
    from api.database import create_database

    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_path = validate_project_not_detached(project_name)

    _, SessionLocal = create_database(project_path)
    db = SessionLocal()
    try:
        yield db, project_path
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(project_name: str):
    """Get all schedules for a project."""
    from api.database import Schedule

    with _get_db_session(project_name) as (db, _):
        schedules = db.query(Schedule).filter(
            Schedule.project_name == project_name
        ).order_by(Schedule.start_time).all()

        return ScheduleListResponse(
            schedules=[_schedule_to_response(s) for s in schedules]
        )


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(project_name: str, data: ScheduleCreate):
    """Create a new schedule for a project."""
    from api.database import Schedule

    from ..services.scheduler_service import get_scheduler

    with _get_db_session(project_name) as (db, project_path):
        # Check schedule limit to prevent resource exhaustion
        existing_count = db.query(Schedule).filter(
            Schedule.project_name == project_name
        ).count()

        if existing_count >= MAX_SCHEDULES_PER_PROJECT:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum schedules per project ({MAX_SCHEDULES_PER_PROJECT}) exceeded"
            )

        # Create schedule record
        schedule = Schedule(
            project_name=project_name,
            start_time=data.start_time,
            duration_minutes=data.duration_minutes,
            days_of_week=data.days_of_week,
            enabled=data.enabled,
            yolo_mode=data.yolo_mode,
            model=data.model,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        # Register with APScheduler if enabled
        if schedule.enabled:
            import logging
            logger = logging.getLogger(__name__)

            scheduler = get_scheduler()
            await scheduler.add_schedule(project_name, schedule, project_path)
            logger.info(f"Registered schedule {schedule.id} with APScheduler")

            # Check if we're currently within this schedule's window
            # If so, start the agent immediately (cron won't trigger until next occurrence)
            now = datetime.now(timezone.utc)
            is_within = scheduler._is_within_window(schedule, now)
            logger.info(f"Schedule {schedule.id}: is_within_window={is_within}, now={now}, start={schedule.start_time}")

            if is_within:
                # Check for manual stop override
                from api.database import ScheduleOverride
                override = db.query(ScheduleOverride).filter(
                    ScheduleOverride.schedule_id == schedule.id,
                    ScheduleOverride.override_type == "stop",
                    ScheduleOverride.expires_at > now,
                ).first()

                logger.info(f"Schedule {schedule.id}: has_override={override is not None}")

                if not override:
                    # Start agent immediately
                    logger.info(
                        f"Schedule {schedule.id} is within active window, starting agent immediately"
                    )
                    try:
                        await scheduler._start_agent(project_name, project_path, schedule)
                        logger.info(f"Successfully started agent for schedule {schedule.id}")
                    except Exception as e:
                        logger.error(f"Failed to start agent for schedule {schedule.id}: {e}", exc_info=True)

        return _schedule_to_response(schedule)


@router.get("/next", response_model=NextRunResponse)
async def get_next_scheduled_run(project_name: str):
    """Calculate next scheduled run across all enabled schedules."""
    from api.database import Schedule, ScheduleOverride

    from ..services.scheduler_service import get_scheduler

    with _get_db_session(project_name) as (db, _):
        schedules = db.query(Schedule).filter(
            Schedule.project_name == project_name,
            Schedule.enabled == True,  # noqa: E712
        ).all()

        if not schedules:
            return NextRunResponse(
                has_schedules=False,
                next_start=None,
                next_end=None,
                is_currently_running=False,
                active_schedule_count=0,
            )

        now = datetime.now(timezone.utc)
        scheduler = get_scheduler()

        # Find active schedules and calculate next run
        active_count = 0
        next_start = None
        latest_end = None

        for schedule in schedules:
            if scheduler._is_within_window(schedule, now):
                # Check for manual stop override
                override = db.query(ScheduleOverride).filter(
                    ScheduleOverride.schedule_id == schedule.id,
                    ScheduleOverride.override_type == "stop",
                    ScheduleOverride.expires_at > now,
                ).first()

                if not override:
                    # Schedule is active and not manually stopped
                    active_count += 1
                    # Calculate end time for this window
                    end_time = _calculate_window_end(schedule, now)
                    if latest_end is None or end_time > latest_end:
                        latest_end = end_time
                # If override exists, treat schedule as not active
            else:
                # Calculate next start time
                next_schedule_start = _calculate_next_start(schedule, now)
                if next_schedule_start and (next_start is None or next_schedule_start < next_start):
                    next_start = next_schedule_start

        return NextRunResponse(
            has_schedules=True,
            next_start=next_start if active_count == 0 else None,
            next_end=latest_end,
            is_currently_running=active_count > 0,
            active_schedule_count=active_count,
        )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(project_name: str, schedule_id: int):
    """Get a single schedule by ID."""
    from api.database import Schedule

    with _get_db_session(project_name) as (db, _):
        schedule = db.query(Schedule).filter(
            Schedule.id == schedule_id,
            Schedule.project_name == project_name,
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        return _schedule_to_response(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    project_name: str,
    schedule_id: int,
    data: ScheduleUpdate
):
    """Update an existing schedule."""
    from api.database import Schedule

    from ..services.scheduler_service import get_scheduler

    with _get_db_session(project_name) as (db, project_path):
        schedule = db.query(Schedule).filter(
            Schedule.id == schedule_id,
            Schedule.project_name == project_name,
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        was_enabled = schedule.enabled

        # Update only fields that were explicitly provided
        # This allows sending {"model": null} to clear it vs omitting the field entirely
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)

        db.commit()
        db.refresh(schedule)

        # Update APScheduler jobs
        scheduler = get_scheduler()
        if schedule.enabled:
            # Re-register with updated times
            await scheduler.add_schedule(project_name, schedule, project_path)
        elif was_enabled:
            # Was enabled, now disabled - remove jobs
            scheduler.remove_schedule(schedule_id)

        return _schedule_to_response(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(project_name: str, schedule_id: int):
    """Delete a schedule."""
    from api.database import Schedule

    from ..services.scheduler_service import get_scheduler

    with _get_db_session(project_name) as (db, _):
        schedule = db.query(Schedule).filter(
            Schedule.id == schedule_id,
            Schedule.project_name == project_name,
        ).first()

        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Remove APScheduler jobs
        scheduler = get_scheduler()
        scheduler.remove_schedule(schedule_id)

        # Delete from database
        db.delete(schedule)
        db.commit()


def _calculate_window_end(schedule, now: datetime) -> datetime:
    """Calculate when the current window ends."""
    start_hour, start_minute = map(int, schedule.start_time.split(":"))

    # Create start time for today in UTC
    window_start = now.replace(
        hour=start_hour, minute=start_minute, second=0, microsecond=0
    )

    # If current time is before start time, the window started yesterday
    if now < window_start:
        window_start = window_start - timedelta(days=1)

    return window_start + timedelta(minutes=schedule.duration_minutes)


def _calculate_next_start(schedule, now: datetime) -> datetime | None:
    """Calculate the next start time for a schedule."""
    start_hour, start_minute = map(int, schedule.start_time.split(":"))

    # Create start time for today
    candidate = now.replace(
        hour=start_hour, minute=start_minute, second=0, microsecond=0
    )

    # If already past today's start time, check tomorrow
    if candidate <= now:
        candidate = candidate + timedelta(days=1)

    # Find the next active day
    for _ in range(7):
        if schedule.is_active_on_day(candidate.weekday()):
            return candidate
        candidate = candidate + timedelta(days=1)

    return None
