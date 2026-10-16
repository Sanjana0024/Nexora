
import asyncio
import random


class RetryHandler:
    def __init__(
        self,
        base_delay=2,
        max_delay=15,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay

    def is_retryable(self, error):
        """Identify temporary errors that may succeed on retry."""
        message = str(error).lower()

        retryable_patterns = [
            "503",
            "unavailable",
            "429",
            "resource_exhausted",
            "rate limit",
            "too many requests",
            "500",
            "502",
            "504",
            "internal server error",
            "temporarily unavailable",
            "timed out",
            "timeout",
            "connection reset",
            "connection refused",
            "network error",
        ]

        return any(
            pattern in message
            for pattern in retryable_patterns
        )

    async def execute_with_retry(
        self,
        function,
        retry_count=0,
    ):
        max_attempts = max(1, retry_count + 1)
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                result = await function()

                return {
                    "success": True,
                    "attempts": attempt,
                    "result": result,
                }

            except Exception as error:
                last_error = error

                print(
                    f"Attempt {attempt}/{max_attempts} failed: "
                    f"{type(error).__name__}: {error}"
                )

                # Stop immediately for permanent errors.
                if not self.is_retryable(error):
                    break

                # Stop when no attempts remain.
                if attempt >= max_attempts:
                    break

                # Exponential backoff with a small random delay.
                delay = min(
                    self.base_delay * (2 ** (attempt - 1)),
                    self.max_delay,
                )
                delay += random.uniform(0, 0.5)

                print(
                    f"Retrying in {delay:.1f} seconds..."
                )

                await asyncio.sleep(delay)

        return {
            "success": False,
            "attempts": attempt,
            "error": str(last_error),
        }
