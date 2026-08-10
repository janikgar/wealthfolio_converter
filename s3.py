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
from dotenv import load_dotenv
from internal import WFLogger


@dataclass
class S3Bucket:
    """S3 class for connecting to buckets"""
    bucket: str
    log: WFLogger
    input_path: str = ""

    def __post_init__(self):
        load_dotenv()
        session = Session()

        client = session.create_client(
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            service_name='s3',
            region_name='homelab',
            endpoint_url='http://192.168.1.28:30900',
            config=Config(
                region_name='homelab',
                s3={
                    'addressing_style': 'path'
                },
            ),
        )

        try:
            client.head_bucket(Bucket=self.bucket)
        except ClientError as _e:
            raise Exception(
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
            raise Exception(
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
            raise Exception(
                f'could not upload {local_path} to {remote_path}: {_e}')from _e
