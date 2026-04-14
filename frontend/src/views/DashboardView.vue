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

const scoreColors = {
  high: 'text-[#0bdf50]',
  good: 'text-[#65b5ff]',
  moderate: 'text-[#fe4c02]',
  low: 'text-[#c41c1c]',
}
const scoreRanges = { high: '80–100', good: '60–79', moderate: '40–59', low: '0–39' }
</script>

<template>
  <div>
    <h2 class="text-2xl font-medium text-off-black mb-8 tracking-[-0.96px]">Dashboard</h2>

    <div v-if="loading" class="text-muted text-sm">Loading...</div>

    <template v-else-if="stats">
      <!-- KPI Cards -->
      <div class="grid grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg border border-oat p-5">
          <p class="text-[11px] text-muted uppercase tracking-widest mb-1">Total Calls</p>
          <p class="text-3xl font-medium text-off-black tracking-[-1.2px]">{{ stats.total_calls }}</p>
        </div>
        <div class="bg-white rounded-lg border border-oat p-5">
          <p class="text-[11px] text-muted uppercase tracking-widest mb-1">Avg Lead Score</p>
          <p class="text-3xl font-medium text-[#65b5ff] tracking-[-1.2px]">{{ stats.avg_lead_score }}</p>
        </div>
        <div class="bg-white rounded-lg border border-oat p-5">
          <p class="text-[11px] text-muted uppercase tracking-widest mb-1">Avg Urgency</p>
          <p class="text-3xl font-medium text-[#fe4c02] tracking-[-1.2px]">{{ stats.avg_urgency }}<span class="text-lg text-muted">/5</span></p>
        </div>
        <div class="bg-white rounded-lg border border-oat p-5">
          <p class="text-[11px] text-muted uppercase tracking-widest mb-1">Needs Review</p>
          <p class="text-3xl font-medium tracking-[-1.2px]" :class="stats.needs_review > 0 ? 'text-[#c41c1c]' : 'text-off-black'">{{ stats.needs_review }}</p>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <!-- Resolution Funnel -->
        <div class="bg-white rounded-lg border border-oat p-5">
          <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Resolution Funnel</h3>
          <div class="space-y-3">
            <div v-for="(count, status) in stats.resolution_funnel" :key="status" class="flex justify-between items-center">
              <span class="text-sm text-black-60 capitalize">{{ status.replace('_', ' ') }}</span>
              <div class="flex items-center gap-2">
                <div class="w-24 bg-cream rounded-full h-1.5">
                  <div class="bg-off-black h-1.5 rounded-full" :style="{ width: (count / stats.total_calls * 100) + '%' }"></div>
                </div>
                <span class="text-sm font-medium text-off-black w-6 text-right">{{ count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Case Type Breakdown -->
        <div class="bg-white rounded-lg border border-oat p-5">
          <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Case Types</h3>
          <div class="space-y-3">
            <div v-for="ct in stats.case_type_breakdown" :key="ct.case_type__name" class="flex justify-between items-center">
              <span class="text-sm text-black-60">{{ ct.case_type__name }}</span>
              <span class="text-xs font-medium bg-cream text-off-black px-2 py-0.5 rounded">{{ ct.count }}</span>
            </div>
          </div>
        </div>

        <!-- Lead Score Distribution -->
        <div class="bg-white rounded-lg border border-oat p-5">
          <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Lead Quality</h3>
          <div class="space-y-3">
            <div v-for="(count, label) in stats.lead_score_distribution" :key="label" class="flex justify-between items-center">
              <span class="text-sm" :class="scoreColors[label]">{{ label }} <span class="text-muted text-xs">({{ scoreRanges[label] }})</span></span>
              <span class="text-sm font-medium text-off-black">{{ count }}</span>
            </div>
          </div>
          <div class="mt-4 pt-3 border-t border-oat text-sm text-muted">
            Avg Playbook: {{ (stats.avg_playbook_completeness * 100).toFixed(0) }}%
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
