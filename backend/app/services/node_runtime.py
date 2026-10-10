
import json
import os

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

    async def execute_trigger(self, node, input_data=None):
        return {
            "type": "trigger",
            "message": f"Trigger '{node.name}' executed",
            "data": input_data,
        }

    async def execute_ai(self, node, input_data=None):
        config = node.config or {}
        task = config.get("task", "general")
        output_field = config.get("output_field", "result")

        # Prefer explicitly configured test output for predictable tests.
        if "mock_output" in config:
            result = config["mock_output"]
            simulated = True

        else:
            lead_data = self._find_lead_data(input_data)
            api_key = os.getenv("GEMINI_API_KEY")

            # Without real lead data, use a clearly marked demo score.
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

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                )

                if not response.text:
                    raise ValueError("Gemini returned an empty AI result")

                result = json.loads(response.text)
                simulated = False

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

    async def execute_action(self, node, input_data=None):
        config = node.config or {}

        if config.get("simulate_failure"):
            raise ValueError("Simulated action failure")

        return {
            "type": "action",
            "message": (
                f"Action '{node.name}' simulated successfully; "
                "no external action was performed"
            ),
            "action_type": config.get("action_type", "unspecified"),
            "simulated": True,
            "input": input_data,
        }

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

                if isinstance(output, dict) and field in output:
                    actual = output[field]
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
