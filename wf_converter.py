#!/usr/bin/env python3
import duckdb
import sys
from internal import ImportSource
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

    import_object: ImportSource

    if args.format == "vanguard":
        import_object = Vanguard(filename=args.input, conn=conn)

    elif args.format == "fidelity":
        import_object = Fidelity(filename=args.input, conn=conn)

    elif args.format == "trowe":
        import_object = TRowe(filename=args.input, conn=conn)

    else:
        sys.exit(0)

    import_object.pre_process()
    import_object.import_csv()

    output_table = import_object.reshape()
    output_table.show()
    output_table.to_csv(args.output)
