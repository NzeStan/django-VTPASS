"""Abstract base models."""

import uuid

import django
from django.db import models
from django.utils.translation import gettext_lazy as _


def check_constraint(condition, name):
    """``CheckConstraint`` across Django versions (``check=`` became ``condition=`` in 5.1)."""
    if django.VERSION >= (5, 1):
        return models.CheckConstraint(condition=condition, name=name)
    return models.CheckConstraint(check=condition, name=name)


class TimeStampedModel(models.Model):
    """
    Integer primary key for fast joins plus a random public ``uid`` that is
    safe to expose in URLs and API responses (sequential IDs leak volumes and
    invite enumeration).
    """

    uid = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True
