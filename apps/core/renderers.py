"""Wraps every API response in the standard structure (Day 13)."""
from rest_framework.renderers import JSONRenderer

from .responses import error_payload, is_envelope, success_payload


class StandardJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if response is None or data is None or is_envelope(data):
            return super().render(data, accepted_media_type, renderer_context)

        status_code = response.status_code
        if status_code >= 400:
            # an error a view returned by hand, for example Response({"detail": ...}, 404)
            if isinstance(data, dict) and set(data) <= {"detail", "code"}:
                payload = error_payload(status_code, str(data.get("detail", "")) or None,
                                        data.get("code"))
            else:
                payload = error_payload(status_code, "Request failed.", None, data)
                if status_code == 400:
                    payload["message"] = "Validation failed."
                    payload["error_code"] = "validation_error"
        elif isinstance(data, dict) and set(data) == {"detail"}:
            payload = success_payload(status_code, None, str(data["detail"]))
        else:
            payload = success_payload(status_code, data)
        return super().render(payload, accepted_media_type, renderer_context)
