// pages/docs/docs.js
Page({
  data: {
    // 统计数据
    stats: {
      total: 0,
      recent: 0,
      shared: 0,
      favorites: 0
    },
    
    // 搜索和筛选
    searchText: '',
    currentFilter: 'all', // all, recent, shared, favorites
    currentSort: 'updatedAt', // updatedAt, createdAt, title, size
    
    // 文档列表
    docs: [],
    filteredDocs: [],
    
    // 弹窗状态
    showDocModal: false,
    showDocOptions: false,
    showTemplates: false,
    showEditor: false,
    
    // 编辑中的文档
    editingDoc: {
      id: '',
      title: '',
      description: '',
      type: 'text',
      tags: [],
      isShared: false,
      permissionIndex: 0
    },
    
    // 选中的文档
    selectedDoc: {},
    currentDoc: {},
    
    // 标签输入
    inputTag: '',
    
    // 权限选项
    permissionOptions: ['仅查看', '可编辑', '可管理'],
    
    // 模板列表
    templates: [
      {
        id: 'meeting-notes',
        title: '会议纪要',
        description: '记录会议内容和决议',
        type: 'text',
        icon: '📝',
        content: '# 会议纪要\n\n**会议时间：** \n**参会人员：** \n**会议主题：** \n\n## 会议内容\n\n## 决议事项\n\n## 后续行动\n'
      },
      {
        id: 'project-plan',
        title: '项目计划',
        description: '制定项目计划和时间表',
        type: 'markdown',
        icon: '📋',
        content: '# 项目计划\n\n## 项目概述\n\n## 项目目标\n\n## 时间计划\n\n## 资源分配\n\n## 风险评估\n'
      },
      {
        id: 'weekly-report',
        title: '周报模板',
        description: '记录本周工作总结',
        type: 'text',
        icon: '📊',
        content: '# 周报\n\n## 本周完成工作\n\n## 下周工作计划\n\n## 遇到的问题\n\n## 需要的支持\n'
      },
      {
        id: 'task-list',
        title: '任务清单',
        description: '管理任务和进度',
        type: 'table',
        icon: '✅',
        content: '# 任务清单\n\n| 任务 | 负责人 | 截止时间 | 状态 |\n|------|--------|----------|------|\n|      |        |          |      |\n'
      }
    ],
    
    // 空状态文本
    emptyText: '暂无文档'
  },

  onLoad(options) {
    // 检查登录状态
    const app = getApp()
    if (!app.checkPageAccess('/pages/docs/docs')) {
      return
    }
    try {
      this.initPage()
    } catch (error) {
      console.error('Docs页面初始化失败:', error)
    }
  },

  onShow() {
    try {
      this.loadDocuments()
    } catch (error) {
      console.error('Docs页面显示失败:', error)
    }
  },

  // 初始化页面
  initPage() {
    this.loadDocs();
  },

  // 加载文档数据
  loadDocuments() {
    this.loadDocs();
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

  onPullDownRefresh() {
    this.loadDocs();
    wx.stopPullDownRefresh();
  },

  // 加载文档列表
  loadDocs() {
    const app = getApp();
    let docs = app.globalData.docs || [];
    
    // 处理文档数据
    docs = docs.map(doc => {
      return {
        id: doc.id,
        title: doc.title,
        content: doc.content,
        type: doc.type,
        size: doc.size,
        tags: doc.tags,
        shared: doc.shared,
        favorite: doc.favorite,
        createdAt: doc.createdAt,
        updatedAt: doc.updatedAt,
        description: doc.description,
        isShared: doc.isShared,
        syncStatus: doc.syncStatus,
        iconText: this.getDocIconText(doc.type),
        updatedAtText: this.formatDate(doc.updatedAt),
        sizeText: this.formatSize(doc.size),
        syncIcon: this.getSyncIcon(doc.syncStatus)
      };
    });
    
    this.setData({
      docs: docs
    });
    
    this.calculateStats();
    this.filterAndSortDocs();
  },

  // 计算统计数据
  calculateStats() {
    const docs = this.data.docs;
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    const stats = {
      total: docs.length,
      recent: docs.filter(doc => new Date(doc.updatedAt) > sevenDaysAgo).length,
      shared: docs.filter(doc => doc.isShared).length,
      favorites: docs.filter(doc => doc.isFavorite).length
    };
    
    this.setData({ stats });
  },

  // 获取文档图标文本
  getDocIconText(type) {
    const iconMap = {
      text: '📝',
      markdown: 'MD',
      table: '📊'
    };
    return iconMap[type] || '📄';
  },

  // 格式化日期
  formatDate(dateStr) {
    const app = getApp();
    return app.utils.formatRelativeTime(dateStr);
  },

  // 格式化文件大小
  formatSize(size) {
    if (!size) return '';
    if (size < 1024) return size + 'B';
    if (size < 1024 * 1024) return Math.round(size / 1024) + 'KB';
    return Math.round(size / (1024 * 1024)) + 'MB';
  },

  // 获取同步图标
  getSyncIcon(status) {
    const iconMap = {
      synced: '✅',
      syncing: '🔄',
      error: '❌'
    };
    return iconMap[status] || '';
  },

  // 搜索输入
  onSearchInput(e) {
    this.setData({
      searchText: e.detail.value
    });
    this.filterAndSortDocs();
  },

  // 切换筛选
  switchFilter(e) {
    const filter = e.currentTarget.dataset.filter;
    this.setData({
      currentFilter: filter
    });
    this.filterAndSortDocs();
  },

  // 切换排序
  switchSort(e) {
    const sort = e.currentTarget.dataset.sort;
    this.setData({
      currentSort: sort
    });
    this.filterAndSortDocs();
  },

  // 筛选和排序文档
  filterAndSortDocs() {
    let docs = this.data.docs.slice();
    const { searchText, currentFilter, currentSort } = this.data;
    
    // 搜索筛选
    if (searchText) {
      docs = docs.filter(doc => 
        doc.title.toLowerCase().includes(searchText.toLowerCase()) ||
        (doc.description && doc.description.toLowerCase().includes(searchText.toLowerCase())) ||
        (doc.tags && doc.tags.some(tag => tag.toLowerCase().includes(searchText.toLowerCase())))
      );
    }
    
    // 类型筛选
    if (currentFilter !== 'all') {
      const now = new Date();
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      
      switch (currentFilter) {
        case 'recent':
          docs = docs.filter(doc => new Date(doc.updatedAt) > sevenDaysAgo);
          break;
        case 'shared':
          docs = docs.filter(doc => doc.isShared);
          break;
        case 'favorites':
          docs = docs.filter(doc => doc.isFavorite);
          break;
      }
    }
    
    // 排序
    docs.sort((a, b) => {
      switch (currentSort) {
        case 'updatedAt':
          return new Date(b.updatedAt) - new Date(a.updatedAt);
        case 'createdAt':
          return new Date(b.createdAt) - new Date(a.createdAt);
        case 'title':
          return a.title.localeCompare(b.title);
        case 'size':
          return (b.size || 0) - (a.size || 0);
        default:
          return 0;
      }
    });
    
    this.setData({
      filteredDocs: docs
    });
    
    this.updateEmptyText();
  },

  // 更新空状态文本
  updateEmptyText() {
    let emptyText = '暂无文档';
    
    if (this.data.searchText) {
      emptyText = '未找到相关文档';
    } else {
      switch (this.data.currentFilter) {
        case 'recent':
          emptyText = '最近没有编辑过的文档';
          break;
        case 'shared':
          emptyText = '暂无共享文档';
          break;
        case 'favorites':
          emptyText = '暂无收藏的文档';
          break;
      }
    }
    
    this.setData({ emptyText });
  },

  // 切换收藏状态
  toggleFavorite(e) {
    const id = e.currentTarget.dataset.id;
    const app = getApp();
    let docs = app.globalData.docs || [];
    
    const docIndex = docs.findIndex(doc => doc.id === id);
    if (docIndex !== -1) {
      docs[docIndex].isFavorite = !docs[docIndex].isFavorite;
      docs[docIndex].updatedAt = new Date().toISOString();
      
      app.globalData.docs = docs;
      app.utils.setStorage('documents', docs);
      
      this.loadDocs();
      
      wx.showToast({
        title: docs[docIndex].isFavorite ? '已收藏' : '已取消收藏',
        icon: 'success'
      });
    }
  },

  // 创建文档
  createDocument() {
    this.resetEditingDoc();
    this.setData({
      showDocModal: true
    });
  },

  // 重置编辑中的文档
  resetEditingDoc() {
    this.setData({
      editingDoc: {
        id: '',
        title: '',
        description: '',
        type: 'text',
        tags: [],
        isShared: false,
        permissionIndex: 0
      },
      inputTag: ''
    });
  },

  // 隐藏文档弹窗
  hideDocModal() {
    this.setData({
      showDocModal: false
    });
  },

  // 表单输入处理
  onTitleInput(e) {
    this.setData({
      'editingDoc.title': e.detail.value
    });
  },

  onDescInput(e) {
    this.setData({
      'editingDoc.description': e.detail.value
    });
  },

  // 选择文档类型
  selectType(e) {
    const type = e.currentTarget.dataset.type;
    let updateData = {
      'editingDoc.type': type
    };
    
    // 如果选择表格类型，提供默认表格数据
    if (type === 'table') {
      updateData['editingDoc.content'] = this.getDefaultTableContent();
    }
    
    this.setData(updateData);
  },
  
  // 获取默认表格内容
  getDefaultTableContent() {
    return `姓名,年龄,部门,职位
张三,28,技术部,工程师
李四,32,市场部,经理
王五,25,人事部,专员`;
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
    
    const tags = this.data.editingDoc.tags || [];
    if (tags.includes(tag)) {
      wx.showToast({
        title: '标签已存在',
        icon: 'none'
      });
      return;
    }
    
    tags.push(tag);
    this.setData({
      'editingDoc.tags': tags,
      inputTag: ''
    });
  },

  // 移除标签
  removeTag(e) {
    const tag = e.currentTarget.dataset.tag;
    const tags = this.data.editingDoc.tags.filter(t => t !== tag);
    this.setData({
      'editingDoc.tags': tags
    });
  },

  // 共享设置变化
  onShareChange(e) {
    this.setData({
      'editingDoc.isShared': e.detail.value
    });
  },

  // 权限变化
  onPermissionChange(e) {
    this.setData({
      'editingDoc.permissionIndex': parseInt(e.detail.value)
    });
  },

  // 保存文档
  saveDocument() {
    const doc = this.data.editingDoc;
    
    if (!doc.title.trim()) {
      wx.showToast({
        title: '请输入文档标题',
        icon: 'none'
      });
      return;
    }
    
    const app = getApp();
    let docs = app.globalData.docs || [];
    const now = new Date().toISOString();
    
    if (doc.id) {
      // 编辑文档
      const index = docs.findIndex(d => d.id === doc.id);
      if (index !== -1) {
        // 创建编辑历史记录
        const editRecord = {
          id: app.utils.generateId(),
          userId: 'current_user',
          userName: '我',
          action: 'edit',
          timestamp: now,
          changes: {
            type: 'metadata_update',
            description: '文档信息已更新'
          }
        };
        
        const updatedEditHistory = (docs[index].editHistory || []).concat([editRecord]).slice(-50);
        
        docs[index] = {
          id: docs[index].id,
          content: docs[index].content,
          size: docs[index].size,
          shared: docs[index].shared,
          favorite: docs[index].favorite,
          createdAt: docs[index].createdAt,
          syncStatus: docs[index].syncStatus,
          title: doc.title.trim(),
          description: doc.description.trim(),
          type: doc.type,
          tags: doc.tags,
          isShared: doc.isShared,
          permission: this.data.permissionOptions[doc.permissionIndex],
          updatedAt: now,
          lastEditTime: now,
          editHistory: updatedEditHistory
        };
      }
    } else {
      // 新建文档
      const newDoc = {
        id: app.utils.generateId(),
        title: doc.title.trim(),
        description: doc.description.trim(),
        type: doc.type,
        tags: doc.tags,
        content: doc.type === 'table' ? (doc.content || this.getDefaultTableContent()) : '',
        isShared: doc.isShared,
        permission: this.data.permissionOptions[doc.permissionIndex],
        isFavorite: false,
        size: 0,
        syncStatus: 'synced',
        author: '我',
        collaborators: [],
        editHistory: [],
        isOnlineEditing: doc.isShared,
        lastEditTime: now,
        createdAt: now,
        updatedAt: now
      };
      
      // 如果是表格类型，添加表格数据
      if (doc.type === 'table') {
        newDoc.tableData = this.parseTableData('table', { content: newDoc.content });
      }
      docs.unshift(newDoc);
    }
    
    app.globalData.docs = docs;
    app.utils.setStorage('documents', docs);
    
    this.hideDocModal();
    this.loadDocs();
    
    wx.showToast({
      title: doc.id ? '文档已更新' : '文档已创建',
      icon: 'success'
    });
  },

  // 打开文档
  openDocument(e) {
    const item = e.currentTarget.dataset.item;
    
    // 初始化协同编辑状态
    const collaborativeData = {
      onlineUsers: [
        { id: 'current_user', name: '我', avatar: '/images/avatar-default.png', isCurrentUser: true },
        // 模拟其他在线用户
        { id: 'user_2', name: '张三', avatar: '/images/avatar-2.png', isCurrentUser: false },
        { id: 'user_3', name: '李四', avatar: '/images/avatar-3.png', isCurrentUser: false }
      ],
      editHistory: item.editHistory || [],
      lastSyncTime: new Date().toLocaleString(),
      conflictResolution: 'none', // none, pending, resolved
      isCollaborativeMode: item.isShared && item.isOnlineEditing
    };
    
    this.setData({
      currentDoc: {
        id: item.id,
        title: item.title,
        type: item.type,
        size: item.size,
        tags: item.tags,
        shared: item.shared,
        favorite: item.favorite,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        description: item.description,
        isShared: item.isShared,
        syncStatus: item.syncStatus,
        content: item.content || '',
        wordCount: (item.content || '').length,
        saveStatus: 'saved',
        saveStatusText: '已保存',
        collaborators: item.collaborators || [],
        isOnlineEditing: item.isOnlineEditing || false,
        lastEditTime: item.lastEditTime || item.updatedAt,
        editHistory: item.editHistory || [],
        tableData: item.tableData || null,
        isEditMode: item.isEditMode || false,
        format: {
          bold: false,
          italic: false,
          underline: false
        },
        showPreview: false,
        formattedContent: ''
      },
      showEditor: true,
      collaborativeData: collaborativeData
    });
    
    // 如果是协同编辑模式，启动实时同步
    if (collaborativeData.isCollaborativeMode) {
      this.startCollaborativeEditing();
    }
  },

  // 隐藏编辑器
  hideEditor() {
    // 停止协同编辑
    this.stopCollaborativeEditing();
    
    this.setData({
      showEditor: false,
      collaborativeData: null
    });
  },

  // 内容输入
  onContentInput(e) {
    const content = e.detail.value;
    this.setData({
      'currentDoc.content': content,
      'currentDoc.wordCount': content.length,
      'currentDoc.saveStatus': 'saving',
      'currentDoc.saveStatusText': '保存中...'
    });
    
    // 模拟自动保存
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => {
      this.saveCurrentDoc();
    }, 1000);
  },

  // 保存当前文档
  saveCurrentDoc() {
    const { currentDoc, collaborativeData } = this.data;
    if (!currentDoc) return;
    
    const app = getApp();
    let docs = app.globalData.docs || [];
    
    const index = docs.findIndex(d => d.id === currentDoc.id);
    if (index !== -1) {
      const now = new Date().toISOString();
      
      // 创建编辑历史记录
      const editRecord = {
        id: app.utils.generateId(),
        userId: 'current_user',
        userName: '我',
        action: 'edit',
        timestamp: now,
        contentLength: currentDoc.content.length,
        changes: {
          type: 'content_update',
          description: '文档内容已更新'
        }
      };
      
      const updatedEditHistory = (currentDoc.editHistory || []).concat([editRecord]).slice(-50);
      
      docs[index] = Object.assign({}, docs[index], {
         content: currentDoc.content,
         size: currentDoc.content.length,
         updatedAt: now,
         lastEditTime: now,
         editHistory: updatedEditHistory
       });
      
      app.globalData.docs = docs;
      app.utils.setStorage('documents', docs);
      
      this.setData({
        'currentDoc.saveStatus': 'saved',
        'currentDoc.saveStatusText': '已保存',
        'currentDoc.editHistory': updatedEditHistory,
        'currentDoc.lastEditTime': now
      });
      
      // 如果是协同编辑模式，更新同步时间
      if (collaborativeData && collaborativeData.isCollaborativeMode) {
        this.setData({
          'collaborativeData.lastSyncTime': new Date().toLocaleString()
        });
        this.broadcastDocumentUpdate(editRecord);
      }
    }
  },

  // 完成编辑
  completeEditing() {
    const { currentDoc } = this.data;
    
    if (!currentDoc || !currentDoc.title || !currentDoc.title.trim()) {
      wx.showToast({
        title: '请输入文档标题',
        icon: 'none'
      });
      return;
    }
    
    // 先保存文档
    this.saveCurrentDoc();
    
    // 延迟关闭编辑器，确保保存完成
    setTimeout(() => {
      this.setData({
        showEditor: false,
        currentDoc: {},
        editorFocus: false
      });
      
      wx.showToast({
        title: '编辑完成',
        icon: 'success'
      });
    }, 500);
  },

  // 切换格式状态
  toggleFormat(e) {
    const format = e.currentTarget.dataset.format;
    const currentDoc = this.data.currentDoc;
    
    if (!currentDoc.format) {
      currentDoc.format = {};
    }
    
    currentDoc.format[format] = !currentDoc.format[format];
    
    this.setData({
      currentDoc: currentDoc
    });
    
    wx.showToast({
      title: `${format === 'bold' ? '粗体' : format === 'italic' ? '斜体' : '下划线'}${currentDoc.format[format] ? '已开启' : '已关闭'}`,
      icon: 'none',
      duration: 1000
    });
  },

  // 插入格式
  insertFormat(e) {
    const format = e.currentTarget.dataset.format;
    const currentDoc = this.data.currentDoc;
    let insertText = '';
    
    switch(format) {
      case 'h1':
        insertText = '# 标题一\n';
        break;
      case 'h2':
        insertText = '## 标题二\n';
        break;
      case 'h3':
        insertText = '### 标题三\n';
        break;
      case 'list':
        insertText = '• 列表项\n';
        break;
      case 'number':
        insertText = '1. 编号列表\n';
        break;
      case 'quote':
        insertText = '> 引用文本\n';
        break;
      case 'link':
        insertText = '[链接文本](https://example.com)';
        break;
      case 'image':
        this.insertImage();
        return;
      case 'table':
        insertText = '| 列1 | 列2 | 列3 |\n|-----|-----|-----|\n| 内容1 | 内容2 | 内容3 |\n';
        break;
    }
    
    currentDoc.content = (currentDoc.content || '') + insertText;
    currentDoc.wordCount = currentDoc.content.length;
    
    this.setData({
      currentDoc: currentDoc,
      editorFocus: true
    });
    
    // 更新格式化内容
    this.updateFormattedContent();
  },

  // 插入图片
  insertImage() {
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const tempFilePath = res.tempFilePaths[0];
        const currentDoc = this.data.currentDoc;
        const imageText = `![图片](${tempFilePath})`;
        
        currentDoc.content = (currentDoc.content || '') + imageText;
        currentDoc.wordCount = currentDoc.content.length;
        
        this.setData({
          currentDoc: currentDoc
        });
        
        this.updateFormattedContent();
        
        wx.showToast({
          title: '图片已插入',
          icon: 'success'
        });
      }
    });
  },

  // 切换编辑模式
  switchEditorMode(e) {
    const mode = e.currentTarget.dataset.mode;
    const currentDoc = this.data.currentDoc;
    
    currentDoc.showPreview = (mode === 'preview');
    
    this.setData({
      currentDoc: currentDoc,
      editorFocus: !currentDoc.showPreview
    });
    
    if (currentDoc.showPreview) {
      this.updateFormattedContent();
    }
  },

  // 更新格式化内容
  updateFormattedContent() {
    const currentDoc = this.data.currentDoc;
    let content = currentDoc.content || '';
    
    // 简单的Markdown转换
    content = content
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^• (.*$)/gim, '<li>$1</li>')
      .replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>')
      .replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<a href="$2">$1</a>')
      .replace(/!\[([^\]]*)\]\(([^\)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto;" />')
      .replace(/\n/g, '<br/>');
    
    // 处理列表
    content = content.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    
    currentDoc.formattedContent = content;
    
    this.setData({
      currentDoc: currentDoc
    });
  },

  // 插入模板
  insertTemplate(e) {
    const template = e.currentTarget.dataset.template;
    const content = this.data.currentDoc.content || '';
    let insertText = '';
    
    switch (template) {
      case 'heading':
        insertText = '\n# 标题\n';
        break;
      case 'bold':
        insertText = '**粗体文本**';
        break;
      case 'italic':
        insertText = '*斜体文本*';
        break;
      case 'list':
        insertText = '\n- 列表项\n';
        break;
    }
    
    this.setData({
      'currentDoc.content': content + insertText,
      'currentDoc.wordCount': (content + insertText).length
    });
  },

  // 显示文档选项
  showDocOptions(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      selectedDoc: item,
      showDocOptions: true
    });
  },

  // 隐藏文档选项
  hideDocOptions() {
    this.setData({
      showDocOptions: false
    });
  },

  // 编辑文档
  editDocument() {
    const doc = this.data.selectedDoc;
    this.setData({
      editingDoc: {
        id: doc.id,
        title: doc.title,
        description: doc.description || '',
        type: doc.type,
        tags: doc.tags || [],
        isShared: doc.isShared || false,
        permissionIndex: this.data.permissionOptions.indexOf(doc.permission) || 0
      },
      showDocOptions: false,
      showDocModal: true
    });
  },

  // 复制文档
  duplicateDocument() {
    const doc = this.data.selectedDoc;
    const app = getApp();
    let docs = app.globalData.docs || [];
    
    const newDoc = {
      content: doc.content,
      type: doc.type,
      size: doc.size,
      tags: doc.tags,
      shared: doc.shared,
      favorite: doc.favorite,
      description: doc.description,
      syncStatus: doc.syncStatus,
      id: app.utils.generateId(),
      title: doc.title + ' - 副本',
      isShared: false,
      isFavorite: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    docs.unshift(newDoc);
    app.globalData.docs = docs;
    app.utils.setStorage('documents', docs);
    
    this.hideDocOptions();
    this.loadDocs();
    
    wx.showToast({
      title: '文档已复制',
      icon: 'success'
    });
  },

  // 分享文档
  shareDocument() {
    const doc = this.data.selectedDoc;
    
    wx.showActionSheet({
      itemList: ['分享给好友', '生成分享链接', '导出为图片'],
      success: (res) => {
        switch (res.tapIndex) {
          case 0:
            // 分享给好友
            wx.showToast({
              title: '分享功能开发中',
              icon: 'none'
            });
            break;
          case 1:
            // 生成分享链接
            wx.setClipboardData({
              data: `文档分享：${doc.title}\n链接：https://example.com/doc/${doc.id}`,
              success: () => {
                wx.showToast({
                  title: '链接已复制',
                  icon: 'success'
                });
              }
            });
            break;
          case 2:
            // 导出为图片
            wx.showToast({
              title: '导出功能开发中',
              icon: 'none'
            });
            break;
        }
      }
    });
    
    this.hideDocOptions();
  },

  // 导出文档
  exportDocument() {
    const doc = this.data.selectedDoc;
    
    wx.showActionSheet({
      itemList: ['导出为文本', '导出为PDF', '导出为Word'],
      success: (res) => {
        const formats = ['TXT', 'PDF', 'Word'];
        wx.showToast({
          title: `${formats[res.tapIndex]}导出功能开发中`,
          icon: 'none'
        });
      }
    });
    
    this.hideDocOptions();
  },

  // 移动到文件夹
  moveToFolder() {
    wx.showToast({
      title: '文件夹功能开发中',
      icon: 'none'
    });
    this.hideDocOptions();
  },

  // 删除文档
  deleteDocument() {
    const doc = this.data.selectedDoc;
    
    wx.showModal({
      title: '确认删除',
      content: `确定要删除文档"${doc.title}"吗？此操作不可恢复。`,
      confirmColor: '#ff4757',
      success: (res) => {
        if (res.confirm) {
          const app = getApp();
          let docs = app.globalData.docs || [];
          
          docs = docs.filter(d => d.id !== doc.id);
          app.globalData.docs = docs;
          app.utils.setStorage('documents', docs);
          
          this.hideDocOptions();
          this.loadDocs();
          
          wx.showToast({
            title: '文档已删除',
            icon: 'success'
          });
        }
      }
    });
  },

  // 导入文档
  importDocument() {
    wx.showActionSheet({
      itemList: ['从相册选择', '从文件选择', '调用WPS打开'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.importFromAlbum()
        } else if (res.tapIndex === 1) {
          this.importFromFile()
        } else if (res.tapIndex === 2) {
          this.openWithWPS()
        }
      }
    })
  },

  // 从相册导入
  importFromAlbum() {
    wx.chooseImage({
      count: 1,
      sizeType: ['original'],
      sourceType: ['album'],
      success: (res) => {
        const tempFilePath = res.tempFilePaths[0]
        this.processImageDocument(tempFilePath)
      }
    })
  },

  // 从文件导入
  importFromFile() {
    wx.chooseMessageFile({
      count: 5, // 支持多文件选择
      type: 'file',
      extension: ['doc', 'docx', 'pdf', 'txt', 'md', 'csv', 'xlsx', 'xls', 'ppt', 'pptx'],
      success: (res) => {
        this.processImportedFiles(res.tempFiles);
      },
      fail: () => {
        wx.showToast({
          title: '导入失败',
          icon: 'none'
        });
      }
    });
  },

  // 调用WPS打开文档
  openWithWPS() {
    wx.showModal({
      title: 'WPS文档操作',
      content: '选择要进行的操作',
      confirmText: '新建文档',
      cancelText: '打开文档',
      success: (res) => {
        if (res.confirm) {
          this.createWPSDocument()
        } else {
          this.openExistingWPSDocument()
        }
      }
    })
  },

  // 创建WPS文档
  createWPSDocument() {
    wx.showActionSheet({
      itemList: ['Word文档', 'Excel表格', 'PowerPoint演示'],
      success: (res) => {
        const docTypes = ['word', 'excel', 'ppt']
        const docType = docTypes[res.tapIndex]
        
        // 模拟调用WPS API
        wx.showLoading({
          title: '正在启动WPS...'
        })
        
        setTimeout(() => {
          wx.hideLoading()
          
          // 创建新文档记录
          const app = getApp();
          const newDoc = {
            id: app.utils.generateId(),
            title: `新建${docType === 'word' ? 'Word' : docType === 'excel' ? 'Excel' : 'PPT'}文档_${new Date().toLocaleDateString()}`,
            content: '',
            type: docType,
            size: 0,
            tags: ['WPS创建'],
            isShared: false,
            isFavorite: false,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            wpsIntegration: true,
            externalPath: '' // WPS文档路径
          }
          
          const docs = app.globalData.docs || []
          docs.unshift(newDoc)
          app.globalData.docs = docs
          
          wx.showModal({
            title: 'WPS文档已创建',
            content: '文档已在WPS中打开，编辑完成后将自动同步到小程序',
            showCancel: false
          })
          
          this.loadDocs()
        }, 2000)
      }
    })
  },

  // 打开现有WPS文档
  openExistingWPSDocument() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'],
      success: (res) => {
        const file = res.tempFiles[0]
        
        wx.showLoading({
          title: '正在用WPS打开...'
        })
        
        setTimeout(() => {
          wx.hideLoading()
          
          wx.showModal({
            title: 'WPS文档已打开',
            content: `文档 "${file.name}" 已在WPS中打开，编辑完成后将自动同步`,
            showCancel: false
          })
          
          // 创建文档记录
          this.processImportedFiles([file])
        }, 2000)
      }
    })
  },

  // 处理图片文档
  processImageDocument(imagePath) {
    wx.showLoading({
      title: '正在识别文字...'
    })
    
    // 模拟OCR文字识别
    setTimeout(() => {
      wx.hideLoading()
      
      const app = getApp();
      const recognizedText = '这是通过OCR识别的文字内容。\n\n在实际应用中，这里会调用OCR服务来识别图片中的文字。'
      
      const newDoc = {
        id: app.utils.generateId(),
        title: `图片识别文档_${new Date().toLocaleDateString()}`,
        description: '通过OCR识别的图片文档',
        type: 'text',
        content: recognizedText,
        tags: ['OCR识别', '图片'],
        isShared: false,
        isFavorite: false,
        size: recognizedText.length,
        syncStatus: 'synced',
        author: '我',
        originalImagePath: imagePath,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
      
      const docs = app.globalData.docs || []
      docs.unshift(newDoc)
      app.globalData.docs = docs
      app.utils.setStorage('documents', docs)
      
      this.loadDocs()
      
      wx.showToast({
        title: '图片识别完成',
        icon: 'success'
      })
    }, 2000)
  },

  // 处理导入的文件
  processImportedFiles(files) {
    const app = getApp();
    let docs = app.globalData.docs || [];
    let successCount = 0;
    
    wx.showLoading({
      title: '正在处理文件...',
      mask: true
    });
    
    files.forEach((file, index) => {
      const fileExtension = this.getFileExtension(file.name);
      const fileType = this.getDocumentType(fileExtension);
      
      // 模拟文件内容解析
      const parsedContent = this.parseFileContent(file, fileExtension);
      
      const newDoc = {
        id: app.utils.generateId(),
        title: file.name.replace(/\.[^/.]+$/, ''),
        description: `导入的${fileType}文档`,
        type: fileType,
        content: parsedContent,
        originalFileName: file.name,
        fileExtension: fileExtension,
        tags: ['导入', fileType.toUpperCase()],
        isShared: true, // 默认开启共享以支持协同编辑
        isFavorite: false,
        size: file.size,
        syncStatus: 'synced',
        author: '我',
        collaborators: [], // 协作者列表
        editHistory: [], // 编辑历史
        isOnlineEditing: true, // 支持在线编辑
        isEditMode: false, // 表格编辑模式
        tableData: this.parseTableData(fileType, file), // 表格数据
        lastEditTime: new Date().toISOString(),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      
      docs.unshift(newDoc);
      successCount++;
      
      // 如果是最后一个文件，完成处理
      if (index === files.length - 1) {
        app.globalData.docs = docs;
        app.utils.setStorage('documents', docs);
        
        wx.hideLoading();
        this.loadDocs();
        
        wx.showToast({
          title: `成功导入${successCount}个文档`,
          icon: 'success'
        });
      }
    });
  },

  // 获取文件扩展名
  getFileExtension(fileName) {
    return fileName.split('.').pop().toLowerCase();
  },

  // 根据文件扩展名确定文档类型
  getDocumentType(extension) {
    const typeMap = {
      'doc': 'word',
      'docx': 'word',
      'pdf': 'pdf',
      'txt': 'text',
      'md': 'markdown',
      'csv': 'table',
      'xlsx': 'excel',
      'xls': 'excel',
      'ppt': 'presentation',
      'pptx': 'presentation'
    };
    return typeMap[extension] || 'text';
  },

  // 解析文件内容（模拟）
  parseFileContent(file, extension) {
    // 在实际应用中，这里需要调用相应的文件解析库
    const contentTemplates = {
      'word': `# ${file.name}\n\n这是从Word文档导入的内容。\n\n**文件大小：** ${this.formatFileSize(file.size)}\n**导入时间：** ${new Date().toLocaleString()}\n\n## 文档内容\n\n[Word文档内容将在这里显示]\n\n---\n*注：此文档支持多人协同编辑*`,
      'pdf': `# ${file.name}\n\n这是从PDF文档导入的内容。\n\n**文件大小：** ${this.formatFileSize(file.size)}\n**导入时间：** ${new Date().toLocaleString()}\n\n## PDF内容\n\n[PDF文档内容将在这里显示]\n\n---\n*注：此文档支持多人协同编辑*`,
      'excel': this.generateExcelContent(file),
      'table': this.generateTableContent(file),
      'presentation': `# ${file.name}\n\n这是从演示文稿导入的内容。\n\n**文件大小：** ${this.formatFileSize(file.size)}\n**导入时间：** ${new Date().toLocaleString()}\n\n## 幻灯片内容\n\n### 第1页\n[幻灯片内容]\n\n### 第2页\n[幻灯片内容]\n\n---\n*注：此文档支持多人协同编辑*`,
      'text': `# ${file.name}\n\n**文件大小：** ${this.formatFileSize(file.size)}\n**导入时间：** ${new Date().toLocaleString()}\n\n## 文本内容\n\n[文本文件内容将在这里显示]\n\n---\n*注：此文档支持多人协同编辑*`,
      'markdown': `# ${file.name}\n\n**文件大小：** ${this.formatFileSize(file.size)}\n**导入时间：** ${new Date().toLocaleString()}\n\n## Markdown内容\n\n[Markdown文档内容将在这里显示]\n\n---\n*注：此文档支持多人协同编辑*`
    };
    
    const docType = this.getDocumentType(extension);
    return contentTemplates[docType] || contentTemplates['text'];
  },

  // 生成Excel内容
  generateExcelContent(file) {
    // 模拟Excel数据解析
    const sampleData = [
      ['姓名', '年龄', '部门', '职位', '薪资'],
      ['张三', '28', '技术部', '前端工程师', '12000'],
      ['李四', '32', '产品部', '产品经理', '15000'],
      ['王五', '25', '设计部', 'UI设计师', '10000'],
      ['赵六', '30', '技术部', '后端工程师', '13000'],
      ['钱七', '27', '市场部', '市场专员', '8000'],
      ['孙八', '35', '人事部', '人事经理', '11000'],
      ['周九', '29', '财务部', '会计师', '9000'],
      ['吴十', '26', '技术部', '测试工程师', '10500']
    ];
    
    let content = `# ${file.name}\n\n`;
    content += `**文件类型：** Excel表格\n`;
    content += `**文件大小：** ${this.formatFileSize(file.size)}\n`;
    content += `**导入时间：** ${new Date().toLocaleString()}\n\n`;
    content += `## 📊 表格数据\n\n`;
    
    // 生成表格
    sampleData.forEach((row, index) => {
      if (index === 0) {
        // 表头
        content += `| ${row.join(' | ')} |\n`;
        content += `|${row.map(() => '---').join('|')}|\n`;
      } else {
        // 数据行
        content += `| ${row.join(' | ')} |\n`;
      }
    });
    
    content += `\n**数据统计：**\n`;
    content += `- 总行数：${sampleData.length - 1}\n`;
    content += `- 总列数：${sampleData[0].length}\n`;
    content += `- 数据类型：员工信息表\n\n`;
    content += `---\n*注：此文档支持多人协同编辑和实时同步*`;
    
    return content;
  },

  // 生成表格内容
  generateTableContent(file) {
    // 模拟CSV数据解析
    const sampleData = [
      ['产品名称', '销售数量', '单价', '总金额', '销售日期'],
      ['iPhone 14', '120', '5999', '719880', '2024-01-15'],
      ['MacBook Pro', '45', '12999', '584955', '2024-01-16'],
      ['iPad Air', '89', '4399', '391511', '2024-01-17'],
      ['Apple Watch', '156', '2499', '389844', '2024-01-18'],
      ['AirPods Pro', '234', '1899', '444366', '2024-01-19']
    ];
    
    let content = `# ${file.name}\n\n`;
    content += `**文件类型：** CSV表格\n`;
    content += `**文件大小：** ${this.formatFileSize(file.size)}\n`;
    content += `**导入时间：** ${new Date().toLocaleString()}\n\n`;
    content += `## 📈 数据表格\n\n`;
    
    // 生成表格
    sampleData.forEach((row, index) => {
      if (index === 0) {
        // 表头
        content += `| ${row.join(' | ')} |\n`;
        content += `|${row.map(() => '---').join('|')}|\n`;
      } else {
        // 数据行
        content += `| ${row.join(' | ')} |\n`;
      }
    });
    
    content += `\n**数据摘要：**\n`;
    content += `- 记录总数：${sampleData.length - 1}\n`;
    content += `- 字段数量：${sampleData[0].length}\n`;
    content += `- 数据类型：销售记录\n\n`;
    content += `---\n*注：此文档支持多人协同编辑和数据分析*`;
    
    return content;
   },

   // 解析表格数据
   parseTableData(fileType, file) {
     if (fileType === 'excel') {
       // 模拟Excel数据解析
       return [
         ['姓名', '年龄', '部门', '职位', '薪资'],
         ['张三', '28', '技术部', '前端工程师', '12000'],
         ['李四', '32', '产品部', '产品经理', '15000'],
         ['王五', '25', '设计部', 'UI设计师', '10000'],
         ['赵六', '30', '技术部', '后端工程师', '13000'],
         ['钱七', '27', '市场部', '市场专员', '8000'],
         ['孙八', '35', '人事部', '人事经理', '11000'],
         ['周九', '29', '财务部', '会计师', '9000'],
         ['吴十', '26', '技术部', '测试工程师', '10500']
       ];
     } else if (fileType === 'table') {
       // 模拟CSV数据解析
       return [
         ['产品名称', '销售数量', '单价', '总金额', '销售日期'],
         ['iPhone 14', '120', '5999', '719880', '2024-01-15'],
         ['MacBook Pro', '45', '12999', '584955', '2024-01-16'],
         ['iPad Air', '89', '4399', '391511', '2024-01-17'],
         ['Apple Watch', '156', '2499', '389844', '2024-01-18'],
         ['AirPods Pro', '234', '1899', '444366', '2024-01-19']
       ];
     }
     return null;
   },

   // 切换编辑模式
   toggleEditMode() {
     const { currentDoc } = this.data;
     if (!currentDoc || (currentDoc.type !== 'excel' && currentDoc.type !== 'table')) {
       return;
     }
     
     this.setData({
       'currentDoc.isEditMode': !currentDoc.isEditMode
     });
     
     wx.showToast({
       title: currentDoc.isEditMode ? '已切换到编辑模式' : '已切换到预览模式',
       icon: 'none',
       duration: 1500
     });
   },
   
   // 添加表格行
   addTableRow() {
     const { currentDoc } = this.data;
     if (!currentDoc || !currentDoc.tableData) return;
     
     const tableData = [...currentDoc.tableData];
     const columnCount = tableData[0] ? tableData[0].length : 4;
     const newRow = new Array(columnCount).fill('');
     
     tableData.push(newRow);
     
     this.setData({
       'currentDoc.tableData': tableData
     });
     
     wx.showToast({
       title: '已添加新行',
       icon: 'success',
       duration: 1000
     });
   },
   
   // 保存表格数据
   saveTableData() {
     const { currentDoc } = this.data;
     if (!currentDoc || !currentDoc.tableData) return;
     
     // 将表格数据转换为CSV格式
     const csvContent = currentDoc.tableData.map(row => row.join(',')).join('\n');
     
     this.setData({
       'currentDoc.content': csvContent
     });
     
     // 保存到本地存储
     const app = getApp();
     let docs = app.globalData.docs || [];
     const docIndex = docs.findIndex(d => d.id === currentDoc.id);
     
     if (docIndex !== -1) {
       docs[docIndex].content = csvContent;
       docs[docIndex].tableData = currentDoc.tableData;
       docs[docIndex].updatedAt = new Date().toISOString();
       
       app.globalData.docs = docs;
       app.utils.setStorage('documents', docs);
     }
     
     wx.showToast({
       title: '表格已保存',
       icon: 'success'
     });
   },
   
   // 处理单元格输入
   onCellInput(e) {
     const { value } = e.detail;
     const { row, col } = e.currentTarget.dataset;
     const { currentDoc } = this.data;
     
     if (!currentDoc || !currentDoc.tableData) return;
     
     const tableData = [...currentDoc.tableData];
     tableData[row][col] = value;
     
     this.setData({
       'currentDoc.tableData': tableData
     });
   },
 
   // 格式化文件大小
  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  // 扫描文档
  scanDocument() {
    wx.scanCode({
      success: (res) => {
        wx.showToast({
          title: '扫描功能开发中',
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
    
    const app = getApp();
    let docs = app.globalData.docs || [];
    
    const newDoc = {
      id: app.utils.generateId(),
      title: template.title,
      description: template.description,
      type: template.type,
      content: template.content,
      tags: ['模板'],
      isShared: false,
      isFavorite: false,
      size: template.content.length,
      syncStatus: 'synced',
      author: '我',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    docs.unshift(newDoc);
    app.globalData.docs = docs;
    app.utils.setStorage('documents', docs);
    
    this.hideTemplates();
    this.loadDocs();
    
    // 直接打开编辑器
    this.setData({
      currentDoc: {
        id: newDoc.id,
        title: newDoc.title,
        content: newDoc.content,
        type: newDoc.type,
        size: newDoc.size,
        tags: newDoc.tags,
        shared: newDoc.shared,
        favorite: newDoc.favorite,
        createdAt: newDoc.createdAt,
        updatedAt: newDoc.updatedAt,
        description: newDoc.description,
        isShared: newDoc.isShared,
        syncStatus: newDoc.syncStatus,
        wordCount: newDoc.content.length,
        saveStatus: 'saved',
        saveStatusText: '已保存',
        format: {
          bold: false,
          italic: false,
          underline: false
        },
        showPreview: false,
        formattedContent: ''
      },
      showEditor: true
    });
    
    wx.showToast({
      title: '模板已创建',
      icon: 'success'
    });
  },

  // 阻止事件冒泡
  preventBubble() {
    // 阻止事件冒泡
  },

  // 阻止关闭
  preventClose() {
    // 阻止关闭
  },

  // 启动协同编辑
  startCollaborativeEditing() {
    // 启动协同编辑模式
    
    // 模拟实时同步定时器
    this.collaborativeTimer = setInterval(() => {
      this.syncCollaborativeChanges();
    }, 5000); // 每5秒同步一次
    
    // 模拟用户状态更新
    this.userStatusTimer = setInterval(() => {
      this.updateOnlineUsers();
    }, 10000); // 每10秒更新用户状态
  },

  // 停止协同编辑
  stopCollaborativeEditing() {
    if (this.collaborativeTimer) {
      clearInterval(this.collaborativeTimer);
      this.collaborativeTimer = null;
    }
    
    if (this.userStatusTimer) {
      clearInterval(this.userStatusTimer);
      this.userStatusTimer = null;
    }
  },

  // 同步协同编辑变更
  syncCollaborativeChanges() {
    const { collaborativeData } = this.data;
    if (!collaborativeData || !collaborativeData.isCollaborativeMode) return;
    
    // 模拟检测到其他用户的编辑
    const hasRemoteChanges = Math.random() > 0.7; // 30%概率有远程更改
    
    if (hasRemoteChanges) {
      const remoteEditRecord = {
        id: Date.now().toString(),
        userId: 'user_2',
        userName: '张三',
        action: 'edit',
        timestamp: new Date().toISOString(),
        changes: {
          type: 'remote_update',
          description: '张三编辑了文档'
        }
      };
      
      this.setData({
        'collaborativeData.lastSyncTime': new Date().toISOString()
      });
      
      // 显示协同编辑提示
      wx.showToast({
        title: '文档已同步',
        icon: 'none',
        duration: 1000
      });
    }
  },

  // 更新在线用户状态
  updateOnlineUsers() {
    const { collaborativeData } = this.data;
    if (!collaborativeData) return;
    
    // 模拟用户上线/下线
    const shouldUpdateUsers = Math.random() > 0.6;
    
    if (shouldUpdateUsers) {
      const possibleUsers = [
        { id: 'user_2', name: '张三', avatar: '/images/avatar-2.png', isCurrentUser: false },
        { id: 'user_3', name: '李四', avatar: '/images/avatar-3.png', isCurrentUser: false },
        { id: 'user_4', name: '王五', avatar: '/images/avatar-4.png', isCurrentUser: false },
        { id: 'user_5', name: '赵六', avatar: '/images/avatar-5.png', isCurrentUser: false }
      ];
      
      // 随机选择1-3个在线用户
      const onlineCount = Math.floor(Math.random() * 3) + 1;
      const randomUsers = possibleUsers.sort(() => 0.5 - Math.random()).slice(0, onlineCount);
      
      const updatedOnlineUsers = [{ id: 'current_user', name: '我', avatar: '/images/avatar-default.png', isCurrentUser: true }].concat(randomUsers);
      
      this.setData({
        'collaborativeData.onlineUsers': updatedOnlineUsers
      });
    }
  },

  // 广播文档更新
  broadcastDocumentUpdate(editRecord) {
    // 广播文档更新
    // 在实际应用中，这里会通过WebSocket或其他实时通信方式广播更新
  },

  // 切换协同编辑模式
  toggleCollaborativeMode() {
    const { currentDoc, collaborativeData } = this.data;
    if (!currentDoc) return;
    
    const newCollaborativeMode = !collaborativeData.isCollaborativeMode;
    
    this.setData({
      'currentDoc.isOnlineEditing': newCollaborativeMode,
      'currentDoc.isShared': newCollaborativeMode,
      'collaborativeData.isCollaborativeMode': newCollaborativeMode
    });
    
    if (newCollaborativeMode) {
      this.startCollaborativeEditing();
      wx.showToast({
        title: '已开启协同编辑',
        icon: 'success'
      });
    } else {
      this.stopCollaborativeEditing();
      wx.showToast({
        title: '已关闭协同编辑',
        icon: 'none'
      });
    }
    
    // 保存设置
     this.saveDocument();
  },

  // 查看编辑历史
  viewEditHistory() {
    const { currentDoc } = this.data;
    if (!currentDoc || !currentDoc.editHistory) {
      wx.showToast({
        title: '暂无编辑历史',
        icon: 'none'
      });
      return;
    }
    
    this.setData({
      showEditHistory: true
    });
  },

  // 隐藏编辑历史
  hideEditHistory() {
    this.setData({
      showEditHistory: false
    });
  },

  // 邀请协作者
  inviteCollaborator() {
    wx.showModal({
      title: '邀请协作者',
      content: '请输入协作者的邮箱或用户名',
      editable: true,
      placeholderText: '邮箱或用户名',
      success: (res) => {
        if (res.confirm && res.content) {
          // 模拟添加协作者
          const newCollaborator = {
            id: Date.now().toString(),
            name: res.content,
            email: res.content.includes('@') ? res.content : `${res.content}@example.com`,
            avatar: '/images/avatar-default.png',
            role: 'editor',
            invitedAt: new Date().toISOString()
          };
          
          const { currentDoc } = this.data;
          const updatedCollaborators = (currentDoc.collaborators || []).concat([newCollaborator]);
          
          this.setData({
            'currentDoc.collaborators': updatedCollaborators
          });
          
          wx.showToast({
            title: '邀请已发送',
            icon: 'success'
          });
          
          this.saveDocument();
        }
      }
    });
  }
});