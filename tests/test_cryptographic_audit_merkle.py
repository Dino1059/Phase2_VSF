import hashlib
import os
import random
import pytest

from backend.audit.cryptographic_audit import (
    SecurityAuditError,
    get_audit_hmac_secret,
    compute_merkle_root,
    generate_digital_signature,
    verify_digital_signature,
)


def test_merkle_tree_deterministic_evaluation_id_sorting():
    """Merkle root must be identical regardless of input order because items are sorted by evaluation_id."""
    records = [
        {"evaluation_id": "eval_003", "lineage_hash": "hash_c", "route": "SILVER"},
        {"evaluation_id": "eval_001", "lineage_hash": "hash_a", "route": "SILVER"},
        {"evaluation_id": "eval_002", "lineage_hash": "hash_b", "route": "QUARANTINE"},
        {"evaluation_id": "eval_004", "lineage_hash": "hash_d", "route": "WARNING"},
    ]

    root_ordered = compute_merkle_root(records)

    # Shuffle records
    shuffled = list(records)
    random.seed(42)
    random.shuffle(shuffled)
    root_shuffled = compute_merkle_root(shuffled)

    assert root_ordered == root_shuffled
    assert len(root_ordered) == 64  # SHA-256 hex string


def test_merkle_tree_odd_node_duplication_invariant():
    """When node count is odd at any level, the last node must be duplicated."""
    leaves = [
        hashlib.sha256(b"leaf_1").hexdigest(),
        hashlib.sha256(b"leaf_2").hexdigest(),
        hashlib.sha256(b"leaf_3").hexdigest(),
    ]

    # Manual calculation with odd duplication:
    # Level 1: [leaf_1, leaf_2, leaf_3, leaf_3 (duplicated)]
    # Level 2: [parent(leaf_1, leaf_2), parent(leaf_3, leaf_3)]
    # Level 3: parent(parent(1,2), parent(3,3))
    p1 = hashlib.sha256(f"{leaves[0]}:{leaves[1]}".encode("utf-8")).hexdigest()
    p2 = hashlib.sha256(f"{leaves[2]}:{leaves[2]}".encode("utf-8")).hexdigest()
    expected_root = hashlib.sha256(f"{p1}:{p2}".encode("utf-8")).hexdigest()

    computed_root = compute_merkle_root(leaves)
    assert computed_root == expected_root


def test_merkle_tree_edge_cases():
    """Tests empty and single-item Merkle trees."""
    empty_root = compute_merkle_root([])
    assert empty_root == hashlib.sha256(b"EMPTY_MERKLE_TREE").hexdigest()

    single_leaf = hashlib.sha256(b"single").hexdigest()
    single_root = compute_merkle_root([single_leaf])
    assert single_root == single_leaf


def test_production_ssm_fail_closed(monkeypatch):
    """In production environment, failing to retrieve secret from SSM must raise SecurityAuditError (fail-closed)."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(SecurityAuditError, match="Fail-Closed: Production AWS environment could not retrieve audit HMAC secret"):
        get_audit_hmac_secret()


def test_local_environment_custom_and_default_secret(monkeypatch):
    """In local dev, reads DATATRUST_AUDIT_HMAC_SECRET or falls back to dev default."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("AWS_EXECUTION_ENV", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    # 1. Custom secret
    monkeypatch.setenv("DATATRUST_AUDIT_HMAC_SECRET", "custom_test_secret_123")
    assert get_audit_hmac_secret() == "custom_test_secret_123"

    # 2. Dev default
    monkeypatch.delenv("DATATRUST_AUDIT_HMAC_SECRET", raising=False)
    assert get_audit_hmac_secret() == "datatrust_local_dev_audit_hmac_secret_2026"


def test_hmac_digital_signature_generation_and_verification():
    """Validates HMAC-SHA256 digital signature creation and tamper-evident verification."""
    payload = {
        "run_id": "RUN-2026-01-11-TEST",
        "dataset_id": "ride_hailing_xanh_sm_trips",
        "evidence_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "scanned_count": 100,
        "silver_count": 90,
        "quarantine_count": 10,
    }

    sig = generate_digital_signature(payload, secret="test_secret_key_456")
    assert len(sig) == 64
    assert verify_digital_signature(payload, sig, secret="test_secret_key_456") is True

    # Tampered payload fails verification
    tampered = dict(payload)
    tampered["silver_count"] = 91
    assert verify_digital_signature(tampered, sig, secret="test_secret_key_456") is False

    # Wrong secret fails verification
    assert verify_digital_signature(payload, sig, secret="wrong_secret_key") is False
