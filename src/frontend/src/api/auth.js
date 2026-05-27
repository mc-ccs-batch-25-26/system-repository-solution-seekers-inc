import api from './axios'

export const authApi = {
  login: async (username, password) => {
    const { data } = await api.post('/auth/login/', { username, password })
    return data
  },
  logout: async () => {
    await api.post('/auth/logout/')
  },
  me: async () => {
    const { data } = await api.get('/users/me/')
    return data
  },
}
