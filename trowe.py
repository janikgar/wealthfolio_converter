from dataclasses import dataclass, field
from duckdb import DuckDBPyConnection, DuckDBPyRelation
from internal import ImportSource, PreProcessPattern, DuckDbFunction
from typing import Dict
from decimal import Decimal
import re

TR_FUNDS: Dict[str, str] = {
    "DODGE & COX INCOME X": "DODIX",
    "DODGE & COX INCOME I": "DODIX",
    "VANGUARD INST INDEX   PLUS": "VIIIX",
    "AMERICAN FUNDS EUPAC R6": "RERGX",
}


def tr_map_activity_types(action: str) -> str:
    if action == "Contribution" or action == "Misc. Receipt":
        return "BUY"

    action = action.upper()

    action = re.sub("EXCHANGE", "TRANSFER", action)

    return action


def tr_map_funds(name: str) -> str:
    if name in set(TR_FUNDS.keys()):
        return TR_FUNDS[name]
    return name

DEFAULT_PREPROCESS = [
    # remove literal dollar signs
    PreProcessPattern(r"\$", ""),
    PreProcessPattern(r"^.*(Rounding Adjustment|Market Fluctuation).*", "")
]


DEFAULT_FUNCTIONS = [
    DuckDbFunction(
        "tr_map_activity_types",
        tr_map_activity_types,
        ["VARCHAR"],
        "VARCHAR",
    ),
    DuckDbFunction(
        "tr_map_funds",
        tr_map_funds,
        ["VARCHAR"],
        "VARCHAR",
    ),
]


TR_COLUMNS: Dict[str, str] = {
    "Date": "date",
    "Activity Type": "varchar",
    "Investment": "varchar",
    "Source": "varchar",
    "Amount": "varchar",
    "Shares": "decimal",
    "Price": "varchar",
}


@dataclass
class TRowe(ImportSource):
    filename: str
    conn: DuckDBPyConnection
    columns: Dict[str, str] = field(default_factory=lambda: TR_COLUMNS)
    source_name: str = "trowe"
    start_row_regex: str = r"Activity Type"
    pre_process_funcs: list[PreProcessPattern] = field(
        default_factory=lambda: DEFAULT_PREPROCESS
    )
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def reshape(self) -> DuckDBPyRelation:
        self.conn.sql("""FROM transactions SELECT
                      Date AS "date",
                      tr_map_activity_types("Activity Type") AS "activityType",
                      tr_map_funds("Investment") AS "symbol",
                      "Source" AS "comment",
                      'EQUITY' as "instrumentType",
                      'USD' AS "currency",
                      "Shares" AS "quantity",
                      "Price" AS "unitPrice",
                      CAST("Amount" AS DECIMAL) AS "amount",
                      """).to_table(self.source_name)
        return self.conn.table(self.source_name)
