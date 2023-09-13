import json

from django.http import HttpResponse


class NonHtmlDebugToolbarMiddleware:
    """
    The Django Debug Toolbar usually only works for views that return HTML.
    This middleware wraps any JSON response in HTML if the request
    has a 'debug' query parameter (e.g. http://localhost/foo?format=json&debug)

    adapted from:
    https://gist.github.com/fabiosussetto/c534d84cbbf7ab60b025
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.GET.get("debug", None) is not None:
            if response["Content-Type"] == "application/json":
                content = json.dumps(json.loads(response.content), sort_keys=True, indent=2)
                response = HttpResponse(f"<html><body><pre>{content}</pre></body></html>")

        return response
