#!/usr/bin/env python3
import duckdb
import sys
from internal import ImportSource, WFLogger
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
        "--format",
        "-f",
        help="format of input file",
        choices=["fidelity", "vanguard", "vanguard-xlsx", "trowe"],
        type=str,
        required=True,
    )
    ap.add_argument(
        "--output",
        "-o",
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
    log = WFLogger("main", "DEBUG")
    log.init()
    args = parse_args()

    conn = duckdb.connect()

    import_object: ImportSource
    import_args = {
        "filename": args.input,
        "conn": conn,
        "log": log,
    }

    log.info(f"using format {args.format}")
    if args.format == "vanguard-xlsx":
        import_object = Vanguard(**import_args)
        import_object.xlsx_to_csv()

    elif args.format == "vanguard":
        import_object = Vanguard(**import_args)

    elif args.format == "fidelity":
        import_object = Fidelity(**import_args)

    elif args.format == "trowe":
        import_object = TRowe(**import_args)

    else:
        log.error(f"could not parse format {args.format}")
        sys.exit(0)

    import_object.pre_process()
    import_object.import_csv()

    output_table = import_object.reshape()
    output_table.show()

    log.info(f"writing final output to {args.output}")
    output_table.to_csv(args.output)
