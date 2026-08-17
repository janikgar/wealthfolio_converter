#!/usr/bin/env python3
"""
wf_converter.py converts files from various financial data sources into a common
format for ingestion into Wealthfolio (https://wealthfolio.app).
"""
import sys
import os
from argparse import ArgumentParser, Namespace

import duckdb
from dotenv import load_dotenv
from botocore.config import Config

from wealthfolio_converter.internal import (
    ImportSource,
    WFLogger,
    CommonConfig,
    classify_input,
    save_output,
)
from wealthfolio_converter.s3 import S3Config
from wealthfolio_converter.vanguard import Vanguard
from wealthfolio_converter.fidelity import Fidelity
from wealthfolio_converter.trowe import TRowe


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
    load_dotenv()

    s3_config = S3Config(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
        region_name='homelab',
        endpoint_url='192.168.1.28:30900',
        config=Config(
            region_name='homelab',
            s3={
                'addressing_style': 'path'
            }
        )
    )

    input_fn, s3_input_bucket = classify_input(args.input, log, s3_config)

    conn = duckdb.connect()

    import_object: ImportSource

    common_config = CommonConfig(
        filename=input_fn,
        conn=conn,
        log=log,
    )

    log.info(f"using format {args.format}")
    if args.format == "vanguard-xlsx":
        import_object = Vanguard(common_config)
        import_object.xlsx_to_csv()

    elif args.format == "vanguard":
        import_object = Vanguard(common_config)

    elif args.format == "fidelity":
        import_object = Fidelity(common_config)

    elif args.format == "trowe":
        import_object = TRowe(common_config)

    else:
        log.error(f"could not parse format {args.format}")
        sys.exit(0)

    import_object.pre_process()
    import_object.import_csv()

    output_table = import_object.reshape()
    output_table.show()

    log.info(f"writing final output to {args.output}")

    s3_output_bucket = save_output(args.output, output_table, log, s3_config)

    if s3_input_bucket:
        os.unlink(s3_input_bucket.temp_filename)
    if s3_output_bucket:
        os.unlink(s3_output_bucket.temp_filename)
