<script setup lang="ts">
import type { Venta } from '@/types'
import { bs, fechaHora } from '@/utils/format'

defineProps<{ venta: Venta }>()
</script>

<template>
  <div class="ticket mx-auto w-[80mm] bg-white p-3 font-mono text-xs text-black">
    <div class="text-center">
      <p class="text-sm font-bold">BioKardex Farmacia</p>
      <p>{{ venta.sucursal_nombre }}</p>
      <p>Recibo interno N° {{ venta.numero }}</p>
      <p>{{ fechaHora(venta.creado_en) }}</p>
      <p v-if="venta.estado === 'anulada'" class="font-bold">*** ANULADA ***</p>
    </div>
    <hr class="my-2 border-dashed border-black" />
    <p>Cliente: {{ venta.nombre_cliente }}</p>
    <p v-if="venta.documento_cliente">Doc.: {{ venta.documento_cliente }}</p>
    <p>Cajero: {{ venta.cajero_nombre }}</p>
    <hr class="my-2 border-dashed border-black" />
    <div v-for="i in venta.items" :key="i.id" class="mb-1">
      <p>{{ i.producto_nombre }}</p>
      <p class="flex justify-between">
        <span>{{ i.cantidad }} x {{ i.presentacion_nombre }} @ {{ bs(i.precio_unitario) }}</span>
        <span>{{ bs(i.subtotal) }}</span>
      </p>
    </div>
    <hr class="my-2 border-dashed border-black" />
    <p class="flex justify-between">
      <span>Subtotal</span><span>{{ bs(venta.subtotal) }}</span>
    </p>
    <p v-if="Number(venta.descuento) > 0" class="flex justify-between">
      <span>Descuento</span><span>-{{ bs(venta.descuento) }}</span>
    </p>
    <p class="flex justify-between text-sm font-bold">
      <span>TOTAL</span><span>{{ bs(venta.total) }}</span>
    </p>
    <p class="flex justify-between">
      <span>IVA incluido (13%)</span><span>{{ bs(venta.iva) }}</span>
    </p>
    <hr class="my-2 border-dashed border-black" />
    <p v-for="p in venta.pagos" :key="p.id" class="flex justify-between">
      <span>{{ p.metodo_display }}{{ p.referencia ? ` (${p.referencia})` : '' }}</span>
      <span>{{ bs(p.recibido) }}</span>
    </p>
    <p v-if="Number(venta.vuelto) > 0" class="flex justify-between font-bold">
      <span>Vuelto</span><span>{{ bs(venta.vuelto) }}</span>
    </p>
    <p class="mt-3 text-center">Gracias por su compra</p>
    <p class="text-center">Documento sin valor fiscal</p>
  </div>
</template>
