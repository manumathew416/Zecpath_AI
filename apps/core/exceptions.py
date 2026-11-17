"""Centralized error handler (Day 13).

Every error raised inside an API view passes through here, so the client
always receives the same structure, whatever caused the error.
"""
import logging

from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from .responses import error_payload

logger = logging.getLogger("api.errors")

SERVER_ERROR_MESSAGE = "Something went wrong on our side. Please try again later."


def _plain(value):
    """Turn DRF ErrorDetail objects into normal strings/lists/dicts."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return str(value)


def _message_and_code(exc):
    """Message and machine code for a non-validation API error."""
    detail = exc.detail
    code = getattr(detail, "code", None) or getattr(exc, "default_code", None)
    if isinstance(detail, dict):                       # SimpleJWT style {"detail":..., "code":...}
        code = detail.get("code") or code
        detail = detail.get("detail") or exc.default_detail
    elif isinstance(detail, list):
        detail = detail[0] if detail else exc.default_detail
    return str(detail), str(code) if code else None


def custom_exception_handler(exc, context):
    # Django's Http404 carries internal text such as "No Job matches the given
    # query." so it is replaced by a neutral message.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound("Not found.")

    response = drf_exception_handler(exc, context)

    # Unexpected error (a bug): log everything, tell the client nothing internal.
    if response is None:
        view = context.get("view")
        request = context.get("request")
        logger.exception(
            "Unhandled error in %s %s (view=%s)",
            getattr(request, "method", "?"), getattr(request, "path", "?"),
            view.__class__.__name__ if view else "?")
        set_rollback()
        return Response(
            error_payload(500, SERVER_ERROR_MESSAGE, "server_error"), status=500)

    status_code = response.status_code
    errors = None

    if isinstance(exc, exceptions.ValidationError):
        data = _plain(exc.detail)
        errors = data if isinstance(data, dict) else {"non_field_errors": data}
        message, code = "Validation failed.", "validation_error"
    elif isinstance(exc, exceptions.Throttled):
        message, code = _message_and_code(exc)
        errors = {"retry_after_seconds": exc.wait}
    elif isinstance(exc, exceptions.APIException):
        message, code = _message_and_code(exc)
    else:                                              # PermissionDenied etc. converted by DRF
        message, code = "Request failed.", None

    response.data = error_payload(status_code, message, code, errors)
    return response
