from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import TieneRol
from apps.core.utils import exigir_sucursal

from .models import Metodo, Pago


class ComprobanteView(APIView):
    """POST /api/pagos/<id>/comprobante/  (multipart: `comprobante` y/o `referencia`)."""

    permission_classes = [TieneRol.con("cajero", "regente")]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            pago = Pago.objects.select_related("venta").get(pk=pk)
        except Pago.DoesNotExist:
            return Response({"detail": "El pago no existe."}, status=status.HTTP_404_NOT_FOUND)
        exigir_sucursal(request.user, pago.venta.sucursal_id)
        if pago.metodo != Metodo.QR:
            return Response(
                {"detail": "Solo los pagos QR admiten comprobante."}, status=status.HTTP_400_BAD_REQUEST
            )
        archivo = request.FILES.get("comprobante")
        referencia = request.data.get("referencia")
        if archivo is None and not referencia:
            return Response(
                {"detail": "Adjunta el comprobante o indica la referencia."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        campos = []
        if archivo is not None:
            pago.comprobante = archivo
            campos.append("comprobante")
        if referencia:
            pago.referencia = str(referencia)[:80]
            campos.append("referencia")
        pago.save(update_fields=campos)
        return Response(
            {
                "id": pago.id,
                "referencia": pago.referencia,
                "comprobante": request.build_absolute_uri(pago.comprobante.url) if pago.comprobante else None,
            }
        )
