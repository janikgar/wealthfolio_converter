import pytest
import duckdb
from .internal import PreProcessPattern, WFLogger, ImportSource, DuckDbFunction


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
    def test_pre_process_pattern(self, name, match, sub, line, expected):
        log = WFLogger("test", "DEBUG")
        log.init()
        log.info(name)
        if isinstance(expected, Exception):
            with pytest.raises(TypeError) as exc_info:
                pattern = PreProcessPattern(match, sub, log)
                pattern.exec(line)
                assert exc_info.type == type(expected)
        else:
            pattern = PreProcessPattern(match, sub, log)
            assert pattern.exec(line) == expected

    def test_import_source(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        conn = duckdb.connect(":memory:")
        log = WFLogger("test", "DEBUG")
        log.init()
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"foo": "VARCHAR"}, log=log)
        assert source.temp_filename != ""

    def test_import_source_pre_process(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo
bin""")
        log = WFLogger("test", "DEBUG")
        log.init()
        pre_processors = [PreProcessPattern("bin", "bar", log)]
        conn = duckdb.connect(":memory:")
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"foo": "VARCHAR"}, log=log,
                              pre_process_funcs=pre_processors)
        source.pre_process()
        source.import_csv()
        assert conn.table("transactions").columns[0] == "foo"
        result = conn.sql("SELECT * FROM transactions").fetchone()
        assert result is not None
        assert result[0] == "bar"

    def test_import_source_start_at_row(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""ignore this line
foo
bin""")
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"foo": "VARCHAR"}, log=log,
                              start_row_regex="foo")
        source.pre_process()
        source.import_csv()
        assert conn.table("transactions").columns[0] == "foo"
        result = conn.sql("SELECT * FROM transactions").fetchone()
        assert result is not None
        assert result[0] == "bin"

    def test_import_source_stop_before_row(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo
bin
stop before this row""")
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"foo": "VARCHAR"}, log=log,
                              stop_before_row_regex="stop.*")
        source.pre_process()
        source.import_csv()
        assert conn.table("transactions").columns[0] == "foo"
        result = conn.sql("SELECT * FROM transactions").fetchone()
        assert result is not None
        assert result[0] == "bin"

    def test_import_source_duckdb_invalid_input(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo
-1""")
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"baz": "UTINYINT"}, log=log)
        source.pre_process()
        with pytest.raises(check=lambda e: isinstance(e, duckdb.DatabaseError)):
            source.import_csv()

    def test_import_source_with_db_functions(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo
1""")
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        db_funcs = [DuckDbFunction(
            "test_udf",
            lambda e: e,
            ["VARCHAR"],
            "VARCHAR"
        )]
        source = ImportSource(filename=str(tmp_file.resolve()), conn=conn,
                              columns={"baz": "UTINYINT"}, log=log,
                              db_functions=db_funcs)
        source.pre_process()
        source.import_csv()
        source.conn.sql("PRAGMA functions").to_table("functions")
        assert len(source.db_functions) == 1
        returned_function = source.conn.sql(
            "SELECT * FROM functions WHERE name = 'test_udf'").fetchone()
        assert returned_function is not None
        print(returned_function)
        assert returned_function == ('test_udf', 'SCALAR', ['VARCHAR'], None, 'VARCHAR', False)
