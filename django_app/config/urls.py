from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import include, path


def app_root(request):
    return redirect("profile" if request.user.is_authenticated else "login")


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("app", app_root),
    path("app/", app_root),
    path("app/health/", health, name="django-health"),
    path("app/admin/", admin.site.urls),
    path("app/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("app/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("app/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
