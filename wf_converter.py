#!/usr/bin/env python3
import duckdb
from vanguard import Vanguard
from fidelity import Fidelity
from argparse import ArgumentParser, Namespace
from trowe import TRowe


def parse_args() -> Namespace:
    ap = ArgumentParser(
        prog="wf_converter.py",
        description="""Converts from financial firm-generated
                       CSVs to Wealthfolio's format""",
    )
    ap.add_argument(
        "--format", "-f",
        help="format of input CSV",
        choices=["fidelity", "vanguard", "trowe"],
        type=str,
        required=True,
    )
    ap.add_argument(
        "--output", "-o",
        help="output filename",
        type=str,
        required=True,
    )
    ap.add_argument(
        "input",
        help="input filename",
        type=str,
    )

    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()

    conn = duckdb.connect()

    if args.format == "vanguard":
        vanguard_import = Vanguard(filename=args.input, conn=conn)
        vanguard_import.pre_process()
        vanguard_import.import_csv()

        wf_table = vanguard_import.reshape()

        wf_table.show()
        wf_table.to_csv(args.output)

    if args.format == "fidelity":
        fidelity_import = Fidelity(filename=args.input, conn=conn)
        fidelity_import.pre_process()
        fidelity_import.import_csv()

        fd_table = fidelity_import.reshape()

        fd_table.show()
        fd_table.to_csv(args.output)

    if args.format == "trowe":
        trowe_import = TRowe(filename=args.input, conn=conn)
        trowe_import.pre_process()
        trowe_import.import_csv()

        tr_table = trowe_import.reshape()
        tr_table.show()
        tr_table.to_csv(args.output)
