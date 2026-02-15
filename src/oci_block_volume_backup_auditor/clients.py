from __future__ import annotations

from typing import Any

import oci

from .config import AppConfig


def create_oci_config(app_config: AppConfig) -> dict[str, Any]:
    config = oci.config.from_file(
        file_location=app_config.oci_config_file,
        profile_name=app_config.oci_config_profile,
    )

    if app_config.oci_region:
        config["region"] = app_config.oci_region

    return config


def create_clients(oci_config: dict[str, Any]) -> dict[str, Any]:
    retry_strategy = oci.retry.DEFAULT_RETRY_STRATEGY

    return {
        "identity": oci.identity.IdentityClient(oci_config, retry_strategy=retry_strategy),
        "compute": oci.core.ComputeClient(oci_config, retry_strategy=retry_strategy),
        "blockstorage": oci.core.BlockstorageClient(oci_config, retry_strategy=retry_strategy),
        "object_storage": oci.object_storage.ObjectStorageClient(oci_config, retry_strategy=retry_strategy),
    }
