from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class AppConfig:
    oci_config_file: str
    oci_config_profile: str
    oci_region: str | None
    root_compartment_ocid: str | None
    include_subcompartments: bool
    max_backup_age_days: int
    output_dir: Path
    object_storage_namespace: str | None
    object_storage_bucket: str | None
    object_storage_prefix: str
    fail_on_upload_error: bool
    auto_discover_bucket: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv(override=False)

        object_storage_bucket = os.getenv("OCI_OBJECT_STORAGE_BUCKET", "").strip() or None

        root_compartment = os.getenv("OCI_ROOT_COMPARTMENT_OCID", "").strip() or None
        namespace = os.getenv("OCI_OBJECT_STORAGE_NAMESPACE", "").strip() or None

        config_file_default = str(Path.home() / ".oci" / "config")

        return cls(
            oci_config_file=os.getenv("OCI_CONFIG_FILE", config_file_default),
            oci_config_profile=os.getenv("OCI_CONFIG_PROFILE", "DEFAULT"),
            oci_region=os.getenv("OCI_REGION", "").strip() or None,
            root_compartment_ocid=root_compartment,
            include_subcompartments=_to_bool(os.getenv("OCI_INCLUDE_SUBCOMPARTMENTS"), True),
            max_backup_age_days=_to_int(os.getenv("OCI_MAX_BACKUP_AGE_DAYS"), 7),
            output_dir=Path(os.getenv("OCI_OUTPUT_DIR", "output")),
            object_storage_namespace=namespace,
            object_storage_bucket=object_storage_bucket,
            object_storage_prefix=os.getenv("OCI_OBJECT_STORAGE_PREFIX", "block-volume-backup-posture").strip("/"),
            fail_on_upload_error=_to_bool(os.getenv("OCI_FAIL_ON_UPLOAD_ERROR"), True),
            auto_discover_bucket=_to_bool(os.getenv("OCI_AUTO_DISCOVER_BUCKET"), True),
        )
