from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


class ApiView(APIView):
    """Base for API views: head and options are not routes, and no Allow header is sent."""

    http_method_names = ["get", "post", "put", "patch", "delete"]

    @property
    def default_response_headers(self) -> dict[str, str]:
        headers = super().default_response_headers
        headers.pop("Allow", None)
        return headers


class NotFoundView(ApiView):
    """Catch-all under the API prefix, so unknown paths answer in the contract's shape."""

    permission_classes = [AllowAny]
