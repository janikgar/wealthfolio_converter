"""
Defines constants, queries, DuckDB functions, and DTOs for Fidelity
"""
from decimal import Decimal
import re
import csv
import os.path
from dataclasses import dataclass, field
from typing import Dict

from duckdb import DuckDBPyRelation
from duckdb.func import SPECIAL

from .internal import (
    ImportSource,
    PreProcessPattern,
    DuckDbFunction,
    WF_TYPES,
    CommonConfig,
)

VG_COLUMNS: Dict[str, str] = {
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

VG_QUERY: str = """
    FROM transactions SELECT
    "Account Number" AS "account",
    "Trade Date" AS "date",
    Symbol as "symbol",
    'EQUITY' as "instrumentType",
    COALESCE(IF(Shares == 0, 1, Shares), 1) as "quantity",
    vg_map_activity_types("Transaction Type", Shares) AS "activityType",
    vg_coalesce_missing_unit_price("Shares", "Share Price", "Net Amount") AS "unitPrice",
    'USD' AS "currency",
    "Commissions and Fees" as "fee",
    "Net Amount" AS "amount",
    "Transaction Description" AS "comment",
"""

VG_XLSX_COLUMNS: Dict[str, str] = {
    "Settlement Date": "date",
    "Trade Date": "date",
    "Symbol": "varchar",
    "Investment Name": "varchar",
    "Transaction Type": "varchar",
    "Account Type": "varchar",
    "Quantity": "decimal",
    "Price": "decimal",
    "Commission & fees**": "decimal",
    "Amount": "decimal",
}

VG_XLSX_QUERY: str = """
    FROM transactions SELECT
    "Trade Date" as "date",
    Symbol as "symbol",
    'EQUITY' as "instrumentType",
    COALESCE(IF(Quantity == 0, 1, Quantity), 1) as "quantity",
    vg_map_activity_types("Transaction Type", Quantity) AS "activityType",
    vg_coalesce_missing_unit_price("Quantity", "Price", "Amount") AS "unitPrice",
    'USD' AS "currency",
    "Commission & fees**" as "fee",
    "Amount" AS "amount",
    "Investment Name" AS "comment",
"""


def vg_coalesce_missing_unit_price(
    quantity: Decimal, unit_price: Decimal, amount: Decimal
) -> Decimal:
    """
    DuckDB function to determine sane default values for unit prices (often
    useful for cash transactions or money market funds)
    """
    if not quantity:
        quantity = Decimal("1")
    if not amount:
        amount = Decimal("1")
    if unit_price == 0 and quantity == 0:
        return amount
    if unit_price == 0 or unit_price is None:
        return amount / quantity

    return unit_price


def vg_map_activity_types(action: str, quantity: Decimal) -> str:
    """
    DuckDB function for mapping activity types to standard Wealthfolio types
    """
    if re.match(r"Buy|Reinvestment|Capital gain.*", action):
        action = "BUY"

    if re.match(r"Sell", action):
        action = "SELL"

    if re.match(r"Exchange", action, re.IGNORECASE):
        if quantity > 0:
            action = "BUY"
        else:
            action = "SELL"

    if re.match(
        r"(Conversion \(incoming\)|Funds Received|(Transfer|Rollover) \(incoming\))",
        action,
        re.IGNORECASE,
    ):
        action = "TRANSFER IN"

    if re.match(
        r"(Transfer To|Rollover To|Transfer \(Outgoing\)|Conversion \(Outgoing\))",
        action,
        re.IGNORECASE,
    ):
        action = "TRANSFER OUT"

    if re.match(r"Withholding", action):
        action = "TAX"

    if re.match(r"Contribution", action):
        action = "DEPOSIT"

    if re.match(r"Distribution", action):
        action = "WITHDRAWAL"

    if re.match(r"Stock split", action):
        action = "SPLIT"

    possible_match = WF_TYPES.intersection([action.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    return action


DEFAULT_PREPROCESS = [
    # drop all sweep lines
    PreProcessPattern(r".*(Sweep).*", ""),
    # remove literal dollar signs
    PreProcessPattern(r"\$", ""),
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
    DuckDbFunction(
        "vg_map_activity_types",
        vg_map_activity_types,
        ["VARCHAR", "DECIMAL"],
        "VARCHAR",
        null_handling=SPECIAL,
    ),
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
    """Vanguard transaction table class"""
    common: CommonConfig
    start_row_regex: str = r"Trade"
    source_name: str = "vanguard"
    query: str = VG_QUERY
    columns: Dict[str, str] = field(default_factory=lambda: VG_COLUMNS)
    pre_process_funcs: list[PreProcessPattern] = field(
        default_factory=lambda: DEFAULT_PREPROCESS
    )
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def xlsx_to_csv(self):
        """Utility class for converting Excel XLSX to CSV"""
        self.common.log.info("converting Vanguard xlsx to csv")
        self.common.conn.install_extension("excel")
        self.common.conn.load_extension("excel")

        temp_table = self.common.conn.execute(
            "SELECT * FROM read_xlsx(?, range = 'A4:J')", [self.common.filename]
        ).fetchall()

        self.common.log.info(f"raw XLSX has {len(temp_table)} rows")

        filtered_table = [row for row in temp_table if None not in row]

        self.common.log.info(f"filtered XLSX has {len(filtered_table)} rows")

        csv_filebase, _ = os.path.splitext(os.path.basename(self.common.filename))
        csv_filename = f"{csv_filebase}.csv"
        with open(csv_filename, "w", encoding="utf-8") as _csv:
            csv_writer = csv.writer(_csv)
            csv_writer.writerow(VG_XLSX_COLUMNS.keys())
            csv_writer.writerows(filtered_table)

        self.common.log.info(f"converted XLSX written to {csv_filename}")

        # mutate object with newly-created file, separate columns,
        # and separate regex to stop ingesting data
        self.common.filename = csv_filename
        self.columns = VG_XLSX_COLUMNS
        self.common.stop_before_row_regex = "DISCLOSURES"
        self.query = VG_XLSX_QUERY

    def reshape(self) -> DuckDBPyRelation:
        """Reshape function for Vanguard"""
        self.common.log.info(f"reshaping {self.common.source_name}-formatted file to table")
        self.common.conn.sql(self.query).to_table(self.common.source_name)
        return self.common.conn.table(self.common.source_name)
