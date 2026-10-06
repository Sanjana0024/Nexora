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
            "input": input_data,
            "output": "AI processing result",
        }

    async def execute_action(self, node, input_data):

        return {
            "type": "action",
            "message": f"Action '{node.name}' executed",
            "input": input_data,
        }

    async def execute_condition(self, node, input_data):

        expected_value = node.config.get("value")

        actual_value = input_data

        result = actual_value == expected_value

        return {
            "type": "condition",
            "result": result,
            "expected": expected_value,
            "actual": actual_value,
        }