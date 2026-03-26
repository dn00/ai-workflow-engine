"""Workflow modules — auto-registers all known workflow types."""

from app.workflows import access_request, invoice_intake
from app.workflows.registry import register_workflow

register_workflow("access_request", access_request)
register_workflow("invoice_intake", invoice_intake)
