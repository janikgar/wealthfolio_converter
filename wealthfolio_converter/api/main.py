import os
from urllib.parse import unquote_plus
from typing import Literal
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from aws_lambda_powertools.utilities.parser.models.s3 import S3Model, S3RecordModel
from botocore.config import Config
import duckdb
from wealthfolio_converter.internal import S3Config, classify_input, WFLogger, ImportSource, CommonConfig, save_output
from wealthfolio_converter.vanguard import Vanguard
from wealthfolio_converter.fidelity import Fidelity
from wealthfolio_converter.trowe import TRowe

app: FastAPI


def create_app() -> FastAPI:
    openapi_url: str | None = "/openapi.json"

    if os.getenv("STAGE", "") == "PRODUCTION":
        openapi_url = None

    return FastAPI(openapi_url=openapi_url)


app = create_app()


class SparseS3Event(BaseModel):
    Service: str
    Event: str
    Time: datetime
    Bucket: str
    RequestId: str
    HostId: str


# mypy: disable_error_code=assignment
class CustomS3RecordModel(S3RecordModel):
    eventSource: Literal["aws:s3"] | Literal["minio:s3"] = "aws:s3" # pyright: ignore[reportIncompatibleVariableOverride]


class CustomS3Model(S3Model):
    Records: list[CustomS3RecordModel] # pyright: ignore[reportIncompatibleVariableOverride]


class GenericS3Model(SparseS3Event, CustomS3Model):
    pass


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


def select_format(input_format: str, this_common_config: CommonConfig) -> ImportSource | None:
    """selector for input format type"""
    this_import_object: ImportSource | None = None
    if input_format == "vanguard-xlsx":
        this_import_object = Vanguard(this_common_config)
        this_import_object.xlsx_to_csv()

    elif input_format == "vanguard":
        this_import_object = Vanguard(this_common_config)

    elif input_format == "fidelity":
        this_import_object = Fidelity(this_common_config)

    elif input_format == "trowe":
        this_import_object = TRowe(this_common_config)

    return this_import_object


# mypy: disable_error_code=
@app.get('/')
async def root() -> JSONResponse:
    return JSONResponse(content={"health": "ok"})


@app.post('/load')
async def load(input_payload: GenericS3Model) -> JSONResponse:
    responses: dict = {
        'responses': []
    }

    log = WFLogger("main", "DEBUG")
    log.init()
    conn = duckdb.connect()

    if isinstance(input_payload, CustomS3Model):
        for r in input_payload.Records:
            print(f"Event Name: {r.eventName}")
            print(f"Bucket: {r.s3.bucket}")
            response = {}
            response['bucket'] = r.s3.bucket.name
            response['event'] = r.eventName
            if r.s3.object:
                print(f"Object: {unquote_plus(r.s3.object.key)}")
                response['key'] = r.s3.object.key

                bucket_subtype = response['key'].split("/")[1]
                input_s3_filename = f"s3://{response['bucket']}/{response['key']}"

                input_filename, s3_input_bucket = classify_input(
                    input_s3_filename, log, s3_config)

                output_filename = input_s3_filename.replace("inputs", "outputs")

                import_object: ImportSource | None

                common_config = CommonConfig(
                    filename=input_filename,
                    conn=conn,
                    log=log,
                )

                import_object = select_format(bucket_subtype, common_config)
                if not import_object:
                    return JSONResponse(
                        content={
                            'error': f'could not determine format from "{bucket_subtype}"'},
                        status_code=500,
                    )

                import_object.pre_process()
                import_object.import_csv()

                output_table = import_object.reshape()
                s3_output_bucket = save_output(output_filename, output_table, log, s3_config)

                if s3_input_bucket:
                    os.unlink(s3_input_bucket.temp_filename)
                if s3_output_bucket:
                    os.unlink(s3_output_bucket.temp_filename)

    elif isinstance(input_payload, SparseS3Event):
        print(f"Event Name: {input_payload.Event}")
        print(f"Bucket: {input_payload.Bucket}")
        responses['responses'].append({
            'bucket': input_payload.Bucket,
            'event': input_payload.Event,
        })
    return JSONResponse(content=responses)
