const api = require('../../utils/api.js');
const cloudDiag = require('../../utils/cloud.js');

Page({
  data: {
    inputCode: '',
    result: null,
    loading: false,
    searched: false
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
    // 组件编码通常为 13 位数字 + 1 位字母，例如 2412550406525A
    if (/^\d{13}[A-Z]$/.test(s)) {
      if (s.endsWith('Q')) return s; // 已是 Q
      return s.slice(0, 13) + 'Q';
    }
    // 兼容 13 位纯数字的情况：补一个 Q
    if (/^\d{13}$/.test(s)) {
      return s + 'Q';
    }
    return s;
  },

  // 执行查询
  doSearch: function () {
    const codeRaw = this.data.inputCode;
    
    if (!codeRaw) {
      wx.showToast({
        title: '请输入板件编码',
        icon: 'none'
      });
      return;
    }

    const code = this.normalizeCodeForSearch(codeRaw);
    // 将输入框更新为归一化后的编码，便于用户确认
    this.setData({ inputCode: code });

    this.setData({
      loading: true,
      result: null,
      searched: false
    });

    console.log('开始查询板件(归一化后):', code);

    api.searchByCode(code).then(res => {
      console.log('API原始返回结果:', res);
      console.log('API返回结果类型:', typeof res);
      console.log('API返回结果JSON:', JSON.stringify(res, null, 2));
      
      if (res && (res.data || res.component || res.package || res.pallet)) {
        // 处理查询结果
        const result = this.processSearchResult(res);
        console.log('处理后的最终结果:', result);
        console.log('处理后的结果JSON:', JSON.stringify(result, null, 2));
        
        this.setData({
          result: result,
          loading: false,
          searched: true
        });

        if (result) {
          wx.showToast({
            title: '查询成功',
            icon: 'success'
          });
        } else {
          wx.showToast({
            title: '未找到相关信息',
            icon: 'none'
          });
        }
      } else {
        console.log('API返回数据为空或无效');
        this.setData({
          result: null,
          loading: false,
          searched: true
        });
        
        wx.showToast({
          title: '未找到相关信息',
          icon: 'none'
        });
      }
    }).catch(err => {
      console.error('查询失败:', err);
      
      this.setData({
        result: null,
        loading: false,
        searched: true
      });
      
      wx.showToast({
        title: '查询失败，请重试',
        icon: 'none'
      });
    });
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

  // 处理搜索结果
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
      result.packageCount = pkgs.length;
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
        // 新增：包裹序号（优先取后端提供的 package_index，否则为 null）
        packageIndex: (p.package_index !== undefined && p.package_index !== null) ? p.package_index : null,
        // 新增：该包裹内板件总数（兼容 components 数组或后端的 component_count 字段）
        // 修正：优先使用后端包裹记录的 component_count 字段；无该字段时回退到 components 长度
        componentCount: (typeof p.component_count === 'number') ? p.component_count : (Array.isArray(p.components) ? p.components.length : undefined)
      }))
    }

    console.log('处理后的结果:', result);
    return result;
  }
});