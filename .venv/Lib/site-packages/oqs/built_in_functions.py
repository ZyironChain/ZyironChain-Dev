import datetime
import json
import re
from .constants.values import MAX_ARGS
from .errors import (
    OQSInvalidArgumentQuantityError,
    OQSDivisionByZeroError,
    OQSTypeError,
    OQSFunctionEvaluationError,
    OQSBaseError,
    OQSCustomErrorParent,
    OQSValueError,
    get_error_name_mapping
)
from .nodes import (FunctionNode, ASTNode)
from .utils.checks import ensure_function_arg_quantity
from .utils.conversion import OQSJSONEncoder
from .utils.shortcuts import (get_oqs_type, is_oqs_instance)


def bif_add(
        interpreter: 'OQSInterpreter', node: FunctionNode
) -> int | float | list | str | dict | datetime.datetime | datetime.date | datetime.time | datetime.timedelta:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: list[any] = [interpreter.evaluate(arg) for arg in node.args]
    completion: any = evaluated_args.pop(0)
    for evaluated_arg in evaluated_args:
        if isinstance(completion, (int, float)) and isinstance(evaluated_arg, (int, float)):
            completion += evaluated_arg
        elif isinstance(completion, list) and isinstance(evaluated_arg, list):
            completion += evaluated_arg
        elif isinstance(completion, str) and isinstance(evaluated_arg, str):
            completion += evaluated_arg
        elif isinstance(completion, dict) and isinstance(evaluated_arg, dict):
            for key, value in evaluated_arg.items():
                completion[key] = value
        elif (
            isinstance(completion, datetime.datetime) and isinstance(evaluated_arg, datetime.timedelta)
        ) or (
            isinstance(completion, datetime.date) and isinstance(evaluated_arg, datetime.timedelta)
        ) or (
            isinstance(completion, datetime.timedelta) and isinstance(
                evaluated_arg, (datetime.datetime, datetime.date, datetime.timedelta)
            )
        ):
            completion += evaluated_arg
        elif (
            isinstance(completion, datetime.time) and isinstance(evaluated_arg, datetime.timedelta)
        ) or (
            isinstance(completion, datetime.timedelta) and isinstance(evaluated_arg, datetime.time)
        ):
            completion, evaluated_arg = (completion, evaluated_arg) if isinstance(
                completion, datetime.time
            ) else (evaluated_arg, completion)
            time_seconds: int = (completion.hour * 3600) + (completion.minute * 60) + completion.second
            total_seconds: int = time_seconds + evaluated_arg.seconds
            new_time: datetime.time = (datetime.datetime.min + datetime.timedelta(seconds=total_seconds)).time()
            completion: datetime.time = new_time
        else:
            raise OQSTypeError(message=f"Cannot add '{get_oqs_type(completion)}' and '{get_oqs_type(evaluated_arg)}'")
    return completion


def bif_subtract(
        interpreter: 'OQSInterpreter', node: FunctionNode
) -> int | float | list | str | datetime.datetime | datetime.date | datetime.time | datetime.timedelta:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    a, b = [interpreter.evaluate(arg) for arg in node.args]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a - b
    elif isinstance(a, list) and isinstance(b, list):
        return [item for item in a if item not in b]
    elif isinstance(a, str) and isinstance(b, str):
        return a.replace(b, '')
    elif isinstance(a, datetime.datetime) and isinstance(b, datetime.timedelta):
        return a - b
    elif isinstance(a, datetime.date) and isinstance(b, datetime.timedelta):
        return a - b
    elif isinstance(a, datetime.time) and isinstance(b, datetime.timedelta):
        time_seconds_a: int = (a.hour * 3600) + (a.minute * 60) + a.second
        total_seconds: int = time_seconds_a - b.seconds
        if total_seconds < 0:
            raise OQSValueError(message="Resulting time is negative, which is not supported for datetime.time objects.")
        new_time: datetime.time = (datetime.datetime.min + datetime.timedelta(seconds=total_seconds)).time()
        return new_time
    elif isinstance(a, datetime.timedelta) and isinstance(b, datetime.timedelta):
        return a - b
    elif isinstance(a, datetime.datetime) and isinstance(b, datetime.datetime):
        return a - b
    elif isinstance(a, datetime.date) and isinstance(b, datetime.date):
        return a - b
    else:
        raise OQSTypeError(message=f"Cannot subtract '{get_oqs_type(a)}' by '{get_oqs_type(b)}'")


