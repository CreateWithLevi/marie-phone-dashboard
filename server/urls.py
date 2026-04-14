from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('calls.urls')),
    # Serve Vue SPA for all non-API routes
    re_path(r'^(?!api/).*$', TemplateView.as_view(template_name='index.html')),
]
