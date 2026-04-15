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
  if (score >= 0.8) return 'text-[#0bdf50]'
  if (score >= 0.6) return 'text-[#fe4c02]'
  return 'text-[#c41c1c]'
}

function accuracyColor(correct) {
  return correct ? 'text-[#0bdf50]' : 'text-[#c41c1c]'
}

function scoreColor(s) {
  if (s >= 80) return 'text-[#0bdf50]'
  if (s >= 60) return 'text-[#65b5ff]'
  if (s >= 40) return 'text-[#fe4c02]'
  return 'text-[#c41c1c]'
}

function verdictClass(v) {
  if (v === 'accept') return 'bg-[#0bdf50]/10 text-[#0a8a36]'
  if (v === 'reject') return 'bg-[#c41c1c]/10 text-[#c41c1c]'
  return 'bg-[#fe4c02]/10 text-[#fe4c02]'
}
</script>

<template>
  <div>
    <button @click="router.push({ name: 'calls' })" class="text-sm text-black-60 hover:text-off-black mb-5 inline-flex items-center gap-1 transition-colors">
      <span>&larr;</span> Back to Calls
    </button>

    <div v-if="loading" class="text-muted text-sm">Loading...</div>

    <template v-else-if="call">
      <!-- Header -->
      <div class="flex items-start justify-between mb-6">
        <div>
          <h2 class="text-2xl font-medium text-off-black tracking-[-0.96px]">
            {{ call.caller_first_name }} {{ call.caller_last_name }}
          </h2>
          <p class="text-xs text-muted font-mono mt-1">{{ call.call_id }}</p>
        </div>
        <div class="flex gap-2">
          <span v-if="call.reflection_applied" class="px-3 py-1 rounded text-xs font-medium bg-[#65b5ff]/10 text-[#2167a8]">
            Reflected
          </span>
          <span v-if="call.needs_human_review" class="px-3 py-1 rounded text-xs font-medium bg-[#ff5600]/10 text-[#ff5600]">
            Needs Review
          </span>
          <span class="px-3 py-1 rounded text-xs font-medium bg-cream text-off-black border border-oat capitalize">
            {{ call.resolution_status?.replace(/_/g, ' ') }}
          </span>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <!-- Left: Contact + Analysis -->
        <div class="col-span-2 space-y-5">
          <!-- Contact Info with Confidence -->
          <div class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Contact Information</h3>
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div v-for="field in ['first_name', 'last_name', 'email', 'phone']" :key="field">
                <span class="text-[11px] text-muted uppercase tracking-widest">{{ field.replace('_', ' ') }}</span>
                <div class="flex items-center gap-2 mt-0.5">
                  <span class="font-medium text-off-black">
                    {{ call['caller_' + field] || call[field] || '—' }}
                  </span>
                  <span
                    v-if="call.confidence_scores?.[field] != null"
                    class="text-[11px] font-medium"
                    :class="confidenceColor(call.confidence_scores[field])"
                  >
                    {{ (call.confidence_scores[field] * 100).toFixed(0) }}%
                  </span>
                  <span
                    v-if="call.extraction_accuracy?.[field] != null"
                    class="text-[11px] font-bold"
                    :class="accuracyColor(call.extraction_accuracy[field])"
                  >
                    {{ call.extraction_accuracy[field] ? '✓' : '✗' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Transcript -->
          <div v-if="call.transcript" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Transcript</h3>
            <p class="text-sm text-black-60 whitespace-pre-wrap leading-relaxed">{{ call.transcript.text }}</p>
            <p class="text-[11px] text-muted mt-3 uppercase tracking-widest">
              {{ call.transcript.whisper_model }} model &middot; {{ call.transcript.processing_time_seconds?.toFixed(1) }}s
            </p>
          </div>

          <!-- Key Facts -->
          <div v-if="call.key_facts?.length" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Key Facts</h3>
            <ul class="space-y-1.5">
              <li v-for="fact in call.key_facts" :key="fact" class="text-sm text-black-60 flex items-start gap-2">
                <span class="text-muted mt-0.5 flex-shrink-0">&bull;</span>
                <span>{{ fact }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Right: Scores + Intelligence -->
        <div class="space-y-5">
          <!-- Lead Score -->
          <div class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Lead Score</h3>
            <div class="text-center mb-3">
              <span class="text-4xl font-medium tracking-[-1.6px]" :class="scoreColor(call.lead_score)">
                {{ call.lead_score ?? '—' }}
              </span>
              <span class="text-muted text-lg">/100</span>
            </div>
            <p v-if="call.lead_score_reasoning" class="text-sm text-black-60 leading-relaxed">{{ call.lead_score_reasoning }}</p>
          </div>

          <!-- Case Info -->
          <div class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Case Details</h3>
            <div class="space-y-2.5 text-sm">
              <div class="flex justify-between">
                <span class="text-muted">Case Type</span>
                <span class="font-medium text-off-black">{{ call.case_type_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">Urgency</span>
                <span class="font-medium text-off-black">{{ call.urgency }}/5</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted">Playbook</span>
                <span class="font-medium text-off-black">{{ call.playbook_completeness != null ? (call.playbook_completeness * 100).toFixed(0) + '%' : '—' }}</span>
              </div>
            </div>
          </div>

          <!-- Playbook Coverage -->
          <div v-if="call.playbook_answered?.length || call.playbook_unanswered?.length" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Playbook Coverage</h3>
            <div class="mb-3">
              <div class="w-full bg-cream rounded-full h-1.5">
                <div class="bg-off-black h-1.5 rounded-full transition-all" :style="{ width: (call.playbook_completeness * 100) + '%' }"></div>
              </div>
              <p class="text-[11px] text-muted mt-1 uppercase tracking-widest">{{ (call.playbook_completeness * 100).toFixed(0) }}% complete</p>
            </div>
            <ul v-if="call.playbook_answered?.length" class="space-y-1.5 mb-2">
              <li v-for="q in call.playbook_answered" :key="q" class="text-sm text-[#0bdf50] flex items-start gap-1.5">
                <span class="mt-0.5 flex-shrink-0">&#10003;</span>
                <span class="text-black-60">{{ q }}</span>
              </li>
            </ul>
            <ul v-if="call.playbook_unanswered?.length" class="space-y-1.5">
              <li v-for="q in call.playbook_unanswered" :key="q" class="text-sm flex items-start gap-1.5">
                <span class="mt-0.5 flex-shrink-0 text-[#c41c1c]">&#10007;</span>
                <span class="text-muted">{{ q }}</span>
              </li>
            </ul>
          </div>

          <!-- Resolution Gaps -->
          <div v-if="call.resolution_gaps?.length" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Resolution Gaps</h3>
            <ul class="space-y-1.5">
              <li v-for="gap in call.resolution_gaps" :key="gap" class="text-sm flex items-start gap-1.5">
                <span class="mt-0.5 text-[#ff5600] flex-shrink-0">!</span>
                <span class="text-black-60">{{ gap }}</span>
              </li>
            </ul>
          </div>

          <!-- Recommended Actions -->
          <div v-if="call.recommended_actions?.length" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Recommended Actions</h3>
            <ul class="space-y-1.5">
              <li v-for="a in call.recommended_actions" :key="a" class="text-sm flex items-start gap-1.5">
                <span class="mt-0.5 text-[#65b5ff] flex-shrink-0">&rarr;</span>
                <span class="text-black-60">{{ a }}</span>
              </li>
            </ul>
          </div>

          <!-- Quality Audit (LLM-as-Judge) -->
          <div v-if="call.quality_audit?.verdict" class="bg-white rounded-lg border border-oat p-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-medium text-off-black tracking-[-0.48px]">Quality Audit</h3>
              <span class="px-2 py-0.5 rounded text-[11px] font-medium capitalize" :class="verdictClass(call.quality_audit.verdict)">
                {{ call.quality_audit.verdict }}
              </span>
            </div>
            <div class="text-sm text-black-60 mb-3">
              Score <span class="font-medium text-off-black">{{ call.quality_audit.quality_score }}/5</span>
            </div>
            <ul v-if="call.quality_audit.issues?.length" class="space-y-1.5 mb-2">
              <li v-for="issue in call.quality_audit.issues" :key="issue" class="text-sm flex items-start gap-1.5">
                <span class="mt-0.5 text-[#fe4c02] flex-shrink-0">!</span>
                <span class="text-black-60">{{ issue }}</span>
              </li>
            </ul>
            <div v-if="call.quality_audit.hallucinated_fields?.length" class="text-[11px] text-muted uppercase tracking-widest mt-2">
              Hallucinated: <span class="text-[#c41c1c]">{{ call.quality_audit.hallucinated_fields.join(', ') }}</span>
            </div>
          </div>

          <!-- Tool Corrections -->
          <div v-if="call.tool_corrections?.length" class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Tool Corrections</h3>
            <ul class="space-y-1.5">
              <li v-for="c in call.tool_corrections" :key="c" class="text-sm flex items-start gap-1.5">
                <span class="mt-0.5 text-[#65b5ff] flex-shrink-0">&#9873;</span>
                <span class="text-black-60">{{ c }}</span>
              </li>
            </ul>
          </div>

          <!-- Summary -->
          <div class="bg-white rounded-lg border border-oat p-5">
            <h3 class="text-sm font-medium text-off-black mb-4 tracking-[-0.48px]">Summary</h3>
            <p class="text-sm text-black-60 leading-relaxed">{{ call.summary || 'No summary available' }}</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
