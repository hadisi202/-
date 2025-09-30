// pages/meeting/meeting.js
Page({
  data: {
    // 统计数据
    stats: {
      total: 0,
      today: 0,
      upcoming: 0,
      completed: 0
    },
    
    // 搜索和筛选
    searchText: '',
    currentFilter: 'all', // all, today, upcoming, completed
    currentSort: 'startTime', // startTime, createdAt, title
    
    // 会议列表
    meetings: [],
    filteredMeetings: [],
    
    // 弹窗状态
    showMeetingModal: false,
    showMeetingOptions: false,
    showTemplates: false,
    showNotes: false,
    showJoinModal: false,
    
    // 编辑中的会议
    editingMeeting: {
      id: '',
      title: '',
      description: '',
      startDate: '',
      startTime: '',
      durationIndex: 2,
      type: 'online',
      location: '',
      meetingLink: '',
      attendees: [],
      reminderIndex: 1,
      tags: []
    },
    
    // 选中的会议
    selectedMeeting: {},
    currentMeeting: {},
    
    // 输入字段
    inputAttendee: '',
    inputTag: '',
    joinMeetingId: '',
    joinMeetingName: '',
    
    // 选项数据
    durationOptions: ['15分钟', '30分钟', '45分钟', '60分钟', '90分钟', '120分钟', '自定义'],
    reminderOptions: ['不提醒', '5分钟前', '10分钟前', '15分钟前', '30分钟前', '1小时前', '1天前'],
    
    // 会议模板
    meetingTemplates: [
      {
        id: 'daily-standup',
        title: '每日站会',
        description: '团队每日同步会议',
        duration: 15,
        icon: '🏃',
        agenda: '1. 昨日完成工作\n2. 今日计划\n3. 遇到的问题'
      },
      {
        id: 'weekly-review',
        title: '周会回顾',
        description: '每周工作回顾和计划',
        duration: 60,
        icon: '📊',
        agenda: '1. 本周工作总结\n2. 下周工作计划\n3. 问题讨论'
      },
      {
        id: 'project-kickoff',
        title: '项目启动',
        description: '新项目启动会议',
        duration: 90,
        icon: '🚀',
        agenda: '1. 项目背景介绍\n2. 目标和范围\n3. 团队分工\n4. 时间计划'
      },
      {
        id: 'brainstorm',
        title: '头脑风暴',
        description: '创意讨论会议',
        duration: 45,
        icon: '💡',
        agenda: '1. 问题定义\n2. 想法收集\n3. 方案讨论\n4. 下一步行动'
      }
    ],
    
    // 空状态文本
    emptyText: '暂无会议'
  },

  onLoad() {
    // 检查登录状态
    const app = getApp()
    if (!app.checkPageAccess('/pages/meeting/meeting')) {
      return
    }
    this.loadMeetings();
  },

  onShow() {
    this.loadMeetings();
  },

  onPullDownRefresh() {
    this.loadMeetings();
    wx.stopPullDownRefresh();
  },

  // 加载会议列表
  loadMeetings() {
    const app = getApp();
    let meetings = app.globalData.meetings || [];
    
    // 处理会议数据
    meetings = meetings.map(meeting => {
      const status = this.getMeetingStatus(meeting);
      return {
        id: meeting.id,
        title: meeting.title,
        startTime: meeting.startTime,
        endTime: meeting.endTime,
        location: meeting.location,
        attendees: meeting.attendees,
        description: meeting.description,
        notes: meeting.notes,
        createdAt: meeting.createdAt,
        updatedAt: meeting.updatedAt,
        status: status,
        timeText: this.formatMeetingTime(meeting),
        attendeesText: this.formatAttendees(meeting.attendees)
      };
    });
    
    this.setData({
      meetings: meetings
    });
    
    this.calculateStats();
    this.filterAndSortMeetings();
  },

  // 计算统计数据
  calculateStats() {
    const meetings = this.data.meetings;
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);
    
    const stats = {
      total: meetings.length,
      today: meetings.filter(meeting => {
        const meetingDate = new Date(meeting.startTime);
        return meetingDate >= today && meetingDate < tomorrow;
      }).length,
      upcoming: meetings.filter(meeting => meeting.status === 'upcoming').length,
      completed: meetings.filter(meeting => meeting.status === 'completed').length
    };
    
    this.setData({ stats });
  },

  // 获取会议状态
  getMeetingStatus(meeting) {
    const now = new Date();
    const startTime = new Date(meeting.startTime);
    const endTime = new Date(startTime.getTime() + (meeting.duration || 60) * 60 * 1000);
    
    if (meeting.cancelled) {
      return 'cancelled';
    } else if (now < startTime) {
      return 'upcoming';
    } else if (now >= startTime && now <= endTime) {
      return 'ongoing';
    } else {
      return 'completed';
    }
  },

  // 格式化会议时间
  formatMeetingTime(meeting) {
    const startTime = new Date(meeting.startTime);
    const app = getApp();
    
    const dateStr = app.utils.formatDate(startTime, 'MM-DD');
    const timeStr = app.utils.formatDate(startTime, 'HH:mm');
    
    const today = new Date();
    const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);
    
    if (startTime.toDateString() === today.toDateString()) {
      return `今天 ${timeStr}`;
    } else if (startTime.toDateString() === tomorrow.toDateString()) {
      return `明天 ${timeStr}`;
    } else {
      return `${dateStr} ${timeStr}`;
    }
  },

  // 格式化参会人员
  formatAttendees(attendees) {
    if (!attendees || attendees.length === 0) {
      return '无参会人员';
    }
    
    if (attendees.length <= 3) {
      return attendees.join('、');
    } else {
      return `${attendees.slice(0, 2).join('、')} 等${attendees.length}人`;
    }
  },

  // 搜索输入
  onSearchInput(e) {
    this.setData({
      searchText: e.detail.value
    });
    this.filterAndSortMeetings();
  },

  // 切换筛选
  switchFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    this.setData({
      currentFilter: filter
    });
    this.filterAndSortMeetings();
  },

  // 切换排序
  switchSort(e) {
    const sort = e.currentTarget.dataset.sort;
    this.setData({
      currentSort: sort
    });
    this.filterAndSortMeetings();
  },

  // 筛选和排序会议
  filterAndSortMeetings() {
    let meetings = this.data.meetings.slice();
    const { searchText, currentFilter, currentSort } = this.data;
    
    // 搜索筛选
    if (searchText) {
      meetings = meetings.filter(meeting => 
        meeting.title.toLowerCase().includes(searchText.toLowerCase()) ||
        (meeting.description && meeting.description.toLowerCase().includes(searchText.toLowerCase())) ||
        (meeting.attendees && meeting.attendees.some(attendee => attendee.toLowerCase().includes(searchText.toLowerCase())))
      );
    }
    
    // 状态筛选
    if (currentFilter !== 'all') {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000);
      
      switch (currentFilter) {
        case 'today':
          meetings = meetings.filter(meeting => {
            const meetingDate = new Date(meeting.startTime);
            return meetingDate >= today && meetingDate < tomorrow;
          });
          break;
        case 'upcoming':
          meetings = meetings.filter(meeting => meeting.status === 'upcoming');
          break;
        case 'completed':
          meetings = meetings.filter(meeting => meeting.status === 'completed');
          break;
      }
    }
    
    // 排序
    meetings.sort((a, b) => {
      switch (currentSort) {
        case 'startTime':
          return new Date(a.startTime) - new Date(b.startTime);
        case 'createdAt':
          return new Date(b.createdAt) - new Date(a.createdAt);
        case 'title':
          return a.title.localeCompare(b.title);
        default:
          return 0;
      }
    });
    
    this.setData({
      filteredMeetings: meetings
    });
    
    this.updateEmptyText();
  },

  // 更新空状态文本
  updateEmptyText() {
    let emptyText = '暂无会议';
    
    if (this.data.searchText) {
      emptyText = '未找到相关会议';
    } else {
      switch (this.data.currentFilter) {
        case 'today':
          emptyText = '今天没有安排会议';
          break;
        case 'upcoming':
          emptyText = '暂无即将开始的会议';
          break;
        case 'completed':
          emptyText = '暂无已完成的会议';
          break;
      }
    }
    
    this.setData({ emptyText });
  },

  // 创建会议
  createMeeting() {
    this.resetEditingMeeting();
    this.setData({
      showMeetingModal: true
    });
  },

  // 重置编辑中的会议
  resetEditingMeeting() {
    const now = new Date();
    const defaultDate = now.toISOString().split('T')[0];
    const defaultTime = `${String(now.getHours()).padStart(2, '0')}:${String(Math.ceil(now.getMinutes() / 15) * 15).padStart(2, '0')}`;
    
    this.setData({
      editingMeeting: {
        id: '',
        title: '',
        description: '',
        startDate: defaultDate,
        startTime: defaultTime,
        durationIndex: 2,
        type: 'online',
        location: '',
        meetingLink: '',
        attendees: [],
        reminderIndex: 1,
        tags: []
      },
      inputAttendee: '',
      inputTag: ''
    });
  },

  // 隐藏会议弹窗
  hideMeetingModal() {
    this.setData({
      showMeetingModal: false
    });
  },

  // 表单输入处理
  onTitleInput(e) {
    this.setData({
      'editingMeeting.title': e.detail.value
    });
  },

  onDescInput(e) {
    this.setData({
      'editingMeeting.description': e.detail.value
    });
  },

  onStartDateChange(e) {
    this.setData({
      'editingMeeting.startDate': e.detail.value
    });
  },

  onStartTimeChange(e) {
    this.setData({
      'editingMeeting.startTime': e.detail.value
    });
  },

  onDurationChange(e) {
    this.setData({
      'editingMeeting.durationIndex': parseInt(e.detail.value)
    });
  },

  // 选择会议类型
  selectMeetingType(e) {
    const type = e.currentTarget.dataset.type;
    this.setData({
      'editingMeeting.type': type
    });
  },

  // 地点/链接输入
  onLocationInput(e) {
    const value = e.detail.value;
    if (this.data.editingMeeting.type === 'online') {
      this.setData({
        'editingMeeting.meetingLink': value
      });
    } else {
      this.setData({
        'editingMeeting.location': value
      });
    }
  },

  // 参会人员输入
  onAttendeeInput(e) {
    this.setData({
      inputAttendee: e.detail.value
    });
  },

  // 添加参会人员
  addAttendee() {
    const attendee = this.data.inputAttendee.trim();
    if (!attendee) return;
    
    const attendees = this.data.editingMeeting.attendees || [];
    if (attendees.includes(attendee)) {
      wx.showToast({
        title: '参会人员已存在',
        icon: 'none'
      });
      return;
    }
    
    attendees.push(attendee);
    this.setData({
      'editingMeeting.attendees': attendees,
      inputAttendee: ''
    });
  },

  // 移除参会人员
  removeAttendee(e) {
    const attendee = e.currentTarget.dataset.attendee;
    const attendees = this.data.editingMeeting.attendees.filter(a => a !== attendee);
    this.setData({
      'editingMeeting.attendees': attendees
    });
  },

  // 选择提醒
  selectReminder(e) {
    const index = parseInt(e.currentTarget.dataset.index);
    this.setData({
      'editingMeeting.reminderIndex': index
    });
  },

  // 标签输入
  onTagInput(e) {
    this.setData({
      inputTag: e.detail.value
    });
  },

  // 添加标签
  addTag() {
    const tag = this.data.inputTag.trim();
    if (!tag) return;
    
    const tags = this.data.editingMeeting.tags || [];
    if (tags.includes(tag)) {
      wx.showToast({
        title: '标签已存在',
        icon: 'none'
      });
      return;
    }
    
    tags.push(tag);
    this.setData({
      'editingMeeting.tags': tags,
      inputTag: ''
    });
  },

  // 移除标签
  removeTag(e) {
    const tag = e.currentTarget.dataset.tag;
    const tags = this.data.editingMeeting.tags.filter(t => t !== tag);
    this.setData({
      'editingMeeting.tags': tags
    });
  },

  // 保存会议
  saveMeeting() {
    const meeting = this.data.editingMeeting;
    
    if (!meeting.title.trim()) {
      wx.showToast({
        title: '请输入会议主题',
        icon: 'none'
      });
      return;
    }
    
    if (!meeting.startDate || !meeting.startTime) {
      wx.showToast({
        title: '请选择开始时间',
        icon: 'none'
      });
      return;
    }
    
    const app = getApp();
    let meetings = app.globalData.meetings || [];
    
    // 构建开始时间
    const startTime = new Date(`${meeting.startDate}T${meeting.startTime}:00`);
    
    // 获取时长
    const durationMap = [15, 30, 45, 60, 90, 120, 60]; // 自定义默认60分钟
    const duration = durationMap[meeting.durationIndex];
    
    if (meeting.id) {
      // 编辑会议
      const index = meetings.findIndex(m => m.id === meeting.id);
      if (index !== -1) {
        meetings[index] = {
          id: meetings[index].id,
          createdAt: meetings[index].createdAt,
          notes: meetings[index].notes,
          status: meetings[index].status,
          title: meeting.title.trim(),
          description: meeting.description.trim(),
          startTime: startTime.toISOString(),
          duration: duration,
          type: meeting.type,
          location: meeting.location.trim(),
          meetingLink: meeting.meetingLink.trim(),
          attendees: meeting.attendees,
          reminder: this.data.reminderOptions[meeting.reminderIndex],
          tags: meeting.tags,
          updatedAt: new Date().toISOString()
        };
      }
    } else {
      // 新建会议
      const newMeeting = {
        id: app.utils.generateId(),
        title: meeting.title.trim(),
        description: meeting.description.trim(),
        startTime: startTime.toISOString(),
        duration: duration,
        type: meeting.type,
        location: meeting.location.trim(),
        meetingLink: meeting.meetingLink.trim(),
        attendees: meeting.attendees,
        reminder: this.data.reminderOptions[meeting.reminderIndex],
        tags: meeting.tags,
        notes: '',
        cancelled: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      meetings.unshift(newMeeting);
      
      // 设置提醒
      this.setMeetingReminder(newMeeting);
    }
    
    app.globalData.meetings = meetings;
    app.utils.setStorage('meetings', meetings);
    
    this.hideMeetingModal();
    this.loadMeetings();
    
    wx.showToast({
      title: meeting.id ? '会议已更新' : '会议已创建',
      icon: 'success'
    });
  },

  // 设置会议提醒
  setMeetingReminder(meeting) {
    if (meeting.reminder === '不提醒') return;
    
    // 这里可以集成系统通知或其他提醒机制
    // 设置会议提醒
  },

  // 打开会议
  openMeeting(e) {
    const item = e.currentTarget.dataset.item;
    
    if (item.status === 'upcoming' || item.status === 'ongoing') {
      this.joinMeetingById(e);
    } else {
      this.showMeetingOptions(e);
    }
  },

  // 通过ID加入会议
  joinMeetingById(e) {
    const id = e.currentTarget.dataset.id || e.currentTarget.dataset.item.id;
    const meeting = this.data.meetings.find(m => m.id === id);
    
    if (!meeting) return;
    
    if (meeting.type === 'online' && meeting.meetingLink) {
      // 在线会议，打开链接
      wx.showModal({
        title: '加入在线会议',
        content: `即将跳转到会议链接：${meeting.meetingLink}`,
        confirmText: '加入',
        success: (res) => {
          if (res.confirm) {
            // 这里可以集成实际的会议系统
            wx.showToast({
              title: '会议功能开发中',
              icon: 'none'
            });
          }
        }
      });
    } else {
      // 线下会议，显示地点信息
      wx.showModal({
        title: '会议信息',
        content: `会议地点：${meeting.location || '未设置'}\n会议时间：${this.formatMeetingTime(meeting)}`,
        showCancel: false
      });
    }
  },

  // 显示会议选项
  showMeetingOptions(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      selectedMeeting: item,
      showMeetingOptions: true
    });
  },

  // 隐藏会议选项
  hideMeetingOptions() {
    this.setData({
      showMeetingOptions: false
    });
  },

  // 加入选中的会议
  joinSelectedMeeting() {
    const meeting = this.data.selectedMeeting;
    this.hideMeetingOptions();
    
    this.joinMeetingById({
      currentTarget: {
        dataset: {
          id: meeting.id
        }
      }
    });
  },

  // 编辑会议
  editMeeting() {
    const meeting = this.data.selectedMeeting;
    const startTime = new Date(meeting.startTime);
    
    this.setData({
      editingMeeting: {
        id: meeting.id,
        title: meeting.title,
        description: meeting.description || '',
        startDate: startTime.toISOString().split('T')[0],
        startTime: `${String(startTime.getHours()).padStart(2, '0')}:${String(startTime.getMinutes()).padStart(2, '0')}`,
        durationIndex: this.data.durationOptions.findIndex(d => d === `${meeting.duration}分钟`) || 2,
        type: meeting.type,
        location: meeting.location || '',
        meetingLink: meeting.meetingLink || '',
        attendees: meeting.attendees || [],
        reminderIndex: this.data.reminderOptions.indexOf(meeting.reminder) || 1,
        tags: meeting.tags || []
      },
      showMeetingOptions: false,
      showMeetingModal: true
    });
  },

  // 复制会议
  duplicateMeeting() {
    const meeting = this.data.selectedMeeting;
    const app = getApp();
    let meetings = app.globalData.meetings || [];
    
    const now = new Date();
    const newStartTime = new Date(now.getTime() + 24 * 60 * 60 * 1000); // 明天同一时间
    
    const newMeeting = {
      attendees: meeting.attendees,
      description: meeting.description,
      endTime: meeting.endTime,
      location: meeting.location,
      type: meeting.type,
      meetingLink: meeting.meetingLink,
      id: app.utils.generateId(),
      title: meeting.title + ' - 副本',
      startTime: newStartTime.toISOString(),
      notes: '',
      cancelled: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    meetings.unshift(newMeeting);
    app.globalData.meetings = meetings;
    app.utils.setStorage('meetings', meetings);
    
    this.hideMeetingOptions();
    this.loadMeetings();
    
    wx.showToast({
      title: '会议已复制',
      icon: 'success'
    });
  },

  // 查看会议纪要
  viewNotes() {
    this.openNotes({
      currentTarget: {
        dataset: {
          id: this.data.selectedMeeting.id
        }
      }
    });
    this.hideMeetingOptions();
  },

  // 打开会议纪要
  openNotes(e) {
    const id = e.currentTarget.dataset.id;
    const meeting = this.data.meetings.find(m => m.id === id);
    
    if (!meeting) return;
    
    this.setData({
      currentMeeting: {
        id: meeting.id,
        title: meeting.title,
        startTime: meeting.startTime,
        endTime: meeting.endTime,
        location: meeting.location,
        attendees: meeting.attendees,
        description: meeting.description,
        status: meeting.status,
        createdAt: meeting.createdAt,
        updatedAt: meeting.updatedAt,
        notes: meeting.notes || '',
        notesWordCount: (meeting.notes || '').length,
        notesSaveStatus: 'saved',
        notesSaveStatusText: '已保存'
      },
      showNotes: true
    });
  },

  // 隐藏会议纪要
  hideNotes() {
    this.setData({
      showNotes: false
    });
  },

  // 纪要输入
  onNotesInput(e) {
    const notes = e.detail.value;
    this.setData({
      'currentMeeting.notes': notes,
      'currentMeeting.notesWordCount': notes.length,
      'currentMeeting.notesSaveStatus': 'saving',
      'currentMeeting.notesSaveStatusText': '保存中...'
    });
    
    // 自动保存
    clearTimeout(this.notesTimer);
    this.notesTimer = setTimeout(() => {
      this.saveNotes();
    }, 1000);
  },

  // 保存纪要
  saveNotes() {
    const meeting = this.data.currentMeeting;
    const app = getApp();
    let meetings = app.globalData.meetings || [];
    
    const index = meetings.findIndex(m => m.id === meeting.id);
    if (index !== -1) {
      meetings[index].notes = meeting.notes;
      meetings[index].updatedAt = new Date().toISOString();
      
      app.globalData.meetings = meetings;
      app.utils.setStorage('meetings', meetings);
      
      this.setData({
        'currentMeeting.notesSaveStatus': 'saved',
        'currentMeeting.notesSaveStatusText': '已保存'
      });
    }
  },

  // 插入纪要模板
  insertNotesTemplate(e) {
    const template = e.currentTarget.dataset.template;
    const notes = this.data.currentMeeting.notes || '';
    let insertText = '';
    
    switch (template) {
      case 'agenda':
        insertText = '\n## 会议议程\n1. \n2. \n3. \n';
        break;
      case 'decision':
        insertText = '\n## 会议决议\n- \n- \n';
        break;
      case 'action':
        insertText = '\n## 后续行动\n- [ ] \n- [ ] \n';
        break;
    }
    
    this.setData({
      'currentMeeting.notes': notes + insertText,
      'currentMeeting.notesWordCount': (notes + insertText).length
    });
  },

  // 分享会议
  shareMeeting() {
    const meeting = this.data.selectedMeeting;
    
    const shareText = `会议邀请\n\n主题：${meeting.title}\n时间：${this.formatMeetingTime(meeting)}\n${meeting.type === 'online' ? '链接：' + (meeting.meetingLink || '待定') : '地点：' + (meeting.location || '待定')}`;
    
    wx.setClipboardData({
      data: shareText,
      success: () => {
        wx.showToast({
          title: '会议信息已复制',
          icon: 'success'
        });
      }
    });
    
    this.hideMeetingOptions();
  },

  // 取消会议
  cancelMeeting() {
    const meeting = this.data.selectedMeeting;
    
    wx.showModal({
      title: '确认取消',
      content: `确定要取消会议"${meeting.title}"吗？`,
      confirmColor: '#ff4757',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          let meetings = app.globalData.meetings || [];
          
          const index = meetings.findIndex(m => m.id === meeting.id);
          if (index !== -1) {
            meetings[index].cancelled = true;
            meetings[index].updatedAt = new Date().toISOString();
            
            app.globalData.meetings = meetings;
            app.utils.setStorage('meetings', meetings);
            
            this.hideMeetingOptions();
            this.loadMeetings();
            
            wx.showToast({
              title: '会议已取消',
              icon: 'success'
            });
          }
        }
      }
    });
  },

  // 删除会议
  deleteMeeting() {
    const meeting = this.data.selectedMeeting;
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除会议"${meeting.title}"吗？此操作不可恢复。`,
      confirmColor: '#ff4757',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          let meetings = app.globalData.meetings || [];
          
          meetings = meetings.filter(m => m.id !== meeting.id);
          app.globalData.meetings = meetings;
          app.utils.setStorage('meetings', meetings);
          
          this.hideMeetingOptions();
          this.loadMeetings();
          
          wx.showToast({
            title: '会议已删除',
            icon: 'success'
          });
        }
      }
    });
  },

  // 加入会议
  joinMeeting() {
    this.setData({
      showJoinModal: true,
      joinMeetingId: '',
      joinMeetingName: ''
    });
  },

  // 隐藏加入会议弹窗
  hideJoinModal() {
    this.setData({
      showJoinModal: false
    });
  },

  // 加入会议ID输入
  onJoinMeetingIdInput(e) {
    this.setData({
      joinMeetingId: e.detail.value
    });
  },

  // 加入会议姓名输入
  onJoinMeetingNameInput(e) {
    this.setData({
      joinMeetingName: e.detail.value
    });
  },

  // 确认加入会议
  confirmJoinMeeting() {
    const { joinMeetingId, joinMeetingName } = this.data;
    
    if (!joinMeetingId.trim()) {
      wx.showToast({
        title: '请输入会议ID或链接',
        icon: 'none'
      });
      return;
    }
    
    if (!joinMeetingName.trim()) {
      wx.showToast({
        title: '请输入您的姓名',
        icon: 'none'
      });
      return;
    }
    
    this.hideJoinModal();
    
    // 这里可以集成实际的会议系统
    wx.showToast({
      title: '会议功能开发中',
      icon: 'none'
    });
  },

  // 快速会议
  quickMeeting() {
    wx.showModal({
      title: '快速会议',
      content: '立即开始一个临时会议？',
      success: (res) => {
        if (res.confirm) {
          // 创建快速会议
          const app = getApp();
          let meetings = app.globalData.meetings || [];
          
          const quickMeeting = {
            id: app.utils.generateId(),
            title: '快速会议',
            description: '临时发起的会议',
            startTime: new Date().toISOString(),
            duration: 30,
            type: 'online',
            location: '',
            meetingLink: 'https://meet.example.com/' + app.utils.generateId(),
            attendees: [],
            reminder: '不提醒',
            tags: ['快速会议'],
            notes: '',
            cancelled: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
          };
          
          meetings.unshift(quickMeeting);
          app.globalData.meetings = meetings;
          app.utils.setStorage('meetings', meetings);
          
          this.loadMeetings();
          
          wx.showToast({
            title: '快速会议已创建',
            icon: 'success'
          });
        }
      }
    });
  },

  // 显示模板
  showTemplates() {
    this.setData({
      showTemplates: true
    });
  },

  // 隐藏模板
  hideTemplates() {
    this.setData({
      showTemplates: false
    });
  },

  // 从模板创建
  createFromTemplate(e) {
    const template = e.currentTarget.dataset.template;
    
    const now = new Date();
    const defaultDate = now.toISOString().split('T')[0];
    const defaultTime = `${String(now.getHours()).padStart(2, '0')}:${String(Math.ceil(now.getMinutes() / 15) * 15).padStart(2, '0')}`;
    
    this.setData({
      editingMeeting: {
        id: '',
        title: template.title,
        description: template.description,
        startDate: defaultDate,
        startTime: defaultTime,
        durationIndex: this.data.durationOptions.findIndex(d => d === `${template.duration}分钟`) || 2,
        type: 'online',
        location: '',
        meetingLink: '',
        attendees: [],
        reminderIndex: 1,
        tags: [template.title]
      },
      inputAttendee: '',
      inputTag: '',
      showTemplates: false,
      showMeetingModal: true
    });
  },

  // 阻止事件冒泡
  preventBubble() {
    // 阻止事件冒泡
  },

  // 阻止关闭
  preventClose() {
    // 阻止关闭
  }
});