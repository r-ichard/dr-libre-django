from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from scheduling.views.api_view import ApiView


class HealthView(ApiView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})
