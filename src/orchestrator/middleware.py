import logging
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from asgi_correlation_id.middleware import CorrelationIdMiddleware

logger = logging.getLogger(__name__)


class ClientIPLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log client IP, user agent, and request path."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log client information."""
        client_ip = self._get_real_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        path = request.url.path
        method = request.method
        
        response = await call_next(request)
        logger.info(
            f"client_ip={client_ip} "
            f"user_agent={user_agent} "
            f"method={method} "
            f"path={path} "
            f"status={response.status_code}"
        )
        return response
    
    def _get_real_client_ip(self, request: Request) -> str:
        """Extract the real client IP from forwarded headers."""
        # Check True-Client-IP header
        true_client_ip = request.headers.get("true-client-ip")
        if true_client_ip:
            return true_client_ip.strip()
        
        # Check X-Forwarded-For header (may contain multiple IPs)
        forwarded_for_ips = request.headers.get("x-forwarded-for")
        if forwarded_for_ips:
            # First IP is the original client
            return forwarded_for_ips.split(",")[0].strip()
        
        # Check other common headers
        for header in ["x-real-ip", "x-client-ip"]:
            client_ip = request.headers.get(header)
            if client_ip:
                return client_ip.strip()
        
        return request.client.host if request.client else "unknown"


def configure_middleware(api: FastAPI) -> FastAPI:
    api.add_middleware(ClientIPLoggingMiddleware)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    api.add_middleware(CorrelationIdMiddleware)
    
    logger.info("Middleware configured successfully")
    
    return api

