import asyncio


class RetryHandler:

    async def execute_with_retry(
        self,
        function,
        retry_count=0,
    ):

        attempts = retry_count + 1

        last_error = None

        for attempt in range(1, attempts + 1):

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
                    f"Attempt {attempt} failed: {error}"
                )

                if attempt < attempts:

                    await asyncio.sleep(1)

        return {
            "success": False,
            "attempts": attempts,
            "error": str(last_error),
        }