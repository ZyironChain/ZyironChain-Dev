from typing import Callable
from . import built_in_functions
from .errors import (
    OQSUndefinedFunctionError,
    OQSBaseError,
    OQSFunctionEvaluationError,
    OQSUndefinedVariableError,
    OQSSyntaxError,
    OQSTypeError,
)
from .nodes import (
    FunctionNode,
    ASTNode,
    NumberNode,
    StringNode,
    NullNode,
    ListNode,
    VariableNode,
    BinaryOpNode,
    KVSNode,
    BooleanNode,
    UnparsedNode,
    ComparisonOpNode,
    PackedNode,
    EvaluatedNode
)
from .parser import OQSParser


class OQSInterpreter:
    OPERATORS: dict[str, str] = {
        '+': "ADD",
        '-': "SUBTRACT",
        '*': "MULTIPLY",
        '/': "DIVIDE",
        '%': "MODULO",
        '**': "EXPONENTIATE",
        '<': "LESS_THAN",
        '>': "GREATER_THAN",
        '<=': "LESS_THAN_OR_EQUAL",
        '>=': "GREATER_THAN_OR_EQUAL",
        '==': "EQUALS",
        '!=': "NOT_EQUALS",
        '===': "STRICTLY_EQUALS",
        '!==': "STRICTLY_NOT_EQUALS",
        '&': "AND",
        '|': "OR"
    }
    FUNCTIONS: dict[str, Callable] = {
        "ADD": built_in_functions.bif_add,
        "SUBTRACT": built_in_functions.bif_subtract,
        "MULTIPLY": built_in_functions.bif_multiply,
        "DIVIDE": built_in_functions.bif_divide,
        "EXPONENTIATE": built_in_functions.bif_exponentiate,
        "MODULO": built_in_functions.bif_modulo,
        "LESS_THAN": built_in_functions.bif_less_than,
        "GREATER_THAN": built_in_functions.bif_greater_than,
        "LESS_THAN_OR_EQUAL": built_in_functions.bif_less_than_or_equal,
        "GREATER_THAN_OR_EQUAL": built_in_functions.bif_greater_than_or_equal,
        "EQUALS": built_in_functions.bif_equals,
        "NOT_EQUALS": built_in_functions.bif_not_equals,
        "STRICTLY_EQUALS": built_in_functions.bif_strictly_equals,
        "STRICTLY_NOT_EQUALS": built_in_functions.bif_strictly_not_equals,
        "AND": built_in_functions.bif_and,
        "OR": built_in_functions.bif_or,
        "NOT": built_in_functions.bif_not,
        "INTEGER": built_in_functions.bif_integer,
        "DECIMAL": built_in_functions.bif_decimal,
        "STRING": built_in_functions.bif_string,
        "LIST": built_in_functions.bif_list,
        "KVS": built_in_functions.bif_kvs,
        "BOOLEAN": built_in_functions.bif_boolean,
        "BOOL": built_in_functions.bif_boolean,
        "KEYS": built_in_functions.bif_keys,
        "VALUES": built_in_functions.bif_values,
        "UNIQUE": built_in_functions.bif_unique,
        "REVERSE": built_in_functions.bif_reverse,
        "MAX": built_in_functions.bif_max,
        "MIN": built_in_functions.bif_min,
        "SUM": built_in_functions.bif_sum,
        "LENGTH": built_in_functions.bif_length,
        "LEN": built_in_functions.bif_length,
        "APPEND": built_in_functions.bif_append,
        "UPDATE": built_in_functions.bif_update,
        "REMOVE_ITEM": built_in_functions.bif_remove_item,
        "REMOVE": built_in_functions.bif_remove,
        "ACCESS": built_in_functions.bif_access,
        "IF": built_in_functions.bif_if,
        "TYPE": built_in_functions.bif_type,
        "IS_TYPE": built_in_functions.bif_is_type,
        "TRY": built_in_functions.bif_try,
        "RANGE": built_in_functions.bif_range,
        "FOR": built_in_functions.bif_for_or_map,
        "MAP": built_in_functions.bif_for_or_map,
        "RAISE": built_in_functions.bif_raise,
        "FILTER": built_in_functions.bif_filter,
        "SORT": built_in_functions.bif_sort,
        "FLATTEN": built_in_functions.bif_flatten,
        "SLICE": built_in_functions.bif_slice,
        "IN": built_in_functions.bif_in,
        "DATE": built_in_functions.bif_date,
        "TIME": built_in_functions.bif_time,
        "DATETIME": built_in_functions.bif_datetime,
        "DURATION": built_in_functions.bif_duration,
        "NOW": built_in_functions.bif_now,
        "TODAY": built_in_functions.bif_today,
        "TIME_NOW": built_in_functions.bif_time_now,
        "PARSE_TEMPORAL": built_in_functions.bif_parse_temporal,
        "FORMAT_TEMPORAL": built_in_functions.bif_format_temporal,
        "EXTRACT_DATE": built_in_functions.bif_date,
        "EXTRACT_TIME": built_in_functions.bif_time
    }

    def __init__(self, expression: str, variables: dict[str, any] | None = None) -> None:
        self.original_expression: str = expression
        self.parser: OQSParser = OQSParser()
        self.original_ast: ASTNode = self.parser.parse(expression=self.original_expression)
        self.variables: dict[str, any] = variables if variables else {}

    def add_additional_function(self, function_name: str, function: Callable):
        self.FUNCTIONS[function_name.upper()] = function

    def results(self) -> any:
        return self.evaluate(self.original_ast)

    def parse_and_evaluate(self, *args, **kwargs) -> any:
        return self.evaluate(self.parser.parse(*args, **kwargs))

    def evaluate(self, node: ASTNode) -> any:
        if isinstance(node, EvaluatedNode):
            return node.value
        elif isinstance(node, NumberNode):
            return node.value
        elif isinstance(node, StringNode):
            return node.value
        elif isinstance(node, NullNode):
            return None
        elif isinstance(node, ListNode):
            elements: list[any] = []
            for elem in node.elements:
                if isinstance(elem, PackedNode):
                    evaluated_elem: any = self.parse_and_evaluate(elem.expression)
                    if isinstance(evaluated_elem, list):
                        elements.extend(evaluated_elem)
                    else:
                        raise OQSTypeError(message="Cannot unpack anything into a list construction other than a List.")
                else:
                    elements.append(self.evaluate(elem))
            return elements
        elif isinstance(node, VariableNode):
            if node.name in self.variables:
                return self.variables[node.name]
            else:
                raise OQSUndefinedVariableError(node.name)
        elif isinstance(node, BinaryOpNode):
            if node.op in self.OPERATORS:
                function_node: FunctionNode = FunctionNode(name=self.OPERATORS[node.op], args=[node.left, node.right])
                return self.FUNCTIONS[function_node.name](self, function_node)
            else:
                raise OQSSyntaxError(f"Invalid binary operator '{node.op}'")
        elif isinstance(node, ComparisonOpNode):
            if node.op in self.OPERATORS:
                function_node: FunctionNode = FunctionNode(name=self.OPERATORS[node.op], args=[node.left, node.right])
                return self.FUNCTIONS[function_node.name](self, function_node)
            else:
                raise OQSSyntaxError(f"Invalid comparison operator '{node.op}'")
        elif isinstance(node, FunctionNode):
            try:
                if node.name.upper() in self.FUNCTIONS:
                    args: list[ASTNode] = []
                    for arg in node.args:
                        if isinstance(arg, PackedNode):
                            parsed_value: any = self.parse_and_evaluate(arg.expression)
                            if isinstance(parsed_value, list):
                                args.extend([EvaluatedNode(part) for part in parsed_value])
                            else:
                                raise OQSTypeError(
                                    message="Cannot unpack anything into a function call other than a List."
                                )
                        else:
                            args.append(arg)
                    return self.FUNCTIONS[node.name.upper()](self, FunctionNode(name=node.name, args=args))
                else:
                    raise OQSUndefinedFunctionError(function_name=node.name)
            except OQSBaseError:
                raise
            except Exception as e:
                raise OQSFunctionEvaluationError(function_name=node.name, message=str(e))
        elif isinstance(node, KVSNode):
            kvs: dict[str, any] = {}
            for key, value in node.key_value_store.items():
                if isinstance(value, PackedNode):
                    unpacked_node: any = self.parse_and_evaluate(value.expression)
                    if isinstance(unpacked_node, list):
                        unpacked_kvs: dict[str, any] = self.evaluate(
                            FunctionNode(name="UNPACKED_KVS", args=unpacked_node)
                        )
                        for unpacked_key, unpacked_value in unpacked_kvs.items():
                            kvs[unpacked_key] = unpacked_value
                    elif isinstance(unpacked_node, dict):
                        for unpacked_key, unpacked_value in unpacked_node.items():
                            kvs[unpacked_key] = unpacked_value
                    else:
                        raise OQSTypeError(
                            message="Cannot unpack anything into a KVS construction other than a List or KVS."
                        )
                else:
                    kvs[self.evaluate(key)] = self.evaluate(value)
            return kvs
        elif isinstance(node, BooleanNode):
            return node.value
        elif isinstance(node, UnparsedNode):
            return self.parse_and_evaluate(node.token)
        else:
            raise OQSSyntaxError(f"Unable to parse the following: {node}")
