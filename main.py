#!/usr/bin/env python3
import duckdb
import sys
from vanguard import Vanguard


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <csv file>")
        sys.exit(0)
    filename = sys.argv[1]

    # conn = duckdb.connect("vanguard.duckdb")
    conn = duckdb.connect()

    vanguard_import = Vanguard(filename=filename, conn=conn)
    vanguard_import.pre_process()
    vanguard_import.import_csv()

    wf_table = vanguard_import.reshape()

    wf_table.show()
    wf_table.to_csv("vanguard_converted.csv")
