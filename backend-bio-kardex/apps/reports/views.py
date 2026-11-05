import csv
from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import TieneRol
from apps.core.utils import hoy, redondear, sucursal_de_consulta
from apps.inventory.models import StockLote
from apps.payments.models import Pago
from apps.sales.models import Devolucion, EstadoVenta, Venta, VentaItem, VentaItemLote

CERO = Decimal("0.00")


class ReporteBase(APIView):
    """Reportes de gestion: solo regente y administrador."""

    permission_classes = [TieneRol.con("regente")]

    def rango(self, request) -> tuple[date, date]:
        def leer(nombre, defecto):
            bruto = request.query_params.get(nombre)
            if not bruto:
                return defecto
            try:
                return date.fromisoformat(bruto)
            except ValueError:
                raise ValidationError({nombre: "Fecha invalida (usa AAAA-MM-DD)."})

        desde = leer("desde", hoy())
        hasta = leer("hasta", hoy())
        if desde > hasta:
            raise ValidationError({"desde": "La fecha inicial no puede ser mayor a la final."})
        return desde, hasta

    @staticmethod
    def quiere_csv(request) -> bool:
        return request.query_params.get("formato") == "csv"


def respuesta_csv(nombre: str, cabecera: list[str], filas) -> HttpResponse:
    """CSV con BOM UTF-8 y separador ';' para que Excel lo abra bien en espanol."""
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
    respuesta.write("﻿")
    escritor = csv.writer(respuesta, delimiter=";")
    escritor.writerow(cabecera)
    for fila in filas:
        escritor.writerow(fila)
    return respuesta


def _dec(valor) -> Decimal:
    return valor if valor is not None else CERO


class VentasReporteView(ReporteBase):
    """GET /api/reportes/ventas/?sucursal=&desde=&hasta=&formato=csv"""

    def get(self, request):
        sucursal_id = sucursal_de_consulta(request)
        desde, hasta = self.rango(request)
        todas = Venta.objects.filter(
            sucursal_id=sucursal_id, creado_en__date__gte=desde, creado_en__date__lte=hasta
        )
        completadas = todas.filter(estado=EstadoVenta.COMPLETADA)

        if self.quiere_csv(request):
            filas = (
                [v.numero, timezone.localtime(v.creado_en).strftime("%Y-%m-%d %H:%M"), v.cajero.username,
                 v.nombre_cliente, v.documento_cliente, v.subtotal, v.descuento, v.total, v.iva, v.estado]
                for v in todas.select_related("cajero").order_by("numero")
            )
            return respuesta_csv(
                f"ventas_{desde}_{hasta}",
                ["Numero", "Fecha", "Cajero", "Cliente", "Documento", "Subtotal", "Descuento", "Total", "IVA", "Estado"],
                filas,
            )

        resumen = completadas.aggregate(
            cantidad=Count("id"), total=Sum("total"), iva=Sum("iva"), descuentos=Sum("descuento")
        )
        devoluciones = Devolucion.objects.filter(
            venta__sucursal_id=sucursal_id, creado_en__date__gte=desde, creado_en__date__lte=hasta
        ).aggregate(total=Sum("monto_total"))["total"]

        por_metodo = (
            Pago.objects.filter(venta__in=completadas).values("metodo").annotate(total=Sum("monto"))
        )
        por_dia = (
            completadas.annotate(dia=TruncDate("creado_en"))
            .values("dia").annotate(cantidad=Count("id"), total=Sum("total")).order_by("dia")
        )
        por_cajero = (
            completadas.values("cajero__username").annotate(cantidad=Count("id"), total=Sum("total"))
            .order_by("-total")
        )
        top = (
            VentaItem.objects.filter(venta__in=completadas)
            .values("producto__nombre_comercial", "producto__concentracion")
            .annotate(unidades_base=Sum("cantidad_base"), total=Sum("subtotal"))
            .order_by("-total")[:10]
        )
        return Response(
            {
                "desde": desde, "hasta": hasta,
                "resumen": {
                    "ventas": resumen["cantidad"],
                    "total": _dec(resumen["total"]),
                    "iva": _dec(resumen["iva"]),
                    "descuentos": _dec(resumen["descuentos"]),
                    "anuladas": todas.filter(estado=EstadoVenta.ANULADA).count(),
                    "devoluciones": _dec(devoluciones),
                    "ticket_promedio": redondear(resumen["total"] / resumen["cantidad"])
                    if resumen["cantidad"] else CERO,
                },
                "por_metodo": [{"metodo": m["metodo"], "total": m["total"]} for m in por_metodo],
                "por_dia": [{"dia": d["dia"], "cantidad": d["cantidad"], "total": d["total"]} for d in por_dia],
                "por_cajero": [
                    {"cajero": c["cajero__username"], "cantidad": c["cantidad"], "total": c["total"]}
                    for c in por_cajero
                ],
                "top_productos": [
                    {
                        "producto": f'{t["producto__nombre_comercial"]} {t["producto__concentracion"]}'.strip(),
                        "unidades_base": t["unidades_base"],
                        "total": t["total"],
                    }
                    for t in top
                ],
            }
        )


