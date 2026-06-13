import io
import uuid as uuid_module
from datetime import datetime, timedelta, timezone

from django.conf import settings
from minio import Minio
from minio.error import S3Error

from ...ports.storage_service import StorageService


class MinIOStorageService(StorageService):
    def __init__(self):
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET_KYC
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error as e:
            raise RuntimeError(f"MinIO bucket setup failed: {e}") from e

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        prefix: str = "",
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique = str(uuid_module.uuid4())[:8]
        safe_name = filename.replace(" ", "_")
        object_name = f"{prefix}/{timestamp}_{unique}_{safe_name}" if prefix else f"{timestamp}_{unique}_{safe_name}"

        self._client.put_object(
            self._bucket,
            object_name,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        return f"{self._bucket}/{object_name}"

    def get_presigned_url(self, file_path: str, expires_seconds: int = 3600) -> str:
        # file_path format: "bucket/object_name"
        parts = file_path.split("/", 1)
        object_name = parts[1] if len(parts) > 1 else parts[0]
        return self._client.presigned_get_object(
            self._bucket,
            object_name,
            expires=timedelta(seconds=expires_seconds),
        )
