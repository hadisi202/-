// utils/cloud.js
const db = () => wx.cloud.database()

function normalizeCode(code) {
  if (!code) return ''
  return String(code).trim()
}

async function findComponentByCode(code) {
  const c = normalizeCode(code)
  // 先精确查；未命中时尝试大小写归一
  let res = await db().collection('components').where({ component_code: c }).limit(1).get()
  if (res.data && res.data[0]) return res.data[0]
  const upper = c.toUpperCase()
  if (upper !== c) {
    res = await db().collection('components').where({ component_code: upper }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  const lower = c.toLowerCase()
  if (lower !== c) {
    res = await db().collection('components').where({ component_code: lower }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  return null
}

async function findPackageByNumber(pkgNo) {
  const p = normalizeCode(pkgNo)
  let res = await db().collection('packages').where({ package_number: p }).limit(1).get()
  if (res.data && res.data[0]) return res.data[0]
  const upper = p.toUpperCase()
  if (upper !== p) {
    res = await db().collection('packages').where({ package_number: upper }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  const lower = p.toLowerCase()
  if (lower !== p) {
    res = await db().collection('packages').where({ package_number: lower }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  return null
}

async function findPalletByNumber(palletNo) {
  const p = normalizeCode(palletNo)
  let res = await db().collection('pallets').where({ pallet_number: p }).limit(1).get()
  if (res.data && res.data[0]) return res.data[0]
  const upper = p.toUpperCase()
  if (upper !== p) {
    res = await db().collection('pallets').where({ pallet_number: upper }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  const lower = p.toLowerCase()
  if (lower !== p) {
    res = await db().collection('pallets').where({ pallet_number: lower }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  return null
}

function isValidId(id) {
  const s = typeof id === 'string' ? id.trim() : ''
  // 云开发文档ID通常为长度>=16的非纯数字字符串，这里做宽松校验
  return s && s.length >= 16 && !/^\d+$/.test(s)
}

async function findPackageById(id) {
  if (!isValidId(id)) return null
  try {
    const res = await db().collection('packages').doc(id).get()
    return res.data
  } catch (e) {
    return null
  }
}

async function findPalletById(id) {
  if (!isValidId(id)) return null
  try {
    const res = await db().collection('pallets').doc(id).get()
    return res.data
  } catch (e) {
    return null
  }
}

async function listComponentsInPackage(packageId, { skip = 0, limit = 20 } = {}) {
  const res = await db().collection('components')
    .where({ package_id: packageId })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

// 兼容旧数据：按本地数值型包裹id查询板件
async function listComponentsByLocalPackageId(localPkgId, { skip = 0, limit = 20 } = {}) {
  if (localPkgId == null) return []
  const res = await db().collection('components')
    .where({ package_id: localPkgId })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

async function listPackagesOnPallet(palletId, { skip = 0, limit = 20 } = {}) {
  const res = await db().collection('packages')
    .where({ pallet_id: palletId })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

// 兼容旧数据：按本地数值型托盘id查询包裹
async function listPackagesByLocalPalletId(localPalId, { skip = 0, limit = 20 } = {}) {
  if (localPalId == null) return []
  const res = await db().collection('packages')
    .where({ pallet_id: localPalId })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

async function listComponentsFallbackByNumber(packageNumber, { skip = 0, limit = 20 } = {}) {
  if (!packageNumber) return []
  const res = await db().collection('components')
    .where({ package_number: packageNumber })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

async function listPackagesFallbackByNumber(palletNumber, { skip = 0, limit = 20 } = {}) {
  if (!palletNumber) return []
  const res = await db().collection('packages')
    .where({ pallet_number: palletNumber })
    .skip(Number(skip) || 0)
    .limit(Math.min(20, Number(limit) || 20))
    .get()
  return res.data || []
}

async function searchByCodeCloud(code, options = {}) {
  if (!code) throw new Error('编码不能为空')
  const { skip = 0, limit = 20 } = options
  
  console.log('开始查询编码:', code)
  
  // 1) 尝试按板件编码查询
  const comp = await findComponentByCode(code)
  console.log('板件查询结果:', comp)
  console.log('板件数据字段:', comp ? Object.keys(comp) : '无数据')
  if (comp) {
    // 找到所在包裹和托盘（先按ID，失败则按编号兜底）
    let pkg = null
    if (comp.package_id) {
      pkg = await findPackageById(comp.package_id)
    }
    if (!pkg && comp.package_number) {
      pkg = await findPackageByNumber(comp.package_number)
    }
    let pal = null
    if (pkg) {
      pal = await findPalletById(pkg.pallet_id)
      if (!pal && pkg.pallet_number) {
        pal = await findPalletByNumber(pkg.pallet_number)
      }
    }
    try {
      if (!comp.customer_address) {
        comp.customer_address = (pkg && pkg.customer_address) || ''
      }
    } catch (e) {}
    const result = {
      type: 'component',
      data: comp,
      package: pkg || null,
      pallet: pal || null
    }
    console.log('板件查询完整结果:', result)
    console.log('包裹数据:', pkg ? Object.keys(pkg) : '无包裹数据')
    console.log('托盘数据:', pal ? Object.keys(pal) : '无托盘数据')
    return result
  }

  // 2) 尝试按包裹号查询（分页）
  const pkg = await findPackageByNumber(code)
  console.log('包裹查询结果:', pkg)
  if (pkg) {
    const byId = await listComponentsInPackage(pkg._id, { skip, limit })
    const byNumber = pkg.package_number ? await listComponentsFallbackByNumber(pkg.package_number, { skip, limit }) : []
    const byLocal = (typeof pkg.id === 'number') ? await listComponentsByLocalPackageId(pkg.id, { skip, limit }) : []
  
    const all = ([]).concat(byId || [], byNumber || [], byLocal || [])
    const seen = new Set()
    const merged = []
    for (const c of all) {
      const codeKey = (c && c.component_code) ? String(c.component_code).trim().toUpperCase() : ''
      const idKey = (c && c._id) ? String(c._id).trim() : ''
      const key = codeKey || idKey || `${c.order_number || ''}|${c.component_name || ''}|${c.finished_size || ''}`
      if (!key) continue
      if (seen.has(key)) continue
      seen.add(key)
      merged.push(c)
    }
  
    merged.sort((a, b) => {
      const ac = (a.component_code || '').toString().toUpperCase()
      const bc = (b.component_code || '').toString().toUpperCase()
      if (ac && bc) return ac.localeCompare(bc)
      if (ac) return -1
      if (bc) return 1
      return 0
    })
  
    let pal = null
    pal = await findPalletById(pkg.pallet_id)
    if (!pal && pkg.pallet_number) {
      pal = await findPalletByNumber(pkg.pallet_number)
    }
  
    // 通过 count() 计算包裹下板件总数，避免被分页截断
    let totalCount = 0
    try {
      const counts = []
      if (pkg._id) {
        const r1 = await db().collection('components').where({ package_id: pkg._id }).count()
        counts.push((typeof r1.total === 'number') ? r1.total : 0)
      }
      if (pkg.package_number) {
        const r2 = await db().collection('components').where({ package_number: pkg.package_number }).count()
        counts.push((typeof r2.total === 'number') ? r2.total : 0)
      }
      if (typeof pkg.id === 'number') {
        const r3 = await db().collection('components').where({ package_id: pkg.id }).count()
        counts.push((typeof r3.total === 'number') ? r3.total : 0)
      }
      totalCount = counts.length ? Math.max(...counts) : 0
    } catch (e) {
      console.warn('包裹板件计数失败:', e)
    }
    pkg.component_count = (typeof pkg.component_count === 'number') ? Math.max(pkg.component_count, totalCount) : totalCount
    if (!pkg.customer_address) {
      const firstNonEmpty = Array.isArray(merged) ? merged.find(c => typeof c.customer_address === 'string' && c.customer_address.trim()) : null
      pkg.customer_address = (firstNonEmpty && firstNonEmpty.customer_address) || ''
    }
  
    return {
      type: 'package',
      data: pkg,
      components: merged,
      pallet: pal || null
    }
  }

  // 3) 尝试按托盘号查询（分页）
  const pal = await findPalletByNumber(code)
  console.log('托盘查询结果:', pal)
  if (pal) {
    let pkgs = await listPackagesOnPallet(pal._id, { skip, limit })
    if ((!pkgs || pkgs.length === 0) && pal.pallet_number) {
      pkgs = await listPackagesFallbackByNumber(pal.pallet_number, { skip, limit })
    }
    if ((!pkgs || pkgs.length === 0) && typeof pal.id === 'number') {
      pkgs = await listPackagesByLocalPalletId(pal.id, { skip, limit })
    }

    // 统计托盘下包裹真实总数（多条件取最大），避免分页截断
    try {
      const counts = []
      if (pal._id) {
        const r1 = await db().collection('packages').where({ pallet_id: pal._id }).count()
        counts.push((typeof r1.total === 'number') ? r1.total : 0)
      }
      if (pal.pallet_number) {
        const r2 = await db().collection('packages').where({ pallet_number: pal.pallet_number }).count()
        counts.push((typeof r2.total === 'number') ? r2.total : 0)
      }
      if (typeof pal.id === 'number') {
        const r3 = await db().collection('packages').where({ pallet_id: pal.id }).count()
        counts.push((typeof r3.total === 'number') ? r3.total : 0)
      }
      pal.package_count = counts.length ? Math.max(...counts) : 0
    } catch (e) {
      console.warn('托盘包裹计数失败:', e)
    }

    const packages = await Promise.all(pkgs.map(async (p) => {
      const byId = await listComponentsInPackage(p._id, { skip, limit })
      const byNumber = p.package_number ? await listComponentsFallbackByNumber(p.package_number, { skip, limit }) : []
      const byLocal = (typeof p.id === 'number') ? await listComponentsByLocalPackageId(p.id, { skip, limit }) : []
      const all = ([]).concat(byId || [], byNumber || [], byLocal || [])
      const seen = new Set()
      const merged = []
      for (const c of all) {
        const codeKey = (c && c.component_code) ? String(c.component_code).trim().toUpperCase() : ''
        const idKey = (c && c._id) ? String(c._id).trim() : ''
        const key = codeKey || idKey || `${c.order_number || ''}|${c.component_name || ''}|${c.finished_size || ''}`
        if (!key) continue
        if (seen.has(key)) continue
        seen.add(key)
        merged.push(c)
      }
      merged.sort((a, b) => {
        const ac = (a.component_code || '').toString().toUpperCase()
        const bc = (b.component_code || '').toString().toUpperCase()
        if (ac && bc) return ac.localeCompare(bc)
        if (ac) return -1
        if (bc) return 1
        return 0
      })
      return Object.assign({}, p, {
        components: merged,
        component_count: typeof p.component_count === 'number' ? p.component_count : merged.length,
        customer_address: (() => {
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
          if (Array.isArray(merged)) {
            for (const c of merged) {
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
        })()
      })
    }))
    const sanitize = (v) => (typeof v === 'string') ? v.trim() : ''
    const isValid = (a) => a && !/^(未知|地址未知|unknown)$/i.test(a)
    const firstPkg = packages && packages[0]
    let fallback = ''
    if (firstPkg) {
      const fromPkg = sanitize(firstPkg.customer_address) || sanitize(firstPkg.address) || sanitize(firstPkg.delivery_address) || sanitize(firstPkg.shipping_address)
      if (isValid(fromPkg)) {
        fallback = fromPkg
      }
      if (!fallback && Array.isArray(firstPkg.components)) {
        for (const c of firstPkg.components) {
          const fromComp = sanitize(c.customer_address) || sanitize(c.address) || sanitize(c.delivery_address) || sanitize(c.shipping_address)
          if (isValid(fromComp)) { fallback = fromComp; break }
        }
      }
    }
    const finalPackages = packages.map(pkg => {
      const cur = sanitize(pkg.customer_address)
      if (!isValid(cur) && fallback) {
        return Object.assign({}, pkg, { customer_address: fallback })
      }
      return pkg
    })
     return {
       type: 'pallet',
       data: pal,
       packages: finalPackages
     }
  }

  console.log('所有查询都未命中，编码:', code)
  throw new Error(`未找到编码 "${code}" 的相关数据`)
}

// 测试数据库连接和数据
async function testDatabaseConnection() {
  try {
    console.log('测试数据库连接...')
    
    // 测试组件集合
    const compRes = await db().collection('components').limit(3).get()
    console.log('组件数据样本:', compRes.data)
    
    // 测试包裹集合
    const pkgRes = await db().collection('packages').limit(3).get()
    console.log('包裹数据样本:', pkgRes.data)
    
    // 测试托盘集合
    const palRes = await db().collection('pallets').limit(3).get()
    console.log('托盘数据样本:', palRes.data)
    
    return {
      components: compRes.data.length,
      packages: pkgRes.data.length,
      pallets: palRes.data.length
    }
  } catch (error) {
    console.error('数据库连接测试失败:', error)
    throw error
  }
}

module.exports = {
  searchByCodeCloud,
  testDatabaseConnection
}