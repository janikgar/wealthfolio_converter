"""
Defines constants, queries, DuckDB functions, and DTOs for T. Rowe Price
"""
from dataclasses import dataclass, field
from typing import Dict
import re
from duckdb import DuckDBPyRelation
from .internal import ImportSource, PreProcessPattern, DuckDbFunction

TR_FUNDS: Dict[str, str] = {
    "DODGE & COX INCOME X": "DODIX",
    "DODGE & COX INCOME I": "DODIX",
    "VANGUARD INST INDEX   PLUS": "VIIIX",
    "AMERICAN FUNDS EUPAC R6": "RERGX",
    "TRP RETIREMENT 2055 TR-F": "TRRNX",
    "TRP US MID-CAP VALUE EQ TR-D": "TRMCX",
    "TRP GROWTH STOCK TR-A": "PRGFX",
    "TRP US SMALL-CAP VALUE EQ TR-D": "PRSVX",
}


TR_QUERY: str = """
    FROM transactions SELECT
    Date AS "date",
    tr_map_activity_types("Activity Type") AS "activityType",
    tr_map_funds("Investment") AS "symbol",
    "Source" AS "comment",
    'EQUITY' as "instrumentType",
    'USD' AS "currency",
    "Shares" AS "quantity",
    "Price" AS "unitPrice",
    CAST("Amount" AS DECIMAL) AS "amount",
"""


def tr_map_activity_types(action: str) -> str:
    """
    DuckDB function for mapping activity types to standard Wealthfolio types
    """
    if re.match(r"Contribution|Misc\. Receipt", action):
        return "TRANSFER IN"

    if re.match(r"Exchange In|In Plan Roth Rollover In", action):
        return "BUY"

    if re.match(r"Exchange Out|In Plan Roth Rollover Out", action):
        return "SELL"

    if re.match(r"Withdrawal", action):
        return "TRANSFER OUT"

    action = action.upper()

    return action


def tr_map_funds(name: str) -> str:
    """DuckDB function for mapping fund names to ticker symbols"""
    if name in TR_FUNDS:
        return TR_FUNDS[name]
    return name


DEFAULT_PREPROCESS = [
    # remove literal dollar signs
    PreProcessPattern(r"\$", ""),
    PreProcessPattern(r"^.*(Rounding Adjustment|Market Fluctuation).*", ""),
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
    """T. Rowe Price transaction table class"""
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
        """Reshape function for T. Rowe Price"""
        self.common.conn.sql(TR_QUERY).to_table(self.source_name)
        return self.common.conn.table(self.source_name)
