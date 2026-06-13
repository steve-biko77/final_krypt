from abc import ABC, abstractmethod


class StorageService(ABC):
    @abstractmethod
    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        prefix: str = "",
    ) -> str:
        ...

    @abstractmethod
    def get_presigned_url(self, file_path: str, expires_seconds: int = 3600) -> str:
        ...
