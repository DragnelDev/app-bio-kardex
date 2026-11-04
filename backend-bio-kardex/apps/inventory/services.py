"""Operaciones de inventario. Todas son atomicas y bloquean las filas de stock que tocan.

Reglas de concurrencia:
- Todo cambio de stock pasa por `select_for_update()` sobre StockLote.
- Para evitar deadlocks, quien toque varios productos debe hacerlo en orden de
  producto_id; y varios lotes del mismo producto siempre se bloquean en orden FEFO
  (vencimiento, id), que es igual para todas las transacciones.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.branches.models import Sucursal
from apps.catalog.models import Presentacion
from apps.core.exceptions import ErrorNegocio, StockInsuficiente
from apps.core.utils import exigir_sucursal, hoy

from .fefo import FaltanteFEFO, asignar_fefo
from .models import (
    EstadoTraspaso,
    Lote,
    MovimientoKardex,
    StockLote,
    TipoMovimiento,
    Traspaso,
    TraspasoItem,
)


def _registrar_movimiento(
    *, usuario, sucursal_id, lote_id, tipo, cantidad, saldo,
    referencia_tipo="", referencia_id=None, motivo="",
):
    return MovimientoKardex.objects.create(
        sucursal_id=sucursal_id,
        lote_id=lote_id,
        tipo=tipo,
        cantidad=cantidad,
        saldo=saldo,
        usuario=usuario,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
    )


def _stock_bloqueado(sucursal_id: int, lote_id: int) -> StockLote:
    """Devuelve el StockLote bloqueado para escritura, creandolo en cero si no existe."""
    consulta = StockLote.objects.select_for_update(of=("self",)).select_related("lote")
    try:
        return consulta.get(sucursal_id=sucursal_id, lote_id=lote_id)
    except StockLote.DoesNotExist:
        pass
    try:
        with transaction.atomic():  # savepoint: un choque no rompe la transaccion externa
            StockLote.objects.create(sucursal_id=sucursal_id, lote_id=lote_id, cantidad=0)
    except IntegrityError:
        pass
    return consulta.get(sucursal_id=sucursal_id, lote_id=lote_id)


def _sumar(stock: StockLote, delta: int) -> None:
    nuevo = stock.cantidad + delta
    if nuevo < 0:
        raise StockInsuficiente(
            "Stock insuficiente en el lote.", lote_id=stock.lote_id, disponible=stock.cantidad
        )
    stock.cantidad = nuevo
    stock.save(update_fields=["cantidad", "actualizado_en"])


# ---------------------------------------------------------------- ingresos

@transaction.atomic
def registrar_ingreso(
    *, usuario, sucursal_id, producto_id, numero_lote, fecha_vencimiento,
    cantidad, costo_unitario=None, motivo="Ingreso de mercaderia",
):
    """Ingresa mercaderia a una sucursal. Lote y fecha de vencimiento son obligatorios."""
    exigir_sucursal(usuario, sucursal_id)
    numero_lote = (numero_lote or "").strip()
    if not numero_lote:
        raise ErrorNegocio("El numero de lote es obligatorio.", "lote_requerido")
    if cantidad <= 0:
        raise ErrorNegocio("La cantidad debe ser mayor a cero.")
    if fecha_vencimiento <= hoy():
        raise ErrorNegocio("No se puede ingresar un lote vencido.", "lote_vencido")

    lote, creado = Lote.objects.get_or_create(
        producto_id=producto_id,
        numero=numero_lote,
        defaults={"fecha_vencimiento": fecha_vencimiento, "costo_unitario": costo_unitario},
    )
    if not creado:
        if lote.fecha_vencimiento != fecha_vencimiento:
            raise ErrorNegocio(
                f"El lote {numero_lote} ya existe con vencimiento {lote.fecha_vencimiento}.",
                "vencimiento_distinto",
            )
        if costo_unitario is not None:
            lote.costo_unitario = costo_unitario
            lote.save(update_fields=["costo_unitario", "actualizado_en"])

    stock = _stock_bloqueado(sucursal_id, lote.id)
    _sumar(stock, cantidad)
    _registrar_movimiento(
        usuario=usuario, sucursal_id=sucursal_id, lote_id=lote.id,
        tipo=TipoMovimiento.INGRESO, cantidad=cantidad, saldo=stock.cantidad, motivo=motivo,
    )
    return stock


# -------------------------------------------------------------------- FEFO

def descontar_fefo(
    *, usuario, sucursal_id, producto_id, cantidad, tipo,
    referencia_tipo="", referencia_id=None, motivo="",
):
    """Descuenta `cantidad` (unidades base) del producto aplicando FEFO estricto.

    Debe llamarse dentro de una transaccion. Excluye lotes vencidos y bloqueados.
    Devuelve [(lote_id, cantidad_tomada)].
    """
    disponibles = list(
        StockLote.objects.select_for_update(of=("self",))
        .select_related("lote")
        .filter(
            sucursal_id=sucursal_id,
            lote__producto_id=producto_id,
            cantidad__gt=0,
            bloqueado=False,
            lote__fecha_vencimiento__gte=hoy(),
        )
        .order_by("lote__fecha_vencimiento", "lote_id")
    )
    try:
        plan = asignar_fefo([(s.lote_id, s.cantidad) for s in disponibles], cantidad)
    except FaltanteFEFO as e:
        total = sum(s.cantidad for s in disponibles)
        raise StockInsuficiente(
            "Stock insuficiente para completar la operacion.",
            producto_id=producto_id, solicitado=cantidad, disponible=total, faltante=e.faltante,
        )

    por_lote = {s.lote_id: s for s in disponibles}
    for lote_id, tomar in plan:
        stock = por_lote[lote_id]
        _sumar(stock, -tomar)
        _registrar_movimiento(
            usuario=usuario, sucursal_id=sucursal_id, lote_id=lote_id, tipo=tipo,
            cantidad=-tomar, saldo=stock.cantidad,
            referencia_tipo=referencia_tipo, referencia_id=referencia_id, motivo=motivo,
        )
    return plan


def reponer_a_lote(
    *, usuario, sucursal_id, lote_id, cantidad, tipo,
    referencia_tipo="", referencia_id=None, motivo="",
):
    """Devuelve stock a un lote concreto (devoluciones, anulaciones, rechazos)."""
    if cantidad <= 0:
        raise ErrorNegocio("La cantidad debe ser mayor a cero.")
    stock = _stock_bloqueado(sucursal_id, lote_id)
    _sumar(stock, cantidad)
    _registrar_movimiento(
        usuario=usuario, sucursal_id=sucursal_id, lote_id=lote_id, tipo=tipo,
        cantidad=cantidad, saldo=stock.cantidad,
        referencia_tipo=referencia_tipo, referencia_id=referencia_id, motivo=motivo,
    )
    return stock


# ------------------------------------------------------- bajas y ajustes

@transaction.atomic
def registrar_baja(*, usuario, sucursal_id, lote_id, cantidad, motivo):
    """Baja de mercaderia (vencida, danada, retirada). El motivo es obligatorio."""
    exigir_sucursal(usuario, sucursal_id)
    if not (motivo or "").strip():
        raise ErrorNegocio("El motivo de la baja es obligatorio.", "motivo_requerido")
    if cantidad <= 0:
        raise ErrorNegocio("La cantidad debe ser mayor a cero.")
    stock = _stock_bloqueado(sucursal_id, lote_id)
    _sumar(stock, -cantidad)
    _registrar_movimiento(
        usuario=usuario, sucursal_id=sucursal_id, lote_id=lote_id,
        tipo=TipoMovimiento.BAJA, cantidad=-cantidad, saldo=stock.cantidad, motivo=motivo.strip(),
    )
    return stock


@transaction.atomic
def ajustar_stock(*, usuario, sucursal_id, lote_id, cantidad_real, motivo):
    """Ajuste por conteo fisico: deja el stock en `cantidad_real` con un movimiento compensatorio."""
    exigir_sucursal(usuario, sucursal_id)
    if not (motivo or "").strip():
        raise ErrorNegocio("El motivo del ajuste es obligatorio.", "motivo_requerido")
    if cantidad_real < 0:
        raise ErrorNegocio("La cantidad real no puede ser negativa.")
    stock = _stock_bloqueado(sucursal_id, lote_id)
    delta = cantidad_real - stock.cantidad
    if delta == 0:
        raise ErrorNegocio("El stock ya coincide con la cantidad indicada.", "sin_diferencia")
    _sumar(stock, delta)
    _registrar_movimiento(
        usuario=usuario, sucursal_id=sucursal_id, lote_id=lote_id,
        tipo=TipoMovimiento.AJUSTE, cantidad=delta, saldo=stock.cantidad, motivo=motivo.strip(),
    )
    return stock


@transaction.atomic
def cambiar_bloqueo(*, usuario, sucursal_id, lote_id, bloqueado: bool):
    exigir_sucursal(usuario, sucursal_id)
    stock = _stock_bloqueado(sucursal_id, lote_id)
    stock.bloqueado = bloqueado
    stock.save(update_fields=["bloqueado", "actualizado_en"])
    return stock


# ---------------------------------------------------------------- traspasos

def _fusionar_items(items):
    """items: [{"lote": id, "cantidad": n}] -> {lote_id: total}, validando positivos."""
    fusion: dict[int, int] = {}
    for item in items:
        if item["cantidad"] <= 0:
            raise ErrorNegocio("Las cantidades del traspaso deben ser positivas.")
        fusion[item["lote"]] = fusion.get(item["lote"], 0) + item["cantidad"]
    if not fusion:
        raise ErrorNegocio("El traspaso no tiene items.")
    return fusion


@transaction.atomic
def crear_traspaso(*, usuario, origen_id, destino_id, items, observacion=""):
    """Envia stock del origen al destino. El stock sale del origen de inmediato."""
    exigir_sucursal(usuario, origen_id)
    if origen_id == destino_id:
        raise ErrorNegocio("El origen y el destino deben ser distintos.")
    if not Sucursal.objects.filter(pk=destino_id, activa=True).exists():
        raise ErrorNegocio("La sucursal destino no existe o esta inactiva.")

    fusion = _fusionar_items(items)
    traspaso = Traspaso.objects.create(
        origen_id=origen_id, destino_id=destino_id, creado_por=usuario, observacion=observacion
    )
    for lote_id in sorted(fusion):  # orden fijo de bloqueo
        cantidad = fusion[lote_id]
        stock = _stock_bloqueado(origen_id, lote_id)
        if stock.lote.vencido:
            raise ErrorNegocio(
                f"El lote {stock.lote.numero} esta vencido y no puede traspasarse.", "lote_vencido"
            )
        if stock.bloqueado:
            raise ErrorNegocio(f"El lote {stock.lote.numero} esta bloqueado.", "lote_bloqueado")
        _sumar(stock, -cantidad)
        TraspasoItem.objects.create(traspaso=traspaso, lote_id=lote_id, cantidad_enviada=cantidad)
        _registrar_movimiento(
            usuario=usuario, sucursal_id=origen_id, lote_id=lote_id,
            tipo=TipoMovimiento.TRASPASO_SALIDA, cantidad=-cantidad, saldo=stock.cantidad,
            referencia_tipo="traspaso", referencia_id=traspaso.id,
            motivo=f"Traspaso #{traspaso.id}",
        )
    return traspaso


def _traspaso_enviado_bloqueado(traspaso_id):
    try:
        traspaso = Traspaso.objects.select_for_update().get(pk=traspaso_id)
    except Traspaso.DoesNotExist:
        raise ErrorNegocio("El traspaso no existe.", "no_encontrado")
    if traspaso.estado != EstadoTraspaso.ENVIADO:
        raise ErrorNegocio("El traspaso ya fue resuelto.", "traspaso_resuelto")
    return traspaso


@transaction.atomic
def recibir_traspaso(*, usuario, traspaso_id, recibidos=None, observacion=""):
    """La sucursal destino confirma la recepcion. `recibidos` = {item_id: cantidad}.

    Si no se indica un item se asume recibido completo. Las diferencias exigen observacion.
    """
    traspaso = _traspaso_enviado_bloqueado(traspaso_id)
    exigir_sucursal(usuario, traspaso.destino_id)
    recibidos = recibidos or {}

    items = list(traspaso.items.select_related("lote").order_by("lote_id"))
    hay_diferencia = False
    for item in items:
        cantidad = recibidos.get(item.id, item.cantidad_enviada)
        if cantidad < 0 or cantidad > item.cantidad_enviada:
            raise ErrorNegocio(
                "La cantidad recibida no puede superar la enviada.", "cantidad_invalida"
            )
        item.cantidad_recibida = cantidad
        item.save(update_fields=["cantidad_recibida"])
        hay_diferencia = hay_diferencia or cantidad != item.cantidad_enviada
        if cantidad > 0:
            reponer_a_lote(
                usuario=usuario, sucursal_id=traspaso.destino_id, lote_id=item.lote_id,
                cantidad=cantidad, tipo=TipoMovimiento.TRASPASO_ENTRADA,
                referencia_tipo="traspaso", referencia_id=traspaso.id,
                motivo=f"Traspaso #{traspaso.id}",
            )
    if hay_diferencia and not (observacion or "").strip():
        raise ErrorNegocio("Hay diferencias: indica una observacion.", "observacion_requerida")

    traspaso.estado = EstadoTraspaso.RECIBIDO
    traspaso.resuelto_por = usuario
    traspaso.resuelto_en = timezone.now()
    traspaso.observacion_recepcion = observacion or ""
    traspaso.save()
    return traspaso


@transaction.atomic
def rechazar_traspaso(*, usuario, traspaso_id, observacion):
    """El destino rechaza el envio: todo el stock vuelve a los mismos lotes del origen."""
    traspaso = _traspaso_enviado_bloqueado(traspaso_id)
    exigir_sucursal(usuario, traspaso.destino_id)
    if not (observacion or "").strip():
        raise ErrorNegocio("Indica el motivo del rechazo.", "observacion_requerida")

    for item in traspaso.items.order_by("lote_id"):
        reponer_a_lote(
            usuario=usuario, sucursal_id=traspaso.origen_id, lote_id=item.lote_id,
            cantidad=item.cantidad_enviada, tipo=TipoMovimiento.TRASPASO_RECHAZO,
            referencia_tipo="traspaso", referencia_id=traspaso.id,
            motivo=f"Rechazo de traspaso #{traspaso.id}",
        )
        item.cantidad_recibida = 0
        item.save(update_fields=["cantidad_recibida"])

    traspaso.estado = EstadoTraspaso.RECHAZADO
    traspaso.resuelto_por = usuario
    traspaso.resuelto_en = timezone.now()
    traspaso.observacion_recepcion = observacion.strip()
    traspaso.save()
    return traspaso


# ------------------------------------------------------------ utilidades

def unidades_base(presentacion_id: int, cantidad: int) -> tuple[int, int]:
    """Convierte cantidad de una presentacion a unidades base. Devuelve (producto_id, base)."""
    try:
        presentacion = Presentacion.objects.get(pk=presentacion_id)
    except Presentacion.DoesNotExist:
        raise ErrorNegocio("La presentacion no existe.", "no_encontrado")
    return presentacion.producto_id, cantidad * presentacion.factor
