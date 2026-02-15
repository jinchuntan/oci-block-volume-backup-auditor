from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(report: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")


def write_markdown_report(report: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(_build_markdown(report), encoding="utf-8")


def _build_markdown(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    summary = report["summary"]
    block_findings = report["findings"]["block_volumes"]
    boot_findings = report["findings"]["boot_volumes"]

    lines: list[str] = []
    lines.append("# OCI Block Volume Backup Posture Audit")
    lines.append("")
    lines.append(f"- Generated (UTC): `{metadata['generated_at_utc']}`")
    lines.append(f"- Region: `{metadata['region']}`")
    lines.append(f"- Tenancy: `{metadata['tenancy_ocid']}`")
    lines.append(f"- Max Backup Age (days): `{metadata['max_backup_age_days']}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Scanned Compartments | {summary['scanned_compartment_count']} |")
    lines.append(f"| Skipped Compartments | {summary['skipped_compartment_count']} |")
    lines.append(f"| Total Volumes Analyzed | {summary['total_volumes_analyzed']} |")
    lines.append(f"| Compliant | {summary['compliant_count']} |")
    lines.append(f"| Stale Backup | {summary['stale_backup_count']} |")
    lines.append(f"| No Backup | {summary['no_backup_count']} |")
    lines.append(f"| Non-Compliant | {summary['non_compliant_count']} |")
    lines.append("")

    lines.append("## Availability Domain Summary")
    lines.append("")
    lines.append("| Availability Domain | Total Volumes | Non-Compliant |")
    lines.append("|---|---:|---:|")
    for ad, stats in summary["availability_domain_summary"].items():
        lines.append(f"| {ad} | {stats['total']} | {stats['non_compliant']} |")
    lines.append("")

    if report["skipped_compartments"]:
        lines.append("## Skipped Compartments")
        lines.append("")
        lines.append("| Compartment OCID | Reason |")
        lines.append("|---|---|")
        for item in report["skipped_compartments"]:
            lines.append(f"| {item['compartment_id']} | {item['reason']} |")
        lines.append("")

    lines.append("## Non-Compliant Findings (Top 50)")
    lines.append("")
    lines.append("| Kind | Compartment | Volume | AD | Status | Backup Age (days) | Attached Instances |")
    lines.append("|---|---|---|---|---|---:|---|")

    non_compliant = [
        *[item for item in block_findings if item["compliance_status"] != "COMPLIANT"],
        *[item for item in boot_findings if item["compliance_status"] != "COMPLIANT"],
    ]

    for item in non_compliant[:50]:
        name = item["resource_name"] or item["resource_id"]
        age = "N/A" if item["backup_age_days"] is None else item["backup_age_days"]
        attached = ", ".join(item["attached_instances"]) if item["attached_instances"] else "-"
        lines.append(
            f"| {item['resource_kind']} | {item['compartment_name']} | {name} | "
            f"{item['availability_domain']} | {item['compliance_status']} | {age} | {attached} |"
        )

    if not non_compliant:
        lines.append("| - | - | - | - | All resources compliant | - | - |")

    lines.append("")
    lines.append("## Full Findings")
    lines.append("")
    lines.append("- Full machine-readable findings are available in the JSON artifact.")

    return "\n".join(lines)
