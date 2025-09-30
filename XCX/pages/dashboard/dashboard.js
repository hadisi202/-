// pages/dashboard/dashboard.js
Page({
  data: {
    // 当前日期
    currentDate: '',
    
    // 概览数据
    overview: {
      totalTodos: 0,
      totalDocs: 0,
      completionRate: 0,
      productivity: 0,
      todoTrend: 0,
      docTrend: 0,
      completionTrend: 0,
      productivityTrend: 0
    },
    
    // 时间范围
    currentTimeRange: 'week',
    currentTimeRangeText: '本周',
    
    // 统计数据
    todoStats: {
      total: 0,
      completed: 0,
      pending: 0,
      overdue: 0,
      avgCompletionTime: '0天',
      highPriorityRate: 0
    },
    
    docStats: {
      total: 0,
      newDocs: 0,
      editCount: 0,
      sharedDocs: 0,
      avgWordCount: 0,
      mostActiveType: '文档'
    },
    
    meetingStats: {
      total: 0,
      completed: 0,
      totalDuration: '0小时',
      avgDuration: '0分钟',
      totalAttendees: 0,
      onlineRate: 0
    },
    
    contactStats: {
      total: 0,
      newContacts: 0,
      groups: 0,
      favorites: 0,
      recentContacts: 0,
      contactFrequency: '低'
    },
    
    // 展开的统计分类
    expandedCategories: {
      todo: true,
      doc: false,
      meeting: false,
      contact: false
    },
    
    // 使用习惯
    habits: {
      mostActiveTime: '09:00-11:00',
      dailyUsage: '2.5小时',
      mostUsedFeature: '待办事项',
      efficiencyImprovement: 15
    },
    
    // 目标列表
    goals: [],
    
    // 目标弹窗
    showGoalModal: false,
    showGoalDetail: false,
    editingGoal: {
      id: '',
      title: '',
      description: '',
      typeIndex: -1,
      target: '',
      deadline: '',
      progress: 0,
      status: 'active'
    },
    selectedGoal: {},
    
    // 目标类型
    goalTypes: [
      { id: 'todo', name: '待办完成', unit: '个' },
      { id: 'doc', name: '文档创建', unit: '篇' },
      { id: 'meeting', name: '会议参与', unit: '次' },
      { id: 'contact', name: '联系人添加', unit: '人' },
      { id: 'time', name: '使用时长', unit: '小时' }
    ]
  },

  onLoad() {
    // 检查登录状态
    const app = getApp()
    if (!app.checkPageAccess('/pages/dashboard/dashboard')) {
      return
    }
    this.initCurrentDate();
    this.loadDashboardData();
    this.loadGoals();
  },

  onShow() {
    this.loadDashboardData();
  },

  // 初始化当前日期
  initCurrentDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const weekDay = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][now.getDay()];
    
    this.setData({
      currentDate: `${year}年${month}月${day}日 ${weekDay}`
    });
  },

  // 加载看板数据
  loadDashboardData() {
    // 模拟数据加载
    const mockData = this.generateMockData();
    
    this.setData({
      overview: mockData.overview,
      todoStats: mockData.todoStats,
      docStats: mockData.docStats,
      meetingStats: mockData.meetingStats,
      contactStats: mockData.contactStats,
      habits: mockData.habits
    });
    
    // 初始化图表
    this.initCharts();
  },

  // 生成模拟数据
  generateMockData() {
    const timeRange = this.data.currentTimeRange;
    
    // 根据时间范围生成不同的数据
    const multiplier = {
      today: 1,
      week: 7,
      month: 30,
      quarter: 90,
      year: 365
    }[timeRange] || 7;
    
    return {
      overview: {
        totalTodos: Math.floor(Math.random() * 50 * multiplier / 7) + 10,
        totalDocs: Math.floor(Math.random() * 20 * multiplier / 7) + 5,
        completionRate: Math.floor(Math.random() * 30) + 70,
        productivity: Math.floor(Math.random() * 20) + 80,
        todoTrend: Math.floor(Math.random() * 20) - 10,
        docTrend: Math.floor(Math.random() * 20) - 10,
        completionTrend: Math.floor(Math.random() * 10) - 5,
        productivityTrend: Math.floor(Math.random() * 10) - 5
      },
      todoStats: {
        total: Math.floor(Math.random() * 100) + 50,
        completed: Math.floor(Math.random() * 60) + 30,
        pending: Math.floor(Math.random() * 30) + 15,
        overdue: Math.floor(Math.random() * 10) + 2,
        avgCompletionTime: `${Math.floor(Math.random() * 5) + 1}天`,
        highPriorityRate: Math.floor(Math.random() * 30) + 20
      },
      docStats: {
        total: Math.floor(Math.random() * 50) + 20,
        newDocs: Math.floor(Math.random() * 15) + 5,
        editCount: Math.floor(Math.random() * 100) + 50,
        sharedDocs: Math.floor(Math.random() * 20) + 10,
        avgWordCount: Math.floor(Math.random() * 1000) + 500,
        mostActiveType: ['文档', '表格', '演示'][Math.floor(Math.random() * 3)]
      },
      meetingStats: {
        total: Math.floor(Math.random() * 20) + 10,
        completed: Math.floor(Math.random() * 15) + 8,
        totalDuration: `${Math.floor(Math.random() * 50) + 20}小时`,
        avgDuration: `${Math.floor(Math.random() * 60) + 30}分钟`,
        totalAttendees: Math.floor(Math.random() * 100) + 50,
        onlineRate: Math.floor(Math.random() * 30) + 60
      },
      contactStats: {
        total: Math.floor(Math.random() * 200) + 100,
        newContacts: Math.floor(Math.random() * 20) + 5,
        groups: Math.floor(Math.random() * 10) + 5,
        favorites: Math.floor(Math.random() * 30) + 15,
        recentContacts: Math.floor(Math.random() * 50) + 20,
        contactFrequency: ['低', '中', '高'][Math.floor(Math.random() * 3)]
      },
      habits: {
        mostActiveTime: ['09:00-11:00', '14:00-16:00', '19:00-21:00'][Math.floor(Math.random() * 3)],
        dailyUsage: `${(Math.random() * 3 + 1).toFixed(1)}小时`,
        mostUsedFeature: ['待办事项', '文档协作', '会议助手', '通讯录'][Math.floor(Math.random() * 4)],
        efficiencyImprovement: Math.floor(Math.random() * 30) + 10
      }
    };
  },

  // 切换时间范围
  switchTimeRange(e) {
    const range = e.currentTarget.dataset.range;
    const rangeText = {
      today: '今天',
      week: '本周',
      month: '本月',
      quarter: '本季度',
      year: '今年'
    }[range];
    
    this.setData({
      currentTimeRange: range,
      currentTimeRangeText: rangeText
    });
    
    // 重新加载数据
    this.loadDashboardData();
  },

  // 初始化图表
  initCharts() {
    this.initTodoTrendChart();
    this.initPriorityChart();
    this.initDocChart();
    this.initMeetingChart();
  },

  // 初始化待办趋势图表
  initTodoTrendChart() {
    const ctx = wx.createCanvasContext('todoTrendChart', this);
    
    // 模拟数据
    const data = this.generateChartData('line');
    
    // 绘制折线图
    this.drawLineChart(ctx, data, {
      width: 300,
      height: 200,
      padding: 40
    });
    
    ctx.draw();
  },

  // 初始化优先级图表
  initPriorityChart() {
    const ctx = wx.createCanvasContext('priorityChart', this);
    
    // 模拟数据
    const data = [
      { label: '高优先级', value: 30, color: '#ef4444' },
      { label: '中优先级', value: 45, color: '#f59e0b' },
      { label: '低优先级', value: 25, color: '#10b981' }
    ];
    
    // 绘制饼图
    this.drawPieChart(ctx, data, {
      centerX: 150,
      centerY: 100,
      radius: 80
    });
    
    ctx.draw();
  },

  // 初始化文档图表
  initDocChart() {
    const ctx = wx.createCanvasContext('docChart', this);
    
    // 模拟数据
    const data = this.generateChartData('bar');
    
    // 绘制柱状图
    this.drawBarChart(ctx, data, {
      width: 300,
      height: 200,
      padding: 40
    });
    
    ctx.draw();
  },

  // 初始化会议图表
  initMeetingChart() {
    const ctx = wx.createCanvasContext('meetingChart', this);
    
    // 模拟数据
    const data = this.generateChartData('area');
    
    // 绘制面积图
    this.drawAreaChart(ctx, data, {
      width: 300,
      height: 200,
      padding: 40
    });
    
    ctx.draw();
  },

  // 生成图表数据
  generateChartData(type) {
    const timeRange = this.data.currentTimeRange;
    let labels = [];
    let values = [];
    
    switch (timeRange) {
      case 'today':
        labels = ['00:00', '06:00', '12:00', '18:00', '24:00'];
        break;
      case 'week':
        labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
        break;
      case 'month':
        labels = ['第1周', '第2周', '第3周', '第4周'];
        break;
      case 'quarter':
        labels = ['第1月', '第2月', '第3月'];
        break;
      case 'year':
        labels = ['Q1', 'Q2', 'Q3', 'Q4'];
        break;
    }
    
    values = labels.map(() => Math.floor(Math.random() * 100) + 20);
    
    return { labels, values };
  },

  // 绘制折线图
  drawLineChart(ctx, data, options) {
    const { width, height, padding } = options;
    const { labels, values } = data;
    
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    const stepX = chartWidth / (labels.length - 1);
    const maxValue = Math.max.apply(Math, values);
    
    // 绘制坐标轴
    ctx.setStrokeStyle('#e5e7eb');
    ctx.setLineWidth(1);
    
    // Y轴
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.stroke();
    
    // X轴
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();
    
    // 绘制数据线
    ctx.setStrokeStyle('#007AFF');
    ctx.setLineWidth(2);
    ctx.beginPath();
    
    values.forEach((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - (value / maxValue) * chartHeight;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
    
    // 绘制数据点
    ctx.setFillStyle('#007AFF');
    values.forEach((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - (value / maxValue) * chartHeight;
      
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, 2 * Math.PI);
      ctx.fill();
    });
  },

  // 绘制饼图
  drawPieChart(ctx, data, options) {
    const { centerX, centerY, radius } = options;
    const total = data.reduce((sum, item) => sum + item.value, 0);
    
    let currentAngle = -Math.PI / 2;
    
    data.forEach(item => {
      const sliceAngle = (item.value / total) * 2 * Math.PI;
      
      ctx.setFillStyle(item.color);
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
      ctx.closePath();
      ctx.fill();
      
      currentAngle += sliceAngle;
    });
  },

  // 绘制柱状图
  drawBarChart(ctx, data, options) {
    const { width, height, padding } = options;
    const { labels, values } = data;
    
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    const barWidth = chartWidth / labels.length * 0.6;
    const stepX = chartWidth / labels.length;
    const maxValue = Math.max.apply(Math, values);
    
    // 绘制坐标轴
    ctx.setStrokeStyle('#e5e7eb');
    ctx.setLineWidth(1);
    
    // Y轴
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.stroke();
    
    // X轴
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();
    
    // 绘制柱子
    ctx.setFillStyle('#007AFF');
    values.forEach((value, index) => {
      const x = padding + index * stepX + (stepX - barWidth) / 2;
      const barHeight = (value / maxValue) * chartHeight;
      const y = height - padding - barHeight;
      
      ctx.fillRect(x, y, barWidth, barHeight);
    });
  },

  // 绘制面积图
  drawAreaChart(ctx, data, options) {
    const { width, height, padding } = options;
    const { labels, values } = data;
    
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    const stepX = chartWidth / (labels.length - 1);
    const maxValue = Math.max.apply(Math, values);
    
    // 绘制面积
    const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
    gradient.addColorStop(0, 'rgba(0, 122, 255, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 122, 255, 0.1)');
    
    ctx.setFillStyle(gradient);
    ctx.beginPath();
    ctx.moveTo(padding, height - padding);
    
    values.forEach((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - (value / maxValue) * chartHeight;
      ctx.lineTo(x, y);
    });
    
    ctx.lineTo(width - padding, height - padding);
    ctx.closePath();
    ctx.fill();
    
    // 绘制线条
    ctx.setStrokeStyle('#007AFF');
    ctx.setLineWidth(2);
    ctx.beginPath();
    
    values.forEach((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - (value / maxValue) * chartHeight;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
  },

  // 切换统计分类
  toggleCategory(e) {
    const category = e.currentTarget.dataset.category;
    const key = `expandedCategories.${category}`;
    
    this.setData({
      [key]: !this.data.expandedCategories[category]
    });
  },

  // 导出数据
  exportData() {
    wx.showActionSheet({
      itemList: ['导出为Excel', '导出为PDF', '分享报告'],
      success: (res) => {
        const actions = ['excel', 'pdf', 'share'];
        const action = actions[res.tapIndex];
        
        switch (action) {
          case 'excel':
            this.exportToExcel();
            break;
          case 'pdf':
            this.exportToPDF();
            break;
          case 'share':
            this.shareReport();
            break;
        }
      }
    });
  },

  // 导出Excel
  exportToExcel() {
    wx.showToast({
      title: '正在导出Excel...',
      icon: 'loading',
      duration: 2000
    });
    
    // 模拟导出过程
    setTimeout(() => {
      wx.showToast({
        title: '导出成功',
        icon: 'success'
      });
    }, 2000);
  },

  // 导出PDF
  exportToPDF() {
    wx.showToast({
      title: '正在导出PDF...',
      icon: 'loading',
      duration: 2000
    });
    
    // 模拟导出过程
    setTimeout(() => {
      wx.showToast({
        title: '导出成功',
        icon: 'success'
      });
    }, 2000);
  },

  // 分享报告
  shareReport() {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline']
    });
  },

  // 加载目标列表
  loadGoals() {
    // 模拟数据
    const mockGoals = [
      {
        id: '1',
        title: '完成50个待办事项',
        description: '提高工作效率，按时完成任务',
        type: 'todo',
        target: 50,
        current: 32,
        progress: 64,
        deadline: '2024-12-31',
        status: 'active',
        createdAt: '2024-01-01'
      },
      {
        id: '2',
        title: '创建20篇文档',
        description: '建立完善的知识库',
        type: 'doc',
        target: 20,
        current: 20,
        progress: 100,
        deadline: '2024-06-30',
        status: 'completed',
        createdAt: '2024-01-15'
      }
    ];
    
    // 处理目标数据
    const processedGoals = mockGoals.map(goal => {
      const deadline = new Date(goal.deadline);
      const now = new Date();
      const remainingDays = Math.ceil((deadline - now) / (1000 * 60 * 60 * 24));
      
      return {
        id: goal.id,
      title: goal.title,
      description: goal.description,
      category: goal.category,
      targetValue: goal.targetValue,
      currentValue: goal.currentValue,
      unit: goal.unit,
      deadline: goal.deadline,
      status: goal.status,
      createdAt: goal.createdAt,
      updatedAt: goal.updatedAt,
      deadlineText: this.formatDate(goal.deadline),
        remainingDays: Math.max(0, remainingDays),
        statusText: this.getGoalStatusText(goal.status),
        createdAtText: this.formatDate(goal.createdAt)
      };
    });
    
    this.setData({
      goals: processedGoals
    });
  },

  // 获取目标状态文本
  getGoalStatusText(status) {
    const statusMap = {
      active: '进行中',
      completed: '已完成',
      overdue: '已逾期'
    };
    return statusMap[status] || '未知';
  },

  // 格式化日期
  formatDate(dateStr) {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  // 添加目标
  addGoal() {
    this.setData({
      showGoalModal: true,
      editingGoal: {
        id: '',
        title: '',
        description: '',
        typeIndex: -1,
        target: '',
        deadline: '',
        progress: 0,
        status: 'active'
      }
    });
  },

  // 打开目标详情
  openGoal(e) {
    const goal = e.currentTarget.dataset.goal;
    this.setData({
      selectedGoal: goal,
      showGoalDetail: true
    });
  },

  // 从详情编辑目标
  editGoalFromDetail() {
    const goal = this.data.selectedGoal;
    const typeIndex = this.data.goalTypes.findIndex(type => type.id === goal.type);
    
    this.setData({
      showGoalDetail: false,
      showGoalModal: true,
      editingGoal: {
        id: goal.id,
        title: goal.title,
        description: goal.description,
        typeIndex: typeIndex,
        target: goal.target.toString(),
        deadline: goal.deadline,
        progress: goal.progress,
        status: goal.status
      }
    });
  },

  // 隐藏目标弹窗
  hideGoalModal() {
    this.setData({
      showGoalModal: false
    });
  },

  // 隐藏目标详情
  hideGoalDetail() {
    this.setData({
      showGoalDetail: false
    });
  },

  // 目标表单输入
  onGoalTitleInput(e) {
    this.setData({
      'editingGoal.title': e.detail.value
    });
  },

  onGoalDescInput(e) {
    this.setData({
      'editingGoal.description': e.detail.value
    });
  },

  onGoalTypeChange(e) {
    this.setData({
      'editingGoal.typeIndex': parseInt(e.detail.value)
    });
  },

  onGoalTargetInput(e) {
    this.setData({
      'editingGoal.target': e.detail.value
    });
  },

  onGoalDeadlineChange(e) {
    this.setData({
      'editingGoal.deadline': e.detail.value
    });
  },

  // 保存目标
  saveGoal() {
    const goal = this.data.editingGoal;
    
    // 验证表单
    if (!goal.title.trim()) {
      wx.showToast({
        title: '请输入目标标题',
        icon: 'none'
      });
      return;
    }
    
    if (goal.typeIndex === -1) {
      wx.showToast({
        title: '请选择目标类型',
        icon: 'none'
      });
      return;
    }
    
    if (!goal.target || isNaN(goal.target)) {
      wx.showToast({
        title: '请输入有效的目标数值',
        icon: 'none'
      });
      return;
    }
    
    if (!goal.deadline) {
      wx.showToast({
        title: '请选择截止日期',
        icon: 'none'
      });
      return;
    }
    
    // 构建目标对象
    const goalType = this.data.goalTypes[goal.typeIndex];
    const newGoal = {
      id: goal.id || Date.now().toString(),
      title: goal.title.trim(),
      description: goal.description.trim(),
      type: goalType.id,
      target: parseInt(goal.target),
      current: goal.id ? goal.current : 0,
      progress: goal.id ? goal.progress : 0,
      deadline: goal.deadline,
      status: goal.status,
      createdAt: goal.id ? goal.createdAt : new Date().toISOString().split('T')[0]
    };
    
    // 添加格式化字段
    const deadline = new Date(newGoal.deadline);
    const now = new Date();
    const remainingDays = Math.ceil((deadline - now) / (1000 * 60 * 60 * 24));
    
    newGoal.deadlineText = this.formatDate(newGoal.deadline);
    newGoal.remainingDays = Math.max(0, remainingDays);
    newGoal.statusText = this.getGoalStatusText(newGoal.status);
    newGoal.createdAtText = this.formatDate(newGoal.createdAt);
    
    // 更新目标列表
    let goals = this.data.goals.slice();
    if (goal.id) {
      // 编辑现有目标
      const index = goals.findIndex(g => g.id === goal.id);
      if (index !== -1) {
        goals[index] = newGoal;
      }
    } else {
      // 添加新目标
      goals.unshift(newGoal);
    }
    
    this.setData({
      goals: goals,
      showGoalModal: false
    });
    
    wx.showToast({
      title: goal.id ? '目标已更新' : '目标已添加',
      icon: 'success'
    });
  },

  // 阻止事件冒泡
  preventClose() {
    // 阻止点击模态框内容时关闭
  }
});