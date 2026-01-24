import logging
from typing import Callable, Awaitable
from orchestrator.apis.meta.models import StatusCheckValue

logger = logging.getLogger(__name__)


class StatusCheck:
    """Registry for status check functions."""
    
    _checks: dict[str, Callable[[], Awaitable[dict]]] = {}
    
    @classmethod
    def register(cls, name: str, func: Callable[[], Awaitable[dict]]):
        """Register a status check function."""
        cls._checks[name] = func
        logger.debug(f"Registered status check: {name}")
    
    @classmethod
    async def run(cls, request=None) -> dict:
        """Run all registered status checks."""
        results = {}
        
        for name, check_func in cls._checks.items():
            try:
                import time
                start = time.time()
                
                # Pass request if check function needs it
                import inspect
                sig = inspect.signature(check_func)
                if 'request' in sig.parameters and request:
                    check_result = await check_func(request)
                else:
                    check_result = await check_func()
                
                response_time = (time.time() - start) * 1000
                
                results[name] = {
                    "status": check_result.get("status", StatusCheckValue.DOWN)
                }
            except Exception as e:
                logger.error(f"Status check failed for {name}: {e}")
                results[name] = {
                    "status": StatusCheckValue.DOWN
                }
        
        return results


def status_check(name: str):
    """
    Decorator to register a status check function.
    
    Usage:
        @status_check(name="my_service")
        async def my_service_status() -> dict:
            return {"status": StatusCheckValue.OK}
    """
    def decorator(func: Callable[[], Awaitable[dict]]):
        StatusCheck.register(name, func)
        return func
    return decorator
