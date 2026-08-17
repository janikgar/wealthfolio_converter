"""
Internal classes used by other modules.
"""
import re
import os
from dataclasses import dataclass, field
from logging import Logger
from typing import List, Callable, Dict, Any
from tempfile import mkstemp, NamedTemporaryFile
from duckdb.func import FunctionNullHandling, DEFAULT, NATIVE
from duckdb import DuckDBPyConnection, DatabaseError, DuckDBPyRelation
from wealthfolio_converter.s3 import S3Bucket, S3Config
from wealthfolio_converter.utils import WFLogger

WF_TYPES = {
    "BUY",
    "SELL",
    "SPLIT",
    "DIVIDEND",
    "INTEREST",
    "CREDIT",
    "DEPOSIT",
    "WITHDRAWAL",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "FEE",
    "TAX",
    "ADJUSTMENT",
}

S3_PATTERN = re.compile(
    r"s3:\/\/(?P<bucket_name>.*?)\/(?P<object_path>.*)")


def classify_input(input_filename: str, log: WFLogger, s3_config: S3Config) -> tuple[str, S3Bucket | None]:
    s3_input_bucket: S3Bucket | None = None
    s3_input_match = S3_PATTERN.fullmatch(input_filename)
    if s3_input_match:
        log.info("detected S3 input path")
        s3_input_bucket = S3Bucket(
            s3_input_match.group('bucket_name'), log, s3_config)
        s3_input_bucket.download_path(s3_input_match.group('object_path'))
        input_filename = s3_input_bucket.temp_filename
    return input_filename, s3_input_bucket


def save_output(output: str, output_table: DuckDBPyRelation, log: WFLogger, s3_config: S3Config) -> S3Bucket | None:
    s3_output_bucket: S3Bucket | None = None
    s3_output_match = S3_PATTERN.fullmatch(output)
    if s3_output_match:
        log.info("detected S3 output path")
        s3_output_bucket = S3Bucket(
            s3_output_match.group('bucket_name'), log, s3_config)
        with NamedTemporaryFile(mode="w+") as _o:
            output_table.to_csv(_o.name)
            s3_output_bucket.upload_path(
                _o.name, s3_output_match.group('object_path'))
    else:
        output_table.to_csv(output)
    return s3_output_bucket


@dataclass
class PreProcessPattern:
    """
    A regex pattern/substitution for pre-processing lines before data reshaping.
    """
    match: str
    sub: str
    log: Logger = field(default_factory=lambda: WFLogger("main"))

    def exec(self, line: str) -> str:
        """executes the substitution against the given line"""
        if self.match == "":
            self.log.debug("match empty; skipping substitution")
            return line
        subst = re.sub(self.match, self.sub, line)
        self.log.debug(subst)
        return subst


@dataclass
class DuckDbFunction:
    """
    Base class for functions to be created within DuckDB tables.
    """
    name: str
    function: Callable
    params: list[Any]
    return_type: str
    null_handling: FunctionNullHandling = DEFAULT


@dataclass
class CommonConfig:
    """Common configuration for all ImportSources"""
    filename: str
    conn: DuckDBPyConnection
    log: WFLogger
    start_row_regex: str = ""
    stop_before_row_regex: str = ""
    source_name: str = ""


@dataclass
class ImportSource:
    """
    Vendor-independent base class for all data imports.
    After data class initialization, a temp file is always created for
    intermediate processing.
    """
    common: CommonConfig
    db_functions: list[DuckDbFunction] = field(default_factory=list[DuckDbFunction])
    pre_process_funcs: List[PreProcessPattern] = field(default_factory=list[PreProcessPattern])
    columns: Dict[str, str] = field(default_factory=Dict[str, str])

    def __post_init__(self) -> None:
        self.mktemp()

    def mktemp(self) -> None:
        """mint temporary file for intermediate processing"""
        _, self.temp_filename = mkstemp(
            prefix=f"{self.common.source_name}-", suffix=".csv", text=True
        )
        self.common.log.info(f"created temp file {self.temp_filename}")

    def pre_process(self) -> None:
        """executes all stored pre-processing substitutions"""
        self.common.log.info("beginning pre-processing")
        with open(self.common.filename, encoding="utf-8") as _c:
            lines: list[str] = []
            for line in _c.readlines():
                self.common.log.debug("current line content: '%s'" % line)
                if self.common.start_row_regex != "" and \
                        re.search(self.common.start_row_regex, line) is not None:
                    lines.clear()
                if (
                    re.search(self.common.stop_before_row_regex,
                              line) is not None
                    and self.common.stop_before_row_regex != ""
                ):
                    break
                for pre_proc_func in self.pre_process_funcs:
                    line = pre_proc_func.exec(line)
                if line != "\n":
                    lines.append(line)
        with open(self.temp_filename, "w", encoding="utf-8") as _temp:
            self.common.log.info(f"writing temp file {self.temp_filename}")
            _temp.writelines(lines)
            _temp.flush()

        self.common.log.info(f"creating {len(self.db_functions)} DB functions")
        for db_func in self.db_functions:
            self.common.conn.create_function(
                name=db_func.name,
                function=db_func.function,
                parameters=db_func.params,
                return_type=db_func.return_type,
                type=NATIVE,
                null_handling=db_func.null_handling,
            )

    def import_csv(self) -> None:
        """imports given file into internal DuckDB table"""
        self.common.log.info(f"importing csv from {self.common.filename}")
        try:
            table = self.common.conn.read_csv(
                self.temp_filename,
                header=True,
                na_values=["NULL", "", "No description", "Free"],
                thousands=",",
                columns=self.columns,
            )
            table.to_table("transactions")
            self.common.log.info(f"cleaning up {self.temp_filename}")
            os.unlink(self.temp_filename)
        except DatabaseError as _e:
            self.common.log.error(
                f"DuckDB exception; temp file {self.temp_filename} remains for debugging"
            )
            raise _e
