"""Backblaze B2 S3-compatible object storage client for application files."""

import boto3
from botocore.config import Config

from app.core.config import settings


def b2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.b2_endpoint_url,
        aws_access_key_id=settings.b2_access_key_id,
        aws_secret_access_key=settings.b2_secret_access_key,
        region_name=settings.b2_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )
