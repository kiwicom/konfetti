try:
    # Python 2 old-style classes
    from types import ClassType as class_type  # type: ignore

    class_types = (class_type, type)
except ImportError:
    class_types = (type,)  # type: ignore
