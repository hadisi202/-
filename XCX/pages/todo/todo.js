// pages/todo/todo.js
const app = getApp()

Page({
  data: {
    // 统计数据
    stats: {
      total: 0,
      pending: 0,
      completed: 0,
      overdue: 0
    },
    
    // 搜索和筛选
    searchText: '',
    currentFilter: 'all', // all, pending, completed, overdue
    currentSort: 'priority', // priority, dueDate, createdAt
    
    // 待办数据
    todos: [],
    filteredTodos: [],
    
    // 弹窗状态
    showTodoModal: false,
    showTodoOptions: false,
    showTodoDetail: false,
    
    // 编辑中的待办
    editingTodo: {
      id: '',
      title: '',
      description: '',
      priority: 'medium',
      dueDate: '',
      dueTime: '',
      tags: [],
      reminder: false,
      reminderIndex: 0
    },
    
    // 输入状态
    inputTag: '',
    
    // 选中的待办
    selectedTodo: {},
    
    // 提醒选项
    reminderOptions: [
      '截止时间前5分钟',
      '截止时间前15分钟',
      '截止时间前30分钟',
      '截止时间前1小时',
      '截止时间前1天'
    ],
    
    // 空状态文本
    emptyText: '暂无待办事项'
  },

  onLoad() {
    // 检查登录状态
    const app = getApp()
    if (!app.checkPageAccess('/pages/todo/todo')) {
      return
    }
    this.loadTodos()
  },

  onShow() {
    this.loadTodos()
  },

  onPullDownRefresh() {
    this.loadTodos()
    setTimeout(() => {
      wx.stopPullDownRefresh()
    }, 1000)
  },

  onShareAppMessage() {
    return {
      title: '我的待办事项',
      path: '/pages/todo/todo'
    }
  },

  // 加载待办列表
  loadTodos() {
    const todos = app.utils.getStorage('todos', [])
    
    // 处理待办数据
    const processedTodos = todos.map(todo => {
      const createdAt = new Date(todo.createdAt)
      const dueDate = todo.dueDate ? new Date(todo.dueDate) : null
      const now = new Date()
      
      return {
        id: todo.id,
      title: todo.title,
      description: todo.description,
      priority: todo.priority,
      category: todo.category,
      tags: todo.tags,
      dueDate: todo.dueDate,
      completed: todo.completed,
      createdAt: todo.createdAt,
      updatedAt: todo.updatedAt,
      createdAtText: app.utils.formatRelativeTime(todo.createdAt),
        dueDateText: dueDate ? this.formatDueDate(dueDate) : '',
        priorityText: this.getPriorityText(todo.priority),
        isOverdue: dueDate && !todo.completed && dueDate < now,
        completedAtText: todo.completedAt ? app.utils.formatDate(new Date(todo.completedAt), 'YYYY-MM-DD HH:mm') : ''
      }
    })
    
    this.setData({ todos: processedTodos })
    this.calculateStats()
    this.filterAndSortTodos()
  },

  // 计算统计数据
  calculateStats() {
    const { todos } = this.data
    const now = new Date()
    
    const stats = {
      total: todos.length,
      pending: todos.filter(todo => !todo.completed).length,
      completed: todos.filter(todo => todo.completed).length,
      overdue: todos.filter(todo => {
        if (todo.completed || !todo.dueDate) return false
        const dueDate = new Date(todo.dueDate)
        return dueDate < now
      }).length
    }
    
    this.setData({ stats })
  },

  // 格式化截止日期
  formatDueDate(dueDate) {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)
    const targetDate = new Date(dueDate.getFullYear(), dueDate.getMonth(), dueDate.getDate())
    
    if (targetDate.getTime() === today.getTime()) {
      return '今天'
    } else if (targetDate.getTime() === tomorrow.getTime()) {
      return '明天'
    } else if (targetDate < today) {
      const diffDays = Math.floor((today - targetDate) / (24 * 60 * 60 * 1000))
      return `${diffDays}天前`
    } else {
      const diffDays = Math.floor((targetDate - today) / (24 * 60 * 60 * 1000))
      if (diffDays <= 7) {
        return `${diffDays}天后`
      } else {
        return app.utils.formatDate(dueDate, 'MM-DD')
      }
    }
  },

  // 获取优先级文本
  getPriorityText(priority) {
    const priorityMap = {
      high: '高',
      medium: '中',
      low: '低'
    }
    return priorityMap[priority] || '中'
  },

  // 搜索输入
  onSearchInput(e) {
    this.setData({ searchText: e.detail.value })
    this.filterAndSortTodos()
  },

  // 切换筛选
  switchFilter(e) {
    const filter = e.currentTarget.dataset.filter
    this.setData({ currentFilter: filter })
    this.filterAndSortTodos()
    this.updateEmptyText()
  },

  // 切换排序
  switchSort(e) {
    const sort = e.currentTarget.dataset.sort
    this.setData({ currentSort: sort })
    this.filterAndSortTodos()
  },

  // 筛选和排序待办
  filterAndSortTodos() {
    let { todos, searchText, currentFilter, currentSort } = this.data
    
    // 搜索筛选
    if (searchText.trim()) {
      todos = todos.filter(todo => 
        todo.title.toLowerCase().includes(searchText.toLowerCase()) ||
        (todo.description && todo.description.toLowerCase().includes(searchText.toLowerCase())) ||
        (todo.tags && todo.tags.some(tag => tag.toLowerCase().includes(searchText.toLowerCase())))
      )
    }
    
    // 状态筛选
    switch (currentFilter) {
      case 'pending':
        todos = todos.filter(todo => !todo.completed)
        break
      case 'completed':
        todos = todos.filter(todo => todo.completed)
        break
      case 'overdue':
        todos = todos.filter(todo => todo.isOverdue)
        break
    }
    
    // 排序
    todos.sort((a, b) => {
      switch (currentSort) {
        case 'priority':
          const priorityOrder = { high: 3, medium: 2, low: 1 }
          const priorityDiff = priorityOrder[b.priority] - priorityOrder[a.priority]
          if (priorityDiff !== 0) return priorityDiff
          return new Date(b.createdAt) - new Date(a.createdAt)
          
        case 'dueDate':
          if (!a.dueDate && !b.dueDate) return new Date(b.createdAt) - new Date(a.createdAt)
          if (!a.dueDate) return 1
          if (!b.dueDate) return -1
          return new Date(a.dueDate) - new Date(b.dueDate)
          
        case 'createdAt':
          return new Date(b.createdAt) - new Date(a.createdAt)
          
        default:
          return 0
      }
    })
    
    this.setData({ filteredTodos: todos })
  },

  // 更新空状态文本
  updateEmptyText() {
    const { currentFilter, searchText } = this.data
    let emptyText = '暂无待办事项'
    
    if (searchText.trim()) {
      emptyText = '未找到相关待办事项'
    } else {
      switch (currentFilter) {
        case 'pending':
          emptyText = '暂无待完成的事项'
          break
        case 'completed':
          emptyText = '暂无已完成的事项'
          break
        case 'overdue':
          emptyText = '暂无逾期的事项'
          break
      }
    }
    
    this.setData({ emptyText })
  },

  // 切换待办状态
  toggleTodo(e) {
    const todoId = e.currentTarget.dataset.id
    const todos = app.utils.getStorage('todos', [])
    
    const todoIndex = todos.findIndex(todo => todo.id === todoId)
    if (todoIndex === -1) return
    
    todos[todoIndex].completed = !todos[todoIndex].completed
    if (todos[todoIndex].completed) {
      todos[todoIndex].completedAt = new Date().toISOString()
    } else {
      delete todos[todoIndex].completedAt
    }
    
    app.utils.setStorage('todos', todos)
    
    wx.showToast({
      title: todos[todoIndex].completed ? '已完成' : '已取消完成',
      icon: 'success',
      duration: 1500
    })
    
    this.loadTodos()
  },

  // 创建待办
  createTodo() {
    this.resetEditingTodo()
    this.setData({ showTodoModal: true })
  },

  // 重置编辑中的待办
  resetEditingTodo() {
    this.setData({
      editingTodo: {
        id: '',
        title: '',
        description: '',
        priority: 'medium',
        dueDate: '',
        dueTime: '',
        tags: [],
        reminder: false,
        reminderIndex: 0
      },
      inputTag: ''
    })
  },

  // 隐藏待办弹窗
  hideTodoModal() {
    this.setData({ showTodoModal: false })
  },

  // 表单输入处理
  onTitleInput(e) {
    this.setData({
      'editingTodo.title': e.detail.value
    })
  },

  onDescInput(e) {
    this.setData({
      'editingTodo.description': e.detail.value
    })
  },

  // 选择优先级
  selectPriority(e) {
    const priority = e.currentTarget.dataset.priority
    this.setData({
      'editingTodo.priority': priority
    })
  },

  // 截止日期变化
  onDueDateChange(e) {
    this.setData({
      'editingTodo.dueDate': e.detail.value
    })
  },

  // 截止时间变化
  onDueTimeChange(e) {
    this.setData({
      'editingTodo.dueTime': e.detail.value
    })
  },

  // 标签输入
  onTagInput(e) {
    this.setData({ inputTag: e.detail.value })
  },

  // 添加标签
  addTag() {
    const { inputTag, editingTodo } = this.data
    const tag = inputTag.trim()
    
    if (!tag) {
      wx.showToast({
        title: '请输入标签内容',
        icon: 'none'
      })
      return
    }
    
    if (editingTodo.tags.includes(tag)) {
      wx.showToast({
        title: '标签已存在',
        icon: 'none'
      })
      return
    }
    
    const newTags = editingTodo.tags.slice();
    newTags.push(tag);
    this.setData({
      'editingTodo.tags': newTags,
      inputTag: ''
    })
  },

  // 移除标签
  removeTag(e) {
    const tag = e.currentTarget.dataset.tag
    const { editingTodo } = this.data
    const newTags = editingTodo.tags.filter(t => t !== tag)
    this.setData({
      'editingTodo.tags': newTags
    })
  },

  // 提醒开关变化
  onReminderChange(e) {
    this.setData({
      'editingTodo.reminder': e.detail.value
    })
  },

  // 提醒选项变化
  onReminderOptionChange(e) {
    this.setData({
      'editingTodo.reminderIndex': e.detail.value
    })
  },

  // 保存待办
  saveTodo() {
    const { editingTodo } = this.data
    
    // 验证
    if (!editingTodo.title.trim()) {
      wx.showToast({
        title: '请输入待办标题',
        icon: 'none'
      })
      return
    }
    
    const todos = app.utils.getStorage('todos', [])
    
    if (editingTodo.id) {
      // 编辑模式
      const todoIndex = todos.findIndex(todo => todo.id === editingTodo.id)
      if (todoIndex !== -1) {
        todos[todoIndex] = {
          id: todos[todoIndex].id,
        description: todos[todoIndex].description,
        priority: todos[todoIndex].priority,
        category: todos[todoIndex].category,
        tags: todos[todoIndex].tags,
        dueDate: todos[todoIndex].dueDate,
        completed: todos[todoIndex].completed,
        createdAt: todos[todoIndex].createdAt,
        updatedAt: todos[todoIndex].updatedAt,
        title: editingTodo.title.trim(),
          description: editingTodo.description.trim(),
          priority: editingTodo.priority,
          dueDate: editingTodo.dueDate || null,
          dueTime: editingTodo.dueTime || null,
          tags: editingTodo.tags,
          reminder: editingTodo.reminder,
          reminderOption: editingTodo.reminder ? this.data.reminderOptions[editingTodo.reminderIndex] : null,
          updatedAt: new Date().toISOString()
        }
      }
    } else {
      // 创建模式
      const newTodo = {
        id: app.utils.generateId(),
        title: editingTodo.title.trim(),
        description: editingTodo.description.trim(),
        priority: editingTodo.priority,
        dueDate: editingTodo.dueDate || null,
        dueTime: editingTodo.dueTime || null,
        tags: editingTodo.tags,
        reminder: editingTodo.reminder,
        reminderOption: editingTodo.reminder ? this.data.reminderOptions[editingTodo.reminderIndex] : null,
        completed: false,
        createdAt: new Date().toISOString()
      }
      todos.unshift(newTodo)
    }
    
    app.utils.setStorage('todos', todos)
    
    // 设置提醒
    if (editingTodo.reminder && editingTodo.dueDate) {
      this.setTodoReminder(editingTodo)
    }
    
    this.setData({ showTodoModal: false })
    
    wx.showToast({
      title: editingTodo.id ? '更新成功' : '创建成功',
      icon: 'success'
    })
    
    this.loadTodos()
  },

  // 设置待办提醒
  setTodoReminder(todo) {
    // 这里可以集成系统通知或第三方推送服务
    // 设置提醒
  },

  // 打开待办详情
  openTodoDetail(e) {
    const item = e.currentTarget.dataset.item
    this.setData({
      selectedTodo: item,
      showTodoDetail: true
    })
  },

  // 隐藏待办详情
  hideTodoDetail() {
    this.setData({ showTodoDetail: false })
  },

  // 从详情编辑
  editTodoFromDetail() {
    const { selectedTodo } = this.data
    this.hideTodoDetail()
    this.editTodo({ currentTarget: { dataset: { item: selectedTodo } } })
  },

  // 显示待办选项
  showTodoOptions(e) {
    const item = e.currentTarget.dataset.item
    this.setData({
      selectedTodo: item,
      showTodoOptions: true
    })
  },

  // 隐藏待办选项
  hideTodoOptions() {
    this.setData({ showTodoOptions: false })
  },

  // 编辑待办
  editTodo() {
    const { selectedTodo } = this.data
    
    this.setData({
      editingTodo: {
        id: selectedTodo.id,
        title: selectedTodo.title,
        description: selectedTodo.description || '',
        priority: selectedTodo.priority,
        dueDate: selectedTodo.dueDate || '',
        dueTime: selectedTodo.dueTime || '',
        tags: selectedTodo.tags || [],
        reminder: !!selectedTodo.reminder,
        reminderIndex: selectedTodo.reminderOption ? 
          this.data.reminderOptions.indexOf(selectedTodo.reminderOption) : 0
      },
      showTodoOptions: false,
      showTodoModal: true
    })
  },

  // 复制待办
  duplicateTodo() {
    const { selectedTodo } = this.data
    const todos = app.utils.getStorage('todos', [])
    
    const newTodo = {
      id: selectedTodo.id,
      title: selectedTodo.title,
      description: selectedTodo.description,
      priority: selectedTodo.priority,
      category: selectedTodo.category,
      tags: selectedTodo.tags,
      dueDate: selectedTodo.dueDate,
      completed: selectedTodo.completed,
      createdAt: selectedTodo.createdAt,
      updatedAt: selectedTodo.updatedAt,
      id: app.utils.generateId(),
      title: `${selectedTodo.title} (副本)`,
      completed: false,
      createdAt: new Date().toISOString()
    }
    
    delete newTodo.completedAt
    delete newTodo.createdAtText
    delete newTodo.dueDateText
    delete newTodo.priorityText
    delete newTodo.isOverdue
    delete newTodo.completedAtText
    
    todos.unshift(newTodo)
    app.utils.setStorage('todos', todos)
    
    this.setData({ showTodoOptions: false })
    
    wx.showToast({
      title: '复制成功',
      icon: 'success'
    })
    
    this.loadTodos()
  },

  // 分享待办
  shareTodo() {
    const { selectedTodo } = this.data
    
    let shareText = `📝 ${selectedTodo.title}`
    if (selectedTodo.description) {
      shareText += `\n${selectedTodo.description}`
    }
    if (selectedTodo.dueDate) {
      shareText += `\n⏰ 截止时间：${selectedTodo.dueDateText}`
    }
    if (selectedTodo.tags && selectedTodo.tags.length > 0) {
      shareText += `\n🏷️ 标签：${selectedTodo.tags.join(', ')}`
    }
    
    wx.setClipboardData({
      data: shareText,
      success: () => {
        wx.showToast({
          title: '已复制到剪贴板',
          icon: 'success'
        })
      }
    })
    
    this.setData({ showTodoOptions: false })
  },

  // 删除待办
  deleteTodo() {
    const { selectedTodo } = this.data
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除待办"${selectedTodo.title}"吗？`,
      confirmColor: '#ff3b30',
      success: (res) => {
        if (res.confirm) {
          const todos = app.utils.getStorage('todos', [])
          const filteredTodos = todos.filter(todo => todo.id !== selectedTodo.id)
          app.utils.setStorage('todos', filteredTodos)
          
          this.setData({ showTodoOptions: false })
          
          wx.showToast({
            title: '删除成功',
            icon: 'success'
          })
          
          this.loadTodos()
        }
      }
    })
  },

  // 阻止事件冒泡
  preventClose() {
    // 阻止点击模态框内容时关闭
  }
})