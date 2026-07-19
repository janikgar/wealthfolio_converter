from internal import (
    ImportSource,
    PreProcessPattern,
    DuckDbFunction,
    WF_COLUMNS,
    WF_TYPES,
)
from duckdb import DuckDBPyConnection, InvalidInputException, DuckDBPyRelation
from duckdb.func import SPECIAL, NATIVE
from tempfile import mkstemp
from decimal import Decimal
import re
import os
from dataclasses import dataclass, field


def coalesce_missing_unit_price(
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


def wf_map_activity_types(value: str) -> str:
    if re.match(r"Reinvestment|Capital gain.*", value):
        value = "BUY"

    possible_match = WF_TYPES.intersection([value.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    else:
        return value


DEFAULT_PREPROCESS = [
    # remove lines with all commas
    PreProcessPattern(r'^(?:,|\s)*$', ""),

    # remove all literal dollar signs
    PreProcessPattern(r"\$", ""),

    # replace all quoted accounting negatives
    PreProcessPattern(r',"\((.*?)\)",', r',"-\1",'),

    # replace all unquoted accounting negatives
    PreProcessPattern(r',\((.*?)\),', r',-\1,'),

    # normalize all dates
    PreProcessPattern(r',(\d/\d+/\d+),', r',0\1,'),
    PreProcessPattern(r',(\d+)/(\d/\d+),', r',\1/0\2,'),
    PreProcessPattern(r',(\d+/\d+)/(\d{2}),', r',\1/20\2,'),
]

DEFAULT_FUNCTIONS = [
    DuckDbFunction("map_activity_types", wf_map_activity_types, ["VARCHAR"], "VARCHAR"),
    DuckDbFunction(
        "coalesce_missing_unit_price",
        coalesce_missing_unit_price,
        ["DECIMAL", "DECIMAL", "DECIMAL"],
        "DECIMAL",
        null_handling=SPECIAL,
    ),
]


@dataclass
class Vanguard(ImportSource):
    filename: str
    conn: DuckDBPyConnection
    start_row_regex: str = r"Trade"
    pre_process_funcs: list[PreProcessPattern] = field(
        default_factory=lambda: DEFAULT_PREPROCESS
    )
    db_functions: list[DuckDbFunction] = field(
        default_factory=lambda: DEFAULT_FUNCTIONS
    )

    def __post_init__(self):
        (_, self.temp_filename) = mkstemp(prefix="vanguard-", suffix=".csv", text=True)

    def pre_process(self):
        with open(self.filename) as _c:
            lines: list[str] = []
            for line in _c.readlines():
                if re.search(self.start_row_regex, line) is not None:
                    lines.clear()
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
            ) # type: ignore

    def import_csv(self):
        try:
            table = self.conn.read_csv(
                self.temp_filename,
                header=True,
                na_values=["NULL", ""],
                thousands=",",
                columns=WF_COLUMNS,
            )
            table.to_table("transactions")
            os.unlink(self.temp_filename)
        except InvalidInputException as _e:
            print(self.temp_filename)
            raise _e

    def reshape(self) -> DuckDBPyRelation:
        self.conn.sql(
            """FROM transactions SELECT
                "Account Number" AS "account",
                "Trade Date" AS "date",
                Symbol as "symbol",
                'EQUITY' as "instrumentType",
                COALESCE(IF(Shares == 0, 1, Shares), 1) as "quantity",
                map_activity_types("Transaction Type") AS "activityType",
                coalesce_missing_unit_price("Shares", "Share Price", "Net Amount") AS "unitPrice",
                'USD' AS "currency",
                "Commissions and Fees" as "fee",
                "Net Amount" AS "amount",
                "Transaction Description" AS "comment",
            """
        ).to_table("wealthfolio")
        return self.conn.table("wealthfolio")
