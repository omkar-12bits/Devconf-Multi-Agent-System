import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions globally.
    
    This catches any exception that wasn't handled by specific endpoints
    and returns a generic 500 error to the client while logging the details.
    
    Args:
        request: The FastAPI request object
        exc: The unhandled exception
        
    Returns:
        JSONResponse with 500 status code
    """
    logger.error(
        f"Unhandled exception occurred",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc)
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred",
            "path": request.url.path
        }
    )

