"""Section 16: the terms and the privacy notice a visitor accepts when booking, open to everyone."""

from django.http import HttpRequest, HttpResponse

from scheduling.views.pages.page_view import PageView


class TermsPage(PageView):
    template_name = "legal/terms.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(request, {})


class PrivacyPage(PageView):
    template_name = "legal/privacy.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        return self.page(request, {})
