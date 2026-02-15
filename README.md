# OCI Block Volume Backup Posture Auditor

Standalone OCI automation tool that audits block/boot volume backup hygiene across compartments, produces JSON + Markdown findings, and uploads the results to OCI Object Storage.

## What It Checks

- Enumerates accessible compartments (OCI Identity)
- Collects block volumes, boot volumes, and their backups (OCI Block Volume)
- Correlates attached instances to each volume (OCI Compute)
- Flags backup posture by policy threshold:
  - `COMPLIANT`
  - `STALE_BACKUP`
  - `NO_BACKUP`
- Writes structured reports locally (`.json` + `.md`)
- Uploads reports to OCI Object Storage

No destructive operations are performed (read-only OCI API calls, except Object Storage uploads).

## Architecture

- `src/oci_block_volume_backup_auditor/collectors`: OCI service data collectors
- `src/oci_block_volume_backup_auditor/analyzers`: compliance analysis logic
- `src/oci_block_volume_backup_auditor/helpers`: output writers and upload helper
- `src/oci_block_volume_backup_auditor/main.py`: orchestration entrypoint

## Prerequisites

- Python 3.10+
- OCI config profile already configured (`~/.oci/config`)
- IAM permissions for read-only listing and Object Storage upload, including:
  - compartments / policies for visibility
  - compute and block volume list/read
  - object storage `put-object`

## Setup (Windows PowerShell)

```powershell
# 1) Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Create environment file (optional customization)
Copy-Item .env.example .env
# You can run without editing; bucket auto-discovery is enabled by default.

# 4) Run the audit
python run_audit.py
```

## Example Environment Variables

See `.env.example`. Optional but recommended:

- `OCI_CONFIG_FILE`
- `OCI_CONFIG_PROFILE`
- `OCI_REGION`
- `OCI_ROOT_COMPARTMENT_OCID`
- `OCI_MAX_BACKUP_AGE_DAYS`
- `OCI_OBJECT_STORAGE_NAMESPACE` (auto-detected if omitted)
- `OCI_OBJECT_STORAGE_BUCKET` (optional; auto-discovered if omitted)

## Output

By default, reports are written to `output/`:

- `block_volume_backup_posture_<timestamp>.json`
- `block_volume_backup_posture_<timestamp>.md`

Then both files are uploaded to Object Storage at:

- `oci://<bucket>@<namespace>/<prefix>/...`

## Evidence Steps

### Terminal Evidence

Run:

```powershell
python run_audit.py
```

Expected terminal checkpoints:

- Compartment discovery count
- Per-compartment collection progress
- Local report file paths
- Uploaded object URIs

### Object Storage Evidence

List uploaded objects (if you know bucket/namespace):

```powershell
oci os object list `
  --namespace-name $env:OCI_OBJECT_STORAGE_NAMESPACE `
  --bucket-name $env:OCI_OBJECT_STORAGE_BUCKET `
  --prefix $env:OCI_OBJECT_STORAGE_PREFIX
```

Optional: verify one object exists:

```powershell
oci os object head `
  --namespace-name $env:OCI_OBJECT_STORAGE_NAMESPACE `
  --bucket-name $env:OCI_OBJECT_STORAGE_BUCKET `
  --name "<prefix>/<report-file-name>"
```

## Troubleshooting

- `401/403` in one compartment: tool continues and records skipped compartments.
- `Bucket not found`: confirm `OCI_OBJECT_STORAGE_BUCKET` and namespace.
- `No module named oci`: reinstall dependencies in the active venv.

## Safety

- Read-only listing across Identity, Compute, and Block Volume APIs
- Only write action: Object Storage `put_object`
