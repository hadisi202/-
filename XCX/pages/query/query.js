// pages/query/query.js
const api = require('../../utils/api.js')

Page({
  data: {
    code: '',
    loading: false,
    result: null,
    error: ''
  },

  onLoad(options) {
    const code = options && options.code ? decodeURIComponent(options.code) : ''
    if (code) {
      this.setData({ code })
      this.doSearch()
    }
  },

  onInput(e) {
    this.setData({ code: e.detail.value })
  },

  scanSearch() {
    wx.scanCode({
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        const content = res.result || res.scanCode || ''
        this.setData({ code: content })
        this.doSearch()
      },
      fail: () => {
        wx.showToast({ title: '扫码失败', icon: 'none' })
      }
    })
  },

  async doSearch() {
    const code = (this.data.code || '').trim()
    if (!code) {
      wx.showToast({ title: '请输入编码或扫码', icon: 'none' })
      return
    }
    this.setData({ loading: true, error: '', result: null })
    try {
      const data = await api.searchByCode(code)
      this.setData({ result: data })
    } catch (e) {
      const msg = (e && e.errMsg) || '查询失败，请检查网络或API配置'
      this.setData({ error: msg })
    } finally {
      this.setData({ loading: false })
    }
  }
})