"""
Defines constants, queries, DuckDB functions, and DTOs for Fidelity
"""
import re
from dataclasses import dataclass, field
from typing import Dict
from decimal import Decimal
from duckdb import DuckDBPyRelation
from duckdb.func import SPECIAL
from .internal import ImportSource, PreProcessPattern, DuckDbFunction, WF_TYPES

FD_FUNDS: Dict[str, str] = {
    "AF EUPAC FUND R6": "RERGX",
    "TCW MW TOT RTN BD P": "MWTRX",
    "PRMCP ODYSSEY GROWTH": "POGRX",
    "DFA US LG CAP VAL": "DFLVX",
    "VANG TARGET RET 2055": "VFFVX",
    "FID 500 INDEX": "FXAIX",
    "DODGE & COX INCOME X": "DOXIX",
    "VANGUARD TARGET 2055": "VFFVX",
    "VANG VAL INDEX INST": "VIVIX",
    "SP 500 INDEX PL CL C": "SPICX",
    "SP TTL INTL IDX CL C": "SPARTAN",
    "JPM LG CAP GROWTH R6": "JLGMX",
    "FID TOTAL INTL IDX": "FTIHX",
    "No Description": "",
}


FD_QUERY: str = """
    FROM transactions SELECT
    concat_ws(' ', "Account Number", Account) AS account,
    "Run Date" AS date,
    COALESCE(Symbol, fd_map_funds(Description), '') AS symbol,
    'EQUITY' as instrumentType,
    COALESCE(IF(Quantity == 0, 1, Quantity), 1) AS quantity,
    fd_map_exchange_activity(Amount, COALESCE(Symbol, fd_map_funds(Description), ''), Action) AS activityType,
    fd_coalesce_missing_unit_price(Quantity, Price, Amount) AS unitPrice,
    'USD' AS currency,
    Commission + Fees AS fee,
    Amount AS amount,
    IF(Description == 'No Description', Action, Description) AS comment,
    fd_add_subtype(Action) AS subtype,
"""


def fd_map_funds(name: str) -> str:
    """DuckDB function for mapping fund names to ticker symbols"""
    if name in FD_FUNDS:
        return FD_FUNDS[name]
    return name


def fd_map_activity_types(action: str) -> str:
    """
    DuckDB function for mapping activity types to standard Wealthfolio types
    """
    if re.match(r"FOREIGN TAX", action):
        action = "TAX"

    if re.match(r"ADJUST FEE", action):
        action = "FEE"

    if re.match(r"(YOU BOUGHT|REINVESTMENT|EXCHANGED TO).*", action):
        action = "BUY"

    if re.match(r"YOU SOLD.*", action):
        action = "SELL"

    if re.match(r"DIVIDEND RECEIVED", action):
        action = "DIVIDEND"

    if re.match(r"(DIRECT DEPOSIT|INTEREST EARNED FDIC INSURED DEPOSIT)", action):
        action = "DEPOSIT"

    if re.match(
        r"(ROLLOVER FROM|TRANSFERRED FROM|Contribution|ELECTRONIC FUNDS TRANSFER RECEIVED|"
        "REVENUE CREDIT|ROLLOVER CASH DIRECT ROLLOVER FROM)",
        action,
        re.IGNORECASE,
    ):
        action = "TRANSFER IN"

    if re.match(
        r"(WITHDRAWALS|DIRECT DEBIT|DEBIT CARD PURCHASE|Electronic Funds Transfer Paid|" \
        "CASH ADVANCE)",
        action,
    ):
        action = "WITHDRAWAL"

    if re.match(r"(TRANSFERRED TO|TRANSFER OF ASSETS ACAT).*", action):
        action = "TRANSFER OUT"

    possible_match = WF_TYPES.intersection([action.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    return action


def fd_add_subtype(action: str) -> str:
    """DuckDB function for adding relevant Wealthfolio subtypese"""
    if re.match(r"REINVESTMENT", action):
        return "DRIP"
    return ""


def fd_map_exchange_activity(amount: Decimal, symbol: str, action: str) -> str:
    """
    DuckDB function for special mapping types related to exchanges or
    realized gains/losses
    """
    return_type = fd_map_activity_types(action)
    if re.match("Exchanges", action):
        if symbol == "BROKERAGELINK":
            if amount < 0:
                return_type = "WITHDRAWAL"
            else:
                return_type = "DEPOSIT"
        elif amount < 0:
            return_type = "BUY"
        else:
            return_type = "SELL"

    if re.match("Realized", action):
        if amount < 0:
            return_type = "WITHDRAWAL"
        else:
            return_type = "DEPOSIT"
    return return_type


def fd_coalesce_missing_unit_price(
    quantity: Decimal, unit_price: Decimal, amount: Decimal
) -> Decimal:
    """
    DuckDB function to determine sane default values for unit prices (often
    useful for cash transactions or money market funds)
    """
    if unit_price == 0 and quantity == 0:
        return amount
    if not quantity:
        quantity = Decimal("1")
    if not amount:
        amount = Decimal("1")
    if unit_price == 0 or unit_price is None:
        return amount / quantity

    return unit_price


DEFAULT_FUNCTIONS = [
    DuckDbFunction(
        "fd_map_activity_types", fd_map_activity_types, ["VARCHAR"], "VARCHAR"
    ),
    DuckDbFunction("fd_add_subtype", fd_add_subtype, ["VARCHAR"], "VARCHAR"),
    DuckDbFunction(
        "fd_map_exchange_activity",
        fd_map_exchange_activity,
        ["DECIMAL", "VARCHAR", "VARCHAR"],
        "VARCHAR",
        null_handling=SPECIAL,
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
    """Fidelity transaction table class"""
    columns: Dict[str, str] = field(default_factory=lambda: FD_COLUMNS)
    source_name: str = "fidelity"
    start_row_regex: str = r"Run Date"
    stop_before_row_regex: str = r"The data and information"
    pre_process_funcs: list[PreProcessPattern] = field(default_factory=list)
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def __post_init__(self):
        self.mktemp()
        self.common.source_name = self.source_name
        self.common.start_row_regex = self.start_row_regex
        self.common.stop_before_row_regex = self.stop_before_row_regex

    def reshape(self) -> DuckDBPyRelation:
        """Reshape function for Fidelity"""
        self.common.conn.sql(FD_QUERY).to_table(self.source_name)
        return self.common.conn.table(self.source_name)
