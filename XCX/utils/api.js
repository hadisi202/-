// utils/api.js
const CONFIG = require('../config.js')
const cloudUtil = require('./cloud.js')

// 云数据库查询函数
function searchByCodeInCloud(code) {
  return new Promise((resolve, reject) => {
    const normalized = (code == null ? '' : String(code)).trim().toUpperCase()
    console.log('云数据库查询:', normalized)
    
    // 初始化云开发
    if (!wx.cloud) {
      reject(new Error('请使用 2.2.3 或以上的基础库以使用云能力'))
      return
    }
    
    // 查询板件
    wx.cloud.callFunction({
      name: 'searchComponents',
      data: { code: normalized }
    }).then(res => {
      if (res.result && res.result.data && res.result.data.length > 0) {
        resolve({
          type: 'component',
          data: res.result.data[0]
        })
        return
      }
      
      // 查询包裹
      return wx.cloud.callFunction({
        name: 'searchPackages',
        data: { code: normalized }
      })
    }).then(res => {
      if (res && res.result && res.result.data && res.result.data.length > 0) {
        resolve({
          type: 'package',
          data: res.result.data[0]
        })
        return
      }
      
      // 查询托盘
      return wx.cloud.callFunction({
        name: 'searchPallets',
        data: { code: normalized }
      })
    }).then(res => {
      if (res && res.result && res.result.data && res.result.data.length > 0) {
        resolve({
          type: 'pallet',
          data: res.result.data[0]
        })
        return
      }
      
      // 没有找到数据
      resolve({
        type: 'not_found',
        data: null
      })
    }).catch(err => {
      console.error('云数据库查询失败:', err)
      reject(new Error(`云数据库查询失败: ${err.errMsg || err.message}`))
    })
  })
}

// API请求函数
function request(path, params = {}) {
  return new Promise((resolve, reject) => {
    const base = getRuntimeApiBase()
    const url = `${base}${path}`
    console.log('API请求:', url, params)
    wx.request({
      url: url,
      method: 'GET',
      data: params,
      timeout: CONFIG.TIMEOUT || 8000,
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${res.data?.error || '请求失败'}`))
        }
      },
      fail: (err) => {
        reject(new Error(`网络错误: ${err && err.errMsg ? err.errMsg : '无法连接到服务器'}`))
      }
    })
  })
}

async function searchByCode(code, options = {}) {
  const normalized = (code == null ? '' : String(code)).trim().toUpperCase()
  if (CONFIG.USE_CLOUD_DATABASE) {
    // 仅走云数据库查询，不再回退到本地API
    return cloudUtil.searchByCodeCloud(normalized, options)
  }
  // 未开启云数据库，走本地API，并传递分页参数（若后端支持）
  return request('/api/search', { code: normalized, ...options })
}

// 运行时API地址管理
function getStoredApiBase() {
  return wx.getStorageSync('API_BASE_OVERRIDE') || wx.getStorageSync('API_BASE_DETECTED') || ''
}
function setStoredApiBase(base) {
  if (typeof base === 'string' && base) {
    wx.setStorageSync('API_BASE_OVERRIDE', base)
  }
}
function getCandidateBases() {
  const bases = []
  const override = wx.getStorageSync('API_BASE_OVERRIDE')
  const detected = wx.getStorageSync('API_BASE_DETECTED')
  if (override) bases.push(override)
  if (detected) bases.push(detected)
  if (CONFIG.API_BASE) bases.push(CONFIG.API_BASE)
  // 常见备选，尽量少量尝试，避免过多请求
  bases.push('http://127.0.0.1:5000')
  bases.push('http://localhost:5000')
  return Array.from(new Set(bases))
}
function getRuntimeApiBase() {
  return getStoredApiBase() || CONFIG.API_BASE
}
function pingApi(base) {
  return new Promise((resolve) => {
    if (!base) return resolve(false)
    wx.request({
      url: `${base}/`,
      method: 'GET',
      timeout: CONFIG.TIMEOUT || 8000,
      success: (res) => {
        const ok = res.statusCode === 200
        resolve(ok)
      },
      fail: () => resolve(false)
    })
  })
}
async function detectApiBase() {
  const candidates = getCandidateBases()
  for (const base of candidates) {
    // 逐个尝试，命中即返回
    /* eslint-disable no-await-in-loop */
    const ok = await pingApi(base)
    if (ok) {
      wx.setStorageSync('API_BASE_DETECTED', base)
      return base
    }
  }
  throw new Error('未检测到可用的本地API地址')
}

module.exports = {
  searchByCode,
  detectApiBase,
  getRuntimeApiBase,
  getCandidateBases,
  getStoredApiBase,
  setStoredApiBase,
  pingApi
}