class CorsMiddleware:
    """Add CORS header Access-Control-Allow-Origin: * to all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            from django.http import HttpResponse
            response = HttpResponse(status=200)
            self._add_cors_headers(response)
            return response
        response = self.get_response(request)
        self._add_cors_headers(response)
        return response

    def _add_cors_headers(self, response):
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
