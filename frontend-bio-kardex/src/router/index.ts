import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore, type Rol } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    publica?: boolean
    roles?: Rol[]
    titulo?: string
    icono?: string
    menu?: boolean
  }
}

const GESTION: Rol[] = ['regente', 'almacenero']
const MOSTRADOR: Rol[] = ['cajero', 'regente']

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { publica: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { titulo: 'Inicio', icono: 'pi-home', menu: true },
        },
        {
          path: 'pos',
          name: 'pos',
          component: () => import('@/views/PosView.vue'),
          meta: {
            titulo: 'Punto de venta',
            icono: 'pi-shopping-cart',
            roles: MOSTRADOR,
            menu: true,
          },
        },
        {
          path: 'ventas',
          name: 'ventas',
          component: () => import('@/views/VentasView.vue'),
          meta: { titulo: 'Ventas', icono: 'pi-receipt', roles: MOSTRADOR, menu: true },
        },
        {
          path: 'caja',
          name: 'caja',
          component: () => import('@/views/CajaView.vue'),
          meta: { titulo: 'Caja', icono: 'pi-wallet', roles: MOSTRADOR, menu: true },
        },
        {
          path: 'catalogo',
          name: 'catalogo',
          component: () => import('@/views/CatalogoView.vue'),
          meta: { titulo: 'Catalogo', icono: 'pi-box', roles: GESTION, menu: true },
        },
        {
          path: 'inventario',
          name: 'inventario',
          component: () => import('@/views/InventarioView.vue'),
          meta: { titulo: 'Inventario', icono: 'pi-database', roles: GESTION, menu: true },
        },
        {
          path: 'kardex',
          name: 'kardex',
          component: () => import('@/views/KardexView.vue'),
          meta: { titulo: 'Kardex', icono: 'pi-list', roles: GESTION, menu: true },
        },
        {
          path: 'traspasos',
          name: 'traspasos',
          component: () => import('@/views/TraspasosView.vue'),
          meta: {
            titulo: 'Traspasos',
            icono: 'pi-arrow-right-arrow-left',
            roles: GESTION,
            menu: true,
          },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restaurar()

  if (to.meta.publica) {
    return auth.autenticado && to.name === 'login' ? { name: 'dashboard' } : true
  }
  if (!auth.autenticado) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!auth.puede(to.meta.roles)) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
