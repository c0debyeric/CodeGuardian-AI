"""API key store.

Backends:
  - InMemoryKeyStore: dev/test default. Seeded from env or admin endpoint.
  - (future) DatabaseKeyStore: Postgres-backed for prod.

Keys are stored as SHA-256 hashes; the plaintext key is only seen at creation.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from src.auth.models import Tenant


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_key(tenant_id: str) -> str:
    """Return a new plaintext API key. Format: sk-<tenant>-<random>."""
    return f"sk-{tenant_id}-{secrets.token_urlsafe(24)}"


@dataclass
class KeyRecord:
    key_hash: str
    tenant: Tenant
    label: str = "default"
    revoked: bool = False


class InMemoryKeyStore:
    """Simple in-memory store. Thread-unsafe; fine for single-process dev."""

    def __init__(self) -> None:
        self._by_hash: dict[str, KeyRecord] = {}

    def create_key(self, tenant: Tenant, *, label: str = "default") -> str:
        plaintext = generate_key(tenant.id)
        self._by_hash[hash_key(plaintext)] = KeyRecord(
            key_hash=hash_key(plaintext), tenant=tenant, label=label
        )
        return plaintext

    def add_existing(self, plaintext: str, tenant: Tenant, *, label: str = "default") -> None:
        """Register a pre-generated key (used by env-seed bootstrap)."""
        h = hash_key(plaintext)
        self._by_hash[h] = KeyRecord(key_hash=h, tenant=tenant, label=label)

    def lookup(self, plaintext: str) -> KeyRecord | None:
        rec = self._by_hash.get(hash_key(plaintext))
        if rec is None or rec.revoked:
            return None
        return rec

    def revoke(self, plaintext: str) -> bool:
        rec = self._by_hash.get(hash_key(plaintext))
        if rec is None:
            return False
        rec.revoked = True
        return True

    def revoke_tenant(self, tenant_id: str) -> int:
        """Revoke every key belonging to a tenant. Returns count revoked.

        UI-friendly: callers don't have plaintext for already-issued keys, so
        revocation has to be addressable by tenant.
        """
        n = 0
        for rec in self._by_hash.values():
            if rec.tenant.id == tenant_id and not rec.revoked:
                rec.revoked = True
                n += 1
        return n

    def list_tenants(self) -> list[Tenant]:
        seen: set[str] = set()
        out: list[Tenant] = []
        for r in self._by_hash.values():
            if r.tenant.id not in seen:
                seen.add(r.tenant.id)
                out.append(r.tenant)
        return out


_store: InMemoryKeyStore | None = None


def get_keystore() -> InMemoryKeyStore:
    global _store
    if _store is None:
        _store = InMemoryKeyStore()
        _seed_from_env(_store)
    return _store


def reset_keystore() -> None:
    global _store
    _store = None


def _seed_from_env(store: InMemoryKeyStore) -> None:
    """Seed a default demo tenant from settings, if a key is configured.

    Set DEMO_TENANT_KEY in env to bootstrap a working key without an admin call.
    """
    import os

    demo_key = os.environ.get("DEMO_TENANT_KEY")
    if demo_key:
        store.add_existing(
            demo_key,
            Tenant(
                id="demo",
                name="Demo Tenant",
                rpm_limit=int(os.environ.get("DEMO_TENANT_RPM", "60")),
                tpm_limit=int(os.environ.get("DEMO_TENANT_TPM", "100000")),
            ),
            label="seed",
        )
