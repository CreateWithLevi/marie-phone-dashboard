<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()
const call = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await api.getCall(route.params.id)
    call.value = data
  } finally {
    loading.value = false
  }
})

function confidenceColor(score) {
  if (score >= 0.8) return 'text-green-600'
  if (score >= 0.6) return 'text-yellow-600'
  return 'text-red-600'
}

function accuracyIcon(correct) {
  return correct ? '✓' : '✗'
}

function accuracyColor(correct) {
  return correct ? 'text-green-600' : 'text-red-600'
}
</script>

<template>
  <div>
    <button @click="router.push({ name: 'calls' })" class="text-sm text-blue-600 hover:underline mb-4 inline-block">
      ← Back to Calls
    </button>

    <div v-if="loading" class="text-gray-500">Loading...</div>

    <template v-else-if="call">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <h2 class="text-2xl font-bold text-gray-900">
            {{ call.caller_first_name }} {{ call.caller_last_name }}
          </h2>
          <p class="text-sm text-gray-500 font-mono">{{ call.call_id }}</p>
        </div>
        <div class="flex gap-2">
          <span v-if="call.needs_human_review" class="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
            Needs Review
          </span>
          <span class="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 capitalize">
            {{ call.resolution_status?.replace(/_/g, ' ') }}
          </span>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-6">
        <!-- Left: Contact + Analysis -->
        <div class="col-span-2 space-y-6">
          <!-- Contact Info with Confidence -->
          <div class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Contact Information</h3>
            <div class="grid grid-cols-2 gap-3 text-sm">
              <div v-for="field in ['first_name', 'last_name', 'email', 'phone']" :key="field">
                <span class="text-gray-500 capitalize">{{ field.replace('_', ' ') }}</span>
                <div class="flex items-center gap-2">
                  <span class="font-medium text-gray-900">
                    {{ call['caller_' + field] || call[field] || '—' }}
                  </span>
                  <span
                    v-if="call.confidence_scores?.[field] != null"
                    class="text-xs"
                    :class="confidenceColor(call.confidence_scores[field])"
                    :title="'Confidence: ' + (call.confidence_scores[field] * 100).toFixed(0) + '%'"
                  >
                    {{ (call.confidence_scores[field] * 100).toFixed(0) }}%
                  </span>
                  <span
                    v-if="call.extraction_accuracy?.[field] != null"
                    class="text-xs font-bold"
                    :class="accuracyColor(call.extraction_accuracy[field])"
                    :title="call.extraction_accuracy[field] ? 'Matches ground truth' : 'Does not match ground truth'"
                  >
                    {{ accuracyIcon(call.extraction_accuracy[field]) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Transcript -->
          <div v-if="call.transcript" class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Transcript</h3>
            <p class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{{ call.transcript.text }}</p>
            <p class="text-xs text-gray-400 mt-2">
              Model: {{ call.transcript.whisper_model }} | Processing: {{ call.transcript.processing_time_seconds?.toFixed(1) }}s
            </p>
          </div>

          <!-- Key Facts -->
          <div v-if="call.key_facts?.length" class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Key Facts</h3>
            <ul class="list-disc list-inside text-sm text-gray-700 space-y-1">
              <li v-for="fact in call.key_facts" :key="fact">{{ fact }}</li>
            </ul>
          </div>
        </div>

        <!-- Right: Scores + Intelligence -->
        <div class="space-y-6">
          <!-- Lead Score -->
          <div class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Lead Score</h3>
            <div class="text-center mb-3">
              <span class="text-4xl font-bold" :class="{
                'text-green-600': call.lead_score >= 80,
                'text-blue-600': call.lead_score >= 60 && call.lead_score < 80,
                'text-yellow-600': call.lead_score >= 40 && call.lead_score < 60,
                'text-red-600': call.lead_score < 40,
              }">{{ call.lead_score ?? '—' }}</span>
              <span class="text-gray-400 text-lg">/100</span>
            </div>
            <p v-if="call.lead_score_reasoning" class="text-sm text-gray-600">{{ call.lead_score_reasoning }}</p>
          </div>

          <!-- Case Info -->
          <div class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Case Details</h3>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-500">Case Type</span>
                <span class="font-medium">{{ call.case_type_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Urgency</span>
                <span class="font-medium">{{ call.urgency }}/5</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Playbook</span>
                <span class="font-medium">{{ call.playbook_completeness != null ? (call.playbook_completeness * 100).toFixed(0) + '%' : '—' }}</span>
              </div>
            </div>
          </div>

          <!-- Playbook Coverage -->
          <div v-if="call.playbook_answered?.length || call.playbook_unanswered?.length" class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Playbook Coverage</h3>
            <div class="mb-2">
              <div class="w-full bg-gray-100 rounded-full h-2">
                <div class="bg-blue-500 h-2 rounded-full" :style="{ width: (call.playbook_completeness * 100) + '%' }"></div>
              </div>
              <p class="text-xs text-gray-500 mt-1">{{ (call.playbook_completeness * 100).toFixed(0) }}% complete</p>
            </div>
            <ul v-if="call.playbook_answered?.length" class="space-y-1 mb-2">
              <li v-for="q in call.playbook_answered" :key="q" class="text-sm text-green-600 flex items-start gap-1">
                <span class="mt-0.5 flex-shrink-0">&#10003;</span>
                <span>{{ q }}</span>
              </li>
            </ul>
            <ul v-if="call.playbook_unanswered?.length" class="space-y-1">
              <li v-for="q in call.playbook_unanswered" :key="q" class="text-sm text-red-500 flex items-start gap-1">
                <span class="mt-0.5 flex-shrink-0">&#10007;</span>
                <span>{{ q }}</span>
              </li>
            </ul>
          </div>

          <!-- Resolution Gaps -->
          <div v-if="call.resolution_gaps?.length" class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Resolution Gaps</h3>
            <ul class="space-y-1">
              <li v-for="gap in call.resolution_gaps" :key="gap" class="text-sm text-red-600 flex items-start gap-1">
                <span class="mt-0.5">!</span>
                <span>{{ gap }}</span>
              </li>
            </ul>
          </div>

          <!-- Recommended Actions -->
          <div v-if="call.recommended_actions?.length" class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Recommended Actions</h3>
            <ul class="space-y-1">
              <li v-for="action in call.recommended_actions" :key="action" class="text-sm text-gray-700 flex items-start gap-1">
                <span class="mt-0.5 text-blue-500 flex-shrink-0">&#8594;</span>
                <span>{{ action }}</span>
              </li>
            </ul>
          </div>

          <!-- Summary -->
          <div class="bg-white rounded-lg border p-4">
            <h3 class="font-semibold text-gray-900 mb-3">Summary</h3>
            <p class="text-sm text-gray-700">{{ call.summary || 'No summary available' }}</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
