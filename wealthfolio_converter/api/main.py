import os
from typing import Literal
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from aws_lambda_powertools.utilities.parser.models.s3 import S3Model, S3RecordModel

app: FastAPI


def create_app() -> FastAPI:
    openapi_url = "/openapi.json"

    if os.getenv("STAGE", "") == "PRODUCTION":
        openapi_url = None

    return FastAPI(openapi_url=openapi_url)


app = create_app()


class CustomS3RecordModel(S3RecordModel):
    # mypy: disable_error_code=assignment
    eventSource: Literal["aws:s3"] | Literal["minio:s3"] = "aws:s3" # pyright: ignore[reportIncompatibleVariableOverride]


class CustomS3Model(S3Model):
    Records: list[CustomS3RecordModel] # pyright: ignore[reportIncompatibleVariableOverride]


# mypy: disable_error_code=
@app.get('/')
async def root() -> JSONResponse:
    return JSONResponse(content={"health": "ok"})


@app.post('/load')
async def load(input: CustomS3Model) -> JSONResponse:
    responses: dict = {
        'responses': []
    }
    for r in input.Records:
        response = {}
        response['bucket'] = r.s3.bucket.name
        if r.s3.object:
            response['key'] = r.s3.object.key
        responses['responses'].append(response)
    return JSONResponse(content=responses)
