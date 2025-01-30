class ASTNode:
    pass


class NullNode(ASTNode):
    pass


class UnparsedNode(ASTNode):
    def __init__(self, token: str) -> None:
        self.token: str = token


class EvaluatedNode(ASTNode):
    def __init__(self, value: any) -> None:
        self.value: any = value


class BinaryOpNode(ASTNode):
    def __init__(self, left: any, op: str, right: any) -> None:
        self.left: any = left
        self.op: str = op
        self.right: any = right


class ComparisonOpNode(ASTNode):
    def __init__(self, left: any, op: str, right: any) -> None:
        self.left: any = left
        self.op: str = op
        self.right: any = right


class NumberNode(ASTNode):
    def __init__(self, value: int | float) -> None:
        self.value: int | float = value


class VariableNode(ASTNode):
    def __init__(self, name: str) -> None:
        self.name: str = name


class StringNode(ASTNode):
    def __init__(self, value: str) -> None:
        self.value: str = value


class ListNode(ASTNode):
    def __init__(self, elements: list[any]) -> None:
        self.elements: list[any] = elements


class KVSNode(ASTNode):
    def __init__(self, key_value_store: dict[ASTNode, ASTNode]) -> None:
        self.key_value_store: dict[ASTNode, ASTNode] = key_value_store


class BooleanNode(ASTNode):
    def __init__(self, value: bool) -> None:
        self.value: bool = value


class FunctionNode(ASTNode):
    def __init__(self, name: str, args: list[any]) -> None:
        self.name: str = name
        self.args: list[any] = args


class PackedNode(ASTNode):
    def __init__(self, expression: str) -> None:
        self.expression: str = expression
