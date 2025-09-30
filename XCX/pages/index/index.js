// pages/index/index.js
const app = getApp()

Page({
  data: {
    // 用户信息
    userInfo: {},
    greeting: '早上好',
    currentDate: '',
    lunarDate: '',
    
    // 天气信息
    weather: {
      temperature: '',
      description: ''
    },
    
    // 统计数据
    stats: {
      todoCount: 0,
      urgentTodos: 0,
      docsCount: 0,
      recentDocs: 0,
      meetingCount: 0,
      todayMeetings: 0,
      contactsCount: 0
    },
    
    // 今日安排
    todaySchedule: [],
    
    // 最近活动
    recentActivity: [],
    
    // 弹窗状态
    showQuickTodo: false,
    showScheduleDetail: false,
    
    // 快速待办
    quickTodoText: '',
    quickTodoPriority: 'medium',
    
    // 选中的安排
    selectedSchedule: {}
  },

  onLoad(options) {
    try {
      // 检查登录状态
      const app = getApp()
      if (!app.checkPageAccess('/pages/index/index')) {
        return
      }
      
      this.initPage()
    } catch (error) {
      console.error('Index页面初始化失败:', error)
    }
  },
  
  onShow() {
    try {
      this.refreshData()
    } catch (error) {
      console.error('Index页面显示失败:', error)
    }
  },
  
  onReady() {
    // 页面初次渲染完成
  },
  
  onHide() {
    // 页面隐藏
  },
  
  onUnload() {
    // 页面卸载
  },

  onShow() {
    // 添加防抖机制，避免频繁刷新
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
    }
    this.refreshTimer = setTimeout(() => {
      this.refreshData()
    }, 100)
  },

  onPullDownRefresh() {
    this.refreshData()
    setTimeout(() => {
      wx.stopPullDownRefresh()
    }, 1000)
  },

  onShareAppMessage() {
    return {
      title: '便捷办公助手 - 让工作更高效',
      path: '/pages/index/index'
    }
  },

  // 刷新数据
  refreshData() {
    this.updateGreeting()
    this.updateDate()
    this.loadStats()
    this.loadTodaySchedule()
    this.loadRecentActivities()
    this.loadQuickActions()
  },

  // 新增：扫码查询入口
  quickScanQuery() {
    wx.scanCode({
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        const content = res.result || res.scanCode || ''
        if (!content) {
          wx.showToast({ title: '未识别到编码', icon: 'none' })
          return
        }
        wx.navigateTo({
          url: `/pages/query/query?code=${encodeURIComponent(content)}`
        })
      },
      fail: () => {
        wx.showToast({ title: '扫码失败', icon: 'none' })
      }
    })
  },

  // 新增：编码查询入口
  quickCodeQuery() {
    wx.navigateTo({ url: '/pages/query/query' })
  },
  
  // 初始化页面
  initPage() {
    this.setGreeting()
    this.setCurrentDate()
    this.getUserInfo()
    this.getWeatherInfo()
    this.loadStats()
    this.loadTodaySchedule()
    this.loadRecentActivity()
  },

  // 刷新数据
  refreshData() {
    const startTime = Date.now()
    
    // 只更新必要的数据
    this.setGreeting()
    this.setCurrentDate()
    
    // 使用Promise.all并行加载数据，提升性能
    Promise.all([
      this.loadStatsAsync(),
      this.loadTodayScheduleAsync(),
      this.loadRecentActivityAsync()
    ]).then(() => {
      const endTime = Date.now()
      // 数据刷新完成
    }).catch(err => {
      console.error('数据刷新失败:', err)
    })
  },

  // 异步加载统计数据
  loadStatsAsync() {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.loadStats()
        resolve()
      }, 0)
    })
  },

  // 异步加载今日安排
  loadTodayScheduleAsync() {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.loadTodaySchedule()
        resolve()
      }, 0)
    })
  },

  // 异步加载最近活动
  loadRecentActivityAsync() {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.loadRecentActivity()
        resolve()
      }, 0)
    })
  },

  // 设置问候语
  setGreeting() {
    const hour = new Date().getHours()
    let greeting = '早上好'
    
    if (hour >= 6 && hour < 12) {
      greeting = '早上好'
    } else if (hour >= 12 && hour < 18) {
      greeting = '下午好'
    } else {
      greeting = '晚上好'
    }
    
    this.setData({ greeting })
  },

  // 设置当前日期
  setCurrentDate() {
    const now = new Date()
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    const currentDate = `${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}`
    const lunarDate = this.getLunarDate(now)
    
    this.setData({
      currentDate,
      lunarDate
    })
  },

  // 获取农历日期（简化版）
  getLunarDate(date) {
    // 这里简化处理，实际项目中可以使用专门的农历转换库
    const lunarMonths = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月']
    const month = date.getMonth()
    const day = date.getDate()
    return `农历${lunarMonths[month]}${day > 15 ? '下旬' : day > 10 ? '中旬' : '上旬'}`
  },

  // 获取用户信息
  getUserInfo() {
    const userInfo = app.getUserInfo()
    if (userInfo) {
      this.setData({ 
        userInfo: {
          nickName: userInfo.nickname || userInfo.username || '用户',
          avatarUrl: userInfo.avatar || '',
          department: userInfo.department || '',
          position: userInfo.position || ''
        }
      })
    } else {
      // 如果没有用户信息，重定向到登录页
      wx.reLaunch({
        url: '/pages/login/login'
      })
    }
  },

  // 获取天气信息
  getWeatherInfo() {
    // 模拟天气数据，实际项目中可以调用天气API
    const weatherData = {
      temperature: Math.floor(Math.random() * 20) + 10,
      description: ['晴', '多云', '阴', '小雨'][Math.floor(Math.random() * 4)]
    }
    
    this.setData({
      weather: weatherData
    })
  },

  // 加载统计数据
  loadStats() {
    const todos = app.utils.getStorage('todos', [])
    const docs = app.utils.getStorage('documents', [])
    const meetings = app.utils.getStorage('meetings', [])
    const contacts = app.utils.getStorage('contacts', [])
    
    const today = new Date()
    const todayStr = app.utils.formatDate(today, 'YYYY-MM-DD')
    
    // 计算统计数据
    const urgentTodos = todos.filter(todo => !todo.completed && todo.priority === 'high').length
    const recentDocs = docs.filter(doc => {
      const docDate = new Date(doc.updatedAt || doc.createdAt)
      const diffDays = (today - docDate) / (1000 * 60 * 60 * 24)
      return diffDays <= 7
    }).length
    
    const todayMeetings = meetings.filter(meeting => {
      const meetingDate = app.utils.formatDate(new Date(meeting.startTime), 'YYYY-MM-DD')
      return meetingDate === todayStr && meeting.status !== 'cancelled'
    }).length
    
    this.setData({
      stats: {
        todoCount: todos.filter(todo => !todo.completed).length,
        urgentTodos,
        docsCount: docs.length,
        recentDocs,
        meetingCount: meetings.filter(meeting => meeting.status !== 'cancelled').length,
        todayMeetings,
        contactsCount: contacts.length
      }
    })
  },

  // 加载今日安排
  loadTodaySchedule() {
    const todos = app.utils.getStorage('todos', [])
    const meetings = app.utils.getStorage('meetings', [])
    const today = new Date()
    const todayStr = app.utils.formatDate(today, 'YYYY-MM-DD')
    
    let schedule = []
    
    // 添加今日待办
    const todayTodos = todos.filter(todo => {
      if (todo.completed) return false
      if (!todo.dueDate) return false
      const dueDate = app.utils.formatDate(new Date(todo.dueDate), 'YYYY-MM-DD')
      return dueDate === todayStr
    })
    
    todayTodos.forEach(todo => {
      schedule.push({
        id: todo.id,
        type: 'todo',
        time: todo.dueTime || '全天',
        title: todo.title,
        description: todo.description,
        tags: todo.tags,
        actionText: '完成',
        fullTime: todo.dueTime ? `今天 ${todo.dueTime}` : '今天 全天',
        priority: todo.priority
      })
    })
    
    // 添加今日会议
    const todayMeetings = meetings.filter(meeting => {
      const meetingDate = app.utils.formatDate(new Date(meeting.startTime), 'YYYY-MM-DD')
      return meetingDate === todayStr && meeting.status !== 'cancelled'
    })
    
    todayMeetings.forEach(meeting => {
      const startTime = new Date(meeting.startTime)
      const endTime = new Date(meeting.endTime)
      schedule.push({
        id: meeting.id,
        type: 'meeting',
        time: app.utils.formatDate(startTime, 'HH:mm'),
        title: meeting.title,
        description: meeting.description,
        location: meeting.location,
        participants: meeting.participants,
        actionText: '加入',
        fullTime: `今天 ${app.utils.formatDate(startTime, 'HH:mm')}-${app.utils.formatDate(endTime, 'HH:mm')}`
      })
    })
    
    // 按时间排序
    schedule.sort((a, b) => {
      if (a.time === '全天') return 1
      if (b.time === '全天') return -1
      return a.time.localeCompare(b.time)
    })
    
    this.setData({ todaySchedule: schedule.slice(0, 5) })
  },

  // 加载最近活动
  loadRecentActivity() {
    const todos = app.utils.getStorage('todos', [])
    const docs = app.utils.getStorage('documents', [])
    const meetings = app.utils.getStorage('meetings', [])
    const contacts = app.utils.getStorage('contacts', [])
    
    let activities = []
    
    // 最近完成的待办
    const recentCompletedTodos = todos
      .filter(todo => todo.completed && todo.completedAt)
      .sort((a, b) => new Date(b.completedAt) - new Date(a.completedAt))
      .slice(0, 3)
    
    recentCompletedTodos.forEach(todo => {
      activities.push({
        id: `todo-${todo.id}`,
        type: 'todo',
        icon: '✅',
        title: `完成待办：${todo.title}`,
        time: app.utils.formatRelativeTime(todo.completedAt),
        status: 'completed',
        statusText: '已完成'
      })
    })
    
    // 最近创建的文档
    const recentDocs = docs
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      .slice(0, 2)
    
    recentDocs.forEach(doc => {
      activities.push({
        id: `doc-${doc.id}`,
        type: 'docs',
        icon: '📄',
        title: `创建文档：${doc.title}`,
        time: app.utils.formatRelativeTime(doc.createdAt)
      })
    })
    
    // 最近的会议
    const recentMeetings = meetings
      .filter(meeting => meeting.status !== 'cancelled')
      .sort((a, b) => new Date(b.createdAt || b.startTime) - new Date(a.createdAt || a.startTime))
      .slice(0, 2)
    
    recentMeetings.forEach(meeting => {
      activities.push({
        id: `meeting-${meeting.id}`,
        type: 'meeting',
        icon: '📞',
        title: `安排会议：${meeting.title}`,
        time: app.utils.formatRelativeTime(meeting.createdAt || meeting.startTime),
        status: meeting.status,
        statusText: meeting.status === 'scheduled' ? '已安排' : '进行中'
      })
    })
    
    // 按时间排序
    activities.sort((a, b) => {
      const timeA = a.time.includes('分钟') ? parseInt(a.time) : 
                   a.time.includes('小时') ? parseInt(a.time) * 60 : 
                   a.time.includes('天') ? parseInt(a.time) * 1440 : 0
      const timeB = b.time.includes('分钟') ? parseInt(b.time) : 
                   b.time.includes('小时') ? parseInt(b.time) * 60 : 
                   b.time.includes('天') ? parseInt(b.time) * 1440 : 0
      return timeA - timeB
    })
    
    this.setData({ recentActivity: activities.slice(0, 6) })
  },

  // 导航到页面
  navigateToTodo() {
    wx.switchTab({
      url: '/pages/todo/todo'
    })
  },

  navigateToDocs() {
    wx.switchTab({
      url: '/pages/docs/docs'
    })
  },

  navigateToMeeting() {
    wx.switchTab({
      url: '/pages/meeting/meeting'
    })
  },

  navigateToContacts() {
    wx.switchTab({
      url: '/pages/contacts/contacts'
    })
  },

  // 查看全部安排
  viewAllSchedule() {
    wx.switchTab({
      url: '/pages/todo/todo'
    })
  },

  // 查看全部活动
  viewAllActivity() {
    wx.switchTab({
      url: '/pages/dashboard/dashboard'
    })
  },

  // 快速操作
  quickAddTodo() {
    this.setData({
      showQuickTodo: true,
      quickTodoText: '',
      quickTodoPriority: 'medium'
    })
  },

  quickCreateDoc() {
    wx.switchTab({
      url: '/pages/docs/docs'
    })
  },

  quickScheduleMeeting() {
    wx.switchTab({
      url: '/pages/meeting/meeting'
    })
  },

  quickAddContact() {
    wx.switchTab({
      url: '/pages/contacts/contacts'
    })
  },

  viewDashboard() {
    wx.navigateTo({
      url: '/pages/dashboard/dashboard'
    })
  },

  scanCode() {
    wx.scanCode({
      success: (res) => {
        wx.showModal({
          title: '扫码结果',
          content: `扫码内容: ${res.result}`,
          showCancel: false
        })
      },
      fail: (err) => {
        console.error('扫码失败:', err)
        wx.showToast({
          title: '扫码失败',
          icon: 'none'
        })
      }
    })
  },

  // 快速扫码功能
  quickScan() {
    wx.scanCode({
      success: (res) => {
          // 根据扫码结果类型进行处理
          const result = res.result
        if (result.startsWith('http')) {
          // 网址类型
          wx.showModal({
            title: '扫码结果',
            content: `检测到网址：${result}`,
            confirmText: '打开',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                wx.setClipboardData({
                  data: result,
                  success: () => {
                    wx.showToast({
                      title: '已复制到剪贴板',
                      icon: 'success'
                    })
                  }
                })
              }
            }
          })
        } else {
          // 其他类型
          wx.showModal({
            title: '扫码结果',
            content: result,
            confirmText: '复制',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) {
                wx.setClipboardData({
                  data: result,
                  success: () => {
                    wx.showToast({
                      title: '已复制到剪贴板',
                      icon: 'success'
                    })
                  }
                })
              }
            }
          })
        }
      },
      fail: (err) => {
        console.error('快速扫码失败:', err)
        wx.showToast({
          title: '扫码失败',
          icon: 'none'
        })
      }
    })
  },

  // 添加安排
  addSchedule() {
    wx.switchTab({
      url: '/pages/todo/todo'
    })
  },

  // 快速待办相关
  onQuickTodoInput(e) {
    this.setData({
      quickTodoText: e.detail.value
    })
  },

  selectPriority(e) {
    const priority = e.currentTarget.dataset.priority
    this.setData({
      quickTodoPriority: priority
    })
  },

  saveQuickTodo() {
    const { quickTodoText, quickTodoPriority } = this.data
    
    if (!quickTodoText.trim()) {
      wx.showToast({
        title: '请输入待办内容',
        icon: 'none'
      })
      return
    }
    
    const todos = app.utils.getStorage('todos', [])
    const newTodo = {
      id: app.utils.generateId(),
      title: quickTodoText.trim(),
      description: '',
      priority: quickTodoPriority,
      completed: false,
      createdAt: new Date().toISOString(),
      dueDate: null,
      tags: []
    }
    
    todos.unshift(newTodo)
    app.utils.setStorage('todos', todos)
    
    this.setData({
      showQuickTodo: false,
      quickTodoText: '',
      quickTodoPriority: 'medium'
    })
    
    wx.showToast({
      title: '添加成功',
      icon: 'success'
    })
    
    // 刷新统计数据
    this.loadStats()
    this.loadTodaySchedule()
  },

  hideQuickTodo() {
    this.setData({ showQuickTodo: false })
  },

  // 安排详情相关
  openScheduleDetail(e) {
    const item = e.currentTarget.dataset.item
    this.setData({
      selectedSchedule: item,
      showScheduleDetail: true
    })
  },

  hideScheduleDetail() {
    this.setData({ showScheduleDetail: false })
  },

  editSchedule() {
    const { selectedSchedule } = this.data
    this.hideScheduleDetail()
    
    if (selectedSchedule.type === 'todo') {
      wx.switchTab({
        url: '/pages/todo/todo'
      })
    } else if (selectedSchedule.type === 'meeting') {
      wx.switchTab({
        url: '/pages/meeting/meeting'
      })
    }
  },

  // 阻止事件冒泡
  preventClose() {
    // 阻止点击模态框内容时关闭
  },

  // 打开设置
  openSettings() {
    wx.showToast({
      title: '设置功能开发中',
      icon: 'none'
    })
  },

  // 语音输入功能
  quickVoice() {
    const app = getApp()
    
    wx.showModal({
      title: '语音输入',
      content: '选择语音输入用途',
      confirmText: '会议记录',
      cancelText: '快速备忘',
      success: (res) => {
        if (res.confirm) {
          this.startVoiceRecording('meeting')
        } else if (res.cancel) {
          this.startVoiceRecording('memo')
        }
      }
    })
  },

  // 开始语音录制
  startVoiceRecording(type) {
    const recorderManager = wx.getRecorderManager()
    
    wx.showLoading({
      title: '开始录音...'
    })
    
    recorderManager.start({
      duration: 60000, // 最长60秒
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 96000,
      format: 'mp3'
    })
    
    recorderManager.onStart(() => {
      wx.hideLoading()
      wx.showToast({
        title: '录音中...',
        icon: 'loading',
        duration: 60000
      })
    })
    
    recorderManager.onStop((res) => {
      wx.hideToast()
      this.processVoiceRecording(res, type)
    })
    
    recorderManager.onError((err) => {
      wx.hideToast()
      wx.showToast({
        title: '录音失败',
        icon: 'none'
      })
      console.error('录音失败:', err)
    })
    
    // 10秒后自动停止录音
    setTimeout(() => {
      recorderManager.stop()
    }, 10000)
  },

  // 处理语音录制结果
  processVoiceRecording(res, type) {
    const app = getApp()
    
    // 模拟语音转文字（实际项目中需要调用语音识别API）
    wx.showLoading({
      title: '正在转换...'
    })
    
    // 模拟转换延迟
    setTimeout(() => {
      wx.hideLoading()
      
      const mockText = type === 'meeting' ? 
        '会议记录：今天讨论了项目进度，需要在下周完成功能开发。' :
        '快速备忘：记得明天上午9点开会。'
      
      if (type === 'meeting') {
        // 创建会议记录文档
        this.createMeetingDocument(mockText, res.tempFilePath)
      } else {
        // 创建快速待办
        this.createVoiceTodo(mockText)
      }
    }, 2000)
  },

  // 创建会议记录文档
  createMeetingDocument(text, audioPath) {
    const app = getApp()
    const docs = app.globalData.docs || []
    
    const newDoc = {
      id: app.utils.generateId(),
      title: `语音会议记录_${new Date().toLocaleDateString()}`,
      content: text,
      type: 'text',
      size: text.length,
      tags: ['语音转换', '会议记录'],
      isShared: false,
      isFavorite: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      audioPath: audioPath // 保存音频文件路径
    }
    
    docs.unshift(newDoc)
    app.globalData.docs = docs
    
    wx.showModal({
      title: '语音转换完成',
      content: '已创建会议记录文档，是否立即查看？',
      success: (res) => {
        if (res.confirm) {
          wx.switchTab({
            url: '/pages/docs/docs'
          })
        }
      }
    })
  },

  // 创建语音待办
  createVoiceTodo(text) {
    const app = getApp()
    const todos = app.utils.getStorage('todos', [])
    
    const newTodo = {
      id: app.utils.generateId(),
      title: text,
      description: '通过语音输入创建',
      priority: 'medium',
      completed: false,
      createdAt: new Date().toISOString(),
      dueDate: null,
      tags: ['语音输入']
    }
    
    todos.unshift(newTodo)
    app.utils.setStorage('todos', todos)
    
    wx.showToast({
      title: '语音待办已创建',
      icon: 'success'
    })
    
    this.loadStats()
    this.loadTodaySchedule()
  },

  // 语音搜索功能
  voiceSearch() {
    const recorderManager = wx.getRecorderManager()
    
    wx.showLoading({
      title: '语音搜索中...'
    })
    
    recorderManager.start({
      duration: 5000, // 最长5秒
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 96000,
      format: 'mp3'
    })
    
    recorderManager.onStart(() => {
      wx.hideLoading()
      wx.showToast({
        title: '请说出搜索内容',
        icon: 'loading',
        duration: 5000
      })
    })
    
    recorderManager.onStop((res) => {
      wx.hideToast()
      
      // 模拟语音识别搜索
      setTimeout(() => {
        const mockSearchText = '会议'
        this.setData({
          searchText: mockSearchText,
          showSearch: true
        })
        this.performSearch(mockSearchText)
      }, 1000)
    })
    
    recorderManager.onError((err) => {
      wx.hideToast()
      wx.showToast({
        title: '语音搜索失败',
        icon: 'none'
      })
    })
    
    // 5秒后自动停止
    setTimeout(() => {
      recorderManager.stop()
    }, 5000)
  },

  // 执行搜索
  performSearch(searchText) {
    // 这里可以实现具体的搜索逻辑
    wx.showToast({
      title: `搜索: ${searchText}`,
      icon: 'none'
    })
  },

  openProfile() {
    wx.showActionSheet({
      itemList: ['个人资料', '账户设置', '切换账户', '退出登录'],
      success: (res) => {
        switch(res.tapIndex) {
          case 0:
            this.openUserProfile();
            break;
          case 1:
            this.openAccountSettings();
            break;
          case 2:
            this.switchAccount();
            break;
          case 3:
            this.logout();
            break;
        }
      }
    });
  },

  // 打开用户资料
  openUserProfile() {
    const userInfo = app.getUserInfo();
    const isGuest = wx.getStorageSync('isGuest');
    
    const content = `用户名：${userInfo.username || '未设置'}\n昵称：${userInfo.nickname || '未设置'}\n邮箱：${userInfo.email || '未设置'}\n部门：${userInfo.department || '未设置'}\n职位：${userInfo.position || '未设置'}${isGuest ? '\n\n注意：您当前是游客模式，数据将在1小时后清除' : ''}`;
    
    wx.showModal({
      title: '个人资料',
      content: content,
      showCancel: false,
      confirmText: isGuest ? '知道了' : '编辑资料',
      success: (res) => {
        if (res.confirm && !isGuest) {
          this.editUserProfile();
        }
      }
    });
  },

  // 编辑用户资料
  editUserProfile() {
    wx.navigateTo({
      url: '/pages/profile/profile'
    }).catch(() => {
      // 如果页面不存在，显示临时编辑界面
      wx.showModal({
        title: '编辑用户名',
        editable: true,
        placeholderText: this.data.userName,
        success: (res) => {
          if (res.confirm && res.content) {
            this.setData({
              userName: res.content
            });
            wx.setStorageSync('userName', res.content);
            wx.showToast({
              title: '用户名已更新',
              icon: 'success'
            });
          }
        }
      });
    });
  },

  // 账户设置
  openAccountSettings() {
    wx.showActionSheet({
      itemList: ['修改密码', '绑定手机', '隐私设置', '通知设置'],
      success: (res) => {
        const settings = ['修改密码', '绑定手机', '隐私设置', '通知设置'];
        wx.showToast({
          title: `打开${settings[res.tapIndex]}`,
          icon: 'none'
        });
      }
    });
  },

  // 切换账户
  switchAccount() {
    const isGuest = wx.getStorageSync('isGuest');
    
    if (isGuest) {
      wx.showToast({
        title: '游客模式无法切换账户',
        icon: 'none'
      });
      return;
    }
    
    wx.showModal({
      title: '切换账户',
      content: '切换账户将退出当前登录，是否继续？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({
            title: '正在切换账户...',
            icon: 'loading'
          });
          
          // 清除当前用户数据并跳转到登录页
          setTimeout(() => {
            app.logout();
          }, 1000);
        }
      }
    });
  },

  // 退出登录
  logout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出当前账户吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({
            title: '正在退出...',
            icon: 'loading'
          });
          
          // 调用app的logout方法
          setTimeout(() => {
            app.logout();
          }, 1000);
        }
      }
    });
  },

  // 显示登录模态框
  showLoginModal() {
    wx.showModal({
      title: '用户登录',
      content: '请输入用户名登录',
      editable: true,
      placeholderText: '请输入用户名',
      success: (res) => {
        if (res.confirm && res.content) {
          this.setData({
            userName: res.content,
            userAvatar: '/images/avatar1.png'
          });
          
          wx.setStorageSync('userName', res.content);
          wx.setStorageSync('userAvatar', '/images/avatar1.png');
          
          wx.showToast({
            title: '登录成功',
            icon: 'success'
          });
        }
      }
    });
  }

})