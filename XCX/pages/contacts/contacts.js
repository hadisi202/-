// pages/contacts/contacts.js
Page({
  data: {
    // 统计数据
    stats: {
      total: 0,
      groups: 0,
      favorites: 0,
      recent: 0
    },
    
    // 搜索和筛选
    searchText: '',
    currentFilter: 'all', // all, favorites, recent, groups
    currentSort: 'name', // name, recent, created
    
    // 联系人列表
    contacts: [],
    filteredContacts: [],
    groupedContacts: [],
    
    // 字母索引
    alphabetList: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '#'],
    currentAlphabet: '',
    
    // 分组
    groups: [],
    groupOptions: [],
    
    // 弹窗状态
    showContactModal: false,
    showContactOptions: false,
    showContactDetail: false,
    showGroupModal: false,
    
    // 编辑中的联系人
    editingContact: {
      id: '',
      name: '',
      phone: '',
      email: '',
      company: '',
      position: '',
      department: '',
      avatar: '',
      groupIndex: -1,
      tags: [],
      notes: '',
      isFavorite: false
    },
    
    // 选中的联系人
    selectedContact: {},
    
    // 输入字段
    inputTag: '',
    newGroupName: '',
    
    // 空状态文本
    emptyText: '暂无联系人'
  },

  onLoad() {
    // 检查登录状态
    const app = getApp()
    if (!app.checkPageAccess('/pages/contacts/contacts')) {
      return
    }
    this.loadContacts();
    this.loadGroups();
  },

  onShow() {
    this.loadContacts();
  },

  onPullDownRefresh() {
    this.loadContacts();
    this.loadGroups();
    wx.stopPullDownRefresh();
  },

  // 加载联系人列表
  loadContacts() {
    const app = getApp();
    let contacts = app.globalData.contacts || [];
    
    // 处理联系人数据
    contacts = contacts.map(contact => {
      const nameInitial = this.getNameInitial(contact.name);
      const group = this.data.groups.find(g => g.id === contact.groupId);
      
      return {
        id: contact.id,
        name: contact.name,
        phone: contact.phone,
        email: contact.email,
        company: contact.company,
        position: contact.position,
        department: contact.department,
        avatar: contact.avatar,
        groupId: contact.groupId,
        tags: contact.tags,
        notes: contact.notes,
        isFavorite: contact.isFavorite,
        lastContactTime: contact.lastContactTime,
        createdAt: contact.createdAt,
        updatedAt: contact.updatedAt,
        nameInitial: nameInitial,
        groupName: group ? group.name : '未分组',
        createdAtText: this.formatDate(contact.createdAt),
        lastContactTimeText: contact.lastContactTime ? this.formatRelativeTime(contact.lastContactTime) : ''
      };
    });
    
    this.setData({
      contacts: contacts
    });
    
    this.calculateStats();
    this.filterAndSortContacts();
  },

  // 加载分组
  loadGroups() {
    const app = getApp();
    let groups = app.globalData.contactGroups || [];
    
    // 确保有默认分组
    if (groups.length === 0) {
      groups = [
        { id: 'default', name: '默认分组', icon: '👥', isDefault: true, count: 0 },
        { id: 'family', name: '家人', icon: '👨‍👩‍👧‍👦', isDefault: false, count: 0 },
        { id: 'friends', name: '朋友', icon: '👫', isDefault: false, count: 0 },
        { id: 'colleagues', name: '同事', icon: '👔', isDefault: false, count: 0 }
      ];
      app.globalData.contactGroups = groups;
      app.utils.setStorage('contactGroups', groups);
    }
    
    // 计算每个分组的联系人数量
    const contacts = this.data.contacts;
    groups = groups.map(group => {
      const count = contacts.filter(contact => contact.groupId === group.id).length;
      return { id: group.id, name: group.name, icon: group.icon, isDefault: group.isDefault, count: count };
    });
    
    // 构建分组选项
    const groupOptions = [{ id: '', name: '未分组' }].concat(groups);
    
    this.setData({
      groups: groups,
      groupOptions: groupOptions,
      stats: {
        total: this.data.stats.total,
        favorites: this.data.stats.favorites,
        recent: this.data.stats.recent,
        groups: groups.length
      }
    });
  },

  // 计算统计数据
  calculateStats() {
    const contacts = this.data.contacts;
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    const stats = {
      total: contacts.length,
      groups: this.data.groups.length,
      favorites: contacts.filter(contact => contact.isFavorite).length,
      recent: contacts.filter(contact => {
        return contact.lastContactTime && new Date(contact.lastContactTime) > sevenDaysAgo;
      }).length
    };
    
    this.setData({ stats });
  },

  // 获取姓名首字母
  getNameInitial(name) {
    if (!name) return '#';
    
    const firstChar = name.charAt(0).toUpperCase();
    
    // 检查是否为英文字母
    if (/^[A-Z]$/.test(firstChar)) {
      return firstChar;
    }
    
    // 中文姓名取第一个字
    return firstChar;
  },

  // 格式化日期
  formatDate(dateString) {
    const app = getApp();
    return app.utils.formatDate(new Date(dateString), 'YYYY-MM-DD');
  },

  // 格式化相对时间
  formatRelativeTime(dateString) {
    const app = getApp();
    return app.utils.formatRelativeTime(new Date(dateString));
  },

  // 搜索输入
  onSearchInput(e) {
    this.setData({
      searchText: e.detail.value
    });
    this.filterAndSortContacts();
  },

  // 切换筛选
  switchFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    this.setData({
      currentFilter: filter
    });
    this.filterAndSortContacts();
  },

  // 切换排序
  switchSort(e) {
    const sort = e.currentTarget.dataset.sort;
    this.setData({
      currentSort: sort
    });
    this.filterAndSortContacts();
  },

  // 筛选和排序联系人
  filterAndSortContacts() {
    let contacts = this.data.contacts.slice();
    const { searchText, currentFilter, currentSort } = this.data;
    
    // 搜索筛选
    if (searchText) {
      contacts = contacts.filter(contact => 
        contact.name.toLowerCase().includes(searchText.toLowerCase()) ||
        (contact.phone && contact.phone.includes(searchText)) ||
        (contact.email && contact.email.toLowerCase().includes(searchText.toLowerCase())) ||
        (contact.company && contact.company.toLowerCase().includes(searchText.toLowerCase())) ||
        (contact.position && contact.position.toLowerCase().includes(searchText.toLowerCase()))
      );
    }
    
    // 状态筛选
    if (currentFilter !== 'all') {
      switch (currentFilter) {
        case 'favorites':
          contacts = contacts.filter(contact => contact.isFavorite);
          break;
        case 'recent':
          const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
          contacts = contacts.filter(contact => {
            return contact.lastContactTime && new Date(contact.lastContactTime) > sevenDaysAgo;
          });
          break;
      }
    }
    
    // 排序
    contacts.sort((a, b) => {
      switch (currentSort) {
        case 'name':
          return a.name.localeCompare(b.name, 'zh-CN');
        case 'recent':
          const aTime = a.lastContactTime ? new Date(a.lastContactTime) : new Date(0);
          const bTime = b.lastContactTime ? new Date(b.lastContactTime) : new Date(0);
          return bTime - aTime;
        case 'created':
          return new Date(b.createdAt) - new Date(a.createdAt);
        default:
          return 0;
      }
    });
    
    this.setData({
      filteredContacts: contacts
    });
    
    // 如果按姓名排序且没有搜索，生成分组数据
    if (currentSort === 'name' && !searchText) {
      this.generateGroupedContacts(contacts);
    } else {
      this.setData({
        groupedContacts: []
      });
    }
    
    this.updateEmptyText();
  },

  // 生成按字母分组的联系人
  generateGroupedContacts(contacts) {
    const grouped = {};
    
    contacts.forEach(contact => {
      const initial = this.getNameInitial(contact.name);
      const letter = /^[A-Z]$/.test(initial) ? initial : '#';
      
      if (!grouped[letter]) {
        grouped[letter] = [];
      }
      grouped[letter].push(contact);
    });
    
    const groupedContacts = Object.keys(grouped)
      .sort((a, b) => {
        if (a === '#') return 1;
        if (b === '#') return -1;
        return a.localeCompare(b);
      })
      .map(letter => ({
        letter,
        contacts: grouped[letter]
      }));
    
    this.setData({
      groupedContacts: groupedContacts
    });
  },

  // 更新空状态文本
  updateEmptyText() {
    let emptyText = '暂无联系人';
    
    if (this.data.searchText) {
      emptyText = '未找到相关联系人';
    } else {
      switch (this.data.currentFilter) {
        case 'favorites':
          emptyText = '暂无收藏联系人';
          break;
        case 'recent':
          emptyText = '最近7天无联系记录';
          break;
      }
    }
    
    this.setData({ emptyText });
  },

  // 跳转到字母
  jumpToAlphabet(e) {
    const alphabet = e.currentTarget.dataset.alphabet;
    this.setData({
      currentAlphabet: alphabet
    });
    
    // 滚动到对应位置
    wx.pageScrollTo({
      selector: `#alphabet-${alphabet}`,
      duration: 300
    });
  },

  // 打开分组
  openGroup(e) {
    const group = e.currentTarget.dataset.group;
    
    // 筛选该分组的联系人
    const groupContacts = this.data.contacts.filter(contact => contact.groupId === group.id);
    
    this.setData({
      filteredContacts: groupContacts,
      currentFilter: 'group',
      searchText: ''
    });
    
    wx.setNavigationBarTitle({
      title: group.name
    });
  },

  // 打开联系人
  openContact(e) {
    const contact = e.currentTarget.dataset.contact;
    this.setData({
      selectedContact: contact,
      showContactDetail: true
    });
    
    // 更新最近联系时间
    this.updateLastContactTime(contact.id);
  },

  // 更新最近联系时间
  updateLastContactTime(contactId) {
    const app = getApp();
    let contacts = app.globalData.contacts || [];
    
    const index = contacts.findIndex(c => c.id === contactId);
    if (index !== -1) {
      contacts[index].lastContactTime = new Date().toISOString();
      app.globalData.contacts = contacts;
      app.utils.setStorage('contacts', contacts);
    }
  },

  // 显示联系人选项
  showContactOptions(e) {
    const contact = e.currentTarget.dataset.contact;
    this.setData({
      selectedContact: contact,
      showContactOptions: true
    });
  },

  // 隐藏联系人选项
  hideContactOptions() {
    this.setData({
      showContactOptions: false
    });
  },

  // 隐藏联系人详情
  hideContactDetail() {
    this.setData({
      showContactDetail: false
    });
  },

  // 从详情编辑
  editFromDetail() {
    this.editContact();
    this.hideContactDetail();
  },

  // 创建联系人
  createContact() {
    this.resetEditingContact();
    this.setData({
      showContactModal: true
    });
  },

  // 重置编辑中的联系人
  resetEditingContact() {
    this.setData({
      editingContact: {
        id: '',
        name: '',
        phone: '',
        email: '',
        company: '',
        position: '',
        department: '',
        avatar: '',
        groupIndex: -1,
        tags: [],
        notes: '',
        isFavorite: false
      },
      inputTag: ''
    });
  },

  // 隐藏联系人弹窗
  hideContactModal() {
    this.setData({
      showContactModal: false
    });
  },

  // 选择头像
  selectAvatar() {
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        this.setData({
          'editingContact.avatar': res.tempFilePaths[0]
        });
      }
    });
  },

  // 表单输入处理
  onNameInput(e) {
    this.setData({
      'editingContact.name': e.detail.value
    });
  },

  onPhoneInput(e) {
    this.setData({
      'editingContact.phone': e.detail.value
    });
  },

  onEmailInput(e) {
    this.setData({
      'editingContact.email': e.detail.value
    });
  },

  onCompanyInput(e) {
    this.setData({
      'editingContact.company': e.detail.value
    });
  },

  onPositionInput(e) {
    this.setData({
      'editingContact.position': e.detail.value
    });
  },

  onDepartmentInput(e) {
    this.setData({
      'editingContact.department': e.detail.value
    });
  },

  onNotesInput(e) {
    this.setData({
      'editingContact.notes': e.detail.value
    });
  },

  // 分组选择
  onGroupChange(e) {
    this.setData({
      'editingContact.groupIndex': parseInt(e.detail.value)
    });
  },

  // 收藏切换
  onFavoriteChange(e) {
    this.setData({
      'editingContact.isFavorite': e.detail.value
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
    
    const tags = this.data.editingContact.tags || [];
    if (tags.includes(tag)) {
      wx.showToast({
        title: '标签已存在',
        icon: 'none'
      });
      return;
    }
    
    tags.push(tag);
    this.setData({
      'editingContact.tags': tags,
      inputTag: ''
    });
  },

  // 移除标签
  removeTag(e) {
    const tag = e.currentTarget.dataset.tag;
    const tags = this.data.editingContact.tags.filter(t => t !== tag);
    this.setData({
      'editingContact.tags': tags
    });
  },

  // 保存联系人
  saveContact() {
    const contact = this.data.editingContact;
    
    if (!contact.name.trim()) {
      wx.showToast({
        title: '请输入姓名',
        icon: 'none'
      });
      return;
    }
    
    const app = getApp();
    let contacts = app.globalData.contacts || [];
    
    // 获取分组ID
    const groupId = contact.groupIndex >= 0 ? this.data.groupOptions[contact.groupIndex].id : '';
    
    if (contact.id) {
      // 编辑联系人
      const index = contacts.findIndex(c => c.id === contact.id);
      if (index !== -1) {
        contacts[index] = {
          id: contacts[index].id,
          name: contact.name.trim(),
          phone: contact.phone.trim(),
          email: contact.email.trim(),
          company: contact.company.trim(),
          position: contact.position.trim(),
          department: contact.department.trim(),
          avatar: contact.avatar,
          groupId: groupId,
          tags: contact.tags,
          notes: contact.notes.trim(),
          isFavorite: contact.isFavorite,
          lastContactTime: contacts[index].lastContactTime,
          createdAt: contacts[index].createdAt,
          updatedAt: new Date().toISOString()
        };
      }
    } else {
      // 新建联系人
      const newContact = {
        id: app.utils.generateId(),
        name: contact.name.trim(),
        phone: contact.phone.trim(),
        email: contact.email.trim(),
        company: contact.company.trim(),
        position: contact.position.trim(),
        department: contact.department.trim(),
        avatar: contact.avatar,
        groupId: groupId,
        tags: contact.tags,
        notes: contact.notes.trim(),
        isFavorite: contact.isFavorite,
        lastContactTime: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      contacts.unshift(newContact);
    }
    
    app.globalData.contacts = contacts;
    app.utils.setStorage('contacts', contacts);
    
    this.hideContactModal();
    this.loadContacts();
    
    wx.showToast({
      title: contact.id ? '联系人已更新' : '联系人已添加',
      icon: 'success'
    });
  },

  // 编辑联系人
  editContact() {
    const contact = this.data.selectedContact;
    const groupIndex = this.data.groupOptions.findIndex(g => g.id === contact.groupId);
    
    this.setData({
      editingContact: {
        id: contact.id,
        name: contact.name,
        phone: contact.phone || '',
        email: contact.email || '',
        company: contact.company || '',
        position: contact.position || '',
        department: contact.department || '',
        avatar: contact.avatar || '',
        groupIndex: groupIndex >= 0 ? groupIndex : -1,
        tags: contact.tags || [],
        notes: contact.notes || '',
        isFavorite: contact.isFavorite || false
      },
      showContactOptions: false,
      showContactModal: true
    });
  },

  // 切换收藏
  toggleFavorite() {
    const contact = this.data.selectedContact;
    const app = getApp();
    let contacts = app.globalData.contacts || [];
    
    const index = contacts.findIndex(c => c.id === contact.id);
    if (index !== -1) {
      contacts[index].isFavorite = !contacts[index].isFavorite;
      contacts[index].updatedAt = new Date().toISOString();
      
      app.globalData.contacts = contacts;
      app.utils.setStorage('contacts', contacts);
      
      this.hideContactOptions();
      this.loadContacts();
      
      wx.showToast({
        title: contacts[index].isFavorite ? '已添加到收藏' : '已取消收藏',
        icon: 'success'
      });
    }
  },

  // 分享联系人
  shareContact() {
    const contact = this.data.selectedContact;
    
    let shareText = `联系人名片\n\n姓名：${contact.name}`;
    if (contact.phone) shareText += `\n手机：${contact.phone}`;
    if (contact.email) shareText += `\n邮箱：${contact.email}`;
    if (contact.company) shareText += `\n公司：${contact.company}`;
    if (contact.position) shareText += `\n职位：${contact.position}`;
    
    wx.setClipboardData({
      data: shareText,
      success: () => {
        wx.showToast({
          title: '名片信息已复制',
          icon: 'success'
        });
      }
    });
    
    this.hideContactOptions();
  },

  // 复制联系人
  duplicateContact() {
    const contact = this.data.selectedContact;
    const app = getApp();
    let contacts = app.globalData.contacts || [];
    
    const newContact = {
      id: app.utils.generateId(),
      name: contact.name + ' - 副本',
      phone: contact.phone,
      email: contact.email,
      company: contact.company,
      position: contact.position,
      department: contact.department,
      avatar: contact.avatar,
      groupId: contact.groupId,
      tags: contact.tags,
      notes: contact.notes,
      isFavorite: contact.isFavorite,
      lastContactTime: '',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    contacts.unshift(newContact);
    app.globalData.contacts = contacts;
    app.utils.setStorage('contacts', contacts);
    
    this.hideContactOptions();
    this.loadContacts();
    
    wx.showToast({
      title: '联系人已复制',
      icon: 'success'
    });
  },

  // 删除联系人
  deleteContact() {
    const contact = this.data.selectedContact;
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除联系人"${contact.name}"吗？此操作不可恢复。`,
      confirmColor: '#ff4757',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          let contacts = app.globalData.contacts || [];
          
          contacts = contacts.filter(c => c.id !== contact.id);
          app.globalData.contacts = contacts;
          app.utils.setStorage('contacts', contacts);
          
          this.hideContactOptions();
          this.loadContacts();
          
          wx.showToast({
            title: '联系人已删除',
            icon: 'success'
          });
        }
      }
    });
  },

  // 拨打电话
  callContact(e) {
    const phone = e.currentTarget.dataset.phone;
    if (!phone) return;
    
    wx.makePhoneCall({
      phoneNumber: phone,
      fail: () => {
        wx.showToast({
          title: '拨打失败',
          icon: 'none'
        });
      }
    });
  },

  // 发送短信
  messageContact(e) {
    const contact = e.currentTarget.dataset.contact;
    if (!contact.phone) {
      wx.showToast({
        title: '该联系人没有手机号',
        icon: 'none'
      });
      return;
    }
    
    // 这里可以集成短信发送功能
    wx.showToast({
      title: '短信功能开发中',
      icon: 'none'
    });
  },

  // 发送邮件
  emailContact(e) {
    const email = e.currentTarget.dataset.email;
    if (!email) return;
    
    // 这里可以集成邮件发送功能
    wx.showToast({
      title: '邮件功能开发中',
      icon: 'none'
    });
  },

  // 导入联系人
  importContacts() {
    wx.showModal({
      title: '导入联系人',
      content: '是否从手机通讯录导入联系人？',
      success: (res) => {
        if (res.confirm) {
          // 这里可以集成通讯录导入功能
          wx.showToast({
            title: '导入功能开发中',
            icon: 'none'
          });
        }
      }
    });
  },

  // 扫描名片
  scanCard() {
    wx.scanCode({
      success: (res) => {
        // 这里可以集成名片识别功能
        wx.showToast({
          title: '名片识别功能开发中',
          icon: 'none'
        });
      },
      fail: () => {
        wx.showToast({
          title: '扫描失败',
          icon: 'none'
        });
      }
    });
  },

  // 管理分组
  manageGroups() {
    this.setData({
      showGroupModal: true,
      newGroupName: ''
    });
  },

  // 隐藏分组弹窗
  hideGroupModal() {
    this.setData({
      showGroupModal: false
    });
  },

  // 新分组名称输入
  onNewGroupNameInput(e) {
    this.setData({
      newGroupName: e.detail.value
    });
  },

  // 添加分组
  addGroup() {
    const name = this.data.newGroupName.trim();
    if (!name) {
      wx.showToast({
        title: '请输入分组名称',
        icon: 'none'
      });
      return;
    }
    
    const app = getApp();
    let groups = app.globalData.contactGroups || [];
    
    // 检查分组名是否已存在
    if (groups.some(g => g.name === name)) {
      wx.showToast({
        title: '分组名已存在',
        icon: 'none'
      });
      return;
    }
    
    const newGroup = {
      id: app.utils.generateId(),
      name: name,
      icon: '📁',
      isDefault: false,
      count: 0
    };
    
    groups.push(newGroup);
    app.globalData.contactGroups = groups;
    app.utils.setStorage('contactGroups', groups);
    
    this.setData({
      newGroupName: ''
    });
    
    this.loadGroups();
    
    wx.showToast({
      title: '分组已添加',
      icon: 'success'
    });
  },

  // 编辑分组
  editGroup(e) {
    const group = e.currentTarget.dataset.group;
    
    wx.showModal({
      title: '编辑分组',
      content: '功能开发中',
      showCancel: false
    });
  },

  // 删除分组
  deleteGroup(e) {
    const group = e.currentTarget.dataset.group;
    
    if (group.count > 0) {
      wx.showToast({
        title: '该分组下还有联系人，无法删除',
        icon: 'none'
      });
      return;
    }
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除分组"${group.name}"吗？`,
      confirmColor: '#ff4757',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          let groups = app.globalData.contactGroups || [];
          
          groups = groups.filter(g => g.id !== group.id);
          app.globalData.contactGroups = groups;
          app.utils.setStorage('contactGroups', groups);
          
          this.loadGroups();
          
          wx.showToast({
            title: '分组已删除',
            icon: 'success'
          });
        }
      }
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