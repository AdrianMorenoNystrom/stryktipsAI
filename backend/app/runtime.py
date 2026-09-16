"""Validated process configuration. Public settings never contain credentials."""
from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class Runtime:
    environment: str
    database_url: str
    origins: tuple[str, ...]

    @property
    def production(self):
        return self.environment == 'production'

    @classmethod
    def load(cls):
        environment = os.getenv('ENVIRONMENT', 'development')
        database = os.getenv('DATABASE_URL', '')
        origins = tuple(o.strip().rstrip('/') for o in os.getenv('ALLOWED_ORIGINS', 'http://localhost:4200,http://127.0.0.1:4200').split(',') if o.strip())
        if environment not in ('development', 'test', 'production'):
            raise ValueError('ENVIRONMENT must be development, test or production')
        if database and urlparse(database).scheme not in ('postgresql', 'postgres'):
            raise ValueError('DATABASE_URL must use PostgreSQL')
        if any(urlparse(o).scheme not in ('http', 'https') or not urlparse(o).hostname or urlparse(o).path or urlparse(o).username or urlparse(o).password or urlparse(o).query or urlparse(o).fragment for o in origins):
            raise ValueError('ALLOWED_ORIGINS must contain exact HTTP(S) origins')
        if environment == 'production' and (not database or not origins or any(not o.startswith('https://') for o in origins)):
            raise ValueError('Production requires Postgres and explicit HTTPS ALLOWED_ORIGINS')
        return cls(environment, database, origins)
