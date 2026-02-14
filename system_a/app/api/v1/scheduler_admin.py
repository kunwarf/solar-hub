"""
Scheduler Administration API endpoints.

Provides endpoints to monitor and manage the billing scheduler.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import require_admin, get_current_user
from ...domain.entities.user import User

router = APIRouter(prefix="/scheduler", tags=["Scheduler Admin"])
logger = logging.getLogger(__name__)


@router.get("/status", dependencies=[Depends(require_admin)])
async def get_scheduler_status(current_user: User = Depends(get_current_user)):
    """
    Get scheduler status and list of registered jobs.

    Returns information about the APScheduler instance and all registered jobs.
    """
    try:
        from ...infrastructure.scheduler import get_scheduler

        scheduler = get_scheduler()

        if not scheduler:
            return {
                "running": False,
                "error": "Scheduler not initialized",
                "jobs": []
            }

        # Get all jobs
        jobs_info = []
        for job in scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            jobs_info.append(job_info)

        return {
            "running": scheduler.running,
            "timezone": str(scheduler.timezone) if hasattr(scheduler, 'timezone') else None,
            "jobs_count": len(jobs_info),
            "jobs": jobs_info
        }

    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scheduler status: {str(e)}"
        )


@router.post("/start", dependencies=[Depends(require_admin)])
async def start_scheduler_manual(current_user: User = Depends(get_current_user)):
    """
    Manually start the scheduler if it's not running.

    This can be used to recover from scheduler startup failures.
    """
    try:
        from ...infrastructure.scheduler import start_scheduler, get_scheduler

        scheduler = get_scheduler()

        if scheduler and scheduler.running:
            return {
                "success": False,
                "message": "Scheduler is already running",
                "running": True
            }

        # Try to start the scheduler
        await start_scheduler()

        scheduler = get_scheduler()
        is_running = scheduler.running if scheduler else False

        logger.info(f"Scheduler manually started by user {current_user.email}")

        return {
            "success": True,
            "message": "Scheduler started successfully",
            "running": is_running,
            "jobs_count": len(scheduler.get_jobs()) if scheduler else 0
        }

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scheduler: {str(e)}"
        )


@router.post("/jobs/{job_id}/run", dependencies=[Depends(require_admin)])
async def trigger_job_manual(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger a specific scheduler job to run immediately.

    Useful for testing or running billing jobs on-demand.
    """
    try:
        from ...infrastructure.scheduler import get_scheduler

        scheduler = get_scheduler()

        if not scheduler or not scheduler.running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduler is not running"
            )

        # Find the job
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found"
            )

        # Trigger the job to run now
        job.modify(next_run_time=datetime.now())

        logger.info(f"Job '{job_id}' manually triggered by user {current_user.email}")

        return {
            "success": True,
            "message": f"Job '{job_id}' ({job.name}) has been queued to run immediately",
            "job_id": job_id,
            "job_name": job.name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger job: {str(e)}"
        )
