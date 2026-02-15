# ACE Contribution Sample

## Title
OCI Block Volume Backup Posture Auditor (Compartment-Wide, Non-Destructive)

## Description
This automation tool audits OCI block and boot volume backup hygiene across accessible compartments. It correlates data from OCI Identity, Compute, and Block Volume services, computes backup-age compliance status (`COMPLIANT`, `STALE_BACKUP`, `NO_BACKUP`), generates JSON and Markdown reports, and uploads report artifacts to OCI Object Storage for evidence retention and operational review. The tool is read-only across OCI APIs except for Object Storage uploads.

## Suggested Product Tags
- Oracle Cloud Infrastructure
- OCI Python SDK
- Compute
- Block Volume
- Identity and Access Management (IAM)
- Object Storage
- Security Operations
- Infrastructure Governance
- Automation
