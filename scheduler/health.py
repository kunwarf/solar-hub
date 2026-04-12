"""
Health check and admin HTTP server for the scheduler service.

Listens on 127.0.0.1:8002 (localhost only — not exposed externally).
System A's scheduler_admin.py proxies to these endpoints.

Endpoints:
  GET  /health                   — liveness + job list
  GET  /jobs                     — detailed job list
  POST /jobs/{job_id}/trigger    — manually run a job immediately
"""
import logging
from datetime import datetime

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def _health_handler(request: web.Request) -> web.Response:
    scheduler: AsyncIOScheduler = request.app["scheduler"]
    jobs = scheduler.get_jobs()
    return web.json_response({
        "status": "healthy" if scheduler.running else "unhealthy",
        "running": scheduler.running,
        "jobs_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ],
    })


async def _list_jobs_handler(request: web.Request) -> web.Response:
    scheduler: AsyncIOScheduler = request.app["scheduler"]
    jobs = scheduler.get_jobs()
    return web.json_response({
        "jobs_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "max_instances": job.max_instances,
                "misfire_grace_time": job.misfire_grace_time,
                "coalesce": job.coalesce,
            }
            for job in jobs
        ],
    })


async def _trigger_job_handler(request: web.Request) -> web.Response:
    scheduler: AsyncIOScheduler = request.app["scheduler"]
    job_id = request.match_info["job_id"]

    if not scheduler.running:
        return web.json_response(
            {"success": False, "message": "Scheduler is not running"},
            status=400,
        )

    job = scheduler.get_job(job_id)
    if not job:
        return web.json_response(
            {"success": False, "message": f"Job '{job_id}' not found"},
            status=404,
        )

    job.modify(next_run_time=datetime.now())
    logger.info("Job '%s' manually triggered via health API", job_id)

    return web.json_response({
        "success": True,
        "message": f"Job '{job_id}' ({job.name}) queued to run immediately",
        "job_id": job_id,
        "job_name": job.name,
    })


async def start_health_server(
    scheduler: AsyncIOScheduler,
    host: str = "127.0.0.1",
    port: int = 8002,
) -> web.AppRunner:
    """
    Start the health check HTTP server.

    Returns the AppRunner so the caller can cleanly shut it down.
    """
    app = web.Application()
    app["scheduler"] = scheduler

    app.router.add_get("/health", _health_handler)
    app.router.add_get("/jobs", _list_jobs_handler)
    app.router.add_post("/jobs/{job_id}/trigger", _trigger_job_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Scheduler health server listening on http://%s:%d", host, port)
    return runner
