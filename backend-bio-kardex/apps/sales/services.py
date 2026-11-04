from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from apps.accounts.models import Rol
from apps.branches.models import Sucursal
from apps.cash.models import TurnoCaja
from apps.catalog.models import Presentacion, PrecioSucursal
from apps.core.exceptions import ErrorNegocio
from apps.core.utils import exigir_sucursal, redondear
from apps.inventory.models import TipoMovimiento
from apps.inventory.services import descontar_fefo, reponer_a_lote
from apps.payments.models import Metodo, Pago

from .models import (
    Cliente,
    Devolucion,
    DevolucionItem,
    EstadoVenta,
    Venta,
    VentaItem,
    VentaItemLote,
)


def _es_supervisor(usuario) -> bool:
    return usuario.es_admin or usuario.rol == Rol.REGENTE


def _turno_abierto(usuario, sucursal_id, bloquear=False):
    qs = TurnoCaja.objects.select_related("caja").filter(
        cajero=usuario, caja__sucursal_id=sucursal_id, cerrado_en__isnull=True
    )
    if bloquear:
        qs = qs.select_for_update(of=("self",))
    turno = qs.first()
    if turno is None:
        raise ErrorNegocio("Debes abrir un turno de caja para operar.", "sin_turno")
    return turno


def _cliente(datos):
    """Devuelve (cliente|None, nombre, documento) segun los datos opcionales del cliente."""
    datos = datos or {}
    numero = (datos.get("numero_documento") or "").strip()
    razon = (datos.get("razon_social") or "").strip()
    if not numero:
        return None, razon or "S/N", ""
    tipo = datos.get("tipo_documento") or "ci"
    cliente, _ = Cliente.objects.get_or_create(
        tipo_documento=tipo, numero_documento=numero, defaults={"razon_social": razon}
    )
    if razon and not cliente.razon_social:
        cliente.razon_social = razon
        cliente.save(update_fields=["razon_social"])
    return cliente, cliente.razon_social or razon or "S/N", numero


