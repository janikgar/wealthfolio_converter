import pytest
import boto3
from moto import mock_aws
from botocore.config import Config
from botocore.exceptions import ClientError
from wealthfolio_converter.internal import WFLogger
from wealthfolio_converter.s3 import S3Bucket, S3Exception, S3Config


mock_config = S3Config(
    aws_access_key_id="qwertyuiop",
    aws_secret_access_key="asdfghjk",
    region_name="us-east-1",
    config=Config(),
)


@mock_aws
class TestS3:
    def init(self) -> None:
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket='test_bucket')
        client.put_object(Bucket='test_bucket',
                          Key='test_file.csv', Body='asdf')

        self.setup_client = boto3.client('s3', region_name='us-east-1')

        self.log = WFLogger('test', 'DEBUG')

    @pytest.mark.parametrize('_,expected_err', [
        ('good_config', None),
        ('bad_config', "could not connect"),
    ])
    def test_s3_bucket(self, _: str, expected_err: str):
        self.init()

        if expected_err:
            with pytest.raises(S3Exception, match=expected_err):
                S3Bucket('bad_bucket', self.log, mock_config)
        else:
            mock_config.endpoint_url = self.setup_client.meta.endpoint_url
            S3Bucket('test_bucket', self.log, mock_config)

    @pytest.mark.parametrize('_,filename,expected_err', [
        ("success", "test_file.csv", None),
        ("fail", "bad_file.csv", "HeadObject operation: Not Found"),
    ])
    def test_s3_bucket_download_path(self, _, filename: str, expected_err: str | None):
        self.init()

        mock_config.endpoint_url = self.setup_client.meta.endpoint_url
        mock_bucket = S3Bucket('test_bucket', self.log, mock_config)
        if expected_err:
            with pytest.raises(Exception, match=expected_err):
                mock_bucket.download_path(filename)
        else:
            mock_bucket.download_path(filename)

    @pytest.mark.parametrize('_,expected_err', [
        ('success', None),
        ('fail', 'NoSuchBucket'),
    ])
    def test_s3_bucket_upload_path(self, _, expected_err: str, tmp_path):
        self.init()
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""foo
bin
stop before this row""")

        mock_bucket = S3Bucket('test_bucket', self.log, mock_config)
        mock_config.endpoint_url = self.setup_client.meta.endpoint_url

        if expected_err:
            with pytest.raises(S3Exception, match=expected_err):
                mock_bucket.bucket = 'bad_bucket'
                mock_bucket.upload_path(str(tmp_file.resolve()), 'failed_upload.csv')
        else:
            mock_bucket.upload_path(str(tmp_file.resolve()), 'success_upload.csv')