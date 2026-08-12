"""
Utility module for interacting with S3-stored files. This implementation
is created with Minio/Silo in mind, but uses Boto3.
"""
import os
from dataclasses import dataclass
from tempfile import mkstemp
from botocore.config import Config
from botocore.session import Session
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from wealthfolio_converter.internal import WFLogger


class S3Exception(Exception):
    """Catchall S3 exception"""


@dataclass
class S3Config:
    """S3 API configuration"""
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str
    config: Config
    endpoint_url: str = ""


@dataclass
class S3Bucket:
    """S3 class for connecting to buckets"""
    bucket: str
    log: WFLogger
    s3_config: S3Config
    input_path: str = ""

    def __post_init__(self):
        session = Session()

        client = session.create_client(
            service_name="s3",
            aws_access_key_id=self.s3_config.aws_access_key_id,
            aws_secret_access_key=self.s3_config.aws_secret_access_key,
            region_name=self.s3_config.region_name,
            endpoint_url=self.s3_config.endpoint_url,
            config=self.s3_config.config,
        )

        try:
            client.head_bucket(Bucket=self.bucket)
        except ClientError as _e:
            raise S3Exception(
                f'could not connect to bucket {self.bucket}: {_e}') from _e

        self.log.info(f'connected to bucket {self.bucket}')
        self.client = client

        _, self.temp_filename = mkstemp(
            prefix=f"{self.bucket}-", text=True
        )

    def download_path(self, path: str):
        """
        Method for downloading a remote path. Stores in a temporary file to be
        cleaned up manually later (since it needs to be used by other classes)
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
        except ClientError as _e:
            raise S3Exception(
                f'could not connect to object s3://{self.bucket}/{path}: {_e}') from _e
        self.input_path = path

        get_output: dict = self.client.get_object(
            Bucket=self.bucket, Key=self.input_path)

        with open(self.temp_filename, 'wb') as _f:
            output: StreamingBody = get_output['Body']
            output_lines = output.readlines()
            _f.writelines(output_lines)
            self.log.info(
                f'wrote {len(output_lines)} lines to {self.temp_filename}')

    def upload_path(self, local_path: str, remote_path: str):
        """
        Method for uploading to a remote path. Takes in a local path
        (likely an externally-created temp file).
        """
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=remote_path, Body=local_path)
            self.log.info(f'uploaded {local_path} to {remote_path}')
        except ClientError as _e:
            raise S3Exception(
                f'could not upload {local_path} to {remote_path}: {_e}')from _e
