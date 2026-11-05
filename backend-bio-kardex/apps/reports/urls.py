from django.urls import path

from . import views

urlpatterns = [
    path("reportes/ventas/", views.VentasReporteView.as_view()),
    path("reportes/valorizado/", views.ValorizadoReporteView.as_view()),
    path("reportes/controlados/", views.ControladosReporteView.as_view()),
]
