#!/usr/bin/env python3
"""
wf_converter.py converts files from various financial data sources into a common
format for ingestion into Wealthfolio (https://wealthfolio.app).
"""
import sys
import os
import re
from argparse import ArgumentParser, Namespace
from tempfile import NamedTemporaryFile

import duckdb
from s3 import S3Bucket

from internal import ImportSource, WFLogger
from vanguard import Vanguard
from fidelity import Fidelity
from trowe import TRowe


def parse_args() -> Namespace:
    """parses command line arguments"""
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

    s3_input_bucket: S3Bucket | None = None
    s3_pattern = re.compile(
        r"s3:\/\/(?P<bucket_name>.*?)\/(?P<object_path>.*)")
    s3_input_match = s3_pattern.fullmatch(args.input)
    if s3_input_match:
        log.info("detected S3 input path")
        s3_input_bucket = S3Bucket(s3_input_match.group('bucket_name'), log)
        s3_input_bucket.download_path(s3_input_match.group('object_path'))
        args.input = s3_input_bucket.temp_filename

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

    s3_output_bucket: S3Bucket | None = None
    s3_output_match = s3_pattern.fullmatch(args.output)
    if s3_output_match:
        log.info("detected S3 output path")
        s3_output_bucket = S3Bucket(s3_output_match.group('bucket_name'), log)
        with NamedTemporaryFile(mode="w+") as _o:
            output_table.to_csv(_o.name)
            s3_output_bucket.upload_path(
                _o.name, s3_output_match.group('object_path'))
    else:
        output_table.to_csv(args.output)

    if s3_input_bucket:
        os.unlink(s3_input_bucket.temp_filename)
    if s3_output_bucket:
        os.unlink(s3_output_bucket.temp_filename)
