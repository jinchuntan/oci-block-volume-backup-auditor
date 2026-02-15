from __future__ import annotations

from typing import Any

from oci.pagination import list_call_get_all_results

from ..models import CompartmentInfo


class IdentityCollector:
    def __init__(self, identity_client: Any) -> None:
        self.identity_client = identity_client

    def list_compartments(
        self,
        tenancy_ocid: str,
        root_compartment_ocid: str | None,
        include_subcompartments: bool,
    ) -> list[CompartmentInfo]:
        root_id = root_compartment_ocid or tenancy_ocid

        if root_compartment_ocid:
            root = self.identity_client.get_compartment(root_id).data
            root_name = root.name
        else:
            tenancy = self.identity_client.get_tenancy(tenancy_ocid).data
            root_name = tenancy.name

        compartments: list[CompartmentInfo] = [CompartmentInfo(id=root_id, name=root_name)]

        if include_subcompartments:
            if root_id == tenancy_ocid:
                response = list_call_get_all_results(
                    self.identity_client.list_compartments,
                    compartment_id=root_id,
                    compartment_id_in_subtree=True,
                    access_level="ACCESSIBLE",
                    lifecycle_state="ACTIVE",
                )
                for item in response.data:
                    compartments.append(CompartmentInfo(id=item.id, name=item.name))
            else:
                # OCI only supports `compartment_id_in_subtree=True` for tenancy root.
                # For a non-root compartment, recursively walk children.
                queue = [root_id]
                visited: set[str] = set()
                while queue:
                    parent_id = queue.pop(0)
                    if parent_id in visited:
                        continue
                    visited.add(parent_id)
                    response = list_call_get_all_results(
                        self.identity_client.list_compartments,
                        compartment_id=parent_id,
                        compartment_id_in_subtree=False,
                        access_level="ACCESSIBLE",
                        lifecycle_state="ACTIVE",
                    )
                    for item in response.data:
                        compartments.append(CompartmentInfo(id=item.id, name=item.name))
                        queue.append(item.id)
        else:
            response = list_call_get_all_results(
                self.identity_client.list_compartments,
                compartment_id=root_id,
                compartment_id_in_subtree=False,
                access_level="ACCESSIBLE",
                lifecycle_state="ACTIVE",
            )
            for item in response.data:
                compartments.append(CompartmentInfo(id=item.id, name=item.name))

        # Deduplicate by OCID, then sort by name for stable output.
        unique = {comp.id: comp for comp in compartments}
        return sorted(unique.values(), key=lambda comp: comp.name.lower())