@transaction.atomic
def crear_venta(*, usuario, datos) -> Venta:
    """Registra una venta completa: precios, FEFO, pagos y Kardex en una sola transaccion."""
    sucursal_id = datos["sucursal"]
    exigir_sucursal(usuario, sucursal_id)

    referencia = datos.get("referencia_cliente")
    if referencia:
        previa = Venta.objects.filter(referencia_cliente=referencia).first()
        if previa:
            if previa.cajero_id != usuario.id:
                raise ErrorNegocio("Referencia de venta duplicada.", "referencia_duplicada")
            return previa  # reintento idempotente

    turno = _turno_abierto(usuario, sucursal_id, bloquear=True)

    # ---- lineas y precios
    entradas = datos["items"]
    ids = {i["presentacion"] for i in entradas}
    presentaciones = {
        p.id: p
        for p in Presentacion.objects.select_related("producto").filter(
            id__in=ids, activa=True, producto__activo=True
        )
    }
    if ids - presentaciones.keys():
        raise ErrorNegocio("Hay productos que ya no estan disponibles para la venta.", "producto_inactivo")
    especificos = {
        ps.presentacion_id: ps.precio
        for ps in PrecioSucursal.objects.filter(sucursal_id=sucursal_id, presentacion_id__in=ids)
    }
    lineas = []
    for entrada in entradas:
        p = presentaciones[entrada["presentacion"]]
        cantidad = entrada["cantidad"]
        precio = especificos.get(p.id, p.precio)
        lineas.append(
            {
                "presentacion": p,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": redondear(precio * cantidad),
                "base": cantidad * p.factor,
            }
        )

    subtotal = sum((l["subtotal"] for l in lineas), Decimal("0"))
    descuento = redondear(datos.get("descuento") or 0)
    if descuento < 0 or descuento >= subtotal:
        raise ErrorNegocio("El descuento debe ser menor al subtotal.", "descuento_invalido")
    if descuento > 0 and not _es_supervisor(usuario):
        raise ErrorNegocio("Solo el regente o el administrador puede aplicar descuentos.", "sin_permiso")
    total = subtotal - descuento
    iva_pct = Decimal(settings.IVA_PORCENTAJE)
    iva = redondear(total * iva_pct / (100 + iva_pct))

    # ---- recetas y productos controlados
    productos = [l["presentacion"].producto for l in lineas]
    receta_numero = (datos.get("receta_numero") or "").strip()
    medico = (datos.get("medico") or "").strip()
    cliente, nombre_cliente, documento = _cliente(datos.get("cliente"))
    if any(p.es_controlado or p.requiere_receta for p in productos) and not receta_numero:
        raise ErrorNegocio("La venta incluye productos que exigen receta.", "receta_requerida")
    if any(p.es_controlado for p in productos):
        if not medico:
            raise ErrorNegocio("Los productos controlados exigen el nombre del medico.", "medico_requerido")
        if not documento:
            raise ErrorNegocio("Los productos controlados exigen identificar al cliente.", "cliente_requerido")

    # ---- pagos
    pagos = []
    for p in datos["pagos"]:
        monto = redondear(p["monto"])
        recibido = monto
        if p["metodo"] == Metodo.EFECTIVO and p.get("recibido") is not None:
            recibido = redondear(p["recibido"])
        if recibido < monto:
            raise ErrorNegocio("El efectivo recibido no cubre el monto del pago.", "recibido_insuficiente")
        pagos.append({"metodo": p["metodo"], "monto": monto, "recibido": recibido, "ref": p.get("referencia", "")})
    pagado = sum((p["monto"] for p in pagos), Decimal("0"))
    if pagado != total:
        raise ErrorNegocio(
            f"Los pagos ({pagado}) no coinciden con el total ({total}).", "pagos_no_cuadran"
        )
    vuelto = sum((p["recibido"] - p["monto"] for p in pagos), Decimal("0"))

    # ---- correlativo por sucursal (se serializa bloqueando la fila de la sucursal)
    Sucursal.objects.select_for_update().get(pk=sucursal_id)
    numero = (Venta.objects.filter(sucursal_id=sucursal_id).aggregate(m=Max("numero"))["m"] or 0) + 1

    venta = Venta.objects.create(
        sucursal_id=sucursal_id, numero=numero, turno=turno, cajero=usuario,
        cliente=cliente, nombre_cliente=nombre_cliente, documento_cliente=documento,
        subtotal=subtotal, descuento=descuento, total=total, iva=iva, vuelto=vuelto,
        receta_numero=receta_numero, medico=medico, referencia_cliente=referencia or None,
    )

    items = []
    for l in lineas:
        p = l["presentacion"]
        item = VentaItem.objects.create(
            venta=venta, presentacion=p, producto=p.producto, cantidad=l["cantidad"],
            factor=p.factor, cantidad_base=l["base"], precio_unitario=l["precio"],
            subtotal=l["subtotal"],
        )
        items.append((l, item))

    # FEFO en orden de producto para que ventas concurrentes bloqueen en el mismo orden
    for l, item in sorted(items, key=lambda x: (x[0]["presentacion"].producto_id, x[1].id)):
        plan = descontar_fefo(
            usuario=usuario, sucursal_id=sucursal_id, producto_id=item.producto_id,
            cantidad=item.cantidad_base, tipo=TipoMovimiento.VENTA,
            referencia_tipo="venta", referencia_id=venta.id, motivo=f"Venta #{numero}",
        )
        VentaItemLote.objects.bulk_create(
            [VentaItemLote(item=item, lote_id=lote_id, cantidad_base=c) for lote_id, c in plan]
        )

    Pago.objects.bulk_create(
        [
            Pago(venta=venta, metodo=p["metodo"], monto=p["monto"], recibido=p["recibido"], referencia=p["ref"] or "")
            for p in pagos
        ]
    )
    return venta


