from internal import (
    ImportSource,
    PreProcessPattern,
    DuckDbFunction,
    WF_TYPES,
)
from duckdb import DuckDBPyConnection, DuckDBPyRelation
from duckdb.func import SPECIAL
from decimal import Decimal
import re
from dataclasses import dataclass, field
from typing import Dict


VG_COLUMNS = {
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


def vg_coalesce_missing_unit_price(
    quantity: Decimal, unit_price: Decimal, amount: Decimal
) -> Decimal:
    if not quantity:
        quantity = Decimal("1")
    if not amount:
        amount = Decimal("1")
    if unit_price == 0 and quantity == 0:
        return amount
    if unit_price == 0 or unit_price is None:
        return amount / quantity

    return unit_price


def vg_map_activity_types(action: str) -> str:
    if re.match(r"Reinvestment|Capital gain.*", action):
        action = "BUY"

    possible_match = WF_TYPES.intersection([action.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    else:
        return action


DEFAULT_PREPROCESS = [
    # remove lines with all commas
    PreProcessPattern(r"^(?:,|\s)*$", ""),
    # replace all quoted accounting negatives
    PreProcessPattern(r',"\((.*?)\)",', r',"-\1",'),
    # replace all unquoted accounting negatives
    PreProcessPattern(r",\((.*?)\),", r",-\1,"),
    # normalize all dates
    PreProcessPattern(r",(\d/\d+/\d+),", r",0\1,"),
    PreProcessPattern(r",(\d+)/(\d/\d+),", r",\1/0\2,"),
    PreProcessPattern(r",(\d+/\d+)/(\d{2}),", r",\1/20\2,"),
]

DEFAULT_FUNCTIONS = [
    DuckDbFunction("vg_map_activity_types", vg_map_activity_types, ["VARCHAR"], "VARCHAR"),
    DuckDbFunction(
        "vg_coalesce_missing_unit_price",
        vg_coalesce_missing_unit_price,
        ["DECIMAL", "DECIMAL", "DECIMAL"],
        "DECIMAL",
        null_handling=SPECIAL,
    ),
]


@dataclass
class Vanguard(ImportSource):
    filename: str
    conn: DuckDBPyConnection
    source_name = "vanguard"
    columns: Dict[str, str] = field(default_factory=lambda: VG_COLUMNS)
    start_row_regex: str = r"Trade"
    pre_process_funcs: list[PreProcessPattern] = field(
        default_factory=lambda: DEFAULT_PREPROCESS
    )
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def reshape(self) -> DuckDBPyRelation:
        self.conn.sql(
            """FROM transactions SELECT
                "Account Number" AS "account",
                "Trade Date" AS "date",
                Symbol as "symbol",
                'EQUITY' as "instrumentType",
                COALESCE(IF(Shares == 0, 1, Shares), 1) as "quantity",
                vg_map_activity_types("Transaction Type") AS "activityType",
                vg_coalesce_missing_unit_price("Shares", "Share Price", "Net Amount") AS "unitPrice",
                'USD' AS "currency",
                "Commissions and Fees" as "fee",
                "Net Amount" AS "amount",
                "Transaction Description" AS "comment",
            """
        ).to_table(self.source_name)
        return self.conn.table(self.source_name)
