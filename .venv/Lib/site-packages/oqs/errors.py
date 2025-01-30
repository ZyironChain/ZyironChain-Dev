from .constants.types import ErrorTypeStrings as ETS
from abc import ABC

from .utils.classes import find_non_abc_subclasses


class OQSBaseError(Exception, ABC):
    def __init__(self, message: str = "An error occurred while evaluating your expression!") -> None:
        super().__init__(message)
        self.readable_name: str = self.READABLE_NAME if hasattr(self, "READABLE_NAME") else ETS.BASE
        self.error_hierarchy: list[str] = self._build_error_hierarchy()

    def _build_error_hierarchy(self) -> list[str]:
        hierarchy: list[str] = []
        for cls in self.__class__.__mro__:
            if issubclass(cls, OQSBaseError) and hasattr(cls, 'READABLE_NAME'):
                hierarchy.append(cls.READABLE_NAME)
        hierarchy.append(ETS.BASE)
        return hierarchy


class OQSInvalidArgumentQuantityError(OQSBaseError):
    READABLE_NAME: str = ETS.INVALID_ARGUMENT_QUANTITY

    def __init__(self, function_name: str, expected_min: int, expected_max: int, actual: int) -> None:
        message: str = (
            f"Function '{function_name}' expected at least {expected_min} with a max of {expected_max} arguments, "
            f"but got {actual}"
        )
        super().__init__(message=message)


class OQSSyntaxError(OQSBaseError):
    READABLE_NAME: str = ETS.SYNTAX

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class OQSTypeError(OQSBaseError):
    READABLE_NAME: str = ETS.TYPE

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class OQSValueError(OQSBaseError):
    READABLE_NAME: str = ETS.VALUE

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class OQSUndefinedVariableError(OQSBaseError):
    READABLE_NAME: str = ETS.UNDEFINED_VARIABLE

    def __init__(self, variable_name: str) -> None:
        message: str = f"The variable {variable_name} is not defined."
        super().__init__(message=message)


class OQSUndefinedFunctionError(OQSBaseError):
    READABLE_NAME: str = ETS.UNDEFINED_FUNCTION

    def __init__(self, function_name: str) -> None:
        message: str = f"The function '{function_name}' is not a valid function."
        super().__init__(message=message)


class OQSFunctionEvaluationError(OQSBaseError):
    READABLE_NAME: str = ETS.FUNCTION_EVALUATION

    def __init__(self, function_name: str, message: str) -> None:
        full_message: str = f"Error in function '{function_name}': {message}"
        super().__init__(message=full_message)


class OQSDivisionByZeroError(OQSBaseError):
    READABLE_NAME: str = ETS.DIVISION_BY_ZERO

    def __init__(self) -> None:
        super().__init__(message="Division by zero results in undefined.")


class OQSUnexpectedCharacterError(OQSSyntaxError):
    READABLE_NAME: str = ETS.UNEXPECTED_CHARACTER

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class OQSMissingExpectedCharacterError(OQSSyntaxError):
    READABLE_NAME: str = ETS.MISSING_EXPECTED_CHARACTER

    def __init__(self, message: str) -> None:
        super().__init__(message=message)


class OQSCustomErrorParent(OQSBaseError, ABC):
    READABLE_NAME: str = ETS.CUSTOM

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


def get_error_name_mapping() -> dict[str, type[OQSBaseError]]:
    error_classes: list[type[OQSBaseError]] = find_non_abc_subclasses(OQSBaseError)
    error_name_mapping: dict[str, type[OQSBaseError]] = {}
    for cls in error_classes:
        if hasattr(cls, "READABLE_NAME"):
            error_name_mapping[cls.READABLE_NAME.upper()] = cls
        else:
            raise TypeError(f"Class {cls.__name__} does not have a 'READABLE_NAME' class attribute.")
    return error_name_mapping
