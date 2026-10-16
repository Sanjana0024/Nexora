
import asyncio
import ipaddress
import json
import os
import socket
from email.message import EmailMessage
from urllib.parse import urlparse

import aiosmtplib
import httpx
from dotenv import load_dotenv
from google import genai

load_dotenv()


class NodeRuntime:

    # --------------------------------------------------
    # MAIN NODE DISPATCHER
    # --------------------------------------------------

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

        # Explicit mock output for predictable testing.
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

                # Run the synchronous Gemini SDK call without blocking
                # the asynchronous event loop.
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
        Basic SSRF safeguards:
        - HTTPS only
        - Default HTTPS port only
        - Reject local and non-public IP destinations
        - Reject URLs containing credentials or fragments
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

        # If the hostname itself is an IP address, validate it directly.
        try:
            ip = ipaddress.ip_address(hostname)

        except ValueError:
            # Otherwise resolve the hostname and check every address.
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
    # ACTION NODE - WEBHOOK, EMAIL, SIMULATED ACTIONS
    # --------------------------------------------------

    async def execute_action(self, node, input_data=None):
        config = node.config or {}

        if config.get("simulate_failure"):
            raise ValueError("Simulated action failure")

        action_type = config.get(
            "action_type",
            "unspecified",
        )

        # --------------------------------------------------
        # REAL WEBHOOK ACTION
        # --------------------------------------------------

        if action_type == "webhook":
            url = await self._validate_webhook_url(
                config.get("url")
            )

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
                "message": "Webhook request completed successfully",
                "action_type": "webhook",
                "simulated": False,
                "status_code": response.status_code,
            }

        # --------------------------------------------------
        # REAL EMAIL ACTION
        # --------------------------------------------------

        if action_type == "email":
            smtp_host = os.getenv("SMTP_HOST")
            smtp_username = os.getenv("SMTP_USERNAME")
            smtp_password = os.getenv("SMTP_PASSWORD")
            from_email = os.getenv("SMTP_FROM_EMAIL")

            try:
                smtp_port = int(os.getenv("SMTP_PORT", "587"))
            except ValueError as error:
                raise ValueError(
                    "SMTP_PORT must be a valid integer"
                ) from error

            if not all([
                smtp_host,
                smtp_username,
                smtp_password,
                from_email,
            ]):
                raise ValueError(
                    "Email SMTP settings are missing from .env"
                )

            recipient = config.get("to")
            subject = config.get("subject")
            body = config.get("body")

            if (
                not isinstance(recipient, str)
                or not recipient.strip()
                or "@" not in recipient
            ):
                raise ValueError(
                    "A valid email recipient is required"
                )

            if not isinstance(subject, str) or not subject.strip():
                raise ValueError("Email subject is required")

            if not isinstance(body, str) or not body.strip():
                raise ValueError("Email body is required")

            message = EmailMessage()
            message["From"] = from_email
            message["To"] = recipient
            message["Subject"] = subject
            message.set_content(body)

            try:
                await aiosmtplib.send(
                    message,
                    hostname=smtp_host,
                    port=smtp_port,
                    username=smtp_username,
                    password=smtp_password,
                    start_tls=True,
                    timeout=10,
                )

            except (
                    aiosmtplib.SMTPException,
                    OSError,
                    TimeoutError,
                ) as error:
                    print(f"SMTP error type: {type(error).__name__}")
                    print(f"SMTP error details: {error!r}")
                    raise ValueError(
                        f"Email sending failed: {type(error).__name__}: {error}"
                    ) from error

            return {
                "type": "action",
                "message": "Email accepted by the SMTP server",
                "action_type": "email",
                "simulated": False,
            }

        # --------------------------------------------------
        # OTHER ACTIONS - SIMULATED FOR NOW
        # --------------------------------------------------

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

        def find_field(data, field_name):
            """Find a condition field inside nested AI output."""
            if not isinstance(data, dict):
                return None

            # Direct match, e.g. {"score": 92}
            if field_name in data:
                return data[field_name]

            # Common nested AI response, e.g.
            # {"result": {"score": 92}}
            for key in ("result", "output", "data"):
                nested = data.get(key)
                if isinstance(nested, dict):
                    value = find_field(nested, field_name)
                    if value is not None:
                        return value

            return None

        actual = None

        if isinstance(input_data, dict):
            for parent_output in input_data.values():
                if not isinstance(parent_output, dict):
                    continue

                # The AI node wraps its result in "output".
                value = find_field(parent_output.get("output"), field)

                # Also support a field directly on the parent output.
                if value is None:
                    value = find_field(parent_output, field)

                if value is not None:
                    actual = value
                    break

        # Support either "score" or "lead_score" as a field name.
        if actual is None and field in ("score", "lead_score"):
            alternate_field = (
                "lead_score" if field == "score" else "score"
            )

            if isinstance(input_data, dict):
                for parent_output in input_data.values():
                    if not isinstance(parent_output, dict):
                        continue

                    value = find_field(
                        parent_output.get("output"),
                        alternate_field,
                    )

                    if value is None:
                        value = find_field(parent_output, alternate_field)

                    if value is not None:
                        actual = value
                        break

        if actual is None:
            raise ValueError(
                f"Condition field '{field}' was not found in parent output"
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
            raise ValueError(f"Unsupported operator: {operator}")

        try:
            result = comparisons[operator](actual, expected)
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
