"""
Custom exception handler.

Normalises all DRF error responses to a consistent JSON shape:

    {
        "error": "Human-readable summary",
        "details": { "field_name": ["error message"] }   ← for validation errors
    }

This gives the frontend a single contract to parse regardless of error type.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Extends DRF's default handler to enforce a uniform error envelope.
    Called by DRF whenever a view raises an exception.
    """
    # Let DRF handle the exception first to get the standard response
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — let Django's 500 handler deal with it
        return None

    # Build unified error structure
    data = response.data

    if isinstance(data, dict):
        # Validation error: {"field": ["msg"]} or {"detail": "msg"}
        if "detail" in data and len(data) == 1:
            # Authentication / permission errors
            unified = {
                "error": str(data["detail"]),
                "details": {},
            }
        else:
            # Field-level validation errors
            non_field = data.pop("non_field_errors", [])
            error_summary = (
                str(non_field[0]) if non_field else "Validation failed. Please check the details."
            )
            unified = {
                "error": error_summary,
                "details": data,
            }
    elif isinstance(data, list):
        unified = {
            "error": str(data[0]) if data else "An error occurred.",
            "details": {},
        }
    else:
        unified = {
            "error": str(data),
            "details": {},
        }

    response.data = unified
    return response
