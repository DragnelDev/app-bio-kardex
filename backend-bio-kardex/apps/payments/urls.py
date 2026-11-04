from django.urls import path

from .views import ComprobanteView

urlpatterns = [path("pagos/<int:pk>/comprobante/", ComprobanteView.as_view())]
