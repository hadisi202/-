// utils/api.js
const CONFIG = require('../config.js')

function request(path, params = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${CONFIG.API_BASE}${path}`,
      method: 'GET',
      data: params,
      timeout: CONFIG.TIMEOUT || 8000,
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else {
          reject(new Error(`HTTP ${res.statusCode}`))
        }
      },
      fail: (err) => reject(err)
    })
  })
}

function searchByCode(code) {
  return request('/api/search', { code })
}

module.exports = {
  searchByCode
}