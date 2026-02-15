from __future__ import annotations

from typing import Any

from oci.pagination import list_call_get_all_results


class ComputeCollector:
    def __init__(self, compute_client: Any) -> None:
        self.compute_client = compute_client

    def list_instances(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.compute_client.list_instances,
            compartment_id=compartment_ocid,
        ).data

    def list_block_volume_attachments(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.compute_client.list_volume_attachments,
            compartment_id=compartment_ocid,
        ).data

    def list_boot_volume_attachments(self, compartment_ocid: str) -> list[Any]:
        return list_call_get_all_results(
            self.compute_client.list_boot_volume_attachments,
            compartment_id=compartment_ocid,
        ).data
