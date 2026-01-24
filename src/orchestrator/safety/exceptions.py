"""
Safety-related exceptions.
"""


class SafetyError(Exception):
    """Base exception for safety and input detection errors."""
    
    def __init__(self, message: str):
        """
        Args:
            message: User-facing error message and explanation
        """
        super().__init__(message)


class SafetyViolationError(SafetyError):
    """Raised when safety guard determines user input violates risk policy."""
    
    def __init__(self, message: str, violation_type: str):
        """
        Args:
            message: User-facing explanation of why request was rejected
            violation_type: Tag identifying violation kind (e.g., "harm", "jailbreak", "guardian_unavailable")
        """
        super().__init__(message)
        self.violation_type = violation_type

