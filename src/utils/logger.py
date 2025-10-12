import logging
import json
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from src.config import config
from typing import Dict, Any

# =========================================================
# 🧱 Global Logger Setup
# =========================================================
logger = logging.getLogger("fraud_chatbot")
logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

# Avoid duplicate handlers if reimported
if logger.hasHandlers():
    logger.handlers.clear()

# =========================================================
# 🧩 Formatters
# =========================================================
class JSONFormatter(logging.Formatter):
    """JSON format for structured logs (ideal for AWS CloudWatch & ELK)."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "claimant_id": getattr(record, "claimant_id", "anonymous"),
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

class ColoredFormatter(logging.Formatter):
    """Simple color-coded output for dev mode."""
    COLORS = {"DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m", "ERROR": "\033[31m", "END": "\033[0m"}
    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        msg = super().format(record)
        return f"{color}{msg}{self.COLORS['END']}"

# =========================================================
# 🖥️ Console Handler (always active)
# =========================================================
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
console_handler.setFormatter(
    ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s")
    if config.DEBUG else JSONFormatter()
)
logger.addHandler(console_handler)

# =========================================================
# 📁 File Handler (Rotating)
# =========================================================
if not config.DEBUG:
    log_file = "fraud_chatbot.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    logger.info(f"File logging active: {log_file}")

# =========================================================
# ☁️ CloudWatch Handler (AWS Integration)
# =========================================================
class CloudWatchHandler(logging.Handler):
    def __init__(self, log_group: str, log_stream: str):
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream
        self.sequence_token = None
        self.client = self._init_client()

    def _init_client(self):
        try:
            client = boto3.client("logs", region_name=config.AWS_REGION)
            # Ensure log group/stream exist
            try:
                client.create_log_group(logGroupName=self.log_group)
            except client.exceptions.ResourceAlreadyExistsException:
                pass
            try:
                client.create_log_stream(logGroupName=self.log_group, logStreamName=self.log_stream)
            except client.exceptions.ResourceAlreadyExistsException:
                pass
            logger.info(f"✅ CloudWatch logging enabled: {self.log_group}/{self.log_stream}")
            return client
        except NoCredentialsError:
            logger.warning("⚠️ AWS credentials not found – CloudWatch disabled.")
            return None
        except ClientError as e:
            logger.error(f"❌ CloudWatch init error: {e}")
            return None

    def emit(self, record: logging.LogRecord):
        if not self.client:
            return
        try:
            message = JSONFormatter().format(record)
            log_event = {
                "logGroupName": self.log_group,
                "logStreamName": self.log_stream,
                "logEvents": [
                    {"timestamp": int(datetime.utcnow().timestamp() * 1000), "message": message}
                ],
            }
            if self.sequence_token:
                log_event["sequenceToken"] = self.sequence_token

            response = self.client.put_log_events(**log_event)
            self.sequence_token = response.get("nextSequenceToken")
        except ClientError as e:
            # AWS CloudWatch often requires sequence token retry
            if "InvalidSequenceTokenException" in str(e):
                token = self._get_latest_token()
                if token:
                    self.sequence_token = token
                    self.emit(record)
            else:
                logger.error(f"CloudWatch emit error: {e}")

    def _get_latest_token(self) -> str:
        """Fetch latest sequence token if invalid."""
        try:
            response = self.client.describe_log_streams(
                logGroupName=self.log_group,
                logStreamNamePrefix=self.log_stream,
            )
            streams = response.get("logStreams", [])
            if streams:
                return streams[0].get("uploadSequenceToken")
        except Exception as e:
            logger.error(f"Error getting CloudWatch sequence token: {e}")
        return None

# Enable CloudWatch if AWS creds present
if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
    cw_handler = CloudWatchHandler("fraud-chatbot-logs", "fraud-api-stream")
    cw_handler.setLevel(logging.INFO)
    logger.addHandler(cw_handler)

# =========================================================
# 🧩 Context-Aware Logging Decorator
# =========================================================
def log_with_context(level: str = "info"):
    """
    Decorator for adding context logs with claimant_id automatically.
    Usage:
        @log_with_context("info")
        def process_claim(...): ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            claimant_id = kwargs.get("claimant_id", "anonymous")
            logger_method = getattr(logger, level, logger.info)
            logger_method(f"Executing {func.__name__}", extra={"claimant_id": claimant_id})
            return func(*args, **kwargs)
        return wrapper
    return decorator

# =========================================================
# 🧪 Local Test
# =========================================================
if __name__ == "__main__":
    logger.debug("Debug message (only in dev)")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    @log_with_context("info")
    def sample_claim_process(claimant_id=None):
        logger.info("Processing claim internally...")

    sample_claim_process(claimant_id="user123")
