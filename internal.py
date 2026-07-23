import re
from typing import List, Callable, Dict, Any
from tempfile import mkstemp
from duckdb.func import FunctionNullHandling, DEFAULT, NATIVE
from duckdb import DuckDBPyConnection, InvalidInputException
from dataclasses import dataclass, field
import os

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
    match: str
    sub: str
    debug: bool = False

    def exec(self, line: str) -> str:
        if self.match == "":
            if self.debug:
                print("match empty; skipping substitution")
            return line
        subst = re.sub(self.match, self.sub, line)
        if self.debug and subst != "":
            print(subst)
        return subst


@dataclass
class DuckDbFunction:
    name: str
    function: Callable
    params: list[Any]
    return_type: str
    null_handling: FunctionNullHandling = DEFAULT


@dataclass
class ImportSource:
    filename: str
    conn: DuckDBPyConnection
    start_row_regex: str = ""
    stop_before_row_regex: str = ""
    source_name: str = ""
    pre_process_funcs: List[PreProcessPattern] = field(default_factory=list)
    db_functions: list[DuckDbFunction] = field(default_factory=list)
    columns: Dict[str, str] = field(default_factory=Dict[str, str])

    def __post_init__(self):
        _, self.temp_filename = mkstemp(
            prefix=f"{self.source_name}-", suffix=".csv", text=True
        )

    def pre_process(self):
        with open(self.filename) as _c:
            lines: list[str] = []
            for line in _c.readlines():
                if re.search(self.start_row_regex, line) is not None:
                    lines.clear()
                if (
                    re.search(self.stop_before_row_regex, line) is not None
                    and self.stop_before_row_regex != ""
                ):
                    break
                for func in self.pre_process_funcs:
                    line = func.exec(line)
                if line != "":
                    lines.append(line)
        with open(self.temp_filename, "w") as _temp:
            _temp.writelines(lines)
            _temp.flush()

        for func in self.db_functions:
            self.conn.create_function(
                name=func.name,
                function=func.function,
                parameters=func.params,
                return_type=func.return_type,
                type=NATIVE,
                null_handling=func.null_handling,
            )

    def import_csv(self):
        try:
            table = self.conn.read_csv(
                self.temp_filename,
                header=True,
                na_values=["NULL", "", "No description"],
                thousands=",",
                columns=self.columns,
            )
            table.to_table("transactions")
            os.unlink(self.temp_filename)
        except InvalidInputException as _e:
            print(self.temp_filename)
            raise _e
