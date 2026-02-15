from __future__ import annotations

from typing import Any

from oci.pagination import list_call_get_all_results


class BlockStorageCollector:
    def __init__(self, blockstorage_client: Any) -> None:
        self.blockstorage_client = blockstorage_client

    def list_block_volumes(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.blockstorage_client.list_volumes,
            compartment_id=compartment_ocid,
        ).data

    def list_boot_volumes(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.blockstorage_client.list_boot_volumes,
            compartment_id=compartment_ocid,
        ).data

    def list_volume_backups(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.blockstorage_client.list_volume_backups,
            compartment_id=compartment_ocid,
        ).data

    def list_boot_volume_backups(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.blockstorage_client.list_boot_volume_backups,
            compartment_id=compartment_ocid,
        ).data
