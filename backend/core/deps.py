"""Dependencias compartidas de FastAPI."""
from backend.services.auth import get_current_user

__all__ = ["get_current_user"]
