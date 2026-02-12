"""
AI-Powered Self-Healing CI/CD Pipeline Monitor
Main FastAPI Application (patched with Prometheus metrics)
"""
import os
import json
import traceback
import asyncio
import aiohttp

# GitHub config
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "20"))

from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio
from datetime import datetime
import logging
from app.github_monitor import GitHubMonitor
from healing_engine import HealingEngine
from ml_predictor import FailurePredictor
from models import Database, PipelineRun, FailureLog, HealingAction

# Metrics (prometheus)
from .metrics import PIPELINE_RUNS, PIPELINE_SUCCESS, PIPELINE_PRED_CONF

# Prometheus Instrumentator
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Self-Healing CI/CD Pipeline",
    description="AI-powered pipeline monitoring and auto-healing system",
    version="1.0.0"
)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Enable Prometheus instrumentation BEFORE startup
try:
    Instrumentator().instrument(app).expose(app)
    logger.info("Prometheus Instrumentator enabled at /metrics")
except Exception as e:
    logger.warning(f"Prometheus Instrumentator init failed: {e}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db = Database()
github_monitor = GitHubMonitor()
healing_engine = HealingEngine()
ml_predictor = FailurePredictor()

# Request/Response Models
class WebhookPayload(BaseModel):
    action: str
    workflow_run: Dict
    repository: Dict

class PipelineStatus(BaseModel):
    run_id: str
    status: str
    conclusion: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    failure_predicted: bool
    healing_attempted: bool
    healing_successful: bool

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, bool]





