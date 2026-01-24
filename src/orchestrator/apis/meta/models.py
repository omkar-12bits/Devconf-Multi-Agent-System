from pydantic import BaseModel


class HealthCheck(BaseModel):
    """Response model to inform health status of API (is it up?)"""
    status: str = "OK"


class StatusCheckValue:
    """Represents the allowed values for each service status"""
    OK: str = "OK"
    DOWN: str = "Down"
    DISABLED: str = "Disabled"


class StatusChecks(BaseModel):
    """Response model for returning the status of major dependencies"""
    services: dict
