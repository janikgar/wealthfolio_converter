import pytest
from .internal import PreProcessPattern, WFLogger


class TestInternal:
    @pytest.mark.parametrize(
        "name,match,sub,line,expected",
        [
            ("successful_substitution", "foo", "bar", "foobar", "barbar"),
            ("successful_noop", "foo", "bar", "bazbar", "bazbar"),
            ("successful_noop_on_empty_sub", "foo", "", "bar", "bar"),
            ("successful_noop_on_empty_match", "", "foo", "bar", "bar"),
            ("empty_output_on_empty_input", "foo", "bar", "", ""),
            ("typeerror_on_null_match", None, "bar", "foobar", TypeError()),
            ("typeerror_on_null_sub", "foo", None, "foobar", TypeError()),
            ("typeerror_on_null_line", "foo", "bar", None, TypeError()),
        ],
    )
    def test_pre_process_pattern(self, name, match, sub, line, expected, capfd):
        log = WFLogger("test", "DEBUG")
        log.info(name)
        if isinstance(expected, Exception):
            with pytest.raises(TypeError) as exc_info:
                pattern = PreProcessPattern(match, sub, log)
                pattern.exec(line)
                assert exc_info.type == type(expected)
        else:
            pattern = PreProcessPattern(match, sub, log)
            assert pattern.exec(line) == expected
            # captured = capfd.readouterr()
            # if match != "":
            #     assert expected in captured.out
            # else:
            #     assert "match empty" in captured.out

    # def test_import_source(self):
    #     conn = duckdb.connect(":memory:")
    #     log = WFLogger("test", "DEBUG")
    #     source = ImportSource(filename="test.csv", conn=conn, columns={"foo": "bar"}, log=log)
