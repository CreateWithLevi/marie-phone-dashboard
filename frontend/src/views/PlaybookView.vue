<script setup>
import { ref, onMounted, nextTick } from 'vue'
import api from '../api'

const playbooks = ref([])
const loading = ref(true)
const expandedId = ref(null)
const newQuestion = ref('')
const adding = ref(false)
const editingId = ref(null)
const editText = ref('')
const editInput = ref(null)

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
  cancelEdit()
}

async function startEdit(question) {
  editingId.value = question.id
  editText.value = question.text
  await nextTick()
  editInput.value?.focus()
  editInput.value?.select()
}

function cancelEdit() {
  editingId.value = null
  editText.value = ''
}

async function saveEdit(playbook, question) {
  const text = editText.value.trim()
  if (!text || text === question.text) {
    cancelEdit()
    return
  }
  try {
    const { data } = await api.updatePlaybookQuestion(playbook.id, question.id, { text })
    question.text = data.text
  } catch (e) {
    console.error('Failed to update question:', e)
  }
  cancelEdit()
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
    <h2 class="text-2xl font-medium text-off-black mb-2 tracking-[-0.96px]">Intake Playbooks</h2>
    <p class="text-sm text-muted mb-6">
      Configure intake requirements per case type. Each call is evaluated against these questions
      to calculate playbook completeness and identify resolution gaps.
    </p>

    <div v-if="loading" class="text-muted text-sm">Loading...</div>

    <div v-else class="space-y-3">
      <div
        v-for="pb in playbooks"
        :key="pb.id"
        class="bg-white rounded-lg border border-oat overflow-hidden"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-cream transition-colors"
          @click="toggle(pb.id)"
        >
          <div>
            <h3 class="font-medium text-off-black tracking-[-0.48px]">{{ pb.case_type_name }}</h3>
            <p class="text-[11px] text-muted uppercase tracking-widest mt-0.5">{{ pb.questions?.length || 0 }} questions</p>
          </div>
          <span class="text-muted text-lg transition-transform" :class="{ 'rotate-45': expandedId === pb.id }">+</span>
        </div>

        <!-- Questions -->
        <div v-if="expandedId === pb.id" class="border-t border-oat px-5 py-4">
          <p class="text-sm text-muted mb-4">{{ pb.description }}</p>
          <ol class="space-y-2.5">
            <li v-for="q in pb.questions" :key="q.id" class="flex items-center justify-between group text-sm">
              <!-- Editing state -->
              <template v-if="editingId === q.id">
                <div class="flex items-start gap-2 flex-1 mr-2">
                  <span class="mt-2 w-4 h-4 rounded border flex items-center justify-center text-[10px] flex-shrink-0"
                    :class="q.is_required ? 'border-[#ff5600] text-[#ff5600]' : 'border-oat text-muted'">
                    {{ q.is_required ? '!' : '?' }}
                  </span>
                  <input
                    ref="editInput"
                    v-model="editText"
                    type="text"
                    class="flex-1 px-2 py-1 border border-off-black rounded bg-white text-sm text-off-black focus:outline-none"
                    @keyup.enter="saveEdit(pb, q)"
                    @keyup.escape="cancelEdit"
                  />
                </div>
                <div class="flex gap-1.5">
                  <button
                    @click.stop="saveEdit(pb, q)"
                    class="text-xs px-2 py-0.5 rounded bg-off-black text-white hover:scale-105 active:scale-95 transition-transform"
                  >save</button>
                  <button
                    @click.stop="cancelEdit"
                    class="text-xs px-2 py-0.5 rounded text-muted hover:text-off-black transition-colors"
                  >cancel</button>
                </div>
              </template>

              <!-- Display state -->
              <template v-else>
                <div
                  class="flex items-start gap-2 flex-1 cursor-pointer rounded px-1 py-0.5 -mx-1 hover:bg-cream transition-colors"
                  @click.stop="startEdit(q)"
                  title="Click to edit"
                >
                  <span class="mt-0.5 w-4 h-4 rounded border flex items-center justify-center text-[10px] flex-shrink-0"
                    :class="q.is_required ? 'border-[#ff5600] text-[#ff5600]' : 'border-oat text-muted'">
                    {{ q.is_required ? '!' : '?' }}
                  </span>
                  <span class="text-black-60 group-hover:text-off-black transition-colors">{{ q.text }}</span>
                </div>
                <button
                  @click.stop="removeQuestion(pb, q.id)"
                  class="text-warm-sand hover:text-[#c41c1c] opacity-0 group-hover:opacity-100 transition-all text-xs px-2 py-0.5 rounded hover:bg-[#c41c1c]/5"
                >
                  remove
                </button>
              </template>
            </li>
          </ol>

          <!-- Add question -->
          <div class="mt-5 pt-4 border-t border-oat flex gap-2">
            <input
              v-model="newQuestion"
              type="text"
              placeholder="Add a new intake question..."
              class="flex-1 px-3 py-2 border border-oat rounded bg-white text-sm text-off-black placeholder:text-warm-sand focus:outline-none focus:border-off-black"
              @keyup.enter="addQuestion(pb)"
            />
            <button
              @click="addQuestion(pb)"
              :disabled="!newQuestion.trim() || adding"
              class="px-4 py-2 bg-off-black text-white text-sm rounded hover:scale-105 active:scale-95 disabled:opacity-30 transition-transform"
            >
              Add
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
