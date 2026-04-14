<script setup>
const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/calls', label: 'Calls' },
  { path: '/playbooks', label: 'Playbooks' },
]
</script>

<template>
  <div class="min-h-screen bg-cream">
    <!-- Sidebar -->
    <nav class="fixed top-0 left-0 h-full w-52 bg-white border-r border-oat p-5 flex flex-col">
      <div class="mb-10">
        <h1 class="text-xl font-medium text-off-black tracking-[-0.96px]">Marie</h1>
        <p class="text-xs text-muted mt-0.5 tracking-wide uppercase">Phone Dashboard</p>
      </div>
      <ul class="space-y-0.5">
        <li v-for="item in navItems" :key="item.path">
          <router-link
            :to="item.path"
            class="block px-3 py-2 rounded text-sm text-black-60 hover:bg-cream transition-colors"
            active-class="!bg-cream !text-off-black font-medium"
          >
            {{ item.label }}
          </router-link>
        </li>
      </ul>
      <div class="mt-auto pt-4 border-t border-oat">
        <p class="text-[11px] text-muted">Powered by AI Pipeline</p>
      </div>
    </nav>

    <!-- Main content -->
    <main class="ml-52 p-8">
      <router-view />
    </main>
  </div>
</template>