def bif_multiply(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float | list | str:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: list[any] = [interpreter.evaluate(arg) for arg in node.args]
    completion: any = evaluated_args.pop(0)
    for evaluated_arg in evaluated_args:
        if isinstance(completion, (int, float)) and isinstance(evaluated_arg, (int, float)):
            completion *= evaluated_arg
        elif (
                isinstance(completion, list) and isinstance(evaluated_arg, int)
        ) or (isinstance(completion, int) and isinstance(evaluated_arg, list)):
            lst, multiplier = (completion, evaluated_arg) if isinstance(
                completion, list
            ) else (evaluated_arg, completion)
            if multiplier > 1:
                for i in range(multiplier - 1):
                    lst.extend(lst)
            return lst
        elif (
                isinstance(completion, str) and isinstance(evaluated_arg, int)
        ) or (isinstance(completion, int) and isinstance(evaluated_arg, str)):
            string, multiplier = (completion, evaluated_arg) if isinstance(
                completion, str
            ) else (evaluated_arg, completion)
            return string * multiplier

        else:
            raise OQSTypeError(
                message=f"Cannot multiply '{get_oqs_type(completion)}' and '{get_oqs_type(evaluated_arg)}'"
            )
    return completion


def bif_divide(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    a, b = [interpreter.evaluate(arg) for arg in node.args]
    if b == 0:
        raise OQSDivisionByZeroError()
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        results: float = a / b
        if isinstance(a, int) and isinstance(b, int) and results == int(results):
            return int(results)
        return results
    else:
        raise OQSTypeError(message=f"Cannot divide type '{get_oqs_type(a)}' by type '{get_oqs_type(b)}'.")


def bif_exponentiate(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float | complex:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    base, exponent = [interpreter.evaluate(arg) for arg in node.args]
    if isinstance(base, (int, float)) and isinstance(exponent, (int, float)):
        return pow(base, exponent)
    else:
        raise OQSTypeError(
            message=f"Cannot exponentiate type '{get_oqs_type(base)}' by type '{get_oqs_type(exponent)}'."
        )


def bif_modulo(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    a, b = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(a, int) or not isinstance(b, int):
        raise OQSTypeError(message=f"Cannot perform modulo on types '{get_oqs_type(a)}' and '{get_oqs_type(b)}'")
    return a % b


def bif_less_than(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if (
                isinstance(left, (int, float)) and isinstance(right, (int, float))
            ) or (
                isinstance(left, datetime.datetime) and isinstance(right, datetime.datetime)
            ) or (
                isinstance(left, datetime.date) and isinstance(right, datetime.date)
            ) or (
                isinstance(left, datetime.time) and isinstance(right, datetime.time)
            ) or (
                isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta)
            ):
                if not left < right:
                    return False
            else:
                raise OQSTypeError(
                    message=f"Cannot evaluated if type '{get_oqs_type(left)}' is less than "
                            f"type '{get_oqs_type(right)}'."
                )
    return True


def bif_greater_than(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if (
                    isinstance(left, (int, float)) and isinstance(right, (int, float))
            ) or (
                    isinstance(left, datetime.datetime) and isinstance(right, datetime.datetime)
            ) or (
                    isinstance(left, datetime.date) and isinstance(right, datetime.date)
            ) or (
                    isinstance(left, datetime.time) and isinstance(right, datetime.time)
            ) or (
                    isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta)
            ):
                if not left > right:
                    return False
            else:
                raise OQSTypeError(
                    message=f"Cannot evaluated if type '{get_oqs_type(left)}' is greater than "
                            f"type '{get_oqs_type(right)}'."
                )
    return True


def bif_less_than_or_equal(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if (
                    isinstance(left, (int, float)) and isinstance(right, (int, float))
            ) or (
                    isinstance(left, datetime.datetime) and isinstance(right, datetime.datetime)
            ) or (
                    isinstance(left, datetime.date) and isinstance(right, datetime.date)
            ) or (
                    isinstance(left, datetime.time) and isinstance(right, datetime.time)
            ) or (
                    isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta)
            ):
                if not left <= right:
                    return False
            else:
                raise OQSTypeError(
                    message=f"Cannot evaluated if type '{get_oqs_type(left)}' is less than or equal to "
                            f"type '{get_oqs_type(right)}'."
                )
    return True


def bif_greater_than_or_equal(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if (
                    isinstance(left, (int, float)) and isinstance(right, (int, float))
            ) or (
                    isinstance(left, datetime.datetime) and isinstance(right, datetime.datetime)
            ) or (
                    isinstance(left, datetime.date) and isinstance(right, datetime.date)
            ) or (
                    isinstance(left, datetime.time) and isinstance(right, datetime.time)
            ) or (
                    isinstance(left, datetime.timedelta) and isinstance(right, datetime.timedelta)
            ):
                if not left >= right:
                    return False
            else:
                raise OQSTypeError(
                    message=f"Cannot evaluated if type '{get_oqs_type(left)}' is greater than or equal to "
                            f"type '{get_oqs_type(right)}'."
                )
    return True


def bif_equals(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if not left == right:
                return False
    return True


def bif_not_equals(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if not left != right:
                return False
    return True


def bif_strictly_equals(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if not (left == right and type(left) == type(right)):
                return False
    return True


def bif_strictly_not_equals(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=2)
    evaluated_args: dict[int, any] = {}
    for i, arg in enumerate(node.args):
        if len(node.args) > i + 1:
            if i in evaluated_args:
                left: any = evaluated_args[i]
            else:
                left: any = interpreter.evaluate(node.args[i])
                evaluated_args[i] = left
            if i + 1 in evaluated_args:
                right: any = evaluated_args[i + 1]
            else:
                right: any = interpreter.evaluate(node.args[i + 1])
                evaluated_args[i + 1] = right
            if not (left != right or type(left) != type(right)):
                return False
    return True


def bif_and(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=2)
    for arg in node.args:
        if not interpreter.evaluate(arg):
            return False
    return True


def bif_or(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=2)
    for arg in node.args:
        if interpreter.evaluate(arg):
            return True
    return False


def bif_not(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    return not bool(value)


def bif_integer(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    if not isinstance(value, (int, float, str)):
        raise OQSTypeError(message=f"Cannot convert type '{get_oqs_type(value)}' to integer")
    return int(value)


def bif_decimal(interpreter: 'OQSInterpreter', node: FunctionNode) -> float:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    if not isinstance(value, (int, float, str)):
        raise OQSTypeError(message=f"Cannot convert type '{get_oqs_type(value)}' to float")
    return float(value)


def bif_string(interpreter: 'OQSInterpreter', node: FunctionNode) -> str:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    return json.dumps(value, cls=OQSJSONEncoder)


def bif_list(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    return [interpreter.evaluate(arg) for arg in node.args]


def bif_kvs(interpreter: 'OQSInterpreter', node: FunctionNode) -> dict[str, any]:
    if len(node.args) % 2 != 0:
        raise OQSInvalidArgumentQuantityError(
            function_name=node.name, expected_min=2, expected_max=MAX_ARGS, actual=len(node.args)
        )
    kvs: dict[str, any] = {}
    for i in range(0, len(node.args), 2):
        key: any = interpreter.evaluate(node.args[i])
        if not isinstance(key, str):
            raise OQSTypeError(message='Key must be a string')
        value: any = interpreter.evaluate(node.args[i + 1])
        kvs[key] = value
    return kvs


def bif_boolean(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    return bool(value)


def bif_keys(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[str]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    kvs: any = interpreter.evaluate(node.args[0])
    if not isinstance(kvs, dict):
        raise OQSTypeError(message='Argument must be a KVS')
    return list(kvs.keys())


def bif_values(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    kvs: any = interpreter.evaluate(node.args[0])
    if not isinstance(kvs, dict):
        raise OQSTypeError(message='Argument must be a KVS')
    return list(kvs.values())


def bif_unique(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    lst: any = interpreter.evaluate(node.args[0])
    if not isinstance(lst, list):
        raise OQSTypeError(message='Argument must be a list')
    return list(set(lst))


def bif_reverse(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    lst: any = interpreter.evaluate(node.args[0])
    if not isinstance(lst, list):
        raise OQSTypeError(message='Argument must be a list')
    return lst[::-1]


def bif_max(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float:
    ensure_function_arg_quantity(node=node, min_args=1)
    numbers: list[any] = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(item, (int, float)) for item in numbers):
        raise OQSTypeError(message="All arguments must be numbers for 'max'")
    return max(numbers)


def bif_min(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float:
    ensure_function_arg_quantity(node=node, min_args=1)
    numbers: list[any] = [interpreter.evaluate(arg) for arg in node.args]
    return min(numbers)


def bif_sum(interpreter: 'OQSInterpreter', node: FunctionNode) -> int | float:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    lst: any = interpreter.evaluate(node.args[0])
    if not isinstance(lst, list) or not all(isinstance(item, (int, float)) for item in lst):
        raise OQSTypeError(message='Argument must be a list of numbers')
    return sum(lst)


def bif_length(interpreter: 'OQSInterpreter', node: FunctionNode) -> int:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    value: any = interpreter.evaluate(node.args[0])
    if not isinstance(value, (str, list, dict)):
        raise OQSTypeError(message="Argument must be a string, list or KVS")
    return len(value)


def bif_append(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    lst, item = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(lst, list):
        raise OQSTypeError(message="First argument must be a list")
    lst.append(item)
    return lst


def bif_update(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any] | dict[str, any]:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=3)
    container, key_or_index, value = [interpreter.evaluate(arg) for arg in node.args]
    if isinstance(container, list):
        if not isinstance(key_or_index, int):
            raise OQSTypeError(message="Index must be an integer")
        key_or_index: int = key_or_index % len(container)
        if key_or_index < 0 or key_or_index >= len(container):
            raise IndexError("List index out of range")
        container[key_or_index] = value
    elif isinstance(container, dict):
        if not isinstance(key_or_index, str):
            raise OQSTypeError(message="Key must be a string")
        container[key_or_index] = value
    else:
        raise OQSTypeError(message="First argument must be a list or KVS")
    return container


def bif_remove_item(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any] | dict[str, any]:
    ensure_function_arg_quantity(node=node, min_args=2)
    container, item = [interpreter.evaluate(arg) for arg in node.args[:2]]
    max_occurrences: int = interpreter.evaluate(node.args[2]) if len(node.args) == 3 else MAX_ARGS
    if not isinstance(max_occurrences, int):
        raise OQSTypeError(message="Third argument must be an Integer")
    if isinstance(container, list):
        new_list: list[str, any] = []
        for elem in container:
            if elem == item and max_occurrences > 0:
                max_occurrences -= 1
                continue
            new_list.append(elem)
        return new_list
    elif isinstance(container, dict):
        if item in container:
            del container[item]
        return container
    else:
        raise OQSTypeError(message="First argument must be a list or KVS")


def bif_remove(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any] | dict[str, any]:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    container, key_or_index = [interpreter.evaluate(arg) for arg in node.args]
    if isinstance(container, list):
        if not isinstance(key_or_index, int):
            raise OQSTypeError(message="Index must be an integer")
        if key_or_index < 0 or key_or_index >= len(container):
            raise IndexError("List index out of range")
        del container[key_or_index]
    elif isinstance(container, dict):
        if not isinstance(key_or_index, str):
            raise OQSTypeError(message="Key must be a string")
        container.pop(key_or_index, None)
    else:
        raise OQSTypeError(message="First argument must be a list or KVS")
    return container


def bif_access(interpreter: 'OQSInterpreter', node: FunctionNode):
    ensure_function_arg_quantity(node=node, min_args=2)
    container, key_or_index = [interpreter.evaluate(arg) for arg in node.args[:2]]
    default_value = interpreter.evaluate(node.args[2]) if len(node.args) == 3 else None
    if isinstance(container, list):
        if not isinstance(key_or_index, int):
            raise OQSTypeError(message="Index must be an integer")
        if key_or_index < 0 or key_or_index >= len(container):
            raise IndexError("List index out of range")
        return container[key_or_index]
    elif isinstance(container, dict):
        return container.get(key_or_index, default_value)
    else:
        raise OQSTypeError(message="First argument must be a list or KVS")


def bif_if(interpreter: 'OQSInterpreter', node: FunctionNode) -> any:
    ensure_function_arg_quantity(node=node, min_args=2)
    for i in range(0, len(node.args) - 1, 2):
        condition: any = interpreter.evaluate(node.args[i])
        if condition:
            return interpreter.evaluate(node.args[i + 1])
    if len(node.args) % 2 != 0:
        return interpreter.evaluate(node.args[-1])
    return None


def bif_type(interpreter: 'OQSInterpreter', node: FunctionNode) -> str:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    argument: any = interpreter.evaluate(node.args[0])
    return get_oqs_type(argument)


def bif_is_type(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    value, expected_type = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(expected_type, str):
        raise OQSTypeError(message=f"Second argument must be a String. Instead got '{get_oqs_type(expected_type)}'.")
    return is_oqs_instance(value, expected_type)


def bif_try(interpreter: 'OQSInterpreter', node: FunctionNode) -> any:
    ensure_function_arg_quantity(node=node, min_args=3)
    if len(node.args) % 2 == 0:
        raise OQSFunctionEvaluationError(
            function_name=node.name, message=f"Expected an odd amount of input arguments. Instead got {len(node.args)}."
        )
    arguments: list[ASTNode] = node.args.copy()
    primary_expression: ASTNode = arguments.pop(0)

    try:
        return interpreter.evaluate(primary_expression)
    except OQSBaseError as error:
        for i in range(0, len(arguments) - 1, 2):
            exception: any = interpreter.evaluate(arguments[i])
            if not isinstance(exception, str):
                raise OQSTypeError(
                    message=f"Even argument must be a String. Instead got '{get_oqs_type(exception)}'."
                )
            if exception in error.error_hierarchy:
                return interpreter.evaluate(arguments[i + 1])
        raise


def bif_range(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[int]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=3)
    start: int = 0
    step: int = 1
    stop: int = 1
    if len(node.args) == 1:
        stop: any = interpreter.evaluate(node.args[0])
    elif len(node.args) == 2:
        start, stop = [interpreter.evaluate(arg) for arg in node.args]
    elif len(node.args) == 3:
        start, stop, step = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(start, int):
        raise OQSTypeError(message=f"start argument must be an Integer. Instead got '{get_oqs_type(start)}'.")
    elif not isinstance(stop, int):
        raise OQSTypeError(message=f"stop argument must be an Integer. Instead got '{get_oqs_type(stop)}'.")
    elif not isinstance(step, int):
        raise OQSTypeError(message=f"step argument must be an Integer. Instead got '{get_oqs_type(step)}'.")
    return list(range(start, stop, step))


def bif_for_or_map(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=3)
    looping_list: any = interpreter.evaluate(node.args[0])
    variable_name: any = interpreter.evaluate(node.args[1])
    expression: ASTNode = node.args[2]
    if not isinstance(looping_list, list):
        raise OQSTypeError(message=f"list argument must be a List. Instead got '{get_oqs_type(looping_list)}'.")
    elif not isinstance(variable_name, str):
        raise OQSTypeError(
            message=f"variable_name argument must be a String. Instead got '{get_oqs_type(variable_name)}'."
        )
    resulting_list: list[any] = []
    for item in looping_list:
        interpreter.variables[variable_name] = item
        evaluated_expression: any = interpreter.evaluate(expression)
        resulting_list.append(evaluated_expression)

    return resulting_list


def bif_raise(interpreter: 'OQSInterpreter', node: FunctionNode) -> any:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    error_name, error_message = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(error_name, str):
        raise OQSTypeError(
            message=f"error_name argument must be a String. Instead got '{get_oqs_type(error_name)}'."
        )
    elif not isinstance(error_message, str):
        raise OQSTypeError(
            message=f"error_message argument must be a String. Instead got '{get_oqs_type(error_message)}'."
        )
    error_name_mapping: dict[str, type[OQSBaseError]] = get_error_name_mapping()
    if error_name.upper() in error_name_mapping:
        raise error_name_mapping[error_name.upper()](message=error_message)
    else:
        class CustomError(OQSCustomErrorParent):
            READABLE_NAME: str = error_name

            def __init__(self):
                super().__init__(message=error_message)
        raise CustomError()


def bif_filter(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any] | dict[str, any]:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=3)
    collection, unevaluated_variable_name, predicate = node.args
    collection_value: any = interpreter.evaluate(collection)
    if not isinstance(collection_value, (list, dict)):
        raise OQSTypeError(
            message=f"FILTER function requires a List or KVS as the first argument. "
                    f"Instead got '{get_oqs_type(collection_value)}'."
        )
    evaluated_variable_name: any = interpreter.evaluate(unevaluated_variable_name)
    if not isinstance(evaluated_variable_name, str):
        raise OQSTypeError(
            message=f"FILTER function requires a String as the second argument. "
                    f"Instead got '{get_oqs_type(evaluated_variable_name)}'. "
        )
    filtered_result: dict[str, any] | list[any] = collection_value.copy()
    if isinstance(collection_value, list):
        for item in collection_value:
            interpreter.variables[evaluated_variable_name] = item
            if not interpreter.evaluate(predicate):
                filtered_result.remove(item)
    else:
        for key, value in collection_value.items():
            interpreter.variables[evaluated_variable_name] = value
            if not interpreter.evaluate(predicate):
                del filtered_result[key]
    return filtered_result


def bif_sort(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=4)
    collection, unevaluated_variable_name, key_expression = node.args[:3]
    descending: bool = interpreter.evaluate(node.args[3]) if len(node.args) == 4 else False

    collection_value: any = interpreter.evaluate(collection)
    if not isinstance(collection_value, list):
        raise OQSTypeError(
            message=f"SORT function requires a list as the first argument. "
                    f"Instead got '{get_oqs_type(collection_value)}'. "
        )

    evaluated_variable_name: any = interpreter.evaluate(unevaluated_variable_name)
    if not isinstance(evaluated_variable_name, str):
        raise OQSTypeError(
            message=f"SORT function requires a String as the second argument. "
                    f"Instead got '{get_oqs_type(evaluated_variable_name)}'. "
        )

    def evaluate_expression_with_variable(item: any) -> any:
        interpreter.variables[evaluated_variable_name] = item
        return interpreter.evaluate(key_expression)

    sorted_collection = sorted(collection_value, key=evaluate_expression_with_variable, reverse=descending)
    return sorted_collection


def bif_flatten(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any]:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    list_to_flatten: any = interpreter.evaluate(node.args[0])
    if not isinstance(list_to_flatten, list):
        raise OQSTypeError(
            message=f"FLATTEN function requires a list as the argument. Instead got '{get_oqs_type(list_to_flatten)}'. "
        )

    def flatten(lst):
        result: list[any] = []
        for i in lst:
            if isinstance(i, list):
                result.extend(flatten(i))
            else:
                result.append(i)
        return result

    return flatten(list_to_flatten)


def bif_slice(interpreter: 'OQSInterpreter', node: FunctionNode) -> list[any] | str:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=3)
    collection, start = [interpreter.evaluate(arg) for arg in node.args[:2]]
    end: any = interpreter.evaluate(node.args[2]) if len(node.args) == 3 else None

    if not isinstance(collection, (list, str)):
        raise OQSTypeError(
            message=f"SLICE function requires a List or String as the first argument. "
                    f"Instead got '{get_oqs_type(collection)}'. "
        )
    if not isinstance(start, int) or (end is not None and not isinstance(end, int)):
        raise OQSTypeError(
            message=f"SLICE function requires Integer arguments for start and end positions. "
                    f"Instead got '{get_oqs_type(start)}', '{get_oqs_type(end)}' respectively. "
        )

    return collection[start:end]


def bif_in(interpreter: 'OQSInterpreter', node: FunctionNode) -> bool:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    value, collection = [interpreter.evaluate(arg) for arg in node.args]
    if isinstance(collection, list):
        return value in collection
    elif isinstance(collection, dict):
        return value in collection.keys()
    else:
        raise OQSTypeError(
            message=f"IN function requires a list or KVS as the second argument. "
                    f"Instead got '{get_oqs_type(collection)}'. "
        )


def bif_date(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.date:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=3)
    year, month, day = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(i, int) for i in [year, month, day]):
        raise OQSTypeError(
            message=f"All arguments must be integers. Instead got the following types in order: "
                    f"'{get_oqs_type(year)}', '{get_oqs_type(month)}', '{get_oqs_type(day)}'. "
        )
    try:
        return datetime.date(year, month, day)
    except ValueError as ve:
        raise OQSValueError(message=str(ve))


def bif_time(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.time:
    ensure_function_arg_quantity(node=node, min_args=3, max_args=4)
    hour, minute, second, *ms = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(i, int) for i in [hour, minute, second] + ms):
        raise OQSTypeError(
            message=f"All arguments must be integers. Instead got the following in order: "
                    f"'{get_oqs_type(hour)}', '{get_oqs_type(minute)}', '{get_oqs_type(second)}'" +
                    (f", '{get_oqs_type(ms[0])}'" if ms else '') + '.'
        )
    try:
        return datetime.time(hour, minute, second, *ms)
    except ValueError as ve:
        raise OQSValueError(message=str(ve))


def bif_datetime(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.datetime:
    ensure_function_arg_quantity(node=node, min_args=6, max_args=7)
    year, month, day, hour, minute, second, *ms = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(i, int) for i in [year, month, day, hour, minute, second] + ms):
        raise OQSTypeError(
            message=f"All arguments must be integers. Instead got the following in order: '{get_oqs_type(year)}', "
                    f"'{get_oqs_type(month)}', '{get_oqs_type(day)}', '{get_oqs_type(hour)}', '{get_oqs_type(minute)}',"
                    f"'{get_oqs_type(second)}'" + (f", '{get_oqs_type(ms[0])}'" if ms else '') + '.'
        )
    try:
        return datetime.datetime(year, month, day, hour, minute, second, *ms)
    except ValueError as ve:
        raise OQSValueError(message=str(ve))


def bif_duration(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.timedelta:
    ensure_function_arg_quantity(node=node, min_args=4, max_args=5)
    days, hours, minutes, seconds, *ms = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(i, int) for i in [days, hours, minutes, seconds] + ms):
        raise OQSTypeError(
            message=f"All arguments must be integers. Instead got the following in order: '{get_oqs_type(days)}', "
                    f"'{get_oqs_type(hours)}', '{get_oqs_type(minutes)}', '{get_oqs_type(seconds)}'" +
                    (f", '{get_oqs_type(ms[0])}'" if ms else '') + '.'
        )
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds, microseconds=ms[0] if ms else 0)


def bif_now(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.datetime:
    ensure_function_arg_quantity(node=node, min_args=0, max_args=0)
    return datetime.datetime.utcnow()


def bif_today(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.date:
    ensure_function_arg_quantity(node=node, min_args=0, max_args=0)
    return datetime.date.today()


def bif_time_now(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.time:
    ensure_function_arg_quantity(node=node, min_args=0, max_args=0)
    return datetime.datetime.utcnow().time()


def bif_parse_temporal(
        interpreter: 'OQSInterpreter', node: FunctionNode
) -> datetime.datetime | datetime.date | datetime.time | datetime.timedelta:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=3)
    string, temporal_type, *optional_format = [interpreter.evaluate(arg) for arg in node.args]
    if not all(isinstance(arg, str) for arg in [string, temporal_type] + optional_format):
        raise OQSTypeError(
            message=f"All arguments must be strings. Received types: '{get_oqs_type(string)}', "
                    f"'{get_oqs_type(temporal_type)}'" +
                    (f", '{get_oqs_type(optional_format[0])}'" if optional_format else '') + '.'
        )
    temporal_type: str = temporal_type.lower()
    format_str: str | None = optional_format[0] if optional_format else None
    try:
        if temporal_type == "datetime":
            default_format: str = "%Y-%m-%dT%H:%M:%S"
            return datetime.datetime.strptime(string, format_str or default_format)
        elif temporal_type == "date":
            default_format: str = "%Y-%m-%d"
            return datetime.datetime.strptime(string, format_str or default_format).date()
        elif temporal_type == "time":
            default_format: str = "%H:%M:%S"
            return datetime.datetime.strptime(string, format_str or default_format).time()
        elif temporal_type == "duration":
            duration_pattern: str = r"(\d+)\s+(\d+):(\d+):(\d+)"
            duration_match: re.Match | None = re.match(duration_pattern, string)
            if duration_match:
                days, hours, minutes, seconds = map(int, duration_match.groups())
                return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
            else:
                raise ValueError("Invalid duration format")
        else:
            raise ValueError("Invalid temporal type specified")

    except ValueError as ve:
        raise OQSValueError(message=str(ve))


def bif_format_temporal(interpreter: 'OQSInterpreter', node: FunctionNode) -> str:
    ensure_function_arg_quantity(node=node, min_args=2, max_args=2)
    temporal, format_str = [interpreter.evaluate(arg) for arg in node.args]
    if not isinstance(format_str, str):
        raise OQSTypeError(
            message=f"Format argument must be a string. Instead got '{get_oqs_type(format_str)}'."
        )
    if not isinstance(temporal, (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)):
        raise OQSTypeError(
            message=f"First argument must be a Temporal type (Date, Time, DateTime, Duration). "
                    f"Instead got '{get_oqs_type(temporal)}'."
        )
    try:
        return temporal.strftime(format_str)
    except ValueError as ve:
        raise OQSValueError(message=str(ve))


def bif_extract_date(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.date:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    datetime_obj: datetime.datetime = interpreter.evaluate(node.args[0])
    if not isinstance(datetime_obj, datetime.datetime):
        raise OQSTypeError(message=f"Argument must be a DateTime type. Instead got '{get_oqs_type(datetime_obj)}'.")
    return datetime_obj.date()


def bif_extract_time(interpreter: 'OQSInterpreter', node: FunctionNode) -> datetime.time:
    ensure_function_arg_quantity(node=node, min_args=1, max_args=1)
    datetime_obj: datetime.datetime = interpreter.evaluate(node.args[0])
    if not isinstance(datetime_obj, datetime.datetime):
        raise OQSTypeError(message=f"Argument must be a DateTime type. Instead got '{get_oqs_type(datetime_obj)}'.")
    return datetime_obj.time()
