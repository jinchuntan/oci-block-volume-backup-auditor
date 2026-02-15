from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import UploadResult


class ObjectStorageUploader:
    def __init__(
        self,
        object_storage_client: Any,
        namespace: str | None,
        bucket: str,
        prefix: str,
    ) -> None:
        self.object_storage_client = object_storage_client
        self.namespace = namespace
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def resolve_namespace(self) -> str:
        if self.namespace:
            return self.namespace
        return self.object_storage_client.get_namespace().data

    def upload_file(self, file_path: Path, content_type: str) -> UploadResult:
        namespace = self.resolve_namespace()
        object_name = f"{self.prefix}/{file_path.name}" if self.prefix else file_path.name

        with file_path.open("rb") as handle:
            self.object_storage_client.put_object(
                namespace_name=namespace,
                bucket_name=self.bucket,
                object_name=object_name,
                put_object_body=handle,
                content_type=content_type,
            )

        return UploadResult(
            namespace=namespace,
            bucket=self.bucket,
            object_name=object_name,
            uri=f"oci://{self.bucket}@{namespace}/{object_name}",
        )
