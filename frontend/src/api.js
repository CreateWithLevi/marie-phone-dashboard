import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export default {
  getCalls(params = {}) {
    return api.get('/calls/', { params })
  },
  getCall(id) {
    return api.get(`/calls/${id}/`)
  },
  getDashboardStats() {
    return api.get('/dashboard/stats/')
  },
  getPlaybooks() {
    return api.get('/playbooks/')
  },
  addPlaybookQuestion(playbookId, text) {
    return api.post(`/playbooks/${playbookId}/add_question/`, { text })
  },
  removePlaybookQuestion(playbookId, questionId) {
    return api.delete(`/playbooks/${playbookId}/remove_question/${questionId}/`)
  },
  getEvaluation() {
    return api.get('/evaluation/')
  },
}
