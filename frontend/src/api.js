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
  getEvaluation() {
    return api.get('/evaluation/')
  },
}
