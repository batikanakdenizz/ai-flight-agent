"""
Date normalization in the MCP server.

The gateway rejects dates that are not full UTC timestamps, and the model sends
whatever the user typed. These helpers sit between the two, so a bug here means
a silently wrong search window rather than a visible error.
"""
import mcp_server as server


class TestToUtcStart:
    def test_plain_date_becomes_midnight(self):
        assert server._to_utc_start("2026-09-01") == "2026-09-01T00:00:00Z"

    def test_time_component_is_discarded(self):
        assert server._to_utc_start("2026-09-01T14:30:00") == "2026-09-01T00:00:00Z"

    def test_surrounding_whitespace_is_ignored(self):
        assert server._to_utc_start("  2026-09-01  ") == "2026-09-01T00:00:00Z"


class TestToUtcEnd:
    def test_plain_date_becomes_last_second(self):
        assert server._to_utc_end("2026-09-01") == "2026-09-01T23:59:59Z"

    def test_time_component_is_discarded(self):
        assert server._to_utc_end("2026-09-01T14:30:00") == "2026-09-01T23:59:59Z"


def test_single_day_search_spans_the_whole_day():
    """
    The system prompt tells the model to pass the same date twice for a one-day
    search. If both ends collapsed to the same instant the query would match
    nothing, so the window has to stay open.
    """
    day = "2026-09-01"
    assert server._to_utc_start(day) < server._to_utc_end(day)


class TestToUtcDatetime:
    def test_date_only_gets_midnight(self):
        assert server._to_utc_datetime("2026-09-01") == "2026-09-01T00:00:00Z"

    def test_naive_datetime_is_marked_as_utc(self):
        assert server._to_utc_datetime("2026-09-01T14:30:00") == "2026-09-01T14:30:00Z"

    def test_utc_datetime_is_left_alone(self):
        assert server._to_utc_datetime("2026-09-01T14:30:00Z") == "2026-09-01T14:30:00Z"

    def test_explicit_offset_is_preserved(self):
        """
        An offset already carries the timezone. Appending a Z would produce
        '...+03:00Z', which the gateway cannot parse.
        """
        value = "2026-09-01T14:30:00+03:00"
        assert server._to_utc_datetime(value) == value

    def test_negative_offset_is_preserved(self):
        value = "2026-09-01T14:30:00-05:00"
        assert server._to_utc_datetime(value) == value

    def test_whitespace_is_stripped(self):
        assert server._to_utc_datetime(" 2026-09-01 ") == "2026-09-01T00:00:00Z"
