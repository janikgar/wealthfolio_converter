from dataclasses import dataclass, field
from typing import Dict
from duckdb import DuckDBPyConnection, DuckDBPyRelation
from duckdb.func import SPECIAL
from decimal import Decimal
from internal import ImportSource, PreProcessPattern, DuckDbFunction, WFLogger, WF_TYPES
import re

FD_FUNDS: Dict[str, str] = {
    "AF EUPAC FUND R6": "RERGX",
    "TCW MW TOT RTN BD P": "MWTRX",
    "PRMCP ODYSSEY GROWTH": "POGRX",
    "DFA US LG CAP VAL": "DFLVX",
    "VANG TARGET RET 2055": "VFFVX",
    "FID 500 INDEX": "FXAIX",
    "DODGE & COX INCOME X": "DOXIX",
}


FD_QUERY : str = """
    FROM transactions SELECT
    concat_ws(' ', "Account Number", "Account") AS "account",
    "Run Date" AS "date",
    COALESCE(Symbol, fd_map_funds(Description), '') as "symbol",
    'EQUITY' as "instrumentType",
    COALESCE(IF(Quantity == 0, 1, Quantity), 1) as "quantity",
    IF(regexp_matches("Action", '^(Exchanges|Realized)'), fd_map_exchange_activity("Amount"), fd_map_activity_types("Action")) AS "activityType",
    fd_coalesce_missing_unit_price("Quantity", "Price", "Amount") AS "unitPrice",
    'USD' AS "currency",
    "Commission" + "Fees" as "fee",
    "Amount" AS "amount",
    IF("Description" == 'No Description', "Action", "Description") AS "comment",
    fd_add_subtype("Action") AS "subtype",
"""


def fd_map_funds(name: str) -> str:
    if name in set(FD_FUNDS.keys()):
        return FD_FUNDS[name]
    return name


def fd_map_activity_types(action: str) -> str:
    if re.match(r"(YOU BOUGHT|REINVESTMENT).*", action):
        action = "BUY"

    if re.match(r"YOU SOLD.*", action):
        action = "SELL"

    if re.match(r"DIVIDEND RECEIVED.*", action):
        action = "DIVIDEND"

    if re.match(r"(DIRECT DEPOSIT|Contribution).*", action):
        action = "DEPOSIT"

    if re.match(r"(.*ROLLOVER FROM|TRANSFERRED FROM).*", action):
        action = "TRANSFER IN"

    if re.match(
        r"(WITHDRAWALS|DIRECT DEBIT|DEBIT CARD PURCHASE|Electronic Funds Transfer Paid)",
        action,
    ):
        action = "WITHDRAWAL"

    if re.match(r"(TRANSFERRED TO|TRANSFER OF ASSETS ACAT).*", action):
        action = "TRANSFER OUT"

    possible_match = WF_TYPES.intersection([action.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    else:
        return action


def fd_add_subtype(action: str) -> str:
    if re.match(r"REINVESTMENT", action):
        return "DRIP"
    return ""


def fd_map_exchange_activity(amount: Decimal) -> str:
    if amount < 0:
        return "BUY"
    else:
        return "SELL"


def fd_coalesce_missing_unit_price(
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


DEFAULT_FUNCTIONS = [
    DuckDbFunction(
        "fd_map_activity_types", fd_map_activity_types, ["VARCHAR"], "VARCHAR"
    ),
    DuckDbFunction("fd_add_subtype", fd_add_subtype, ["VARCHAR"], "VARCHAR"),
    DuckDbFunction(
        "fd_map_exchange_activity", fd_map_exchange_activity, ["DECIMAL"], "VARCHAR"
    ),
    DuckDbFunction(
        "fd_coalesce_missing_unit_price",
        fd_coalesce_missing_unit_price,
        ["DECIMAL", "DECIMAL", "DECIMAL"],
        "DECIMAL",
        null_handling=SPECIAL,
    ),
    DuckDbFunction(
        "fd_map_funds",
        fd_map_funds,
        ["VARCHAR"],
        "VARCHAR",
    ),
]

FD_COLUMNS: Dict[str, str] = {
    "Run Date": "date",
    "Account": "varchar",
    "Account Number": "varchar",
    "Action": "varchar",
    "Symbol": "varchar",
    "Description": "varchar",
    "Type": "varchar",
    "Exchange Quantity": "decimal",
    "Exchange Currency": "varchar",
    "Currency": "varchar",
    "Price": "decimal",
    "Quantity": "decimal",
    "Exchange Rate": "decimal",
    "Commission": "decimal",
    "Fees": "decimal",
    "Accrued Interest": "decimal",
    "Amount": "decimal",
    "Settlement Date": "date",
}


@dataclass
class Fidelity(ImportSource):
    filename: str
    conn: DuckDBPyConnection
    log: WFLogger
    columns: Dict[str, str] = field(default_factory=lambda: FD_COLUMNS)
    source_name: str = "fidelity"
    start_row_regex: str = r"Run Date"
    stop_before_row_regex: str = r"The data and information"
    pre_process_funcs: list[PreProcessPattern] = field(default_factory=list)
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def reshape(self) -> DuckDBPyRelation:
        self.conn.sql(FD_QUERY).to_table(self.source_name)
        return self.conn.table(self.source_name)
