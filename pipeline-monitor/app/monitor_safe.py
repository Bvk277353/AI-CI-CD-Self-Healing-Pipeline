# pipeline-monitor/app/monitor_safe.py
"""
Safe monitoring loop — replaces any existing monitor.
Extremely defensive: never indexes lists without checks and logs raw responses.
"""

import asyncio
import json
import logging

from datetime import datetime

# import the same helpers & metrics your main app uses
try:
    # prefer package import style
    from app.main import GITHUB_REPO, GITHUB_TOKEN, POLL_INTERVAL, github_get
    from app.main import ml_predictor, healing_engine, logger as main_logger
    from app.metrics import PIPELINE_RUNS, PIPELINE_SUCCESS, PIPELINE_PRED_CONF
except Exception:
    # fallback if running with different import style
    from main import GITHUB_REPO, GITHUB_TOKEN, POLL_INTERVAL, github_get
    from main import ml_predictor, healing_engine, logger as main_logger
    from metrics import PIPELINE_RUNS, PIPELINE_SUCCESS, PIPELINE_PRED_CONF

logger = main_logger if 'main_logger' in globals() else logging.getLogger("monitor_safe")

last_seen = set()

async def run_safe_monitor():
    logger.info("Starting safe monitor (monitor_safe.run_safe_monitor)")
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.warning("GitHub config missing; safe monitor will sleep.")
    while True:
        try:
            # Try to fetch up to 5 recent runs (safer)
            url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=5"
            raw = await github_get(url)

            # Defensive: if not dict, log and sleep
            if not isinstance(raw, dict):
                logger.warning("monitor_safe: unexpected raw response (not dict). Logging and sleeping.")
                logger.debug("Raw response: %r", raw)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            runs = raw.get("workflow_runs") or []
            if not isinstance(runs, list):
                logger.warning("monitor_safe: 'workflow_runs' not a list. Raw: %r", raw)
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if len(runs) == 0:
                logger.debug("monitor_safe: no workflow_runs returned.")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            # iterate safely over runs
            for run in runs:
                if not isinstance(run, dict):
                    logger.debug("monitor_safe: skipping non-dict run: %r", run)
                    continue

                run_id = run.get("id")
                if run_id is None:
                    logger.debug("monitor_safe: run missing id: %r", run)
                    continue

                # dedupe by seen set (so we don't spam same run)
                if run_id in last_seen:
                    continue
                last_seen.add(run_id)
                # limit the set size to avoid memory growth
                if len(last_seen) > 200:
                    # drop oldest entries
                    while len(last_seen) > 100:
                        last_seen.pop()

                run_name = run.get("name", "<unnamed>")
                conclusion = run.get("conclusion")
                status = conclusion if conclusion is not None else run.get("status", "unknown")

                logger.info(f"monitor_safe: observed run {run_name} id={run_id} status={status}")

                # metrics - defensive
                try:
                    PIPELINE_RUNS.inc()
                except Exception:
                    logger.debug("monitor_safe: failed to inc PIPELINE_RUNS")

                # prepare payload safely
                payload = {
                    "created_at": run.get("created_at"),
                    "commit_size": run.get("run_attempt") or 0,
                    "previous_failures": run.get("run_number") or 0,
                    "test_coverage": run.get("test_coverage", 0),
                    "changed_files": run.get("changed_files", 0),
                    "dependency_changes": run.get("dependency_changes", 0),
                    "code_complexity": run.get("code_complexity", 0),
                    "test_count": run.get("test_count", 0),
                }

                # prediction
                try:
                    prediction = await ml_predictor.predict_failure(payload)
                except Exception as e:
                    logger.error(f"monitor_safe: prediction error for run {run_id}: {e}")
                    prediction = {}

                try:
                    PIPELINE_PRED_CONF.set(float(prediction.get("confidence", 0.0)))
                except Exception:
                    logger.debug("monitor_safe: failed to set PIPELINE_PRED_CONF")

                if conclusion == "success":
                    try:
                        PIPELINE_SUCCESS.inc()
                    except Exception:
                        logger.debug("monitor_safe: failed to inc PIPELINE_SUCCESS")

                # failure handling
                if conclusion == "failure":
                    logger.warning(f"monitor_safe: run {run_id} concluded failure; analyzing...")
                    logs_text = "NO LOGS"
                    try:
                        logs_url = run.get("logs_url")
                        if logs_url:
                            ld = await github_get(logs_url)
                            logs_text = json.dumps(ld) if ld else "NO LOGS"
                    except Exception as e:
                        logger.debug(f"monitor_safe: failed to fetch logs for {run_id}: {e}")
                        logs_text = "NO LOGS"

                    try:
                        analysis = await healing_engine.analyze_failure(logs_text)
                    except Exception as e:
                        logger.error(f"monitor_safe: analyze_failure error for {run_id}: {e}")
                        analysis = {"error_type": "unknown", "error_message": str(e)}

                    try:
                        prob = await ml_predictor.predict_healing_success(analysis)
                    except Exception as e:
                        logger.error(f"monitor_safe: predict_healing_success error for {run_id}: {e}")
                        prob = 0.0

                    logger.info(f"monitor_safe: healing probability for {run_id} = {prob}")

                    if prob and float(prob) > 0.7:
                        try:
                            await healing_engine.heal(run_id=str(run_id), failure_analysis=analysis, workflow_run=run)
                        except TypeError:
                            await healing_engine.heal(str(run_id), analysis, run)
                        except Exception as e:
                            logger.error(f"monitor_safe: heal() exception for {run_id}: {e}")

            # sleep
            await asyncio.sleep(POLL_INTERVAL)

        except Exception as e:
            # log everything including raw if IndexError suspected
            logger.exception(f"monitor_safe: top-level monitor exception: {e}")
            await asyncio.sleep(POLL_INTERVAL)
