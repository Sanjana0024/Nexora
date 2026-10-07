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

        raise ValueError(
            f"Unsupported node type: {node.type}"
        )

    async def execute_trigger(self, node, input_data):

        return {
            "type": "trigger",
            "message": f"Trigger '{node.name}' executed",
            "data": input_data,
        }

    async def execute_ai(self, node, input_data):

        return {
            "type": "ai",
            "message": f"AI node '{node.name}' executed",
            "output": {
                "score": 85,
                "intent": "buy",
            },
        }

    async def execute_action(self, node, input_data):

        return {
            "type": "action",
            "message": f"Action '{node.name}' executed",
            "input": input_data,
        }

    async def execute_condition(self, node, input_data):

        field = node.config.get("field")
        operator = node.config.get("operator")
        expected = node.config.get("value")

        actual = None

        if isinstance(input_data, dict):

            for parent_output in input_data.values():

                if not isinstance(parent_output, dict):
                    continue

                output = parent_output.get("output")

                if isinstance(output, dict):
                    actual = output.get(field)

                    if actual is not None:
                        break

        if actual is None:
            raise ValueError(
                f"Condition field '{field}' was not found"
            )

        if operator == "==":
            result = actual == expected

        elif operator == "!=":
            result = actual != expected

        elif operator == ">":
            result = actual > expected

        elif operator == ">=":
            result = actual >= expected

        elif operator == "<":
            result = actual < expected

        elif operator == "<=":
            result = actual <= expected

        else:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )

        return {
            "type": "condition",
            "field": field,
            "operator": operator,
            "expected": expected,
            "actual": actual,
            "result": result,
        }
    async def execute_action(self, node, input_data):

        if node.config.get("simulate_failure"):

            raise ValueError(
                "Simulated action failure"
            )

        return {
            "type": "action",
            "message": f"Action '{node.name}' executed",
            "input": input_data,
        }