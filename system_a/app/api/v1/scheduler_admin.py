"""
Scheduler Administration API endpoints.

When SCHEDULER_ENABLED=true (default), talks to the in-process APScheduler.
When SCHEDULER_ENABLED=false, proxies requests to the standalone scheduler
service at http://127.0.0.1:8002 (solarhub-scheduler.service).

The response contract is identical in both modes so callers need no changes.
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import require_admin, get_current_user
from ...config import settings
from ...domain.entities.user import User

router = APIRouter(prefix="/scheduler", tags=["Scheduler Admin"])
logger = logging.getLogger(__name__)

_EXTERNAL_SCHEDULER_URL = os.environ.get(
    "SCHEDULER_SERVICE_URL", "http://127.0.0.1:8002"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _proxy_get(path: str) -> Dict[str, Any]:
    """GET a path on the external scheduler service."""
    url = f"{_EXTERNAL_SCHEDULER_URL}{path}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scheduler service is not reachable at " + _EXTERNAL_SCHEDULER_URL,
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            )


async def _proxy_post(path: str) -> Dict[str, Any]:
    """POST a path on the external scheduler service."""
    url = f"{_EXTERNAL_SCHEDULER_URL}{path}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scheduler service is not reachable at " + _EXTERNAL_SCHEDULER_URL,
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", dependencies=[Depends(require_admin)])
async def get_scheduler_status(current_user: User = Depends(get_current_user)):
    """
    Get scheduler status and list of registered jobs.

    Proxies to solarhub-scheduler.service when SCHEDULER_ENABLED=false.
    """
    if not settings.scheduler_enabled:
        return await _proxy_get("/health")

    try:
        from ...infrastructure.scheduler import get_scheduler

        scheduler = get_scheduler()

        if not scheduler:
            return {"running": False, "error": "Scheduler not initialized", "jobs": []}

        jobs_info = []
        for job in scheduler.get_jobs():
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

        return {
            "running": scheduler.running,
            "timezone": str(scheduler.timezone) if hasattr(scheduler, "timezone") else None,
            "jobs_count": len(jobs_info),
            "jobs": jobs_info,
        }

    except Exception as e:
        logger.error("Failed to get scheduler status: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scheduler status: {str(e)}",
        )


@router.post("/start", dependencies=[Depends(require_admin)])
async def start_scheduler_manual(current_user: User = Depends(get_current_user)):
    """
    Manually start the embedded scheduler if it's not running.

    Not applicable when using the external scheduler service — returns a
    descriptive message in that case.
    """
    if not settings.scheduler_enabled:
        return {
            "success": False,
            "message": (
                "Embedded scheduler is disabled. "
                "Manage the scheduler via systemctl start solarhub-scheduler.service"
            ),
            "running": None,
        }

    try:
        from ...infrastructure.scheduler import start_scheduler, get_scheduler

        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            return {"success": False, "message": "Scheduler is already running", "running": True}

        await start_scheduler()
        scheduler = get_scheduler()
        is_running = scheduler.running if scheduler else False

        logger.info("Scheduler manually started by user %s", current_user.email)
        return {
            "success": True,
            "message": "Scheduler started successfully",
            "running": is_running,
            "jobs_count": len(scheduler.get_jobs()) if scheduler else 0,
        }

    except Exception as e:
        logger.error("Failed to start scheduler: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scheduler: {str(e)}",
        )


@router.post("/jobs/{job_id}/run", dependencies=[Depends(require_admin)])
async def trigger_job_manual(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger a specific scheduler job to run immediately.

    Proxies to solarhub-scheduler.service when SCHEDULER_ENABLED=false.
    """
    if not settings.scheduler_enabled:
        result = await _proxy_post(f"/jobs/{job_id}/trigger")
        logger.info(
            "Job '%s' manually triggered via external scheduler by user %s",
            job_id,
            current_user.email,
        )
        return result

    try:
        from ...infrastructure.scheduler import get_scheduler

        scheduler = get_scheduler()
        if not scheduler or not scheduler.running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduler is not running",
            )

        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job '{job_id}' not found",
            )

        job.modify(next_run_time=datetime.now())
        logger.info("Job '%s' manually triggered by user %s", job_id, current_user.email)

        return {
            "success": True,
            "message": f"Job '{job_id}' ({job.name}) has been queued to run immediately",
            "job_id": job_id,
            "job_name": job.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger job: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger job: {str(e)}",
        )
