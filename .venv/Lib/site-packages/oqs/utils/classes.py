import abc


def find_non_abc_subclasses(cls: type):
    subclasses: list[type] = []
    for subclass in cls.__subclasses__():
        if not issubclass(subclass, abc.ABC):
            subclasses.append(subclass)
            subclasses.extend(find_non_abc_subclasses(subclass))
    return subclasses
