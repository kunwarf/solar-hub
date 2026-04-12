"""
Solar Hub Standalone Scheduler Service.

Runs all APScheduler-based jobs independently from the System A API process.
Can be horizontally scaled — Redis distributed locks prevent duplicate execution.

Entry point: python -m scheduler
Health check: http://127.0.0.1:8002/health
"""
