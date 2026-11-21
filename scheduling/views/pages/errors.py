"""Section 16: error pages in the layout, with the correlation id a user can quote."""

from django.http import HttpRequest, HttpResponse

from scheduling.views.pages.page_view import render_page


def forbidden_page(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render_page(request, "errors/403.html", status=403)


def not_found_page(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render_page(request, "errors/404.html", status=404)


def server_error_page(request: HttpRequest) -> HttpResponse:
    return render_page(request, "errors/500.html", status=500)
