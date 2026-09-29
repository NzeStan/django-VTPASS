"""
Base models for the VTpass package.
This module defines abstract base models with common fields.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.settings import vtpass_settings


class UUIDModel(models.Model):
    """
    Abstract base model with UUID primary key.
    Used when USE_UUID setting is True.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID')
    )
    
    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """
    Abstract base model with created_at and updated_at fields.
    """
    created_at = models.DateTimeField(
        _('Created at'),
        auto_now_add=True,
        editable=False
    )
    updated_at = models.DateTimeField(
        _('Updated at'),
        auto_now=True,
        editable=False
    )
    
    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Base model for all VTpass models.
    This will use UUIDModel if USE_UUID setting is True.
    """
    class Meta:
        abstract = True


# Dynamically select the base model based on the settings
if vtpass_settings.USE_UUID:
    BaseModel.__bases__ = (UUIDModel,) + BaseModel.__bases__