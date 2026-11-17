"""One response structure for the whole API (Day 13).

Success:  {"success": true,  "status_code": 200, "message": "Success", "data": {...}}
Error:    {"success": false, "status_code": 400, "message": "Validation failed.",
           "error_code": "validation_error", "errors": {...} or null}
"""
from http import HTTPStatus

DEFAULT_MESSAGES = {
    200: "Success",
    201: "Created successfully",
    202: "Accepted",
    205: "Done",
}

DEFAULT_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
    500: "server_error",
}


def success_payload(status_code, data=None, message=None):
    return {
        "success": True,
        "status_code": status_code,
        "message": message or DEFAULT_MESSAGES.get(status_code, "Success"),
        "data": data,
    }


def error_payload(status_code, message=None, error_code=None, errors=None):
    if message is None:
        try:
            message = HTTPStatus(status_code).phrase
        except ValueError:
            message = "Error"
    return {
        "success": False,
        "status_code": status_code,
        "message": message,
        "error_code": error_code or DEFAULT_ERROR_CODES.get(status_code, "error"),
        "errors": errors,
    }


def is_envelope(data):
    return isinstance(data, dict) and "success" in data and "status_code" in data
