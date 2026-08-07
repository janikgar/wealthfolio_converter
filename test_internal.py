import pytest
import duckdb
from internal import PreProcessPattern, ImportSource


class TestInternal:
    @pytest.mark.parametrize(
        "match,sub,line,expected,debug",
        [
            ("foo", "bar", "foobar", "barbar", False),
            ("foo", "bar", "foobar", "barbar", True),
            ("foo", "bar", "bazbar", "bazbar", False),
            (None, "bar", "foobar", TypeError(), False),
            ("foo", None, "foobar", TypeError(), False),
            ("foo", "bar", None, TypeError(), False),
            ("foo", "bar", "", "", False),
            ("foo", "", "bar", "bar", False),
            ("", "foo", "bar", "bar", False),
            ("", "foo", "bar", "bar", True),
        ],
    )
    def test_pre_process_pattern(self, match, sub, line, expected, debug, capfd):
        if isinstance(expected, Exception):
            with pytest.raises(TypeError) as exc_info:
                pattern = PreProcessPattern(match, sub, debug)
                pattern.exec(line)
                assert exc_info.type == type(expected)
        else:
            pattern = PreProcessPattern(match, sub, debug)
            assert pattern.exec(line) == expected
            if debug:
                captured = capfd.readouterr()
                if match != "":
                    assert expected in captured.out
                else:
                    assert "match empty" in captured.out

    def test_import_source(self):
        conn = duckdb.connect(":memory:")
        source = ImportSource(filename="test.csv", conn=conn, columns={"foo": "bar"})