@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Self-Healing CI/CD Pipeline Monitor...")
    await db.connect()
    await ml_predictor.load_model()
    # start background monitor task
    asyncio.create_task(monitor_pipelines())
    logger.info("System ready!")
    # add these inside your startup function, after models are loaded
    from app.monitor_safe import run_safe_monitor
    asyncio.create_task(run_safe_monitor())
    logger.info("monitor_safe started as replacement monitor.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await db.disconnect()
    logger.info("System shutdown complete")


@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


@app.get("/", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        services={
            "database": await db.is_connected(),
            "github_api": github_monitor.check_connection(),
            "ml_model": ml_predictor.is_loaded()
        }
    )

@app.post("/webhook/github")
async def github_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receive GitHub Actions webhook events
    Triggers monitoring and healing on workflow completion
    """
    try:
        if payload.action in ["completed", "failed"]:
            workflow_run = payload.workflow_run
            
            # Store pipeline run
            pipeline_run = await db.create_pipeline_run(
                run_id=workflow_run["id"],
                repo=payload.repository["full_name"],
                status=workflow_run["status"],
                conclusion=workflow_run.get("conclusion"),
                started_at=workflow_run["created_at"],
                completed_at=workflow_run.get("updated_at")
            )

            # Metric: observed a run
            try:
                PIPELINE_RUNS.inc()
            except Exception:
                logger.debug("Failed to increment PIPELINE_RUNS metric")

            # Metric: if it already concluded as success, count it
            if workflow_run.get("conclusion") == "success":
                try:
                    PIPELINE_SUCCESS.inc()
                except Exception:
                    logger.debug("Failed to increment PIPELINE_SUCCESS metric")

            # If failed, trigger healing in background
            if workflow_run.get("conclusion") == "failure":
                background_tasks.add_task(
                    handle_pipeline_failure,
                    pipeline_run.run_id,
                    workflow_run
                )
            
            return {"status": "received", "run_id": workflow_run["id"]}
        
        return {"status": "ignored", "action": payload.action}
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_pipeline_failure(run_id: str, workflow_run: Dict):
    """
    Handle pipeline failure with AI-powered healing
    """
    try:
        logger.info(f"Processing failure for run {run_id}")
        
        # Fetch detailed logs
        logs = await github_monitor.fetch_workflow_logs(run_id)
        
        # Parse and analyze failure
        failure_analysis = await healing_engine.analyze_failure(logs)
        
        # Store failure log
        await db.create_failure_log(
            run_id=run_id,
            error_type=failure_analysis.get("error_type", "unknown"),
            error_message=failure_analysis.get("error_message", ""),
            stack_trace=failure_analysis.get("stack_trace", "")
        )
        
        # Predict if healing will succeed
        success_probability = await ml_predictor.predict_healing_success(
            failure_analysis
        )
        
        logger.info(f"Healing success probability: {success_probability:.2%}")
        
        # Attempt healing if probability > 70%
        if success_probability > 0.70:
            healing_result = await healing_engine.heal(
                run_id=run_id,
                failure_analysis=failure_analysis,
                workflow_run=workflow_run
            )
            
            # Store healing action
            await db.create_healing_action(
                run_id=run_id,
                action_type=healing_result.get("action_type", "unknown"),
                success=healing_result.get("success", False),
                details=healing_result.get("details", {})
            )
            
            if healing_result.get("success"):
                logger.info(f"✅ Successfully healed pipeline {run_id}")
                # Re-trigger the workflow
                await github_monitor.rerun_workflow(run_id)
            else:
                logger.warning(f"❌ Healing failed for {run_id}")
                # Send notification to developers
                await send_notification(run_id, failure_analysis)
        else:
            logger.info(f"Skipping auto-heal (low confidence): {run_id}")
            await send_notification(run_id, failure_analysis)
    
    except Exception as e:
        logger.error(f"Error handling pipeline failure: {e}")


@app.post("/auto-heal")
async def auto_heal(payload: dict):
    logs = payload.get("logs", "")
    app_name = payload.get("app_name", "unknown")

    analysis = await healing_engine.analyze_failure(logs)
    healing_result = await healing_engine.heal(analysis)

    return {
        "app": app_name,
        "analysis": analysis,
        "action_taken": healing_result
    }


last_seen_run = None

async def github_get(url: str):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            return await resp.json()

async def monitor_pipelines():
    """
    Robust background task to continuously monitor recent workflows.
    Defensive: handles empty/malformed responses, missing keys, and logs helpful debug info.
    """
    global last_seen_run

    if not hasattr(github_monitor, "get_active_workflows") and (not GITHUB_REPO or not GITHUB_TOKEN):
        logger.warning("No github monitor method or GitHub config missing. Skipping monitor.")
        return

    logger.info(f"🔍 Starting pipeline monitor loop for repo: {GITHUB_REPO or '<not configured>'}")

    while True:
        try:
            # Prefer using github_monitor.get_active_workflows() if implemented
            runs_data = []
            try:
                if hasattr(github_monitor, "get_active_workflows"):
                    runs_data = await github_monitor.get_active_workflows() or []
                else:
                    # fallback to direct API call if github_monitor doesn't provide helper
                    if GITHUB_REPO and GITHUB_TOKEN:
                        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=5"
                        raw = await github_get(url)
                        if isinstance(raw, dict):
                            runs_data = raw.get("workflow_runs") or []
            except Exception as e:
                logger.debug(f"Error fetching active workflows via github_monitor: {e}")
                runs_data = []

            # ensure runs_data is iterable
            if not runs_data:
                logger.debug("No active runs returned; sleeping.")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            # loop through recent runs defensively
            for run in runs_data:
                if not isinstance(run, dict):
                    logger.debug("Skipping non-dict run entry: %r", run)
                    continue

                run_id = run.get("id")
                if not run_id:
                    logger.debug("Skipping run with no id: %r", run)
                    continue

                # avoid re-processing the same run very frequently; track last_seen_run
                if run_id == last_seen_run:
                    continue

                last_seen_run = run_id

                run_name = run.get("name", "<unnamed>")
                run_conclusion = run.get("conclusion")  # can be None while running
                run_status = run_conclusion if run_conclusion is not None else run.get("status", "unknown")

                logger.info(f"Observed workflow: name={run_name}, id={run_id}, status={run_status}")

                # metric: new observed run
                try:
                    PIPELINE_RUNS.inc()
                except Exception:
                    logger.debug("Failed to increment PIPELINE_RUNS metric")

                # Build safe payload for prediction (provide defaults)
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

                # run prediction (protected)
                try:
                    prediction = await ml_predictor.predict_failure(payload)
                except Exception as e:
                    logger.error(f"Prediction error for run {run_id}: {e}")
                    prediction = {}

                logger.info(f"Prediction for run {run_id}: {prediction}")

                # update prediction confidence metric
                try:
                    PIPELINE_PRED_CONF.set(float(prediction.get("confidence", 0.0)))
                except Exception:
                    logger.debug("Failed to set PIPELINE_PRED_CONF metric")

                # if concluded as success, increment success metric
                if run_conclusion == "success":
                    try:
                        PIPELINE_SUCCESS.inc()
                    except Exception:
                        logger.debug("Failed to increment PIPELINE_SUCCESS metric")

                # if run failed, perform analysis + healing
                if run_conclusion == "failure":
                    logger.error(f"Workflow {run_id} failed — running analysis & healing")

                    # get logs if available
                    logs_text = "NO LOGS"
                    logs_url = run.get("logs_url")
                    if logs_url:
                        try:
                            logs_data = await github_get(logs_url)
                            logs_text = json.dumps(logs_data) if logs_data else "NO LOGS"
                        except Exception as e:
                            logger.debug(f"Failed to fetch logs for run {run_id}: {e}")
                            logs_text = "NO LOGS"

                    # analyze failure
                    try:
                        failure_analysis = await healing_engine.analyze_failure(logs_text)
                    except Exception as e:
                        logger.error(f"Failure analysis exception for run {run_id}: {e}")
                        failure_analysis = {"error_type": "unknown", "error_message": str(e)}

                    logger.info(f"Failure analysis for {run_id}: {failure_analysis}")

                    # estimate healing success probability
                    try:
                        healing_prob = await ml_predictor.predict_healing_success(failure_analysis)
                    except Exception as e:
                        logger.error(f"Healing prediction error for run {run_id}: {e}")
                        healing_prob = 0.0

                    logger.info(f"Healing success probability for {run_id}: {healing_prob}")

                    # attempt healing if confidence high enough
                    try:
                        if healing_prob and float(healing_prob) > 0.7:
                            try:
                                # prefer explicit keyword args, but support older signature
                                result = await healing_engine.heal(failure_analysis=failure_analysis, run_id=str(run_id), workflow_run=run)
                            except TypeError:
                                result = await healing_engine.heal(str(run_id), failure_analysis, run)
                            logger.info(f"Healing result for {run_id}: {result}")
                        else:
                            logger.info(f"Skipping auto-heal for {run_id} due to low predicted probability ({healing_prob})")
                    except Exception as e:
                        logger.error(f"Error while attempting healing for {run_id}: {e}")

            # sleep before next poll
            await asyncio.sleep(POLL_INTERVAL)

        except Exception as e:
            tb = traceback.format_exc()
            logger.error("🔥 FULL TRACEBACK:\n" + tb)
            logger.error(f"Monitor loop error: {e}")



async def send_notification(run_id: str, failure_analysis: Dict):
    """Send notification about pipeline failure"""
    # Implementation for Slack/Email notifications
    logger.info(f"Sending notification for {run_id}")
    # Add your notification logic here (Slack, email, etc.)

async def send_early_warning(run: Dict, prediction: Dict):
    """Send early warning about potential failure"""
    logger.warning(
        f"Early warning: Pipeline {run.get('id')} likely to fail "
        f"(confidence: {prediction.get('confidence',0):.2%})"
    )
    # Send proactive notification

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    
