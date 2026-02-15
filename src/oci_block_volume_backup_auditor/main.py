from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from oci.exceptions import ServiceError

from .analyzers import BackupPostureAnalyzer
from .clients import create_clients, create_oci_config
from .collectors import BlockStorageCollector, ComputeCollector, IdentityCollector
from .config import AppConfig
from .helpers import ObjectStorageUploader, write_json_report, write_markdown_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit OCI block/boot volume backup posture and upload reports to Object Storage."
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Generate local reports only, do not upload to Object Storage.",
    )
    return parser.parse_args()


def collect_compartment_data(
    compartment: Any,
    compute_collector: ComputeCollector,
    block_collector: BlockStorageCollector,
) -> dict[str, Any]:
    instances = compute_collector.list_instances(compartment.id)
    block_volume_attachments = compute_collector.list_block_volume_attachments(compartment.id)
    boot_volume_attachments = compute_collector.list_boot_volume_attachments(compartment.id)

    block_volumes = block_collector.list_block_volumes(compartment.id)
    boot_volumes = block_collector.list_boot_volumes(compartment.id)
    volume_backups = block_collector.list_volume_backups(compartment.id)
    boot_volume_backups = block_collector.list_boot_volume_backups(compartment.id)

    return {
        "compartment": compartment,
        "instances": instances,
        "block_volume_attachments": block_volume_attachments,
        "boot_volume_attachments": boot_volume_attachments,
        "block_volumes": block_volumes,
        "boot_volumes": boot_volumes,
        "volume_backups": volume_backups,
        "boot_volume_backups": boot_volume_backups,
    }


def discover_candidate_buckets(
    object_storage_client: Any,
    namespace: str,
    compartment_ids: list[str],
) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()

    for compartment_id in compartment_ids:
        try:
            response = object_storage_client.list_buckets(
                namespace_name=namespace,
                compartment_id=compartment_id,
            )
        except ServiceError:
            continue

        for bucket in response.data:
            name = getattr(bucket, "name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            discovered.append(name)

    return sorted(discovered)


def main() -> int:
    args = parse_args()

    try:
        app_config = AppConfig.from_env()
        oci_config = create_oci_config(app_config)
        clients = create_clients(oci_config)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Configuration failed: {exc}")
        return 1

    identity_collector = IdentityCollector(clients["identity"])
    compute_collector = ComputeCollector(clients["compute"])
    block_collector = BlockStorageCollector(clients["blockstorage"])

    tenancy_ocid = oci_config["tenancy"]
    region = oci_config["region"]

    try:
        compartments = identity_collector.list_compartments(
            tenancy_ocid=tenancy_ocid,
            root_compartment_ocid=app_config.root_compartment_ocid,
            include_subcompartments=app_config.include_subcompartments,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to enumerate compartments: {exc}")
        return 1

    print(f"[INFO] Discovered {len(compartments)} accessible compartments.")

    collected: list[dict[str, Any]] = []
    skipped_compartments: list[dict[str, str]] = []

    for index, compartment in enumerate(compartments, start=1):
        print(f"[INFO] [{index}/{len(compartments)}] Collecting compartment: {compartment.name}")
        try:
            data = collect_compartment_data(compartment, compute_collector, block_collector)
            collected.append(data)
        except ServiceError as exc:
            skipped_compartments.append(
                {
                    "compartment_id": compartment.id,
                    "reason": f"{exc.status} {exc.code}: {exc.message}",
                }
            )
            print(f"[WARN] Skipping compartment due to OCI error: {compartment.name}")
        except Exception as exc:  # noqa: BLE001
            skipped_compartments.append(
                {
                    "compartment_id": compartment.id,
                    "reason": str(exc),
                }
            )
            print(f"[WARN] Skipping compartment due to unexpected error: {compartment.name} ({exc})")

    generated_at = datetime.now(timezone.utc)
    analyzer = BackupPostureAnalyzer(max_backup_age_days=app_config.max_backup_age_days)
    report = analyzer.analyze(
        collected=collected,
        skipped_compartments=skipped_compartments,
        generated_at=generated_at,
        region=region,
        tenancy_ocid=tenancy_ocid,
    )

    timestamp_slug = generated_at.strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(app_config.output_dir)
    json_path = output_dir / f"block_volume_backup_posture_{timestamp_slug}.json"
    md_path = output_dir / f"block_volume_backup_posture_{timestamp_slug}.md"

    write_json_report(report, json_path)
    write_markdown_report(report, md_path)

    print(f"[INFO] JSON report written: {json_path}")
    print(f"[INFO] Markdown report written: {md_path}")

    if args.skip_upload:
        print("[INFO] Upload skipped by flag --skip-upload")
        return 0

    try:
        namespace = app_config.object_storage_namespace or clients["object_storage"].get_namespace().data
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to resolve Object Storage namespace: {exc}")
        return 2 if app_config.fail_on_upload_error else 0

    bucket_candidates: list[str] = []
    if app_config.object_storage_bucket:
        bucket_candidates.append(app_config.object_storage_bucket)

    if app_config.auto_discover_bucket:
        compartment_ids = [comp.id for comp in compartments]
        discovered = discover_candidate_buckets(
            object_storage_client=clients["object_storage"],
            namespace=namespace,
            compartment_ids=compartment_ids,
        )
        for bucket in discovered:
            if bucket not in bucket_candidates:
                bucket_candidates.append(bucket)

    if not bucket_candidates:
        print("[ERROR] No accessible Object Storage bucket found.")
        print("[ERROR] Set OCI_OBJECT_STORAGE_BUCKET or create bucket access for this principal.")
        return 2 if app_config.fail_on_upload_error else 0

    upload_success = False
    last_error: str | None = None
    report_files = [(json_path, "application/json"), (md_path, "text/markdown")]

    for bucket in bucket_candidates:
        uploader = ObjectStorageUploader(
            object_storage_client=clients["object_storage"],
            namespace=namespace,
            bucket=bucket,
            prefix=app_config.object_storage_prefix,
        )
        print(f"[INFO] Attempting upload using bucket: {bucket}")
        bucket_failed = False
        for file_path, content_type in report_files:
            try:
                result = uploader.upload_file(file_path=file_path, content_type=content_type)
                print(f"[INFO] Uploaded: {result.uri}")
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                bucket_failed = True
                print(f"[WARN] Upload failed in bucket '{bucket}' for {file_path.name}: {exc}")
                break
        if not bucket_failed:
            upload_success = True
            break

    if not upload_success:
        print("[ERROR] Upload failed for all candidate buckets.")
        if last_error:
            print(f"[ERROR] Last upload error: {last_error}")
        if app_config.fail_on_upload_error:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
