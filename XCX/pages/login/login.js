// pages/login/login.js
Page({
  data: {
    username: '',
    password: '',
    showPassword: false,
    loginLoading: false,
    canLogin: false,
    stars: [], // 星空背景数据
    
    // 注册相关数据
    showRegisterModal: false,
    registerData: {
      username: '',
      password: '',
      confirmPassword: '',
      email: '',
      captcha: '',
      generatedCaptcha: ''
    },
    registerLoading: false,
    usernameCheckStatus: '', // 'checking', 'available', 'unavailable', ''
    usernameCheckMessage: '',
    
    // 忘记密码相关数据
    showForgotModal: false,
    forgotData: {
      username: '',
      email: ''
    },
    forgotLoading: false
  },

  onLoad(options) {
    // 检查是否已登录
    this.checkLoginStatus()
    
    // 生成星空背景
    this.generateStars()
    
    // 清理游客数据定时器
    this.startGuestDataCleanup()
  },

  onShow() {
    // 重置表单
    this.setData({
      username: '',
      password: '',
      showPassword: false,
      loginLoading: false,
      canLogin: false
    })
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
        this.clearGuestData()
        return
      }
      
      // 正常用户：7天内免登录
      if (!isGuest && timeDiff < 7 * 24 * 60 * 60 * 1000) {
        this.navigateToMain()
        return
      }
      
      // 登录过期，清除数据
      if (!isGuest) {
        wx.removeStorageSync('userInfo')
        wx.removeStorageSync('loginTime')
      }
    }
  },

  // 生成星空背景
  generateStars() {
    const stars = []
    for (let i = 0; i < 100; i++) {
      stars.push({
        left: Math.random() * 100,
        top: Math.random() * 100,
        delay: Math.random() * 3
      })
    }
    this.setData({ stars })
  },

  // 用户名输入
  onUsernameInput(e) {
    const username = e.detail.value
    this.setData({ 
      username,
      canLogin: username.length > 0 && this.data.password.length > 0
    })
  },

  // 密码输入
  onPasswordInput(e) {
    const password = e.detail.value
    this.setData({ 
      password,
      canLogin: this.data.username.length > 0 && password.length > 0
    })
  },

  // 切换密码显示
  togglePassword() {
    this.setData({
      showPassword: !this.data.showPassword
    })
  },

  // 处理登录
  async handleLogin() {
    if (!this.data.canLogin || this.data.loginLoading) return
    
    this.setData({ loginLoading: true })
    
    try {
      // 模拟登录请求
      const result = await this.performLogin(this.data.username, this.data.password)
      
      if (result.success) {
        // 保存用户信息
        wx.setStorageSync('userInfo', result.userInfo)
        wx.setStorageSync('loginTime', Date.now())
        wx.setStorageSync('isGuest', false)
        
        wx.showToast({
          title: '登录成功',
          icon: 'success'
        })
        
        // 跳转到主页
        setTimeout(() => {
          this.navigateToMain()
        }, 1500)
      } else {
        wx.showToast({
          title: result.message || '登录失败',
          icon: 'none'
        })
      }
    } catch (error) {
      console.error('登录错误:', error)
      wx.showToast({
        title: '网络错误，请重试',
        icon: 'none'
      })
    } finally {
      this.setData({ loginLoading: false })
    }
  },

  // 执行登录请求
  performLogin(username, password) {
    return new Promise((resolve) => {
      // 模拟网络请求延迟
      setTimeout(() => {
        // 默认管理员账号
        if (username === 'admin' && password === '123456') {
          resolve({
            success: true,
            userInfo: {
              id: 'user_admin',
              username: username,
              nickname: '管理员',
              avatar: '',
              email: 'admin@example.com',
              phone: '',
              department: '技术部',
              position: '系统管理员'
            }
          })
          return
        }
        
        // 检查注册用户
        const registeredUsers = wx.getStorageSync('registeredUsers') || []
        const user = registeredUsers.find(u => u.username === username && u.password === password)
        
        if (user) {
          resolve({
            success: true,
            userInfo: user
          })
        } else {
          resolve({
            success: false,
            message: '用户名或密码错误'
          })
        }
      }, 1000)
    })
  },

  // 游客登录
  handleGuestLogin() {
    wx.showModal({
      title: '游客模式',
      content: '游客模式下，您的数据将在1小时后自动清除。确定要继续吗？',
      confirmText: '继续',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          // 创建游客用户信息
          const guestInfo = {
            id: 'guest_' + Date.now(),
            username: 'guest',
            nickname: '游客用户',
            avatar: '',
            email: '',
            phone: '',
            department: '游客',
            position: '访客'
          }
          
          // 保存游客信息
          wx.setStorageSync('userInfo', guestInfo)
          wx.setStorageSync('loginTime', Date.now())
          wx.setStorageSync('isGuest', true)
          
          wx.showToast({
            title: '游客登录成功',
            icon: 'success'
          })
          
          // 跳转到主页
          setTimeout(() => {
            this.navigateToMain()
          }, 1500)
        }
      }
    })
  },

  // 跳转到主页
  navigateToMain() {
    wx.switchTab({
      url: '/pages/index/index'
    })
  },

  // 显示注册页面
  showRegister() {
    // 先生成验证码
    const chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    let captcha = ''
    for (let i = 0; i < 4; i++) {
      captcha += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    
    this.setData({
      showRegisterModal: true,
      registerData: {
        username: '',
        password: '',
        confirmPassword: '',
        email: '',
        captcha: '',
        generatedCaptcha: captcha
      },
      usernameCheckStatus: '',
      usernameCheckMessage: ''
    })
  },

  // 显示忘记密码
  showForgotPassword() {
    this.setData({
      showForgotModal: true,
      forgotData: {
        username: '',
        email: ''
      }
    })
  },

  // 生成4位验证码
  generateCaptcha() {
    const chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    let captcha = ''
    for (let i = 0; i < 4; i++) {
      captcha += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    
    // 确保registerData存在后再更新
    const currentRegisterData = this.data.registerData || {
      username: '',
      password: '',
      confirmPassword: '',
      email: '',
      captcha: '',
      generatedCaptcha: ''
    }
    
    this.setData({
      registerData: {
        ...currentRegisterData,
        generatedCaptcha: captcha
      }
    })
  },

  // 关闭注册弹窗
  closeRegisterModal() {
    // 清除用户名检测定时器
    if (this.usernameCheckTimer) {
      clearTimeout(this.usernameCheckTimer)
      this.usernameCheckTimer = null
    }
    
    this.setData({ 
      showRegisterModal: false,
      usernameCheckStatus: '',
      usernameCheckMessage: ''
    })
  },

  // 关闭忘记密码弹窗
  closeForgotModal() {
    this.setData({ showForgotModal: false })
  },

  // 阻止事件冒泡
  stopPropagation() {
    // 空函数，用于阻止事件冒泡
  },

  // 注册表单输入处理
  onRegisterInput(e) {
    const { field } = e.currentTarget.dataset
    const value = e.detail.value
    
    // 更新数据
    const currentRegisterData = this.data.registerData || {}
    const updatedData = {
      ...currentRegisterData,
      [field]: value
    }
    
    this.setData({
      registerData: updatedData
    })
    
    // 如果是用户名字段，实时检测重复
    if (field === 'username' && value.length >= 3) {
      this.checkUsernameAvailability(value)
    }
  },

  // 忘记密码表单输入处理
  onForgotInput(e) {
    const { field } = e.currentTarget.dataset
    const value = e.detail.value
    this.setData({
      [`forgotData.${field}`]: value
    })
  },

  // 检测用户名是否可用
  checkUsernameAvailability(username) {
    // 清除之前的检测定时器
    if (this.usernameCheckTimer) {
      clearTimeout(this.usernameCheckTimer)
    }
    
    // 设置检测状态
    this.setData({
      usernameCheckStatus: 'checking',
      usernameCheckMessage: '检测中...'
    })
    
    // 延迟检测，避免频繁请求
    this.usernameCheckTimer = setTimeout(() => {
      const existingUsers = wx.getStorageSync('registeredUsers') || []
      const userExists = existingUsers.some(user => 
        user.username.toLowerCase() === username.toLowerCase()
      )
      
      if (userExists) {
        this.setData({
          usernameCheckStatus: 'unavailable',
          usernameCheckMessage: '用户名已存在'
        })
      } else {
        this.setData({
          usernameCheckStatus: 'available',
          usernameCheckMessage: '用户名可用'
        })
      }
    }, 500) // 延迟500ms检测
  },

  // 刷新验证码
  refreshCaptcha() {
    const chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    let captcha = ''
    for (let i = 0; i < 4; i++) {
      captcha += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    
    const currentRegisterData = this.data.registerData || {
      username: '',
      password: '',
      confirmPassword: '',
      email: '',
      captcha: '',
      generatedCaptcha: ''
    }
    
    this.setData({
      registerData: {
        ...currentRegisterData,
        generatedCaptcha: captcha
      }
    })
  },

  // 处理注册
  async handleRegister() {
    const { registerData, usernameCheckStatus } = this.data
    
    // 表单验证
    if (!registerData.username || registerData.username.length < 3) {
      wx.showToast({ title: '用户名至少3位字符', icon: 'none' })
      return
    }
    
    // 检查用户名是否可用
    if (usernameCheckStatus === 'unavailable') {
      wx.showToast({ title: '用户名已存在，请更换', icon: 'none' })
      return
    }
    
    // 如果还没检测过用户名，先检测
    if (usernameCheckStatus !== 'available') {
      wx.showToast({ title: '请等待用户名检测完成', icon: 'none' })
      this.checkUsernameAvailability(registerData.username)
      return
    }
    
    if (!registerData.password || registerData.password.length < 6) {
      wx.showToast({ title: '密码至少6位字符', icon: 'none' })
      return
    }
    
    if (registerData.password !== registerData.confirmPassword) {
      wx.showToast({ title: '两次密码输入不一致', icon: 'none' })
      return
    }
    
    if (!this.validateEmail(registerData.email)) {
      wx.showToast({ title: '请输入正确的邮箱地址', icon: 'none' })
      return
    }
    
    if (registerData.captcha.toUpperCase() !== registerData.generatedCaptcha) {
      wx.showToast({ title: '验证码错误', icon: 'none' })
      this.refreshCaptcha()
      return
    }
    
    this.setData({ registerLoading: true })
    
    try {
      // 模拟注册请求
      const result = await this.performRegister(registerData)
      
      if (result.success) {
        wx.showToast({ title: '注册成功', icon: 'success' })
        
        // 自动登录
        wx.setStorageSync('userInfo', result.userInfo)
        wx.setStorageSync('loginTime', Date.now())
        wx.setStorageSync('isGuest', false)
        
        this.setData({ showRegisterModal: false })
        
        setTimeout(() => {
          this.navigateToMain()
        }, 1500)
      } else {
        wx.showToast({ title: result.message || '注册失败', icon: 'none' })
        this.generateCaptcha()
      }
    } catch (error) {
      console.error('注册错误:', error)
      wx.showToast({ title: '网络错误，请重试', icon: 'none' })
      this.generateCaptcha()
    } finally {
      this.setData({ registerLoading: false })
    }
  },

  // 执行注册请求
  performRegister(registerData) {
    return new Promise((resolve) => {
      setTimeout(() => {
        // 检查用户名是否已存在（模拟）
        const existingUsers = wx.getStorageSync('registeredUsers') || []
        const userExists = existingUsers.some(user => user.username === registerData.username)
        
        if (userExists) {
          resolve({ success: false, message: '用户名已存在' })
          return
        }
        
        // 创建新用户
        const newUser = {
          id: 'user_' + Date.now(),
          username: registerData.username,
          password: registerData.password, // 实际项目中应该加密
          nickname: registerData.username,
          avatar: '',
          email: registerData.email,
          phone: '',
          department: '新用户',
          position: '员工',
          registerTime: Date.now()
        }
        
        // 保存到本地存储（模拟数据库）
        existingUsers.push(newUser)
        wx.setStorageSync('registeredUsers', existingUsers)
        
        resolve({
          success: true,
          userInfo: newUser
        })
      }, 1000)
    })
  },

  // 处理忘记密码
  async handleForgotPassword() {
    const { forgotData } = this.data
    
    if (!forgotData.username) {
      wx.showToast({ title: '请输入用户名', icon: 'none' })
      return
    }
    
    if (!this.validateEmail(forgotData.email)) {
      wx.showToast({ title: '请输入正确的邮箱地址', icon: 'none' })
      return
    }
    
    this.setData({ forgotLoading: true })
    
    try {
      const result = await this.performForgotPassword(forgotData)
      
      if (result.success) {
        wx.showModal({
          title: '密码重置',
          content: `新密码已发送到邮箱 ${forgotData.email}，请查收。\n\n临时密码：${result.newPassword}`,
          showCancel: false,
          confirmText: '知道了',
          success: () => {
            this.setData({ showForgotModal: false })
          }
        })
      } else {
        wx.showToast({ title: result.message || '重置失败', icon: 'none' })
      }
    } catch (error) {
      console.error('密码重置错误:', error)
      wx.showToast({ title: '网络错误，请重试', icon: 'none' })
    } finally {
      this.setData({ forgotLoading: false })
    }
  },

  // 执行忘记密码请求
  performForgotPassword(forgotData) {
    return new Promise((resolve) => {
      setTimeout(() => {
        const registeredUsers = wx.getStorageSync('registeredUsers') || []
        const user = registeredUsers.find(u => u.username === forgotData.username && u.email === forgotData.email)
        
        if (!user) {
          resolve({ success: false, message: '用户名或邮箱不匹配' })
          return
        }
        
        // 生成新密码
        const newPassword = this.generateRandomPassword()
        
        // 更新用户密码
        user.password = newPassword
        const userIndex = registeredUsers.findIndex(u => u.id === user.id)
        registeredUsers[userIndex] = user
        wx.setStorageSync('registeredUsers', registeredUsers)
        
        resolve({
          success: true,
          newPassword: newPassword
        })
      }, 1000)
    })
  },

  // 生成随机密码
  generateRandomPassword() {
    const chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    let password = ''
    for (let i = 0; i < 8; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return password
  },

  // 邮箱格式验证
  validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(email)
  },

  // 启动游客数据清理定时器
  startGuestDataCleanup() {
    // 每分钟检查一次游客数据是否需要清理
    setInterval(() => {
      const isGuest = wx.getStorageSync('isGuest')
      const loginTime = wx.getStorageSync('loginTime')
      
      if (isGuest && loginTime) {
        const currentTime = Date.now()
        const timeDiff = currentTime - loginTime
        
        // 1小时后清除游客数据
        if (timeDiff > 60 * 60 * 1000) {
          this.clearGuestData()
        }
      }
    }, 60000) // 每分钟检查一次
  },

  // 清除游客数据
  clearGuestData() {
    wx.removeStorageSync('userInfo')
    wx.removeStorageSync('loginTime')
    wx.removeStorageSync('isGuest')
    
    // 清除其他游客相关数据
    wx.removeStorageSync('guestTodos')
    wx.removeStorageSync('guestDocs')
    wx.removeStorageSync('guestMeetings')
    wx.removeStorageSync('guestContacts')
    
    wx.showToast({
      title: '游客数据已清除',
      icon: 'none'
    })
  },

  onUnload() {
    // 页面卸载时清理定时器
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer)
    }
  }
})