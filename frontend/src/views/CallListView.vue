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
    // Remove empty params
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
  if (u >= 4) return 'bg-red-100 text-red-700'
  if (u >= 3) return 'bg-yellow-100 text-yellow-700'
  return 'bg-green-100 text-green-700'
}

function scoreBadge(s) {
  if (s >= 80) return 'bg-green-100 text-green-700'
  if (s >= 60) return 'bg-blue-100 text-blue-700'
  if (s >= 40) return 'bg-yellow-100 text-yellow-700'
  return 'bg-red-100 text-red-700'
}

function statusLabel(s) {
  return s.replace(/_/g, ' ')
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-gray-900 mb-4">Calls</h2>

    <!-- Filters -->
    <div class="flex gap-3 mb-4">
      <input
        v-model="filters.search"
        type="text"
        placeholder="Search name, email, summary..."
        class="flex-1 px-3 py-2 border rounded-md text-sm"
      />
      <select v-model="filters.resolution_status" class="px-3 py-2 border rounded-md text-sm">
        <option value="">All Statuses</option>
        <option value="resolved">Resolved</option>
        <option value="needs_followup">Needs Follow-up</option>
        <option value="appointment_booked">Appointment Booked</option>
        <option value="dropped">Dropped</option>
      </select>
      <select v-model="filters.ordering" class="px-3 py-2 border rounded-md text-sm">
        <option value="-lead_score">Lead Score (High→Low)</option>
        <option value="lead_score">Lead Score (Low→High)</option>
        <option value="-urgency">Urgency (High→Low)</option>
        <option value="call_id">Call ID</option>
      </select>
    </div>

    <div v-if="loading" class="text-gray-500">Loading...</div>

    <!-- Table -->
    <div v-else class="bg-white rounded-lg border overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-500">Call</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500">Caller</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500">Case Type</th>
            <th class="text-center px-4 py-3 font-medium text-gray-500">Urgency</th>
            <th class="text-center px-4 py-3 font-medium text-gray-500">Lead Score</th>
            <th class="text-left px-4 py-3 font-medium text-gray-500">Status</th>
            <th class="text-center px-4 py-3 font-medium text-gray-500">Review</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr
            v-for="call in calls"
            :key="call.id"
            class="hover:bg-gray-50 cursor-pointer"
            @click="router.push({ name: 'call-detail', params: { id: call.id } })"
          >
            <td class="px-4 py-3 font-mono text-xs text-gray-500">{{ call.call_id }}</td>
            <td class="px-4 py-3">
              <div class="font-medium text-gray-900">{{ call.caller_first_name }} {{ call.caller_last_name }}</div>
              <div class="text-xs text-gray-500">{{ call.caller_email }}</div>
            </td>
            <td class="px-4 py-3 text-gray-600">{{ call.case_type_name }}</td>
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
            <td class="px-4 py-3 text-gray-600 capitalize text-xs">{{ statusLabel(call.resolution_status) }}</td>
            <td class="px-4 py-3 text-center">
              <span v-if="call.needs_human_review" class="text-red-500" title="Needs human review">!</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
