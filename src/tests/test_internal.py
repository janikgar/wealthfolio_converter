import pytest
import duckdb
import boto3
from botocore.config import Config
from moto import mock_aws
import duckdb
from wealthfolio_converter.internal import (
    PreProcessPattern,
    WFLogger,
    ImportSource,
    DuckDbFunction,
    CommonConfig,
    classify_input,
    save_output,
)
from wealthfolio_converter.s3 import S3Config

mock_config = S3Config(
    aws_access_key_id="qwertyuiop",
    aws_secret_access_key="asdfghjk",
    region_name="us-east-1",
    config=Config(),
)


class TestInternal:
    @mock_aws
    @pytest.mark.parametrize("_,input_filename", [
        ("reg_file", "input.csv"),
        ("s3_file", "s3://test_bucket/input.csv"),
    ])
    def test_classify_input(self, _, input_filename: str):
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket='test_bucket')
        client.put_object(Bucket='test_bucket',
                          Key='input.csv', Body='asdf')

        mock_config.endpoint_url = client.meta.endpoint_url

        log = WFLogger("test", "DEBUG")
        log.init()
        new_input_fn, bucket = classify_input(input_filename, log, mock_config)
        if input_filename.startswith("s3"):
            # assert that temp file is not equal to original filename
            # skip assertion matching `/tmp`; not platform-independent
            assert new_input_fn != input_filename
            assert bucket is not None
        else:
            assert new_input_fn == input_filename
            assert bucket is None

    @mock_aws
    @pytest.mark.parametrize("_,output_filename", [
        ("reg_file", "output.csv"),
        ("s3_file", "s3://test_bucket/output.csv"),
    ])
    def test_save_output(self, _, output_filename: str):
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket='test_bucket')

        mock_config.endpoint_url = client.meta.endpoint_url

        log = WFLogger("test", "DEBUG")
        log.init()

        ddb = duckdb.connect(':memory:')
        ddb.sql("create table temp as select * from range(1,2) tbl(id)")
        ddb_table = ddb.table('temp')

        bucket = save_output(output_filename, ddb_table, log, mock_config)
        if output_filename.startswith('s3'):
            assert bucket is not None
        else:
            assert bucket is None

    @pytest.mark.parametrize(
        "_,match,sub,line,expected",
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
    def test_pre_process_pattern(self, _, match, sub, line: str, expected: str | Exception):
        log = WFLogger("test", "DEBUG")
        log.init()
        if isinstance(expected, Exception):
            with pytest.raises(TypeError, check=lambda e: isinstance(e, TypeError)):
                pattern = PreProcessPattern(match, sub, log)
                pattern.exec(line)
        else:
            pattern = PreProcessPattern(match, sub, log)
            assert pattern.exec(line) == expected

    def test_import_source(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        conn = duckdb.connect(":memory:")
        log = WFLogger("test", "DEBUG")
        log.init()
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ), columns={"foo": "VARCHAR"})
        assert source.temp_filename != ""

    def test_import_source_pre_process(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo



bin""")
        log = WFLogger("test", "DEBUG")
        log.init()
        pre_processors = [PreProcessPattern("bin", "bar", log)]
        conn = duckdb.connect(":memory:")
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ), columns={"foo": "VARCHAR"},
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
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
            start_row_regex="foo",
        ), columns={"foo": "VARCHAR"})
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
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
            stop_before_row_regex="stop.*",
        ), columns={"foo": "VARCHAR"})
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
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ), columns={"baz": "UTINYINT"})
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
        source = ImportSource(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ), columns={"baz": "UTINYINT"},
            db_functions=db_funcs)
        source.pre_process()
        source.import_csv()
        conn.sql("PRAGMA functions").to_table("functions")
        assert len(source.db_functions) == 1
        returned_function = conn.sql(
            "SELECT * FROM functions WHERE name = 'test_udf'").fetchone()
        assert returned_function is not None
        print(returned_function)
        assert returned_function == ('test_udf', 'SCALAR', [
                                     'VARCHAR'], None, 'VARCHAR', False)
