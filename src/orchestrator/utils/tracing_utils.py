import logging
import threading
from langfuse import Langfuse
from typing import Optional

from orchestrator.config import app_cfg

logger = logging.getLogger(__name__)


class LangfuseSetupError(Exception):
    """Raised only when Langfuse is enabled but fails to work correctly."""


class LangfuseProvider:
    _instance: Optional[Langfuse] = None
    _lock = threading.Lock()

    @classmethod
    def get_client(cls) -> Langfuse:
        """
        Always returns a valid Langfuse client instance.
        
        - If tracing is disabled: returns a no-op client (safe, zero overhead).
        - If tracing is enabled: ensures client is fully functional;
          raises LangfuseSetupError on any failure.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._initialize_client()
        return cls._instance

    @staticmethod
    def _initialize_client() -> Langfuse:
        """
        Initialize Langfuse client using the built-in tracing_enabled parameter.
        
        When tracing_enabled=False, Langfuse returns a no-op client with all methods
        but zero overhead.
        
        Returns:
            Langfuse client (either active or no-op depending on config)
            
        Raises:
            LangfuseSetupError: Only if tracing is enabled but authentication fails
        """
        tracing_enabled = app_cfg.LANGFUSE_TRACING_ENABLED

        # Create Langfuse client with tracing_enabled parameter
        # When tracing_enabled=False, client becomes a no-op (all methods exist but do nothing)
        client = Langfuse(
            public_key=app_cfg.LANGFUSE_PUBLIC_KEY,
            secret_key=app_cfg.LANGFUSE_SECRET_KEY,
            base_url=app_cfg.LANGFUSE_BASE_URL,
            tracing_enabled=tracing_enabled,
        )

        # Only validate authentication if tracing is actually enabled
        if tracing_enabled:
            try:
                if not client.auth_check():
                    raise LangfuseSetupError(
                        "Langfuse authentication failed. Please verify your LANGFUSE_PUBLIC_KEY "
                        "and LANGFUSE_SECRET_KEY."
                    )
                logger.info("✅ Langfuse client initialized and authenticated.")
            except LangfuseSetupError:
                raise
            except Exception as e:
                # Authentication check itself failed (network, etc.)
                logger.exception("Langfuse authentication check failed")
                raise LangfuseSetupError(f"Failed to verify Langfuse authentication: {e}") from e
        else:
            logger.debug("Langfuse tracing is disabled. Client will operate in no-op mode.")

        return client