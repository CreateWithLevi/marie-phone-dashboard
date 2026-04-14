<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const playbooks = ref([])
const loading = ref(true)
const expandedId = ref(null)
const newQuestion = ref('')
const adding = ref(false)

onMounted(async () => {
  try {
    const { data } = await api.getPlaybooks()
    playbooks.value = data.results || data
  } finally {
    loading.value = false
  }
})

function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
  newQuestion.value = ''
}

async function addQuestion(playbook) {
  const text = newQuestion.value.trim()
  if (!text) return

  adding.value = true
  try {
    const { data } = await api.addPlaybookQuestion(playbook.id, text)
    playbook.questions.push(data)
    newQuestion.value = ''
  } finally {
    adding.value = false
  }
}

async function removeQuestion(playbook, questionId) {
  try {
    await api.removePlaybookQuestion(playbook.id, questionId)
    playbook.questions = playbook.questions.filter(q => q.id !== questionId)
  } catch (e) {
    console.error('Failed to remove question:', e)
  }
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-gray-900 mb-2">Intake Playbooks</h2>
    <p class="text-sm text-gray-500 mb-6">
      Configure intake requirements per case type. Marie evaluates each call against these questions
      to calculate playbook completeness and identify resolution gaps.
    </p>

    <div v-if="loading" class="text-gray-500">Loading...</div>

    <div v-else class="space-y-3">
      <div
        v-for="pb in playbooks"
        :key="pb.id"
        class="bg-white rounded-lg border overflow-hidden"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50"
          @click="toggle(pb.id)"
        >
          <div>
            <h3 class="font-medium text-gray-900">{{ pb.case_type_name }}</h3>
            <p class="text-xs text-gray-500">{{ pb.questions?.length || 0 }} questions</p>
          </div>
          <span class="text-gray-400 text-lg">{{ expandedId === pb.id ? '−' : '+' }}</span>
        </div>

        <!-- Questions -->
        <div v-if="expandedId === pb.id" class="border-t px-4 py-3">
          <p class="text-sm text-gray-500 mb-3">{{ pb.description }}</p>
          <ol class="space-y-2">
            <li v-for="q in pb.questions" :key="q.id" class="flex items-center justify-between group text-sm">
              <div class="flex items-start gap-2">
                <span class="mt-0.5 w-4 h-4 rounded border flex items-center justify-center text-xs flex-shrink-0"
                  :class="q.is_required ? 'border-blue-400 text-blue-400' : 'border-gray-300 text-gray-300'">
                  {{ q.is_required ? '!' : '?' }}
                </span>
                <span class="text-gray-700">{{ q.text }}</span>
              </div>
              <button
                @click.stop="removeQuestion(pb, q.id)"
                class="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity text-xs px-1"
                title="Remove question"
              >
                x
              </button>
            </li>
          </ol>

          <!-- Add question -->
          <div class="mt-4 pt-3 border-t flex gap-2">
            <input
              v-model="newQuestion"
              type="text"
              placeholder="Add a new intake question..."
              class="flex-1 px-3 py-1.5 border rounded text-sm"
              @keyup.enter="addQuestion(pb)"
            />
            <button
              @click="addQuestion(pb)"
              :disabled="!newQuestion.trim() || adding"
              class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
