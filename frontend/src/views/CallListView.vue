<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const calls = ref([])
const loading = ref(true)
const filters = ref({
  ordering: '-lead_score',
  resolution_status: '',
  search: '',
})

async function fetchCalls() {
  loading.value = true
  try {
    const params = { ...filters.value }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const { data } = await api.getCalls(params)
    calls.value = data.results || data
  } finally {
    loading.value = false
  }
}

onMounted(fetchCalls)
watch(filters, fetchCalls, { deep: true })

function urgencyBadge(u) {
  if (u >= 4) return 'bg-[#c41c1c]/10 text-[#c41c1c]'
  if (u >= 3) return 'bg-[#fe4c02]/10 text-[#fe4c02]'
  return 'bg-[#0bdf50]/10 text-[#0bdf50]'
}

function scoreBadge(s) {
  if (s >= 80) return 'bg-[#0bdf50]/10 text-[#0bdf50]'
  if (s >= 60) return 'bg-[#65b5ff]/10 text-[#65b5ff]'
  if (s >= 40) return 'bg-[#fe4c02]/10 text-[#fe4c02]'
  return 'bg-[#c41c1c]/10 text-[#c41c1c]'
}

function verdictBadge(v) {
  if (v === 'accept') return 'bg-[#0bdf50]/10 text-[#0a8a36]'
  if (v === 'reject') return 'bg-[#c41c1c]/10 text-[#c41c1c]'
  return 'bg-[#fe4c02]/10 text-[#fe4c02]'
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-medium text-off-black mb-6 tracking-[-0.96px]">Calls</h2>

    <!-- Filters -->
    <div class="flex gap-3 mb-5">
      <input
        v-model="filters.search"
        type="text"
        placeholder="Search name, email, summary..."
        class="flex-1 px-3 py-2 border border-oat rounded bg-white text-sm text-off-black placeholder:text-warm-sand focus:outline-none focus:border-off-black"
      />
      <select v-model="filters.resolution_status" class="px-3 py-2 border border-oat rounded bg-white text-sm text-off-black focus:outline-none focus:border-off-black">
        <option value="">All Statuses</option>
        <option value="resolved">Resolved</option>
        <option value="needs_followup">Needs Follow-up</option>
        <option value="appointment_booked">Appointment Booked</option>
        <option value="dropped">Dropped</option>
      </select>
      <select v-model="filters.ordering" class="px-3 py-2 border border-oat rounded bg-white text-sm text-off-black focus:outline-none focus:border-off-black">
        <option value="-lead_score">Lead Score (High first)</option>
        <option value="lead_score">Lead Score (Low first)</option>
        <option value="-urgency">Urgency (High first)</option>
        <option value="call_id">Call ID</option>
      </select>
    </div>

    <div v-if="loading" class="text-muted text-sm">Loading...</div>

    <!-- Table -->
    <div v-else class="bg-white rounded-lg border border-oat overflow-hidden">
      <table class="w-full text-sm">
        <thead class="border-b border-oat">
          <tr class="bg-cream">
            <th class="text-left px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Call</th>
            <th class="text-left px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Caller</th>
            <th class="text-left px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Case Type</th>
            <th class="text-center px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Urgency</th>
            <th class="text-center px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Score</th>
            <th class="text-left px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Status</th>
            <th class="text-center px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Audit</th>
            <th class="text-center px-4 py-3 text-[11px] text-muted font-medium uppercase tracking-widest">Review</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-oat">
          <tr
            v-for="call in calls"
            :key="call.id"
            class="hover:bg-cream cursor-pointer transition-colors"
            @click="router.push({ name: 'call-detail', params: { id: call.id } })"
          >
            <td class="px-4 py-3 font-mono text-xs text-muted">{{ call.call_id }}</td>
            <td class="px-4 py-3">
              <div class="font-medium text-off-black">{{ call.caller_first_name }} {{ call.caller_last_name }}</div>
              <div class="text-xs text-muted">{{ call.caller_email }}</div>
            </td>
            <td class="px-4 py-3 text-black-60">{{ call.case_type_name }}</td>
            <td class="px-4 py-3 text-center">
              <span class="inline-block px-2 py-0.5 rounded text-xs font-medium" :class="urgencyBadge(call.urgency)">
                {{ call.urgency }}/5
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <span class="inline-block px-2 py-0.5 rounded text-xs font-medium" :class="scoreBadge(call.lead_score)">
                {{ call.lead_score }}
              </span>
            </td>
            <td class="px-4 py-3 text-black-60 capitalize text-xs">{{ call.resolution_status?.replace(/_/g, ' ') }}</td>
            <td class="px-4 py-3 text-center">
              <span
                v-if="call.quality_audit?.verdict"
                class="inline-block px-2 py-0.5 rounded text-[11px] font-medium capitalize"
                :class="verdictBadge(call.quality_audit.verdict)"
                :title="'Quality ' + (call.quality_audit.quality_score ?? '?') + '/5'"
              >
                {{ call.quality_audit.verdict }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <span v-if="call.needs_human_review" class="text-[#ff5600] font-bold" title="Needs human review">!</span>
              <span v-if="call.reflection_applied" class="ml-1 text-[10px] text-[#2167a8]" title="Reflection applied">R</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
