try:
    # Python 2 old-style classes
    from types import ClassType as class_type  # type: ignore

    class_types = (class_type, type)
    string_types = (unicode, str)  # type: ignore  # pylint: disable=undefined-variable
except ImportError:
    class_types = (type,)  # type: ignore
    string_types = (str,)  # type: ignore
