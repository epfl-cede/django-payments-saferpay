"""
URL configuration for example_app project.

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
from django.urls import include, path

from example_app import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("payments/", include("payments.urls")),
    path(
        "payment-failure/<str:token>",
        views.payment_failure,
        name="payment-failure",
    ),
    path(
        "payment-success/<str:token>",
        views.payment_success,
        name="payment-success",
    ),
    path(
        "payment-details/<str:token>",
        views.payment_details,
        name="payment-details",
    ),
    path("create-payment/", views.create_payment),
]
