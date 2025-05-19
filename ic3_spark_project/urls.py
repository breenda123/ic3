"""
URL configuration for ic3_spark_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# ic3_spark_project/urls.py
from django.contrib import admin
from django.urls import path, include # Thêm include
from quiz_api.views import frontend_view # Import view
from django.conf import settings # Thêm import này
from django.conf.urls.static import static # Thêm import này

urlpatterns = [
    path('', frontend_view, name='frontend-home'), # URL gốc
    path('admin/', admin.site.urls),
    path('api/', include('quiz_api.urls')), # Bao gồm các URL từ app quiz_api
]

# Phục vụ media files trong môi trường development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