class ValorizadoReporteView(ReporteBase):
    """Stock valorizado a costo por producto. Los lotes sin costo se reportan aparte."""

    def get(self, request):
        sucursal_id = sucursal_de_consulta(request)
        stocks = StockLote.objects.filter(sucursal_id=sucursal_id, cantidad__gt=0).select_related(
            "lote", "lote__producto"
        )
        productos: dict[int, dict] = {}
        sin_costo = 0
        for s in stocks:
            fila = productos.setdefault(
                s.lote.producto_id,
                {"producto": str(s.lote.producto), "cantidad": 0, "valor": CERO},
            )
            fila["cantidad"] += s.cantidad
            if s.lote.costo_unitario is None:
                sin_costo += 1
            else:
                fila["valor"] += redondear(s.lote.costo_unitario * s.cantidad)
        filas = sorted(productos.values(), key=lambda f: f["producto"])

        if self.quiere_csv(request):
            return respuesta_csv(
                f"valorizado_{hoy()}", ["Producto", "Unidades base", "Valor a costo (Bs)"],
                ([f["producto"], f["cantidad"], f["valor"]] for f in filas),
            )
        return Response(
            {
                "total": sum((f["valor"] for f in filas), CERO),
                "lotes_sin_costo": sin_costo,
                "productos": filas,
            }
        )


class ControladosReporteView(ReporteBase):
    """Libro de ventas de medicamentos controlados (receta, medico, cliente y lote)."""

    def get(self, request):
        sucursal_id = sucursal_de_consulta(request)
        desde, hasta = self.rango(request)
        registros = (
            VentaItemLote.objects.filter(
                item__producto__es_controlado=True,
                item__venta__estado=EstadoVenta.COMPLETADA,
                item__venta__sucursal_id=sucursal_id,
                item__venta__creado_en__date__gte=desde,
                item__venta__creado_en__date__lte=hasta,
            )
            .select_related("item__venta__cajero", "item__producto", "lote")
            .order_by("item__venta__creado_en", "id")
        )
        filas = [
            {
                "fecha": timezone.localtime(r.item.venta.creado_en).strftime("%Y-%m-%d %H:%M"),
                "venta": r.item.venta.numero,
                "producto": str(r.item.producto),
                "lote": r.lote.numero,
                "cantidad_base": r.cantidad_base,
                "receta": r.item.venta.receta_numero,
                "medico": r.item.venta.medico,
                "documento": r.item.venta.documento_cliente,
                "cliente": r.item.venta.nombre_cliente,
                "cajero": r.item.venta.cajero.username,
            }
            for r in registros
        ]
        if self.quiere_csv(request):
            return respuesta_csv(
                f"controlados_{desde}_{hasta}",
                ["Fecha", "Venta", "Producto", "Lote", "Cantidad (u. base)", "Receta", "Medico", "Documento", "Cliente", "Cajero"],
                ([f[k] for k in ("fecha", "venta", "producto", "lote", "cantidad_base", "receta", "medico", "documento", "cliente", "cajero")] for f in filas),
            )
        return Response({"desde": desde, "hasta": hasta, "registros": filas})
