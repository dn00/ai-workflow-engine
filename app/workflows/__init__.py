"""Workflow modules — auto-registers all known workflow types."""

from app.workflows import access_request
from app.workflows.registry import register_workflow

register_workflow("access_request", access_request)
