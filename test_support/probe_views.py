"""Views used only by tests, mounted through probe_urls with override_settings."""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import HttpRequest, HttpResponse
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduling.domain.failure import Failure
from scheduling.use_cases.request_context import current_request_context
from scheduling.views import clock
from scheduling.views.failure_response import failure_response
from scheduling.views.schemas import StrictSerializer, validate_body

SENSITIVE_MESSAGE = "patient reports chest pain, a@b.example, tok_abc123"


class UndeclaredView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"reached": True})


class ExplodingView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        raise ValueError(SENSITIVE_MESSAGE)


class IdentifierRouteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, email: str) -> Response:
        return Response({"ok": True})


class ContextView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        first = current_request_context()
        clock.now_utc()
        second = current_request_context()
        return Response(
            {
                "correlation_id": first.correlation_id,
                "first": first.now.isoformat(),
                "second": second.now.isoformat(),
            }
        )


class ConflictView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return failure_response(Failure.conflict(["clinician", "room"]))


class AppointmentSchema(StrictSerializer):
    start = serializers.DateTimeField()
    reason = serializers.CharField(read_only=True, required=False)


class WriteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        result = validate_body(AppointmentSchema, request.data)
        if isinstance(result, Failure):
            return failure_response(result)
        return Response({"accepted": True}, status=201)


class DjangoDeniedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        raise DjangoPermissionDenied(SENSITIVE_MESSAGE)


class AuthenticationFailedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        raise exceptions.AuthenticationFailed(SENSITIVE_MESSAGE)


class UnsupportedMediaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        raise exceptions.UnsupportedMediaType("text/plain")


def plain_explode(request: HttpRequest) -> HttpResponse:
    raise ValueError(SENSITIVE_MESSAGE)


class AddressSchema(serializers.Serializer[dict[str, object]]):
    city = serializers.CharField()


class ItemSchema(serializers.Serializer[dict[str, object]]):
    name = serializers.CharField()


class NestedSchema(StrictSerializer):
    address = AddressSchema()
    items = ItemSchema(many=True)


class NestedWriteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        result = validate_body(NestedSchema, request.data)
        if isinstance(result, Failure):
            return failure_response(result)
        return Response({"accepted": True}, status=201)
