from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class BackupPostureAnalyzer:
    def __init__(self, max_backup_age_days: int) -> None:
        self.max_backup_age_days = max_backup_age_days

    def analyze(
        self,
        collected: list[dict[str, Any]],
        skipped_compartments: list[dict[str, str]],
        generated_at: datetime,
        region: str,
        tenancy_ocid: str,
    ) -> dict[str, Any]:
        block_findings: list[dict[str, Any]] = []
        boot_findings: list[dict[str, Any]] = []
        ad_summary: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "non_compliant": 0})
        compartment_summary: list[dict[str, Any]] = []

        for compartment_data in collected:
            compartment = compartment_data["compartment"]
            instances = compartment_data["instances"]
            block_attachments = compartment_data["block_volume_attachments"]
            boot_attachments = compartment_data["boot_volume_attachments"]
            block_volumes = compartment_data["block_volumes"]
            boot_volumes = compartment_data["boot_volumes"]
            volume_backups = compartment_data["volume_backups"]
            boot_volume_backups = compartment_data["boot_volume_backups"]

            instance_name_by_id = {instance.id: instance.display_name for instance in instances}

            latest_backup_by_volume = self._latest_backups(volume_backups, "volume_id")
            latest_backup_by_boot_volume = self._latest_backups(boot_volume_backups, "boot_volume_id")

            volume_to_instances: dict[str, list[str]] = defaultdict(list)
            for attachment in block_attachments:
                if attachment.lifecycle_state != "ATTACHED":
                    continue
                volume_id = getattr(attachment, "volume_id", None)
                instance_id = getattr(attachment, "instance_id", None)
                if not volume_id:
                    continue
                label = instance_name_by_id.get(instance_id, instance_id or "UNKNOWN_INSTANCE")
                volume_to_instances[volume_id].append(label)

            boot_volume_to_instances: dict[str, list[str]] = defaultdict(list)
            for attachment in boot_attachments:
                if attachment.lifecycle_state != "ATTACHED":
                    continue
                boot_volume_id = getattr(attachment, "boot_volume_id", None)
                instance_id = getattr(attachment, "instance_id", None)
                if not boot_volume_id:
                    continue
                label = instance_name_by_id.get(instance_id, instance_id or "UNKNOWN_INSTANCE")
                boot_volume_to_instances[boot_volume_id].append(label)

            compartment_non_compliant = 0

            for volume in block_volumes:
                latest_backup = latest_backup_by_volume.get(volume.id)
                record = self._build_finding(
                    generated_at=generated_at,
                    compartment=compartment,
                    resource_kind="BLOCK_VOLUME",
                    resource_id=volume.id,
                    resource_name=volume.display_name,
                    availability_domain=volume.availability_domain,
                    size_gb=getattr(volume, "size_in_gbs", None),
                    source_type=getattr(volume, "source_details", None),
                    latest_backup=latest_backup,
                    attached_instances=sorted(set(volume_to_instances.get(volume.id, []))),
                )
                block_findings.append(record)
                if record["compliance_status"] != "COMPLIANT":
                    compartment_non_compliant += 1
                    ad_summary[record["availability_domain"]]["non_compliant"] += 1
                ad_summary[record["availability_domain"]]["total"] += 1

            for boot_volume in boot_volumes:
                latest_backup = latest_backup_by_boot_volume.get(boot_volume.id)
                record = self._build_finding(
                    generated_at=generated_at,
                    compartment=compartment,
                    resource_kind="BOOT_VOLUME",
                    resource_id=boot_volume.id,
                    resource_name=boot_volume.display_name,
                    availability_domain=boot_volume.availability_domain,
                    size_gb=getattr(boot_volume, "size_in_gbs", None),
                    source_type=getattr(boot_volume, "source_details", None),
                    latest_backup=latest_backup,
                    attached_instances=sorted(set(boot_volume_to_instances.get(boot_volume.id, []))),
                )
                boot_findings.append(record)
                if record["compliance_status"] != "COMPLIANT":
                    compartment_non_compliant += 1
                    ad_summary[record["availability_domain"]]["non_compliant"] += 1
                ad_summary[record["availability_domain"]]["total"] += 1

            compartment_summary.append(
                {
                    "compartment_id": compartment.id,
                    "compartment_name": compartment.name,
                    "block_volume_count": len(block_volumes),
                    "boot_volume_count": len(boot_volumes),
                    "non_compliant_volume_count": compartment_non_compliant,
                }
            )

        all_findings = block_findings + boot_findings
        summary = self._build_summary(all_findings, ad_summary, len(compartment_summary), len(skipped_compartments))

        return {
            "metadata": {
                "report_name": "block_volume_backup_posture_audit",
                "generated_at_utc": generated_at.isoformat(),
                "region": region,
                "tenancy_ocid": tenancy_ocid,
                "max_backup_age_days": self.max_backup_age_days,
            },
            "summary": summary,
            "compartments": sorted(compartment_summary, key=lambda item: item["compartment_name"].lower()),
            "skipped_compartments": skipped_compartments,
            "findings": {
                "block_volumes": self._sorted_findings(block_findings),
                "boot_volumes": self._sorted_findings(boot_findings),
            },
        }

    def _latest_backups(self, backups: list[Any], id_field: str) -> dict[str, Any]:
        latest: dict[str, Any] = {}
        for backup in backups:
            resource_id = getattr(backup, id_field, None)
            if not resource_id:
                continue
            candidate = latest.get(resource_id)
            if candidate is None or backup.time_created > candidate.time_created:
                latest[resource_id] = backup
        return latest

    def _build_finding(
        self,
        generated_at: datetime,
        compartment: Any,
        resource_kind: str,
        resource_id: str,
        resource_name: str | None,
        availability_domain: str | None,
        size_gb: int | None,
        source_type: Any,
        latest_backup: Any,
        attached_instances: list[str],
    ) -> dict[str, Any]:
        latest_backup_time = latest_backup.time_created if latest_backup else None
        latest_backup_ocid = latest_backup.id if latest_backup else None

        if latest_backup_time is None:
            status = "NO_BACKUP"
            age_days = None
        else:
            age = generated_at - latest_backup_time.astimezone(timezone.utc)
            age_days = round(age.total_seconds() / 86400, 2)
            status = "COMPLIANT" if age_days <= self.max_backup_age_days else "STALE_BACKUP"

        return {
            "compartment_id": compartment.id,
            "compartment_name": compartment.name,
            "resource_kind": resource_kind,
            "resource_id": resource_id,
            "resource_name": resource_name,
            "availability_domain": availability_domain or "UNKNOWN_AD",
            "size_gb": size_gb,
            "source_type": str(source_type) if source_type else None,
            "attached_instances": attached_instances,
            "backup_ocid": latest_backup_ocid,
            "latest_backup_time_utc": latest_backup_time.astimezone(timezone.utc).isoformat() if latest_backup_time else None,
            "backup_age_days": age_days,
            "compliance_status": status,
        }

    def _build_summary(
        self,
        all_findings: list[dict[str, Any]],
        ad_summary: dict[str, dict[str, int]],
        scanned_compartment_count: int,
        skipped_compartment_count: int,
    ) -> dict[str, Any]:
        compliant = sum(1 for item in all_findings if item["compliance_status"] == "COMPLIANT")
        stale = sum(1 for item in all_findings if item["compliance_status"] == "STALE_BACKUP")
        no_backup = sum(1 for item in all_findings if item["compliance_status"] == "NO_BACKUP")

        return {
            "scanned_compartment_count": scanned_compartment_count,
            "skipped_compartment_count": skipped_compartment_count,
            "total_volumes_analyzed": len(all_findings),
            "compliant_count": compliant,
            "stale_backup_count": stale,
            "no_backup_count": no_backup,
            "non_compliant_count": stale + no_backup,
            "availability_domain_summary": dict(sorted(ad_summary.items())),
        }

    def _sorted_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority = {"NO_BACKUP": 0, "STALE_BACKUP": 1, "COMPLIANT": 2}
        return sorted(
            findings,
            key=lambda row: (
                priority.get(row["compliance_status"], 9),
                row["compartment_name"].lower(),
                (row.get("resource_name") or "").lower(),
            ),
        )
