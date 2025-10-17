const api = require('../../utils/api.js');
const cloudDiag = require('../../utils/cloud.js');

Page({
  data: {
    inputCode: '',
    result: null,
    loading: false,
    searched: false,
    // 分页状态
    pageIndex: 0, // 从 0 开始
    pageSize: 20,
    hasMore: false, // 是否还有下一页
    // 累加分页：记录每一页实际加载的数量（用于上一页回滚）
    pageLengths: []
  },

  onLoad: function (options) {
    console.log('板件查询页面加载');
  },

  // 输入框内容变化
  onInputChange: function (e) {
    this.setData({
      inputCode: e.detail.value.trim()
    });
  },

  // 归一化编码（板件编码最后一位改为 Q）
  normalizeCodeForSearch: function (raw) {
    const s = (raw || '').trim().toUpperCase();
    if (/^\d{13}[A-Z]$/.test(s)) {
      if (s.endsWith('Q')) return s; // 已是 Q
      return s.slice(0, 13) + 'Q';
    }
    if (/^\d{13}$/.test(s)) {
      return s + 'Q';
    }
    return s;
  },

  // 执行查询（首页首次或翻页）
  doSearch: function () {
    const codeRaw = this.data.inputCode;
    if (!codeRaw) {
      wx.showToast({ title: '请输入板件编码', icon: 'none' });
      return;
    }

    const code = this.normalizeCodeForSearch(codeRaw);
    // 将输入框更新为归一化后的编码，便于用户确认
    this.setData({ inputCode: code });

    // 首次查询或重新查询，重置分页到第一页
    const pageIndex = 0;
    const pageSize = 20;
    const skip = pageIndex * pageSize;
    const limit = pageSize;

    this.setData({
      loading: true,
      searched: false,
      pageIndex,
      pageSize,
      hasMore: false
    });

    console.log('开始查询板件(归一化后):', code, 'skip=', skip, 'limit=', limit);

    api.searchByCode(code, { skip, limit }).then(res => {
      const result = this.processSearchResult(res);
      let hasMore = false;
      let firstPageLen = 0;
      if (result && result.type === '包裹') {
        const total = (res && res.data && typeof res.data.component_count === 'number') ? res.data.component_count : (Array.isArray(result.components) ? result.components.length : 0);
        const shown = Array.isArray(result.components) ? result.components.length : 0;
        hasMore = shown < total;
        firstPageLen = shown;
      } else if (result && result.type === '托盘') {
        const total = (res && res.data && typeof res.data.package_count === 'number') ? res.data.package_count : (Array.isArray(result.packages) ? result.packages.length : 0);
        const shown = Array.isArray(result.packages) ? result.packages.length : 0;
        hasMore = shown < total;
        firstPageLen = shown;
      }

      this.setData({
        result: result,
        loading: false,
        searched: true,
        hasMore,
        pageLengths: firstPageLen > 0 ? [firstPageLen] : []
      });

      wx.showToast({ title: result ? '查询成功' : '未找到相关信息', icon: result ? 'success' : 'none' });
    }).catch(err => {
      console.error('查询失败:', err);
      this.setData({ loading: false, searched: true });
      wx.showToast({ title: '查询失败，请重试', icon: 'none' });
    });
  },

  // 上一页（包裹场景：支持回滚累加状态，删除上一页追加的记录）
  prevPage: function () {
    const { inputCode, pageIndex, pageSize, result, pageLengths } = this.data;
    if (!inputCode) return;
    // 若为包裹且有累加历史，优先做前端回滚，不请求后端
    if (result && result.type === '包裹' && Array.isArray(result.components) && pageLengths.length > 1 && pageIndex > 0) {
      const lastLen = pageLengths[pageLengths.length - 1] || 0;
      const trimmed = result.components.slice(0, Math.max(0, result.components.length - lastLen));
      const newLengths = pageLengths.slice(0, pageLengths.length - 1);
      const newIndex = Math.max(0, pageIndex - 1);
      const total = typeof result.componentCount === 'number' ? result.componentCount : trimmed.length;
      const hasMore = trimmed.length < total;
      this.setData({ result: Object.assign({}, result, { components: trimmed }), pageIndex: newIndex, pageLengths: newLengths, hasMore });
      return;
    }

    // 否则退回覆盖展示（非累加场景）
    const newIndex = Math.max(0, pageIndex - 1);
    const skip = newIndex * pageSize;
    const limit = pageSize;
    this.setData({ loading: true });
    api.searchByCode(this.normalizeCodeForSearch(inputCode), { skip, limit }).then(res => {
      const newResult = this.processSearchResult(res);
      // 计算 hasMore
      let hasMore = false;
      let pageLen = 0;
      if (newResult && newResult.type === '包裹') {
        const total = (res && res.data && typeof res.data.component_count === 'number') ? res.data.component_count : (Array.isArray(newResult.components) ? newResult.components.length : 0);
        const shown = Array.isArray(newResult.components) ? newResult.components.length : 0;
        hasMore = shown < total;
        pageLen = shown;
      } else if (newResult && newResult.type === '托盘') {
        const total = (res && res.data && typeof res.data.package_count === 'number') ? res.data.package_count : (Array.isArray(newResult.packages) ? newResult.packages.length : 0);
        const shown = Array.isArray(newResult.packages) ? newResult.packages.length : 0;
        hasMore = shown < total;
        pageLen = shown;
      }
      const newLengths = pageLen > 0 ? [pageLen] : []
      this.setData({ result: newResult, pageIndex: newIndex, loading: false, searched: true, hasMore, pageLengths: newLengths });
    }).catch(err => {
      console.error('上一页失败:', err);
      this.setData({ loading: false });
      wx.showToast({ title: '上一页失败', icon: 'none' });
    });
  },

  // 下一页（保持覆盖展示）
  nextPage: function () {
    const { inputCode, pageIndex, pageSize } = this.data;
    if (!inputCode) return;
    const newIndex = pageIndex + 1;
    const skip = newIndex * pageSize;
    const limit = pageSize;
    this.setData({ loading: true });
    api.searchByCode(this.normalizeCodeForSearch(inputCode), { skip, limit }).then(res => {
      const newResult = this.processSearchResult(res);
      // 计算 hasMore
      let hasMore = false;
      if (newResult && newResult.type === '包裹') {
        const total = (res && res.data && typeof res.data.component_count === 'number') ? res.data.component_count : (Array.isArray(newResult.components) ? newResult.components.length : 0);
        const shown = Array.isArray(newResult.components) ? newResult.components.length : 0;
        hasMore = shown < total;
      } else if (newResult && newResult.type === '托盘') {
        const total = (res && res.data && typeof res.data.package_count === 'number') ? res.data.package_count : (Array.isArray(newResult.packages) ? newResult.packages.length : 0);
        const shown = Array.isArray(newResult.packages) ? newResult.packages.length : 0;
        hasMore = shown < total;
      }
      this.setData({ result: newResult, pageIndex: newIndex, loading: false, searched: true, hasMore });
    }).catch(err => {
      console.error('下一页失败:', err);
      this.setData({ loading: false });
      wx.showToast({ title: '下一页失败', icon: 'none' });
    });
  },

  // 加载更多：包裹与托盘均支持累加展示（包含去重与页长度记录）
  loadMore: function () {
    const { inputCode, pageIndex, pageSize, result, pageLengths } = this.data;
    if (!inputCode || !result) return;
    const newIndex = pageIndex + 1;
    const skip = newIndex * pageSize;
    const limit = pageSize;
    this.setData({ loading: true });
    api.searchByCode(this.normalizeCodeForSearch(inputCode), { skip, limit }).then(res => {
      const nextResult = this.processSearchResult(res);
      if (result.type === '包裹') {
        const before = result.components || [];
        const incoming = nextResult.components || [];
        // 依据 componentCode 去重
        const map = new Map();
        for (const c of before) { if (c && (c.componentCode || c.orderNumber)) map.set(c.componentCode || `${c.orderNumber}|${c.componentName}|${c.finishedSize}`, c); }
        for (const c of incoming) { if (c && (c.componentCode || c.orderNumber)) map.set(c.componentCode || `${c.orderNumber}|${c.componentName}|${c.finishedSize}`, c); }
        const merged = Array.from(map.values());
        const total = (res && res.data && typeof res.data.component_count === 'number') ? res.data.component_count : (typeof result.componentCount === 'number' ? result.componentCount : merged.length);
        const addedLen = Math.max(0, merged.length - before.length);
        const newLengths = pageLengths.concat([addedLen]);
        this.setData({ result: Object.assign({}, result, { components: merged, componentCount: total }), pageIndex: newIndex, loading: false, searched: true, hasMore: merged.length < total, pageLengths: newLengths });
      } else if (result.type === '托盘') {
        const beforePkgs = result.packages || [];
        const incomingPkgs = nextResult.packages || [];
        // 依据 packageNumber 去重
        const mapP = new Map();
        for (const p of beforePkgs) { if (p && p.packageNumber) mapP.set(p.packageNumber, p); }
        for (const p of incomingPkgs) { if (p && p.packageNumber) mapP.set(p.packageNumber, p); }
        const mergedPkgs = Array.from(mapP.values());
        const totalPkg = (res && res.data && typeof res.data.package_count === 'number') ? res.data.package_count : (typeof result.packageCount === 'number' ? result.packageCount : mergedPkgs.length);
        const addedLen = Math.max(0, mergedPkgs.length - beforePkgs.length);
        const newLengths = pageLengths.concat([addedLen]);
        this.setData({ result: Object.assign({}, result, { packages: mergedPkgs, packageCount: totalPkg }), pageIndex: newIndex, loading: false, searched: true, hasMore: mergedPkgs.length < totalPkg, pageLengths: newLengths });
      } else {
        this.setData({ loading: false });
      }
    }).catch(err => {
      console.error('加载更多失败:', err);
      this.setData({ loading: false });
      wx.showToast({ title: '加载更多失败', icon: 'none' });
    });
  },

  // 新增：滚动触底自动加载更多（包裹与托盘都支持）
  onReachBottom: function () {
    if (this.data.hasMore) {
      this.loadMore();
    }
  },

  // 新增：扫码查询
  scanCodeSearch: function () {
    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['barCode', 'qrCode'],
      success: (res) => {
        const codeRaw = (res.result || '').trim().toUpperCase();
        const code = this.normalizeCodeForSearch(codeRaw);
        if (!code) {
          wx.showToast({ title: '未识别到编码', icon: 'none' });
          return;
        }
        this.setData({ inputCode: code });
        this.doSearch();
      },
      fail: (err) => {
        console.error('扫码失败:', err);
        wx.showToast({ title: '扫码失败', icon: 'none' });
      }
    })
  },

  // 新增：连接诊断
  diagnoseConnection: function () {
    wx.showLoading({ title: '诊断中...', mask: true });
    cloudDiag.testDatabaseConnection().then(res => {
      wx.hideLoading();
      wx.showModal({
        title: '测试云连接诊断结果',
        content: `组件:${res.components} 包裹:${res.packages} 托盘:${res.pallets}`,
        showCancel: false
      });
    }).catch(err => {
      wx.hideLoading();
      console.error('连接诊断失败:', err);
      wx.showModal({
        title: '连接诊断失败',
        content: (err && err.errMsg) || (err && err.message) || '未知错误',
        showCancel: false
      });
    });
  },

  // 处理搜索结果（保留原实现）
  processSearchResult: function (res) {
    if (!res) {
      return null;
    }

    const type = res.type || 'unknown';
    // 同时兼容两种返回结构：
    // 1) 云数据库：{ type, data }
    // 2) 本地API：{ type, component, package, pallet }
    const base = res.data || (type === 'component' ? (res.component || {})
                      : type === 'package' ? (res.package || {})
                      : type === 'pallet' ? (res.pallet || {})
                      : {});

    // 基础结果对象
    let result = {
      code: base.component_code || base.package_number || base.pallet_number || '',
      name: base.component_name || base.package_number || base.pallet_number || '',
      type: type === 'component' ? '板件' : type === 'package' ? '包裹' : type === 'pallet' ? '托盘' : '未知',
      orderNumber: base.order_number || '',
      customerAddress: base.customer_address || '',
      roomNumber: base.room_number || '',
      cabinetNumber: base.cabinet_number || '',
      material: base.material || '',
      finishedSize: base.finished_size || ''
    };

    // 包裹信息（兼容两种结构）
    const pkg = res.package || (type === 'package' ? base : null);
    if (pkg) {
      result.package = {
        code: pkg.package_number || '',
        package_index: (pkg.package_index !== undefined && pkg.package_index !== null) ? pkg.package_index : null
      };
    }

    // 托盘信息（兼容两种结构）
    const pal = res.pallet || (type === 'pallet' ? base : null);
    if (pal) {
      result.pallet = {
        code: pal.pallet_number || '',
        pallet_index: (pal.pallet_index !== undefined && pal.pallet_index !== null) ? pal.pallet_index : null
      };
    }

    // 当查询的是包裹：添加板件统计与列表
    if (type === 'package') {
      const comps = Array.isArray(res.components) ? res.components : [];
      // 修正：优先使用包裹记录中的 component_count 字段，若不存在再回退到实际组件数组长度
      result.componentCount = (pkg && typeof pkg.component_count === 'number') ? pkg.component_count : comps.length;
      result.components = comps.map(c => ({
        orderNumber: c.order_number || '',
        componentCode: c.component_code || '',
        componentName: c.component_name || '',
        material: c.material || '',
        finishedSize: c.finished_size || '',
        roomNumber: c.room_number || '',
        cabinetNumber: c.cabinet_number || ''
      }));
    }

    // 当查询的是托盘：添加包裹统计与列表
    if (type === 'pallet') {
      const pkgs = Array.isArray(res.packages) ? res.packages : [];
      // 修正：优先使用托盘记录中的 package_count 字段作为总数
      const palRecord = res.pallet || (type === 'pallet' ? base : null);
      const totalPkgs = (palRecord && typeof palRecord.package_count === 'number') ? palRecord.package_count : pkgs.length;
      result.packageCount = totalPkgs;
      result.packages = pkgs.map((p, idx) => ({
        packageNumber: p.package_number || '',
        orderNumber: p.order_number || '',
        customerAddress: (() => {
          const candidates = []
          const add = (v) => {
            if (typeof v === 'string') {
              const t = v.trim()
              if (t && !/^(未知|地址未知|unknown)$/i.test(t)) candidates.push(t)
            }
          }
          add(p.customer_address)
          add(p.address)
          add(p.delivery_address)
          add(p.shipping_address)
          if (Array.isArray(p.components)) {
            for (const c of p.components) {
              add(c.customer_address)
              add(c.address)
              add(c.delivery_address)
              add(c.shipping_address)
            }
          }
          if (candidates.length === 0) return ''
          const freq = {}
          let best = ''
          let bestCount = 0
          for (const a of candidates) {
            freq[a] = (freq[a] || 0) + 1
            if (freq[a] > bestCount) {
              best = a
              bestCount = freq[a]
            }
          }
          return best
        })(),
        packageIndex: (p.package_index !== undefined && p.package_index !== null) ? p.package_index : null,
        componentCount: (typeof p.component_count === 'number') ? p.component_count : (Array.isArray(p.components) ? p.components.length : undefined)
      }))
    }

    console.log('处理后的结果:', result);
    return result;
  }
});