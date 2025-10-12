"""
S3 / MinIO Handler
------------------
Unified helper for uploading, downloading, and listing claim files
(e.g., invoices, documents, ML models) to S3 or local MinIO.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from typing import Optional, List
from datetime import datetime
from src.config import config
from src.utils.logger import logger
import os
import json


class S3Handler:
    def __init__(self):
        """
        Initialize S3 client.
        Works with:
          - AWS S3 (default)
          - MinIO (via S3_ENDPOINT_URL in .env)
        """
        self.bucket_name = config.S3_BUCKET_NAME
        endpoint_url = os.getenv("S3_ENDPOINT_URL", "")  # Optional for MinIO

        try:
            self.s3_client = boto3.client(
                "s3",
                region_name=config.AWS_REGION,
                endpoint_url=endpoint_url or None,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

            # Check bucket existence (soft validation)
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ S3 client initialized for bucket: {self.bucket_name}")
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                    logger.warning(f"⚠️ Bucket '{self.bucket_name}' not found — attempting to create.")
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    logger.warning(f"⚠️ Skipping bucket check: {e}")
            except EndpointConnectionError:
                logger.warning("⚠️ Cannot reach S3 endpoint (check network or MinIO). Continuing without test.")

        except NoCredentialsError:
            logger.warning("⚠️ AWS credentials missing — S3 client disabled.")
            self.s3_client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {e}")
            self.s3_client = None

    # =========================================================
    # 📤 Upload Methods
    # =========================================================
    def upload_file(
        self, file_path: str, s3_key: str, content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """Upload a local file to S3 or MinIO. Returns the S3 URL on success."""
        if not self.s3_client:
            logger.warning("S3 not available — skipping upload.")
            return None

        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
            )
            s3_url = f"https://{self.bucket_name}.s3.{config.AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"📤 Uploaded {file_path} to {s3_url}")
            return s3_url
        except ClientError as e:
            logger.error(f"❌ Upload failed: {e}")
            return None

    def upload_bytes(
        self, data: bytes, s3_key: str, content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """Upload binary content (e.g., OCR output or in-memory PDF)."""
        if not self.s3_client:
            return None

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
            s3_url = f"https://{self.bucket_name}.s3.{config.AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"📦 Uploaded bytes to {s3_url}")
            return s3_url
        except ClientError as e:
            logger.error(f"❌ Error uploading bytes to S3: {e}")
            return None

    # =========================================================
    # 📥 Download & Listing
    # =========================================================
    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download a file from S3 to local storage."""
        if not self.s3_client:
            return False
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"📥 Downloaded {s3_key} → {local_path}")
            return True
        except ClientError as e:
            logger.error(f"❌ Download failed: {e}")
            return False

    def list_objects(self, prefix: str = "") -> List[str]:
        """List object keys within a prefix (e.g., 'claims/user1/')."""
        if not self.s3_client:
            return []
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            keys = [obj["Key"] for obj in response.get("Contents", [])]
            logger.debug(f"📄 Listed {len(keys)} objects under '{prefix}'")
            return keys
        except ClientError as e:
            logger.error(f"❌ List objects failed: {e}")
            return []

    # =========================================================
    # 🔗 Presigned URLs
    # =========================================================
    def get_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for temporary access."""
        if not self.s3_client:
            return None
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            logger.debug(f"🔗 Presigned URL (expires in {expiration}s): {url}")
            return url
        except ClientError as e:
            logger.error(f"❌ Presigned URL generation failed: {e}")
            return None


# =========================================================
# 🧩 Global instance (singleton)
# =========================================================
s3_handler = S3Handler()


# =========================================================
# 🧰 Helper shortcuts
# =========================================================
def upload_to_s3(file_path: str, s3_key: str) -> Optional[str]:
    """Shortcut for uploading a file."""
    return s3_handler.upload_file(file_path, s3_key)


def upload_invoice_bytes(data: bytes, claimant_id: str) -> Optional[str]:
    """Shortcut for uploading an invoice PDF."""
    s3_key = f"claims/{claimant_id}/invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return s3_handler.upload_bytes(data, s3_key, "application/pdf")


# =========================================================
# 🧪 Manual Test (Dev Only)
# =========================================================
if __name__ == "__main__":
    url = upload_to_s3("test_invoice.pdf", "test/test.pdf")
    print(f"✅ Uploaded to: {url}")
