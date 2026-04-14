<script setup>
const navItems = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/calls', label: 'Calls', icon: '📞' },
  { path: '/playbooks', label: 'Playbooks', icon: '📋' },
]
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Sidebar -->
    <nav class="fixed top-0 left-0 h-full w-56 bg-white border-r border-gray-200 p-4">
      <div class="mb-8">
        <h1 class="text-lg font-bold text-gray-900">Marie Dashboard</h1>
        <p class="text-xs text-gray-500 mt-1">AI Phone Assistant</p>
      </div>
      <ul class="space-y-1">
        <li v-for="item in navItems" :key="item.path">
          <router-link
            :to="item.path"
            class="flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100 transition-colors"
            active-class="bg-blue-50 text-blue-700 font-medium"
          >
            <span>{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </router-link>
        </li>
      </ul>
    </nav>

    <!-- Main content -->
    <main class="ml-56 p-6">
      <router-view />
    </main>
  </div>
</template>
