"""
Predefined responses for safety violations.
"""


class PredefinedResponses:
    """Predefined canned responses for safety violations."""
    
    DEFAULT_SAFETY_VIOLATION_MESSAGE: str = (
        "I can't answer that. This query appears to violate our content policy. "
        "Please ask a relevant question about Red Hat products, services, or support."
    )
    
    GUARDIAN_UNAVAILABLE_MESSAGE: str = (
        "I'm unable to process your request at this time due to a service issue. "
        "Please try again later."
    )

