import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from './views/DashboardView.vue'
import CallListView from './views/CallListView.vue'
import CallDetailView from './views/CallDetailView.vue'
import PlaybookView from './views/PlaybookView.vue'

const routes = [
  { path: '/', name: 'dashboard', component: DashboardView },
  { path: '/calls', name: 'calls', component: CallListView },
  { path: '/calls/:id', name: 'call-detail', component: CallDetailView },
  { path: '/playbooks', name: 'playbooks', component: PlaybookView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
