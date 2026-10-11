
import asyncio
import ipaddress
import json
import os
import socket
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from google import genai

load_dotenv()


class NodeRuntime:

    async def execute(self, node, input_data=None):
        if node.type == "trigger":
            return await self.execute_trigger(node, input_data)

        if node.type == "ai":
            return await self.execute_ai(node, input_data)

        if node.type == "action":
            return await self.execute_action(node, input_data)

        if node.type == "condition":
            return await self.execute_condition(node, input_data)

        raise ValueError(f"Unsupported node type: {node.type}")

    # --------------------------------------------------
    # TRIGGER NODE
    # --------------------------------------------------

    async def execute_trigger(self, node, input_data=None):
        return {
            "type": "trigger",
            "message": f"Trigger '{node.name}' executed",
            "data": input_data,
        }

    # --------------------------------------------------
    # AI NODE - GEMINI INTEGRATION
    # --------------------------------------------------

    async def execute_ai(self, node, input_data=None):
        config = node.config or {}

        task = config.get("task", "general")
        output_field = config.get("output_field", "result")

        # Use configured mock output for predictable testing.
        if "mock_output" in config:
            result = config["mock_output"]
            simulated = True

        else:
            lead_data = self._find_lead_data(input_data)
            api_key = os.getenv("GEMINI_API_KEY")

            # Use demo output when real input or API key is unavailable.
            if not lead_data or not api_key:
                result = {
                    "score": config.get("test_score", 85),
                    "intent": config.get("test_intent", "buy"),
                }
                simulated = True

            else:
                model = os.getenv(
                    "GEMINI_MODEL",
                    "gemini-2.5-flash",
                )

                client = genai.Client(api_key=api_key)

                prompt = f"""
You are Nexora's AI workflow execution engine.

Task: {task}
Instructions: {config.get("instructions", "")}
Required output field: {output_field}

Analyze this input data:
{json.dumps(lead_data, default=str)}

For lead_scoring, return a score from 0 to 100 and an intent.
Return JSON only, with no Markdown.
"""

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )

                if not response.text:
                    raise ValueError(
                        "Gemini returned an empty AI result"
                    )

                try:
                    result = json.loads(response.text)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "Gemini returned invalid JSON"
                    ) from error

                simulated = False

        if not isinstance(result, dict):
            raise ValueError("AI node must return a JSON object")

        if task == "lead_scoring":
            score = result.get("score")

            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not 0 <= score <= 100
            ):
                raise ValueError(
                    "Lead scoring must return a numeric score from 0 to 100"
                )

        return {
            "type": "ai",
            "message": f"AI node '{node.name}' processed",
            "output": result,
            "simulated": simulated,
        }

    def _find_lead_data(self, input_data):
        if not isinstance(input_data, dict):
            return None

        for parent_output in input_data.values():
            if not isinstance(parent_output, dict):
                continue

            data = parent_output.get("data")

            if isinstance(data, dict) and data:
                return data

            output = parent_output.get("output")

            if isinstance(output, dict) and output:
                return output

        return None

    # --------------------------------------------------
    # WEBHOOK URL VALIDATION
    # --------------------------------------------------

    async def _validate_webhook_url(self, url):
        """
        Allow HTTPS webhook URLs that resolve to public IP addresses.
        Reject local/private destinations and non-default ports.
        """

        if not isinstance(url, str) or not url.strip():
            raise ValueError("Webhook URL is required")

        parsed = urlparse(url)

        if parsed.scheme.lower() != "https":
            raise ValueError("Webhook URLs must use HTTPS")

        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("Invalid webhook URL")

        hostname = parsed.hostname.rstrip(".").lower()

        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError(
                "Local webhook destinations are not allowed"
            )

        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("Invalid webhook port") from error

        if port not in (None, 443):
            raise ValueError(
                "Only the default HTTPS port is allowed"
            )

        # Reject private, loopback, reserved and other non-public IPs.
        try:
            ip = ipaddress.ip_address(hostname)

        except ValueError:
            # Hostname is not a literal IP; resolve its addresses.
            try:
                records = await asyncio.to_thread(
                    socket.getaddrinfo,
                    hostname,
                    443,
                    type=socket.SOCK_STREAM,
                )
            except (socket.gaierror, OSError) as error:
                raise ValueError(
                    "Webhook hostname could not be resolved"
                ) from error

            addresses = {
                record[4][0]
                for record in records
            }

            if not addresses:
                raise ValueError(
                    "Webhook hostname has no valid address"
                )

            for address in addresses:
                try:
                    resolved_ip = ipaddress.ip_address(address)
                except ValueError as error:
                    raise ValueError(
                        "Webhook hostname returned an invalid address"
                    ) from error

                if not resolved_ip.is_global:
                    raise ValueError(
                        "Webhook hostname resolves to a non-public address"
                    )

        else:
            if not ip.is_global:
                raise ValueError(
                    "Webhook destination must be public"
                )

        return url

    # --------------------------------------------------
    # ACTION NODE - WEBHOOK + SIMULATED ACTIONS
    # --------------------------------------------------

    async def execute_action(self, node, input_data=None):
        config = node.config or {}

        if config.get("simulate_failure"):
            raise ValueError("Simulated action failure")

        action_type = config.get(
            "action_type",
            "unspecified",
        )

        # REAL WEBHOOK REQUEST
        if action_type == "webhook":
            url = await self._validate_webhook_url(
                config.get("url")
            )

            # Send the configured payload, or parent-node data
            # when no explicit payload has been configured.
            payload = config.get("payload", input_data)

            timeout = httpx.Timeout(10.0)

            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:

                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json"
                        },
                    )

                    response.raise_for_status()

            except httpx.HTTPStatusError as error:
                raise ValueError(
                    f"Webhook returned HTTP "
                    f"{error.response.status_code}"
                ) from error

            except httpx.RequestError as error:
                raise ValueError(
                    f"Webhook request failed: "
                    f"{type(error).__name__}"
                ) from error

            return {
                "type": "action",
                "message": (
                    "Webhook request completed successfully"
                ),
                "action_type": "webhook",
                "simulated": False,
                "status_code": response.status_code,
            }

        # OTHER ACTIONS ARE STILL SIMULATED
        return {
            "type": "action",
            "message": (
                f"Action '{node.name}' simulated successfully; "
                "no external action was performed"
            ),
            "action_type": action_type,
            "simulated": True,
            "input": input_data,
        }

    # --------------------------------------------------
    # CONDITION NODE
    # --------------------------------------------------

    async def execute_condition(self, node, input_data=None):
        config = node.config or {}

        field = config.get("field")
        operator = config.get("operator")
        expected = config.get("value")

        actual = None

        if isinstance(input_data, dict):
            for parent_output in input_data.values():
                if not isinstance(parent_output, dict):
                    continue

                output = parent_output.get("output")

                if (
                    isinstance(output, dict)
                    and field in output
                ):
                    actual = output[field]
                    break

        if actual is None:
            raise ValueError(
                f"Condition field '{field}' "
                "was not found in parent output"
            )

        comparisons = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
        }

        if operator not in comparisons:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )

        try:
            result = comparisons[operator](
                actual,
                expected,
            )
        except TypeError as error:
            raise ValueError(
                "Condition values have incompatible types"
            ) from error

        return {
            "type": "condition",
            "field": field,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "result": result,
        }
