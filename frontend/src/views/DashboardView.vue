<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await api.getDashboardStats()
    stats.value = data
  } finally {
    loading.value = false
  }
})

function scoreColor(label) {
  return { high: 'text-green-600', good: 'text-blue-600', moderate: 'text-yellow-600', low: 'text-red-600' }[label] || ''
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Dashboard</h2>

    <div v-if="loading" class="text-gray-500">Loading...</div>

    <template v-else-if="stats">
      <!-- KPI Cards -->
      <div class="grid grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg border p-4">
          <p class="text-sm text-gray-500">Total Calls</p>
          <p class="text-3xl font-bold text-gray-900">{{ stats.total_calls }}</p>
        </div>
        <div class="bg-white rounded-lg border p-4">
          <p class="text-sm text-gray-500">Avg Lead Score</p>
          <p class="text-3xl font-bold text-blue-600">{{ stats.avg_lead_score }}</p>
        </div>
        <div class="bg-white rounded-lg border p-4">
          <p class="text-sm text-gray-500">Avg Urgency</p>
          <p class="text-3xl font-bold text-orange-600">{{ stats.avg_urgency }}/5</p>
        </div>
        <div class="bg-white rounded-lg border p-4">
          <p class="text-sm text-gray-500">Needs Review</p>
          <p class="text-3xl font-bold text-red-600">{{ stats.needs_review }}</p>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-6">
        <!-- Resolution Funnel -->
        <div class="bg-white rounded-lg border p-4">
          <h3 class="font-semibold text-gray-900 mb-4">Resolution Funnel</h3>
          <div class="space-y-3">
            <div v-for="(count, status) in stats.resolution_funnel" :key="status" class="flex justify-between items-center">
              <span class="text-sm text-gray-600 capitalize">{{ status.replace('_', ' ') }}</span>
              <div class="flex items-center gap-2">
                <div class="w-24 bg-gray-100 rounded-full h-2">
                  <div class="bg-blue-500 h-2 rounded-full" :style="{ width: (count / stats.total_calls * 100) + '%' }"></div>
                </div>
                <span class="text-sm font-medium w-6 text-right">{{ count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Case Type Breakdown -->
        <div class="bg-white rounded-lg border p-4">
          <h3 class="font-semibold text-gray-900 mb-4">Case Types</h3>
          <div class="space-y-3">
            <div v-for="ct in stats.case_type_breakdown" :key="ct.case_type__name" class="flex justify-between items-center">
              <span class="text-sm text-gray-600">{{ ct.case_type__name }}</span>
              <span class="text-sm font-medium bg-gray-100 px-2 py-0.5 rounded">{{ ct.count }}</span>
            </div>
          </div>
        </div>

        <!-- Lead Score Distribution -->
        <div class="bg-white rounded-lg border p-4">
          <h3 class="font-semibold text-gray-900 mb-4">Lead Quality</h3>
          <div class="space-y-3">
            <div v-for="(count, label) in stats.lead_score_distribution" :key="label" class="flex justify-between items-center">
              <span class="text-sm capitalize" :class="scoreColor(label)">{{ label }} ({{ {high:'80-100',good:'60-79',moderate:'40-59',low:'0-39'}[label] }})</span>
              <span class="text-sm font-medium">{{ count }}</span>
            </div>
          </div>
          <div class="mt-4 pt-3 border-t text-sm text-gray-500">
            Avg Playbook Completeness: {{ (stats.avg_playbook_completeness * 100).toFixed(0) }}%
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
