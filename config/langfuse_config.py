"""Langfuse configuration and instrumentation setup for Frame AI."""

import os
from typing import Optional
from dotenv import load_dotenv
from langfuse import Langfuse
from config.logger import get_logger

load_dotenv(override=True)
logger = get_logger(__name__)


class LangfuseConfig:
    """Configuration manager for Langfuse integration."""

    def __init__(self):
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self.host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self.enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        self._client: Optional[Langfuse] = None

    @property
    def is_configured(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(self.public_key and self.secret_key and self.enabled)

    def get_client(self) -> Optional[Langfuse]:
        """Get or create Langfuse client instance."""
        if not self.is_configured:
            logger.warning(
                "Langfuse is not configured. Set LANGFUSE_ENABLED=true and provide API keys."
            )
            return None

        if self._client is None:
            try:
                # Initialize with optimized settings for better performance
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                    debug=False,  # Suppress debug output
                    flush_interval=1.0,  # Flush more frequently
                )
                logger.info(
                    f"Langfuse client initialized successfully (host: {self.host})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse client: {e}")
                return None

        return self._client

    def flush(self):
        """Flush any pending traces to Langfuse."""
        if self._client:
            try:
                self._client.flush()
                logger.debug("Langfuse traces flushed successfully")
            except Exception as e:
                logger.error(f"Failed to flush Langfuse traces: {e}")


# Global instance
langfuse_config = LangfuseConfig()
