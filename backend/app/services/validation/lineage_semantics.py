from enum import Enum


class LineageSemantics(str, Enum):
    """Documentation marker for lineage semantic boundaries.

    These values are referenced from docstrings/comments only and do not drive
    runtime validation logic.
    """

    TRACE_LEVEL = "trace_level"
    EVENT_LEVEL = "event_level"
