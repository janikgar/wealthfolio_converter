"""
Internal classes used by other modules.
"""
import re
import os
from dataclasses import dataclass, field
from logging import Logger, StreamHandler, Formatter
from typing import List, Callable, Dict, Any
from tempfile import mkstemp
from duckdb.func import FunctionNullHandling, DEFAULT, NATIVE
from duckdb import DuckDBPyConnection, DatabaseError

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
class ImportSource:  # pylint: disable=R0902
    """
    Vendor-independent base class for all data imports.
    After data class initialization, a temp file is always created for
    intermediate processing.
    """
    common: CommonConfig
    pre_process_funcs: List[PreProcessPattern] = field(default_factory=list)
    db_functions: list[DuckDbFunction] = field(default_factory=list)
    columns: Dict[str, str] = field(default_factory=Dict[str, str])

    def __post_init__(self):
        self.mktemp()

    def mktemp(self):
        _, self.temp_filename = mkstemp(
            prefix=f"{self.common.source_name}-", text=True
        )
        self.common.log.info(f"created temp file {self.temp_filename}")

    def pre_process(self):
        """executes all stored pre-processing substitutions"""
        self.common.log.info("beginning pre-processing")
        with open(self.common.filename, encoding="utf-8") as _c:
            lines: list[str] = []
            for line in _c.readlines():
                if self.common.start_row_regex != "" and \
                        re.search(self.common.start_row_regex, line) is not None:
                    lines.clear()
                if (
                    re.search(self.common.stop_before_row_regex,
                              line) is not None
                    and self.common.stop_before_row_regex != ""
                ):
                    break
                for func in self.pre_process_funcs:
                    line = func.exec(line)
                if line != "":
                    lines.append(line)
        with open(self.temp_filename, "w", encoding="utf-8") as _temp:
            self.common.log.info(f"writing temp file {self.temp_filename}")
            _temp.writelines(lines)
            _temp.flush()

        self.common.log.info(f"creating {len(self.db_functions)} DB functions")
        for func in self.db_functions:
            self.common.conn.create_function(
                name=func.name,
                function=func.function,
                parameters=func.params,
                return_type=func.return_type,
                type=NATIVE,
                null_handling=func.null_handling,
            )

    def import_csv(self):
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


class WFLogger(Logger):
    """Base logging class to be passed into other classes."""

    def init(self):
        """Instantiate class-specific logging"""
        h = StreamHandler()
        f = Formatter(
            "{levelname:s} - {filename:s}:{lineno:d} ({funcName:s}) - {message:s}",
            style="{",
        )
        h.setFormatter(f)
        self.addHandler(h)
