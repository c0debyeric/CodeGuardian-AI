"""Auth package: API key tenants + dependency for protected routes."""

from src.auth.models import Tenant
from src.auth.dependencies import get_current_tenant, optional_tenant

__all__ = ["Tenant", "get_current_tenant", "optional_tenant"]
