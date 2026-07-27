from __future__ import annotations

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.fernet import MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class EncryptedTextField(models.TextField):
    prefix = "enc::"

    def _cipher(self) -> MultiFernet:
        keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", ())
        if not keys:
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEYS deve conter ao menos uma chave Fernet.",
            )
        try:
            return MultiFernet([Fernet(key.encode("ascii")) for key in keys])
        except (ValueError, TypeError) as exc:
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEYS contém uma chave Fernet inválida.",
            ) from exc

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if value is None or not isinstance(value, str) or not value.startswith(self.prefix):
            return value
        try:
            token = value[len(self.prefix) :].encode("ascii")
            return self._cipher().decrypt(token).decode("utf-8")
        except (InvalidToken, UnicodeError) as exc:
            raise ImproperlyConfigured(
                f"Não foi possível descriptografar {self.model._meta.label}.{self.name}.",
            ) from exc

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, "") or value.startswith(self.prefix):
            return value
        token = self._cipher().encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.prefix}{token}"
