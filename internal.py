import re
from typing import List, Callable, Union
from decimal import Decimal
from duckdb.func import FunctionNullHandling, DEFAULT
from duckdb import DuckDBPyConnection
from dataclasses import dataclass, field

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

WF_COLUMNS = {
    "Account Number": "bigint",
    "Trade Date": "date",
    "Settlement Date": "date",
    "Transaction Type": "varchar",
    "Transaction Description": "varchar",
    "Investment Name": "varchar",
    "Symbol": "varchar",
    "Shares": "decimal",
    "Share Price": "decimal",
    "Principal Amount": "decimal",
    "Commissions and Fees": "decimal",
    "Net Amount": "decimal",
    "Accrued Interest": "decimal",
    "Account Type": "varchar",
}


@dataclass
class PreProcessPattern:
    match: str
    sub: str
    debug: bool = False

    def exec(self, line: str) -> str:
        subst = re.sub(self.match, self.sub, line)
        if self.debug and subst != "":
            print(subst)
        return subst


@dataclass
class DuckDbFunction:
    name: str
    function: Callable
    params: list[str]
    return_type: str
    null_handling: FunctionNullHandling = DEFAULT


@dataclass
class ImportSource:
    filename: str
    conn: DuckDBPyConnection
    start_row_regex: str = ""
    pre_process_funcs: List[PreProcessPattern] = field(default_factory=list)
