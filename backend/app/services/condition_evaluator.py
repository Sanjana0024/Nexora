class ConditionEvaluator:

    def evaluate(self, value, operator, expected):

        if operator == "==":
            return value == expected

        if operator == "!=":
            return value != expected

        if operator == ">":
            return value > expected

        if operator == ">=":
            return value >= expected

        if operator == "<":
            return value < expected

        if operator == "<=":
            return value <= expected

        raise ValueError(
            f"Unsupported operator: {operator}"
        )