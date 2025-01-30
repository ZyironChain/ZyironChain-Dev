from .errors import (OQSSyntaxError, OQSMissingExpectedCharacterError, OQSUnexpectedCharacterError)
from .nodes import (
    ASTNode,
    BinaryOpNode,
    NumberNode,
    BooleanNode,
    NullNode,
    StringNode,
    KVSNode,
    ListNode,
    VariableNode,
    FunctionNode,
    UnparsedNode,
    ComparisonOpNode,
    PackedNode
)


class OQSParser:
    OPERATOR_PRECEDENCE: dict[str, int] = {
        '**': 1, '*': 2, '/': 2, '%': 2, '+': 3, '-': 3,
        '==': 4, '!=': 4, '<': 4, '<=': 4, '>': 4, '>=': 4, '===': 4, '!==': 4, '&': 4, '|': 4
    }

    def parse(self, expression: str) -> ASTNode:
        tokens: list[str] = self.tokenize_expression(expression=expression)
        return self.parse_expression(tokens=tokens)

    @staticmethod
    def tokenize_expression(expression: str) -> list[str]:
        def char_is_operator(single_char_str: str) -> bool:
            return single_char_str in ['+', '-', '*', '/', '%', '<', '>', '=', '!', '&', '|']

        def token_is_operator(token: str) -> bool:
            return char_is_operator(token[0]) and not (token.startswith('***') and len(token) > 3 and token[3] != '*')

        def none_operator_char_is_valid_beginning_or_ending(single_char_str: str) -> bool:
            return single_char_str in ['_', '(', ')', '[', ']', '{', '}', '"', "'"] or single_char_str.isalnum()

        tokens: list[str] = []
        expression: str = expression.strip()
        i: int = 0
        while i < len(expression):
            char: str = expression[i]
            if char in ['"', "'"]:
                start_index: int = i
                i += 1
                while i < len(expression) and expression[i] != char:
                    i += 1
                i += 1
                tokens.append(expression[start_index:i])
            elif char.isdigit() or (char == '.' and i + 1 < len(expression) and expression[i + 1].isdigit()):
                start_index: int = i
                i += 1
                while i < len(expression) and (expression[i].isdigit() or expression[i] in ['.', '_']):
                    i += 1
                number: str = expression[start_index:i]
                if number.startswith('.'):
                    number: str = '0' + number
                if number.endswith('.'):
                    number += '0'
                if number.count('.') > 1:
                    raise OQSUnexpectedCharacterError(message=f"A Decimal cannot contain more than one '.': {number}")
                if '.' in number:
                    split_number_list: list[str] = number.split('.')
                    decimal_number: str = split_number_list[1]
                    if '_' in decimal_number:
                        raise OQSUnexpectedCharacterError(
                            message=f"An underscore cannot be used to split a number after the decimal point: {number}"
                        )
                number: str = number.replace('_', '')
                tokens.append(number)
                if i < len(expression) and not (
                        char_is_operator(expression[i]) or expression[i] in ['}', ']', ')', ' ']
                ):
                    raise OQSUnexpectedCharacterError(
                        message=f"The character '{expression[i]}' is not expected after the number '{number}'. "
                                f"It is suggested these be separated by a space or an operator."
                    )
            elif char.isalpha() or char == '_':
                start_index: int = i
                i += 1
                while i < len(expression) and (expression[i].isalnum() or expression[i] == '_'):
                    i += 1
                tokens.append(expression[start_index:i])
            elif char_is_operator(char):
                start_index: int = i
                while i + 1 < len(expression) and char_is_operator(expression[i + 1]):
                    i += 1
                i += 1
                tokens.append(expression[start_index:i])
            elif char in ['(', '[', '{']:
                closing_char: str = ')' if char == '(' else ']' if char == '[' else '}'
                level: int = 1
                start_index: int = i
                i += 1
                while i < len(expression) and level > 0:
                    if expression[i] == char:
                        level += 1
                    elif expression[i] == closing_char:
                        level -= 1
                    i += 1
                if level != 0:
                    raise OQSMissingExpectedCharacterError(f"Unclosed '{char}' in expression: {expression}")
                tokens.append(expression[start_index:i])
            elif char == '*' and i + 2 < len(expression) and expression[i:i + 3] == '***' and (
                    expression[i + 3] != '*' if i + 3 < len(expression) else True
            ):
                tokens.append('***')
                i += 3
            elif char == ' ':
                i += 1
            else:
                raise OQSUnexpectedCharacterError(
                    message=f"The character '{char}' is not recognized in this setting: {expression}"
                )

        tokens: list[str] = [token.strip() for token in tokens if token.strip()]
        tokens: list[str] = [
            token + tokens[i + 1] if token == '***' and i + 1 < len(tokens) else token
            for i, token in enumerate(tokens) if (tokens[i - 1] != '***' if i != 0 else True)
        ]
        tokens: list[str] = [
            token + tokens[i + 1]
            if (token[0].isalpha() or token[0] == '_') and i + 1 < len(tokens) and tokens[i + 1].startswith('(')
            else token
            for i, token in enumerate(tokens)
            if (
                not (token.startswith('(') and (tokens[i - 1][0].isalpha() or tokens[i - 1][0] == '_'))
                if i != 0 else True
            )
        ]

        for i, token in enumerate(tokens):
            if token_is_operator(token):
                if i == 0:
                    raise OQSMissingExpectedCharacterError(
                        message=f"There must be something preceding an operator: "
                                f"There is nothing preceding the '{token}' operator."
                    )
                elif token_is_operator(tokens[i - 1]):
                    raise OQSMissingExpectedCharacterError(
                        message=f"Operators must be preceded by something other than an operator: "
                                f"Your '{token}' operator is being preceded by '{tokens[i - 1]}' operator."
                    )
                if i == len(tokens) - 1:
                    raise OQSMissingExpectedCharacterError(
                        message=f"There must be something following an operator: "
                                f"There is nothing following your '{token}' operator."
                    )
                elif token_is_operator(tokens[i + 1]):
                    raise OQSMissingExpectedCharacterError(
                        message=f"Operators must be followed by something other than an operator: "
                                f"Your '{token}' operator is being followed by '{tokens[i + 1]}' operator."
                    )
            else:
                if i > 0 and not token_is_operator(tokens[i - 1]):
                    raise OQSMissingExpectedCharacterError(
                        message=f"non-operators must be preceded by an operator: "
                                f"Your non-operator '{token}' is being preceded by '{tokens[i - 1]}' non-operator."
                    )
                elif i + 1 < len(tokens) and not token_is_operator(tokens[i + 1]):
                    raise OQSMissingExpectedCharacterError(
                        message=f"non-operators must be followed by an operator: "
                                f"Your non-operator '{token}' is being followed by '{tokens[i + 1]}'"
                    )
                elif not none_operator_char_is_valid_beginning_or_ending(token[0]) and not token.startswith('***'):
                    raise OQSUnexpectedCharacterError(
                        message=f"the character '{token[0]}' is not expected: {expression}."
                    )
                elif not none_operator_char_is_valid_beginning_or_ending(token[-1]):
                    raise OQSUnexpectedCharacterError(
                        message=f"the character '{token[-1]}' is not expected: {expression}."
                    )
                elif token.startswith('***') and len(token) > 3 and (
                        not none_operator_char_is_valid_beginning_or_ending(
                            token[3]
                        ) or token[3].isdigit() or token[3] in ['"', "'"]
                ):
                    raise OQSUnexpectedCharacterError(
                        message=f"Unexpected unpacking syntax as the provided item to unpack is invalid: {token}"
                    )
        return tokens

    @staticmethod
    def separate_arguments(expression: str) -> list[str]:
        tokens: list[str] = []
        expression: str = expression.strip()
        level: int = 0
        start_index: int = 0
        in_quote: bool = False
        quote_char: str = ''
        for i, char in enumerate(expression):
            if char in ['"', "'"]:
                if in_quote and char == quote_char:
                    in_quote: bool = False
                elif not in_quote:
                    in_quote: bool = True
                    quote_char: str = char
            elif char in ['(', '{', '[']:
                if not in_quote:
                    level += 1
            elif char in [')', '}', ']']:
                if not in_quote:
                    level -= 1
            elif char == ',' and level == 0 and not in_quote:
                tokens.append(expression[start_index:i].strip())
                start_index: int = i + 1
        tokens.append(expression[start_index:].strip())

        return [token.strip() for token in tokens if token.strip()]

    def parse_expression(self, tokens: list[str]) -> ASTNode:
        if len(tokens) == 0:
            return NullNode()
        elif len(tokens) == 1:
            return self.parse_term(tokens[0])

        op_pos: int | None = None
        highest_precedence: int = 0
        for i, token in reversed(list(enumerate(tokens))):
            if token in self.OPERATOR_PRECEDENCE and self.OPERATOR_PRECEDENCE[token] > highest_precedence:
                highest_precedence: int = self.OPERATOR_PRECEDENCE[token]
                op_pos: int = i

        if op_pos is not None:
            if op_pos == 0:
                raise OQSUnexpectedCharacterError(
                    message=f"Cannot process an operator without something in front of it: {tokens[op_pos]}."
                )
            elif op_pos + 2 > len(tokens):
                raise OQSMissingExpectedCharacterError(
                    message=f"Missing expected value after operator: {tokens[op_pos]}."
                )
            left_tokens: list[str] = tokens[:op_pos]
            right_tokens: list[str] = tokens[op_pos + 1:]

            left_subtree: ASTNode = self.parse_expression(left_tokens)
            right_subtree: ASTNode = self.parse_expression(right_tokens)

            op: str = tokens[op_pos]

            if op in ['==', '!=', '<', '<=', '>', '>=', '===', '!==', '&', '|']:
                return ComparisonOpNode(left=left_subtree, op=op, right=right_subtree)
            elif op in ['+', '-', '*', '/', '%', '**']:
                return BinaryOpNode(left=left_subtree, op=op, right=right_subtree)
            else:
                raise OQSSyntaxError(f"Invalid Operator: '{op}'")

    def parse_term(self, token: str) -> ASTNode:
        try:
            return NumberNode(value=int(token))
        except ValueError:
            try:
                return NumberNode(value=float(token))
            except ValueError:
                pass
        if token in ['true', 'false']:
            return BooleanNode(value=token == 'true')
        elif token == 'null':
            return NullNode()
        elif token.startswith('"') and token.endswith('"') or token.startswith("'") and token.endswith("'"):
            return StringNode(value=token[1:-1])
        elif token.startswith('{') and token.endswith('}'):
            kvs: dict[ASTNode, ASTNode] = self.parse_kvs(token[1:-1])
            return KVSNode(key_value_store=kvs)
        elif token.startswith('[') and token.endswith(']'):
            elements: list[ASTNode] = self.parse_list(args_str=token[1:-1])
            return ListNode(elements=elements)
        elif token.startswith('(') and token.endswith(')'):
            return self.parse(expression=token[1:-1])
        elif token.startswith('***'):
            return PackedNode(expression=token.lstrip('***'))
        elif '(' in token and token.endswith(')'):
            return self.parse_function_call(token)
        else:
            return VariableNode(name=token)

    def parse_function_call(self, token: str) -> FunctionNode:
        function_name, args_str = token[:-1].split('(', 1)
        args_tokens: list[str] = self.separate_arguments(expression=args_str)
        args: list[ASTNode] = [
            self.parse_term(arg)
            if arg.startswith('***') else UnparsedNode(token=arg) for arg in args_tokens
        ]
        return FunctionNode(name=function_name, args=args)

    def parse_list(self, args_str: str) -> list[ASTNode]:
        if not args_str.strip():
            return []
        args_tokens: list[str] = self.separate_arguments(expression=args_str)
        return [self.parse_expression(tokens=[token]) for token in args_tokens]

    def parse_kvs(self, kvs_str: str) -> dict[ASTNode, ASTNode]:
        kvs_tokens: list[str] = self.separate_arguments(expression=kvs_str)
        kvs: dict[ASTNode, ASTNode] = {}
        for i, token in enumerate(kvs_tokens):
            if token.startswith('***'):
                key: str = f'"PACKED_TOKEN__{i}"'
                value: str = token
            else:
                key, value = self.split_key_value_pair(token)
            kvs[self.parse_expression([key])] = self.parse_expression([value])
        return kvs

    @staticmethod
    def split_key_value_pair(token: str) -> tuple[str, str]:
        colon_index: int = -1
        level: int = 0
        in_string: bool = False
        string_char: str = ''
        for i, char in enumerate(token):
            if char in ['"', "'"]:
                if in_string and char == string_char:
                    in_string: bool = False
                elif not in_string:
                    in_string: bool = True
                    string_char: str = char
            elif char == ":" and level == 0 and not in_string:
                colon_index: int = i
                break
            elif char in ['{', '[', '(']:
                level += 1
            elif char in ['}', '[', ')']:
                level -= 1
        if colon_index == -1:
            raise OQSSyntaxError(F"Invalid KVS pair {token}")
        key: str = token[:colon_index].strip()
        value: str = token[colon_index + 1:].strip()
        return key, value
