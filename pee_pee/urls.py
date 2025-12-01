"""
URL configuration for PriMag Enterprise Sales Management Platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView

# Customize the default admin site - PriMag Enterprise
admin.site.site_header = "PriMag Enterprise"
admin.site.site_title = "PriMag Enterprise - Sales Management Platform"
admin.site.index_title = "PriMag Enterprise Dashboard"

urlpatterns = [
    path('admin/', admin.site.urls),
    # Redirect root URL to the admin login page so the landing page shows admin login
    path('', RedirectView.as_view(url='/admin/login/?next=/admin/')),
]
