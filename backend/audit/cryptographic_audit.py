"""
DataTrust OS: Cryptographic Audit Ledger & Merkle Tree Verification
Implements:
1. Deterministic Merkle tree with ascending evaluation_id sorting and odd-node duplication.
2. Production AWS SSM Parameter Store / Secrets Manager HMAC key retrieval.
3. Fail-Closed security invariant for production environments (no hardcoded secrets).
4. HMAC-SHA256 digital signature computation and verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Union


class SecurityAuditError(RuntimeError):
    """Raised when security audit requirements or cryptographic secrets are violated."""


def get_audit_hmac_secret() -> str:
    """
    Retrieves the HMAC secret key.
    In production (ENVIRONMENT=production or AWS environment detected),
    requires reading from AWS SSM Parameter Store or Secrets Manager.
    Fail-closed: raises SecurityAuditError if unreachable or missing.
    """
    is_production = (
        os.getenv("ENVIRONMENT", "").lower() == "production"
        or bool(os.getenv("AWS_EXECUTION_ENV"))
        or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    )

    if is_production:
        param_name = os.getenv("AWS_SSM_AUDIT_SECRET_PATH", "/datatrust/production/audit_hmac_secret")
        try:
            import boto3
            from botocore.exceptions import ClientError, BotoCoreError

            ssm = boto3.client("ssm")
            response = ssm.get_parameter(Name=param_name, WithDecryption=True)
            secret = response.get("Parameter", {}).get("Value")
            if not secret:
                raise SecurityAuditError(f"AWS SSM returned empty value for {param_name}")
            if len(secret.encode("utf-8")) < 32:
                raise SecurityAuditError(f"Audit HMAC secret at {param_name} must be at least 32 bytes")
            return secret
        except Exception as exc:
            raise SecurityAuditError(
                f"Fail-Closed: Production AWS environment could not retrieve audit HMAC secret from SSM ({param_name}): {exc}"
            ) from exc

    # Local / Test / Dev environment fallback
    local_secret = os.getenv("DATATRUST_AUDIT_HMAC_SECRET")
    if local_secret:
        return local_secret

    return "datatrust_local_dev_audit_hmac_secret_2026"


def canonical_json_dumps(data: Any) -> str:
    """Serializes data to canonical JSON (sorted keys, compact separators)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_merkle_root(items: Sequence[Union[Dict[str, Any], str]]) -> str:
    """
    Computes deterministic Merkle tree root hash.
    Invariant:
    - Records sorted in ascending order of evaluation_id (_raw_id).
    - If node count at any level is odd, duplicate the last node.
    - Leaves are SHA-256 hashes of record contents or provided leaf hashes.
    """
    if not items:
        return hashlib.sha256(b"EMPTY_MERKLE_TREE").hexdigest()

    # Determine whether items are dicts or pre-computed leaf hashes
    if isinstance(items[0], dict):
        # Sort items deterministically by evaluation_id
        sorted_records = sorted(
            items,
            key=lambda r: str(r.get("evaluation_id") or r.get("_raw_id") or r.get("id") or ""),
        )
        leaves: List[str] = []
        for r in sorted_records:
            eval_id = str(r.get("evaluation_id") or r.get("_raw_id") or r.get("id") or "")
            lineage_hash = str(r.get("lineage_hash") or "")
            route = str(r.get("route") or r.get("routing_verdict") or "")
            leaf_payload = f"{eval_id}:{lineage_hash}:{route}"
            leaf_hash = hashlib.sha256(leaf_payload.encode("utf-8")).hexdigest()
            leaves.append(leaf_hash)
    else:
        # Pre-computed leaf hashes (assumed ordered)
        leaves = [str(item) for item in items]

    if len(leaves) == 1:
        return leaves[0]

    current_level = list(leaves)
    while len(current_level) > 1:
        next_level = []
        # Odd node duplication invariant
        if len(current_level) % 2 == 1:
            current_level.append(current_level[-1])

        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1]
            parent_bytes = f"{left}:{right}".encode("utf-8")
            parent_hash = hashlib.sha256(parent_bytes).hexdigest()
            next_level.append(parent_hash)

        current_level = next_level

    return current_level[0]


def generate_digital_signature(payload: Dict[str, Any], secret: Optional[str] = None) -> str:
    """Generates an HMAC-SHA256 digital signature over canonical evidence payload."""
    secret_key = secret or get_audit_hmac_secret()
    serialized = canonical_json_dumps(payload)
    return hmac.new(secret_key.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_digital_signature(payload: Dict[str, Any], signature: str, secret: Optional[str] = None) -> bool:
    """Verifies HMAC-SHA256 digital signature with constant-time comparison."""
    secret_key = secret or get_audit_hmac_secret()
    expected = generate_digital_signature(payload, secret=secret_key)
    return hmac.compare_digest(expected, signature)
