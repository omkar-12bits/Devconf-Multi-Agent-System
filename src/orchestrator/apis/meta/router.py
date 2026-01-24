import logging
import httpx
from fastapi import APIRouter, Response, Request, status
from starlette.concurrency import run_in_threadpool
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH

from orchestrator.apis.meta.models import HealthCheck, StatusChecks, StatusCheckValue
from orchestrator.apis.meta.status import StatusCheck, status_check
from orchestrator.config import app_cfg
from orchestrator.db.base import db_connection_check


logger = logging.getLogger(__name__)

meta_router = APIRouter(
    redirect_slashes=True,
    tags=["meta"]
)

_optional_services = []


@meta_router.get("/health", status_code=status.HTTP_200_OK, operation_id="health_check")
async def health_check() -> HealthCheck:
    """
    Simple health check for load balancers and Kubernetes probes.
    Returns 200 OK if service is running.
    """
    return HealthCheck(status=StatusCheckValue.OK)


@status_check(name="supervisor-agent")
async def supervisor_status(request: Request) -> dict:
    """Check if supervisor agent is initialized and operational."""
    try:
        supervisor = request.app.state.supervisor
        if supervisor and hasattr(supervisor, 'supervisor_agent'):
            return {"status": StatusCheckValue.OK}
        else:
            return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"Supervisor check error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="session-service")
async def session_service_status(request: Request) -> dict:
    """Check if session service is operational."""
    try:
        session_service = request.app.state.session_service
        app_name = request.app.state.app_name
        
        # Test session service with a quick operation
        await session_service.get_session(
            app_name=app_name,
            user_id="health_check",
            session_id="health_test"
        )
        return {"status": StatusCheckValue.OK}
    except Exception as e:
        logger.error(f"Session service check error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="adk-runner")
async def adk_runner_status(request: Request) -> dict:
    """Check if ADK runner is initialized."""
    try:
        runner = request.app.state.runner
        if runner and hasattr(runner, 'agent'):
            return {"status": StatusCheckValue.OK}
        else:
            return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"Runner check error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="google-api")
async def google_api_status() -> dict:
    """Check if Google API key is configured."""
    try:
        if app_cfg.GOOGLE_API_KEY:
            return {"status": StatusCheckValue.OK}
        else:
            return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"Google API check error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="granite-guardian")
async def granite_guardian_status() -> dict:
    """Check if Granite Guardian (safety model) is accessible."""
    if not app_cfg.INPUT_GUARDRAILS_ENABLED:
        return {"status": StatusCheckValue.DISABLED}
    
    base_url_v1 = app_cfg.GRANITE_GUARDIAN_HOST
    url = base_url_v1.replace("/v1", "/health")
    headers = {"Authorization": f"Bearer {app_cfg.GRANITE_GUARDIAN_API_KEY}"}
    
    try:
        async with httpx.AsyncClient(verify=app_cfg.VERIFY_SSL, timeout=app_cfg.DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return {"status": StatusCheckValue.OK}
            else:
                return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"Granite Guardian connection error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="google-search-agent")
async def google_search_agent_status() -> dict:
    """Check if google_search_agent service is accessible."""
    if not app_cfg.GOOGLE_SEARCH_AGENT_BASE_URL:
        return {"status": StatusCheckValue.DISABLED}
    
    url = f"{app_cfg.GOOGLE_SEARCH_AGENT_BASE_URL}{AGENT_CARD_WELL_KNOWN_PATH}"
    
    try:
        async with httpx.AsyncClient(verify=app_cfg.VERIFY_SSL, timeout=app_cfg.DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return {"status": StatusCheckValue.OK}
            else:
                return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"google_search_agent connection error: {e}")
        return {"status": StatusCheckValue.DOWN}


@status_check(name="github-agent")
async def github_agent_status() -> dict:
    """Check if github_agent service is accessible."""
    if not app_cfg.GITHUB_AGENT_BASE_URL:
        return {"status": StatusCheckValue.DISABLED}
    
    url = f"{app_cfg.GITHUB_AGENT_BASE_URL}{AGENT_CARD_WELL_KNOWN_PATH}"
    try:
        async with httpx.AsyncClient(verify=app_cfg.VERIFY_SSL, timeout=app_cfg.DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return {"status": StatusCheckValue.OK}
            else:
                return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"github_agent connection error: {e}")
        return {"status": StatusCheckValue.DOWN}

@status_check(name="database")
async def database_status(request: Request = None) -> dict:
    """Check database connection (if enabled)."""
    if not app_cfg.USE_DATABASE_SESSIONS:
        return {"status": StatusCheckValue.DISABLED}
    
    try:
        is_healthy = await run_in_threadpool(db_connection_check)
        
        if is_healthy:
            return {"status": StatusCheckValue.OK}
        else:
            return {"status": StatusCheckValue.DOWN}
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return {"status": StatusCheckValue.DOWN}


@meta_router.get("/status", status_code=status.HTTP_200_OK, operation_id="status_check")
async def service_status(
    request: Request,
    response: Response,
) -> StatusChecks:
    """Comprehensive status check of all system components."""
    logger.debug('Requesting component statuses...')
    
    result = await StatusCheck.run(request)
    status_checks = StatusChecks(services=result)
    
    # Check if any critical service is DOWN
    for service_name, service_status in status_checks.services.items():
        # Skip optional services
        if service_name in _optional_services:
            continue
        
        if service_status.get("status") == StatusCheckValue.DOWN:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            logger.warning(f"Service {service_name} is DOWN - returning 503")
            break
    
    return status_checks