@transaction.atomic
def anular_venta(*, usuario, venta_id, motivo) -> Venta:
    """Anula una venta del turno aun abierto y devuelve todo el stock a sus lotes."""
    if not _es_supervisor(usuario):
        raise ErrorNegocio("Solo el regente o el administrador puede anular ventas.", "sin_permiso")
    if not (motivo or "").strip():
        raise ErrorNegocio("El motivo de anulacion es obligatorio.", "motivo_requerido")
    try:
        venta = Venta.objects.select_for_update().select_related("turno").get(pk=venta_id)
    except Venta.DoesNotExist:
        raise ErrorNegocio("La venta no existe.", "no_encontrado")
    exigir_sucursal(usuario, venta.sucursal_id)
    if venta.estado != EstadoVenta.COMPLETADA:
        raise ErrorNegocio("La venta ya esta anulada.", "venta_anulada")
    if not venta.turno.abierto:
        raise ErrorNegocio("El turno de esta venta ya se cerro: registra una devolucion.", "turno_cerrado")
    if venta.devoluciones.exists():
        raise ErrorNegocio("La venta tiene devoluciones; no puede anularse.", "tiene_devoluciones")

    asignaciones = VentaItemLote.objects.filter(item__venta=venta).order_by("lote_id")
    for a in asignaciones:
        reponer_a_lote(
            usuario=usuario, sucursal_id=venta.sucursal_id, lote_id=a.lote_id,
            cantidad=a.cantidad_base, tipo=TipoMovimiento.ANULACION_VENTA,
            referencia_tipo="venta", referencia_id=venta.id,
            motivo=f"Anulacion venta #{venta.numero}",
        )
    venta.estado = EstadoVenta.ANULADA
    venta.anulada_por = usuario
    venta.anulada_en = timezone.now()
    venta.motivo_anulacion = motivo.strip()
    venta.save()
    return venta


@transaction.atomic
def registrar_devolucion(*, usuario, venta_id, items, motivo, metodo_reembolso) -> Devolucion:
    """Devolucion total o parcial: items = [{"venta_item_lote": id, "cantidad": base}].

    El stock vuelve al mismo lote de la sucursal y el reembolso resta de la caja del turno actual.
    """
    if not _es_supervisor(usuario):
        raise ErrorNegocio("Solo el regente o el administrador puede registrar devoluciones.", "sin_permiso")
    if not (motivo or "").strip():
        raise ErrorNegocio("El motivo de la devolucion es obligatorio.", "motivo_requerido")
    try:
        venta = Venta.objects.select_for_update().get(pk=venta_id)
    except Venta.DoesNotExist:
        raise ErrorNegocio("La venta no existe.", "no_encontrado")
    exigir_sucursal(usuario, venta.sucursal_id)
    if venta.estado != EstadoVenta.COMPLETADA:
        raise ErrorNegocio("No se puede devolver una venta anulada.", "venta_anulada")
    turno = _turno_abierto(usuario, venta.sucursal_id, bloquear=True)

    pedidos: dict[int, int] = {}
    for it in items:
        pedidos[it["venta_item_lote"]] = pedidos.get(it["venta_item_lote"], 0) + it["cantidad"]
    if not pedidos:
        raise ErrorNegocio("Indica que items se devuelven.")

    factor_descuento = venta.total / venta.subtotal  # reparte el descuento proporcionalmente
    asignaciones = {
        a.id: a
        for a in VentaItemLote.objects.select_related("item").filter(
            id__in=pedidos.keys(), item__venta=venta
        ).order_by("lote_id")
    }
    if set(pedidos) - asignaciones.keys():
        raise ErrorNegocio("Hay items que no pertenecen a esta venta.", "item_invalido")

    devolucion = Devolucion.objects.create(
        venta=venta, turno=turno, usuario=usuario, motivo=motivo.strip(),
        metodo_reembolso=metodo_reembolso, monto_total=Decimal("0"),
    )
    total = Decimal("0")
    for item_lote_id in sorted(pedidos):
        a = asignaciones[item_lote_id]
        cantidad = pedidos[item_lote_id]
        previa = (
            DevolucionItem.objects.filter(venta_item_lote=a).aggregate(t=Sum("cantidad_base"))["t"] or 0
        )
        if cantidad <= 0 or cantidad > a.cantidad_base - previa:
            raise ErrorNegocio("La cantidad a devolver supera lo vendido.", "cantidad_invalida")
        monto = redondear(a.item.precio_unitario * cantidad / a.item.factor * factor_descuento)
        DevolucionItem.objects.create(
            devolucion=devolucion, venta_item_lote=a, cantidad_base=cantidad, monto=monto
        )
        reponer_a_lote(
            usuario=usuario, sucursal_id=venta.sucursal_id, lote_id=a.lote_id, cantidad=cantidad,
            tipo=TipoMovimiento.DEVOLUCION_VENTA, referencia_tipo="devolucion",
            referencia_id=devolucion.id, motivo=f"Devolucion venta #{venta.numero}: {motivo.strip()}",
        )
        total += monto
    devolucion.monto_total = total
    devolucion.save(update_fields=["monto_total"])
    return devolucion
