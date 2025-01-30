from ..errors import OQSInvalidArgumentQuantityError
from ..nodes import FunctionNode
from ..constants.values import MAX_ARGS


def ensure_function_arg_quantity(node: FunctionNode, min_args: int, max_args: int = MAX_ARGS) -> None:
    arg_count: int = len(node.args)
    if not (min_args <= arg_count <= max_args):
        raise OQSInvalidArgumentQuantityError(
            function_name=node.name, expected_min=min_args, expected_max=max_args, actual=arg_count
        )
