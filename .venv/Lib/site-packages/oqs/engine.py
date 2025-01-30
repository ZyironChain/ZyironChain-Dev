import re
import time
from typing import Callable
from .interpreter import OQSInterpreter
from .errors import OQSBaseError
from .utils.shortcuts import get_oqs_type


class ExpressionInput:
    def __init__(self, expression: str, variables: dict[str, any] | None = None, string_embedded: bool = False) -> None:
        self.expression: str = expression
        self.variables: dict[str, any] = variables
        self.string_embedded: bool = string_embedded


def evaluate_expression(
        expression: str | ExpressionInput,
        variables: dict[str, any] | None = None,
        string_embedded: bool = False,
        additional_functions: list[tuple[str, Callable]] | None = None
) -> dict[str, any]:
    if isinstance(expression, ExpressionInput):
        variables: dict[str, any] | None = expression.variables
        string_embedded: bool = expression.string_embedded
        expression: str = expression.expression
    if additional_functions is None:
        additional_functions: list[tuple[str, Callable]] = []
    try:
        if string_embedded:
            def replace_embedded(match: re.match):
                embedded_expr: str = match.group(1)
                embedded_result: dict[str, any] = evaluate_expression(
                    expression=embedded_expr,
                    variables=variables,
                    string_embedded=False,
                    additional_functions=additional_functions
                )
                return str(embedded_result["results"]["value"])

            result_expression: str = re.sub(r'<\{(.*?)\}>', replace_embedded, expression)
            return {"results": {"value": result_expression, "type": "String"}}

        interpreter: OQSInterpreter = OQSInterpreter(expression=expression, variables=variables)
        for function_name, function in additional_functions:
            interpreter.add_additional_function(function_name=function_name, function=function)
        result: any = interpreter.results()

        return {"results": {"value": result, "type": get_oqs_type(result)}}
    except OQSBaseError as e:
        return {"error": {"type": e.readable_name, "message": str(e)}}
    except Exception as e:
        return {
            "error": {
                "type": "unknown", "message": "An unknown error occurred. Please reach out to our help team immediately"
            },
            "additional_info": {"type": type(e).__name__, "message": str(e)}
        }


def oqs_engine(
        expression: str = None,
        variables: dict[str, any] | None = None,
        string_embedded: bool = False,
        report_usage: bool = False,
        evaluate_multiple: bool = False,
        expression_inputs: list[ExpressionInput] = None,
        additional_functions: list[tuple[str, Callable]] | None = None
) -> dict[str, any]:
    start_cpu_time: int = time.process_time_ns()
    if evaluate_multiple:
        if expression_inputs is None:
            expression_inputs: list[ExpressionInput] = []
        expression_results: list[dict[str, any]] = []
        for expression_input in expression_inputs:
            expression_results.append(evaluate_expression(expression=expression_input))
        results: dict[str, any] = {"results": expression_results}
    else:
        results: dict[str, any] = evaluate_expression(
            expression=expression,
            variables=variables,
            string_embedded=string_embedded,
            additional_functions=additional_functions
        )
    if report_usage:
        results["cpu_time_ns"] = time.process_time_ns() - start_cpu_time
    return results
