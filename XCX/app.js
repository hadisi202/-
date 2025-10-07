// app.js
const api = require('./utils/api.js')
App({
  onLaunch() {
    // 初始化云开发环境
    if (!wx.cloud) {
      console.error('请使用基础库 2.2.3 或以上以使用云能力')
    } else {
      wx.cloud.init({
        env: wx.cloud.DYNAMIC_CURRENT_ENV,
        traceUser: true
      })
    }
    // 展示本地存储能力
    const logs = wx.getStorageSync('logs') || []
    logs.unshift(Date.now())
    wx.setStorageSync('logs', logs)

    // 微信登录
    wx.login({
      success: res => {
        // 发送 res.code 到后台换取 openId, sessionKey, unionId
        console.log('微信登录成功', res.code)
      },
      fail: err => {
        console.error('微信登录失败', err)
      }
    })

    // 初始化数据
    this.initData()
    
    // 预加载页面
    this.preloadPages()
    
    // 取消登录拦截
    this.checkLoginStatus()
    // 方案一（云做中心）：不再自动探测本地API，避免不必要的网络尝试
    // 如需临时覆盖，可在设置页手动设定 API_BASE_OVERRIDE
    // try {
    //   api.detectApiBase().then((base) => {
    //     if (base) {
    //       console.log('检测到可用本地API:', base)
    //       wx.setStorageSync('API_BASE_DETECTED', base)
    //     }
    //   }).catch((err) => {
    //     console.warn('本地API自动检测未找到可用地址', (err && err.message) || '')
    //   })
    // } catch (e) {
    //   console.warn('自动检测API时出现异常', e && e.message)
    // }
  },

  onShow() {
    // 应用切换到前台
  },

  onHide() {
    // 应用切换到后台
  },

  onError(error) {
    // 应用发生脚本错误或 API 调用报错时触发
    console.error('应用错误:', error)
    
    // 记录错误信息
    const errorLogs = wx.getStorageSync('errorLogs') || []
    errorLogs.unshift({
      error: error.toString(),
      timestamp: new Date().toISOString(),
      stack: error.stack || 'No stack trace'
    })
    
    // 只保留最近50条错误日志
    if (errorLogs.length > 50) {
      errorLogs.splice(50)
    }
    
    wx.setStorageSync('errorLogs', errorLogs)
    
    wx.showToast({
      title: '应用出现错误',
      icon: 'none'
    })
  },
  
  // 预加载页面
  preloadPages() {
    try {
      // 预加载关键页面，提高切换速度
      const pages = [
        'pages/index/index'
      ]
      
      pages.forEach(page => {
        wx.preloadPage({
          url: `/${page}`,
          success: () => {
          // 页面预加载成功
        },
        fail: (err) => {
          // 页面预加载失败
        }
        })
      })
    } catch (error) {
        // 预加载页面失败
      }
  },

  // 初始化应用数据
  initData() {
    // 初始化用户设置
    if (!wx.getStorageSync('userSettings')) {
      wx.setStorageSync('userSettings', {
        theme: 'light',
        notifications: true,
        autoSync: true,
        language: 'zh-CN'
      })
    }
  },

  // 检查登录状态
  checkLoginStatus() {
    const userInfo = wx.getStorageSync('userInfo')
    const loginTime = wx.getStorageSync('loginTime')
    const isGuest = wx.getStorageSync('isGuest')
    
    if (userInfo && loginTime) {
      const currentTime = Date.now()
      const timeDiff = currentTime - loginTime
      
      // 游客模式：1小时后自动清除
      if (isGuest && timeDiff > 60 * 60 * 1000) {
        this.clearUserData()
        this.globalData.userInfo = null
        return
      }
      
      // 正常用户：7天内免登录
      if (!isGuest && timeDiff < 7 * 24 * 60 * 60 * 1000) {
        this.globalData.userInfo = userInfo
        return
      }
      
      // 登录过期，清除数据
      if (!isGuest) {
        this.clearUserData()
      }
    }
    
    this.globalData.userInfo = null
  },
  
  // 清除用户数据
  clearUserData() {
    wx.removeStorageSync('userInfo')
    wx.removeStorageSync('loginTime')
    wx.removeStorageSync('isGuest')
    
    // 清除游客相关数据
    const isGuest = wx.getStorageSync('isGuest')
    if (isGuest) {
      // 清除游客数据（如果有的话）
    }
  },
  
  // 检查页面访问权限
  checkPageAccess(pagePath) {
    // 取消登录拦截，所有页面均可访问
    return true
  },
  
  // 获取用户信息
  getUserInfo() {
    return this.globalData.userInfo || wx.getStorageSync('userInfo')
  },
  
  // 设置用户信息
  setUserInfo(userInfo) {
    this.globalData.userInfo = userInfo
    wx.setStorageSync('userInfo', userInfo)
    wx.setStorageSync('loginTime', Date.now())
  },
  
  // 用户登出
  logout() {
    this.clearUserData()
    this.globalData.userInfo = null
    // 取消登录页，登出后返回首页
    wx.reLaunch({ url: '/pages/index/index' })
  },

  // 全局数据
  globalData: {
    userInfo: null,
    version: '1.0.0',
    apiUrl: 'https://api.example.com',
    isDebug: false
  },

  // 工具方法
  utils: {
    // 格式化日期
    formatDate(date, format = 'YYYY-MM-DD') {
      if (!date) return ''
      const d = new Date(date)
      const year = d.getFullYear()
      const month = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      const hour = String(d.getHours()).padStart(2, '0')
      const minute = String(d.getMinutes()).padStart(2, '0')
      const second = String(d.getSeconds()).padStart(2, '0')

      return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hour)
        .replace('mm', minute)
        .replace('ss', second)
    },

    // 格式化时间为相对时间
    formatRelativeTime(date) {
      if (!date) return ''
      const now = new Date()
      const target = new Date(date)
      const diff = now - target
      const seconds = Math.floor(diff / 1000)
      const minutes = Math.floor(seconds / 60)
      const hours = Math.floor(minutes / 60)
      const days = Math.floor(hours / 24)

      if (days > 0) {
        return `${days}天前`
      } else if (hours > 0) {
        return `${hours}小时前`
      } else if (minutes > 0) {
        return `${minutes}分钟前`
      } else {
        return '刚刚'
      }
    },

    // 生成唯一ID
    generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2)
    },

    // 深拷贝
    deepClone(obj) {
      if (obj === null || typeof obj !== 'object') return obj
      if (obj instanceof Date) return new Date(obj)
      if (obj instanceof Array) return obj.map(item => this.deepClone(item))
      if (typeof obj === 'object') {
        const clonedObj = {}
        for (const key in obj) {
          if (obj.hasOwnProperty(key)) {
            clonedObj[key] = this.deepClone(obj[key])
          }
        }
        return clonedObj
      }
    },

    // 防抖函数
    debounce(func, wait) {
      let timeout
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout)
          func(...args)
        }
        clearTimeout(timeout)
        timeout = setTimeout(later, wait)
      }
    },

    // 节流函数
    throttle(func, limit) {
      let inThrottle
      return function() {
        const args = arguments
        const context = this
        if (!inThrottle) {
          func.apply(context, args)
          inThrottle = true
          setTimeout(() => inThrottle = false, limit)
        }
      }
    },

    // 显示加载提示
    showLoading(title = '加载中...') {
      wx.showLoading({
        title,
        mask: true
      })
    },

    // 隐藏加载提示
    hideLoading() {
      wx.hideLoading()
    },

    // 显示成功提示
    showSuccess(title = '操作成功') {
      wx.showToast({
        title,
        icon: 'success',
        duration: 2000
      })
    },

    // 显示错误提示
    showError(title = '操作失败') {
      wx.showToast({
        title,
        icon: 'none',
        duration: 2000
      })
    },

    // 确认对话框
    showConfirm(options = {}) {
      return new Promise((resolve, reject) => {
        wx.showModal({
          title: options.title || '提示',
          content: options.content || '确定要执行此操作吗？',
          confirmText: options.confirmText || '确定',
          cancelText: options.cancelText || '取消',
          confirmColor: options.confirmColor || '#007aff',
          success: (res) => {
            if (res.confirm) {
              resolve(true)
            } else {
              resolve(false)
            }
          },
          fail: reject
        })
      })
    },

    // 存储数据
    setStorage(key, data) {
      try {
        wx.setStorageSync(key, data)
        return true
      } catch (error) {
        console.error('存储数据失败:', error)
        return false
      }
    },

    // 获取存储数据
    getStorage(key, defaultValue = null) {
      try {
        const data = wx.getStorageSync(key)
        return data || defaultValue
      } catch (error) {
        console.error('获取数据失败:', error)
        return defaultValue
      }
    },

    // 删除存储数据
    removeStorage(key) {
      try {
        wx.removeStorageSync(key)
        return true
      } catch (error) {
        console.error('删除数据失败:', error)
        return false
      }
    },

    // 清空存储
    clearStorage() {
      try {
        wx.clearStorageSync()
        return true
      } catch (error) {
        console.error('清空存储失败:', error)
        return false
      }
    },

    // 网络请求
    request(options = {}) {
      return new Promise((resolve, reject) => {
        wx.request({
          url: options.url,
          method: options.method || 'GET',
          data: options.data || {},
          header: {
            'Content-Type': 'application/json',
            ...options.header
          },
          success: (res) => {
            if (res.statusCode === 200) {
              resolve(res.data)
            } else {
              reject(new Error(`请求失败: ${res.statusCode}`))
            }
          },
          fail: reject
        })
      })
    }
  }
})