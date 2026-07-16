#!/usr/bin/env python3
import duckdb
import re
import tempfile
import sys
import os


def preprocess_vanguard_csv(csvfile: str) -> str:
    with open(csvfile) as _c:
        lines: list[str] = []
        for line in _c.readlines():
            if re.search(r'Trade', line) is not None:
                lines.clear()

            # remove lines with all commas
            line = re.sub(r'^,*$', '', line)

            # remove all literal dollar signs
            line = re.sub(r'\$', '', line)

            # replace all quoted accounting negatives
            line = re.sub(r',"\((.*?)\)",', r',"-\1",', line)

            # replace all unquoted accounting negatives
            line = re.sub(r',\((.*?)\),', r',-\1,', line)

            # normalize all dates
            line = re.sub(r',(\d/\d+/\d+),', r',0\1,', line)
            line = re.sub(r',(\d+)/(\d/\d+),', r',\1/0\2,', line)
            line = re.sub(r',(\d+/\d+)/(\d{2}),', r',\1/20\2,', line)
            if line != '':
                lines.append(line)
    (_, temp_file) = tempfile.mkstemp(suffix=".csv", text=True)
    with open(temp_file, 'w') as _temp:
        _temp.writelines(lines)
        _temp.flush()
    return temp_file


def import_csv(csv_filename: str, conn: duckdb.DuckDBPyConnection):
    processed_file = preprocess_vanguard_csv(csv_filename)
    try:
        table = conn.read_csv(
            processed_file,
            header=True,
            na_values=["NULL", ""],
            thousands=",",
            columns={
                'Account Number': "bigint",
                'Trade Date': "date",
                'Settlement Date': "date",
                'Transaction Type': "varchar",
                'Transaction Description': "varchar",
                'Investment Name': "varchar",
                'Symbol': "varchar",
                'Shares': "decimal",
                'Share Price': "decimal",
                'Principal Amount': "decimal",
                'Commissions and Fees': "decimal",
                'Net Amount': "decimal",
                'Accrued Interest': "decimal",
                'Account Type': "varchar"}
        )
        table.to_table("transactions")
        os.unlink(processed_file)
    except duckdb.InvalidInputException as _e:
        print(_e)
        print(processed_file)


def wealthfolio_reshape(conn: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
    conn.sql("""FROM transactions SELECT
                "Account Number" AS "account",
                "Trade Date" AS "date",
                Symbol as "symbol",
                'EQUITY' as "instrumentType",
                COALESCE(IF(Shares == 0, 1, Shares), 1) as "quantity",
                map_activity_types("Transaction Type") AS "activityType",
                COALESCE("Share Price", 1) AS "unitPrice",
                'USD' AS "currency",
                "Commissions and Fees" as "fee",
                "Net Amount" AS "amount",
                "Transaction Description" AS "comment",
            """).to_table("wealthfolio")
    return conn.table("wealthfolio")


def wf_map_activity_types(value: str) -> str:
    primary_types = {
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
        "ADJUSTMENT"
    }
        
    if re.match(r"Reinvestment|Capital gain.*", value):
        value = "BUY"

    possible_match = primary_types.intersection([value.upper()])

    if len(possible_match) > 0:
        return possible_match.pop()
    else:
        return value


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <csv file>")
        sys.exit(0)
    filename = sys.argv[1]

    # conn = duckdb.connect("vanguard.duckdb")
    conn = duckdb.connect()
    if len(conn.sql("SHOW")) == 0:
        import_csv(filename, conn)

    conn.create_function(
        "map_activity_types",
        wf_map_activity_types,
        [str],
        str
        )

    wf_table = wealthfolio_reshape(conn)

    wf_table.show()
