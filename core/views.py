from django.http import HttpResponse
from django.views.decorators.cache import cache_control


@cache_control(public=True, max_age=86400)
def robots_txt(request):
    """Allow the portfolio, keep crawlers out of private and admin areas."""
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /album/",   # private client deliveries
        "",
        f"Sitemap: {sitemap_url}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
