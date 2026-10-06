import logging
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

log = logging.getLogger(__name__)
_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_warned = False


def require_api_key(key: str | None = Security(_header)) -> None:
    """Protège les écritures. Si API_KEY est vide (dev), on laisse passer avec un avertissement."""
    global _warned
    if not settings.api_key:
        if not _warned:
            log.warning("API_KEY non définie : les écritures sont ouvertes (mode dev uniquement !)")
            _warned = True
        return
    if not key or not secrets.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clé API invalide")
