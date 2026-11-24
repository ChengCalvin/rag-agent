"""Settings shared by the five agent builders (private to `agents/`)."""

from google.adk.workflow import RetryConfig

from novamart_agent.config import Settings

# Model failures worth retrying: rate limits and transient outages (ARCH-ERR-1). The node retry
# policy re-runs the agent; if it still fails the turn fails visibly, with no invented reply.
_RETRYABLE = ["ClientError", "ServerError"]


def model_retry(settings: Settings) -> RetryConfig:
    """The node retry policy for an agent; attempts and the first delay come from configuration."""
    return RetryConfig(
        max_attempts=settings.pipeline.model_retry_attempts,
        initial_delay=float(settings.pipeline.model_retry_delay_seconds),
        exceptions=list(_RETRYABLE),
    )
