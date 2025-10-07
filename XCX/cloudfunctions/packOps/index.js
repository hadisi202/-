// 云函数：packOps（HTTP服务）
// 功能：提供本地系统与云数据库的可靠同步，以及查询接口
// 路由：
//   GET    /search?code=...                     查询板件/包裹/托盘
//   POST   /sync/components  {items:[...]}      批量同步板件（按 component_code 唯一）
//   POST   /sync/packages   {items:[...]}       批量同步包裹（按 package_number 唯一，解析 pallet_number 关联）
//   POST   /sync/pallets    {items:[...]}       批量同步托盘（按 pallet_number 唯一）
// 认证：设置云函数环境变量 API_KEY，在请求头 X-API-Key 传入匹配的密钥

const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

// 统一响应封装
function response(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type,X-API-Key'
    },
    body: JSON.stringify(body)
  }
}

function getApiKey() {
  return process.env.API_KEY || ''
}

function checkAuth(event) {
  const headers = event.headers || {}
  const apiKey = headers['X-API-Key'] || headers['x-api-key'] || (event.queryStringParameters && event.queryStringParameters.api_key)
  return apiKey && apiKey === getApiKey()
}

// 工具：安全解析JSON
function parseJson(body) {
  if (!body) return {}
  try {
    if (typeof body === 'string') return JSON.parse(body)
    return body
  } catch (e) {
    return {}
  }
}

// 查询工具（与小程序 utils/cloud.js 逻辑保持一致）
async function findComponentByCode(code) {
  const res = await db.collection('components').where({ component_code: code }).limit(1).get()
  return res.data && res.data[0]
}

async function findPackageByNumber(pkgNo) {
  const p = String(pkgNo || '').trim()
  if (!p) return null
  // 精确命中
  let res = await db.collection('packages').where({ package_number: p }).limit(1).get()
  if (res.data && res.data[0]) return res.data[0]
  // 大小写兜底（如含字母前缀）
  const upper = p.toUpperCase()
  if (upper !== p) {
    res = await db.collection('packages').where({ package_number: upper }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  const lower = p.toLowerCase()
  if (lower !== p) {
    res = await db.collection('packages').where({ package_number: lower }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  return null
}

async function findPalletByNumber(palletNo) {
  const p = String(palletNo || '').trim()
  if (!p) return null
  let res = await db.collection('pallets').where({ pallet_number: p }).limit(1).get()
  if (res.data && res.data[0]) return res.data[0]
  const upper = p.toUpperCase()
  if (upper !== p) {
    res = await db.collection('pallets').where({ pallet_number: upper }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  const lower = p.toLowerCase()
  if (lower !== p) {
    res = await db.collection('pallets').where({ pallet_number: lower }).limit(1).get()
    if (res.data && res.data[0]) return res.data[0]
  }
  return null
}

async function findPackageById(id) {
  try {
    if (!id || (typeof id === 'string' && (/^\d+$/.test(id) || id.length < 16))) return null
    const res = await db.collection('packages').doc(id).get()
    return res.data
  } catch (e) {
    return null
  }
}

async function findPalletById(id) {
  try {
    if (!id || (typeof id === 'string' && (/^\d+$/.test(id) || id.length < 16))) return null
    const res = await db.collection('pallets').doc(id).get()
    return res.data
  } catch (e) {
    return null
  }
}

async function listComponentsInPackage(packageId) {
  const res = await db.collection('components').where({ package_id: packageId }).limit(1000).get()
  return res.data || []
}

async function listPackagesOnPallet(palletId) {
  const res = await db.collection('packages').where({ pallet_id: palletId }).limit(1000).get()
  return res.data || []
}

async function listComponentsFallbackByNumber(packageNumber) {
  if (!packageNumber) return []
  const res = await db.collection('components').where({ package_number: packageNumber }).limit(1000).get()
  return res.data || []
}

async function listPackagesFallbackByNumber(palletNumber) {
  if (!palletNumber) return []
  const res = await db.collection('packages').where({ pallet_number: palletNumber }).limit(1000).get()
  return res.data || []
}

async function searchByCodeCloud(code) {
  // 1) 板件编码
  const comp = await findComponentByCode(code)
  if (comp) {
    let pkg = null
    let pal = null
    // 先按ID取包裹，失败再按编号
    if (comp.package_id) {
      pkg = await findPackageById(comp.package_id)
    }
    if (!pkg && comp.package_number) {
      pkg = await findPackageByNumber(comp.package_number)
    }
    if (pkg) {
      // 先按ID取托盘，失败再按编号
      pal = await findPalletById(pkg.pallet_id)
      if (!pal && pkg.pallet_number) {
        pal = await findPalletByNumber(pkg.pallet_number)
      }
    }
    return { type: 'component', data: comp, package: pkg || null, pallet: pal || null }
  }

  // 2) 包裹号
  const pkg = await findPackageByNumber(code)
  if (pkg) {
    let comps = await listComponentsInPackage(pkg._id)
    if ((!comps || comps.length === 0) && pkg.package_number) {
      comps = await listComponentsFallbackByNumber(pkg.package_number)
    }
    let pal = await findPalletById(pkg.pallet_id)
    if (!pal && pkg.pallet_number) {
      pal = await findPalletByNumber(pkg.pallet_number)
    }
    // 兜底补充数量与地址
    pkg.component_count = typeof pkg.component_count === 'number' ? pkg.component_count : (Array.isArray(comps) ? comps.length : 0)
    if (!pkg.customer_address) {
      const first = comps && comps[0]
      pkg.customer_address = (first && first.customer_address) || ''
    }
    return { type: 'package', data: pkg, components: comps, pallet: pal || null }
  }

  // 3) 托盘号
  const pal = await findPalletByNumber(code)
  if (pal) {
    let pkgs = await listPackagesOnPallet(pal._id)
    if ((!pkgs || pkgs.length === 0) && pal.pallet_number) {
      pkgs = await listPackagesFallbackByNumber(pal.pallet_number)
    }
    const compLists = await Promise.all(pkgs.map(async (p) => {
      let list = await listComponentsInPackage(p._id)
      if ((!list || list.length === 0) && p.package_number) {
        list = await listComponentsFallbackByNumber(p.package_number)
      }
      return list
    }))
    const packages = pkgs.map((p, i) => {
      const list = compLists[i] || []
      return Object.assign({}, p, {
        components: list,
        component_count: typeof p.component_count === 'number' ? p.component_count : list.length,
        customer_address: p.customer_address || (list[0] && list[0].customer_address) || ''
      })
    })
    return { type: 'pallet', data: pal, packages }
  }

  throw new Error('未找到相关数据')
}

// 批量同步：托盘
async function syncPallets(items) {
  let added = 0, updated = 0
  for (const it of items) {
    const pallet_number = String(it.pallet_number || '').trim()
    if (!pallet_number) continue
    const exist = await findPalletByNumber(pallet_number)
    const payload = {
      pallet_number,
      pallet_type: it.pallet_type || 'physical',
      order_number: it.order_number || '',
      package_count: typeof it.package_count === 'number' ? it.package_count : (exist ? exist.package_count : 0),
      status: it.status || (exist ? exist.status : 'open'),
      notes: it.notes || '',
      change_reason: it.change_reason || '',
      customer_address: it.customer_address || (exist ? exist.customer_address : ''),
      // 新增：托盘序号
      pallet_index: (typeof it.pallet_index === 'number' ? it.pallet_index : (exist ? exist.pallet_index : undefined))
    }
    if (exist) {
      const same = (
        (exist.pallet_number || '') === payload.pallet_number &&
        (exist.pallet_type || '') === payload.pallet_type &&
        (exist.order_number || '') === payload.order_number &&
        (Number(exist.package_count) || 0) === (Number(payload.package_count) || 0) &&
        (exist.status || '') === payload.status &&
        (exist.notes || '') === payload.notes &&
        (exist.change_reason || '') === payload.change_reason &&
        (exist.customer_address || '') === payload.customer_address &&
        ((exist.pallet_index == null && payload.pallet_index == null) || (Number(exist.pallet_index) || 0) === (Number(payload.pallet_index) || 0))
      )
      if (!same) {
        await db.collection('pallets').doc(exist._id).update({ data: payload })
        updated++
      }
    } else {
      await db.collection('pallets').add({ data: payload })
      added++
    }
  }
  return { added, updated }
}

// 批量同步：包裹（解析 pallet_number → pallet_id）
async function syncPackages(items) {
  let added = 0, updated = 0
  const processed = new Set()
  for (const it of items) {
    const package_number = String(it.package_number || '').trim()
    if (!package_number) continue
    const key = package_number.toUpperCase()
    if (processed.has(key)) continue
    processed.add(key)
    const exist = await findPackageByNumber(package_number)
    // 解析托盘关联
    let pallet_id = ''
    if (it.pallet_number) {
      const pal = await findPalletByNumber(String(it.pallet_number).trim())
      if (pal) pallet_id = pal._id
    }
    const payload = {
      package_number,
      order_number: it.order_number || '',
      pallet_id: pallet_id || (exist ? exist.pallet_id : ''),
      pallet_number: it.pallet_number || (exist ? exist.pallet_number : ''),
      component_count: typeof it.component_count === 'number' ? it.component_count : (exist ? exist.component_count : 0),
      status: it.status || (exist ? exist.status : 'open'),
      notes: it.notes || '',
      change_reason: it.change_reason || '',
      customer_address: it.customer_address || (exist ? exist.customer_address : ''),
      // 新增：包裹序号
      package_index: (typeof it.package_index === 'number' ? it.package_index : (exist ? exist.package_index : undefined))
    }
    if (exist) {
      const same = (
        (exist.order_number || '') === payload.order_number &&
        (exist.pallet_id || '') === payload.pallet_id &&
        (exist.pallet_number || '') === payload.pallet_number &&
        (Number(exist.component_count) || 0) === (Number(payload.component_count) || 0) &&
        (exist.status || '') === payload.status &&
        (exist.notes || '') === payload.notes &&
        (exist.change_reason || '') === payload.change_reason &&
        (exist.customer_address || '') === payload.customer_address &&
        ((exist.package_index == null && payload.package_index == null) || (Number(exist.package_index) || 0) === (Number(payload.package_index) || 0))
      )
      if (!same) {
        await db.collection('packages').doc(exist._id).update({ data: payload })
        updated++
      }
    } else {
      await db.collection('packages').add({ data: payload })
      added++
    }
  }
  return { added, updated }
}

// 批量同步：板件（解析 package_number → package_id）
async function syncComponents(items) {
  let added = 0, updated = 0
  const processed = new Set()
  for (const it of items) {
    const raw = String(it.component_code || '').trim()
    if (!raw) continue
    const component_code = raw.endsWith('q') ? (raw.slice(0, -1) + 'Q') : raw
    const key = component_code
    if (processed.has(key)) continue
    processed.add(key)
    const exist = await findComponentByCode(component_code)
    // 解析包裹关联
    let package_id = ''
    if (it.package_number) {
      const pkg = await findPackageByNumber(String(it.package_number).trim())
      if (pkg) package_id = pkg._id
    }
    const payload = {
      component_code,
      component_name: it.component_name || (exist ? exist.component_name : ''),
      order_number: it.order_number || (exist ? exist.order_number : ''),
      package_id: package_id || (exist ? exist.package_id : ''),
      package_number: it.package_number || (exist ? exist.package_number : ''),
      status: it.status || (exist ? exist.status : 'pending'),
      // 可选字段：用于前端展示
      material: it.material || (exist ? exist.material : ''),
      finished_size: it.finished_size || (exist ? exist.finished_size : ''),
      room_number: it.room_number || (exist ? exist.room_number : ''),
      cabinet_number: it.cabinet_number || (exist ? exist.cabinet_number : ''),
      customer_address: it.customer_address || (exist ? exist.customer_address : '')
    }
    if (exist) {
      const same = (
        (exist.component_name || '') === payload.component_name &&
        (exist.order_number || '') === payload.order_number &&
        (exist.package_id || '') === payload.package_id &&
        (exist.package_number || '') === payload.package_number &&
        (exist.status || '') === payload.status &&
        (exist.material || '') === payload.material &&
        (exist.finished_size || '') === payload.finished_size &&
        (exist.room_number || '') === payload.room_number &&
        (exist.cabinet_number || '') === payload.cabinet_number &&
        (exist.customer_address || '') === payload.customer_address
      )
      if (!same) {
        await db.collection('components').doc(exist._id).update({ data: payload })
        updated++
      }
    } else {
      await db.collection('components').add({ data: payload })
      added++
    }
  }
  return { added, updated }
}

// 新增：删除接口实现（组件/包裹/托盘）
async function deleteComponents(items) {
  let removed = 0
  for (const it of items) {
    const code = String(it.component_code || '').trim()
    if (!code) continue
    const comp = await findComponentByCode(code)
    if (comp && comp._id) {
      try {
        await db.collection('components').doc(comp._id).remove()
        removed++
      } catch (e) {}
    }
  }
  return { removed }
}

async function deletePackages(items) {
  let removed = 0, affected_components = 0
  for (const it of items) {
    const num = String(it.package_number || '').trim()
    if (!num) continue
    const pkg = await findPackageByNumber(num)
    if (!pkg || !pkg._id) continue
    try {
      // 解除组件关联并恢复状态（按包裹ID与编号兜底）
      const compsById = await listComponentsInPackage(pkg._id)
      const compsByNum = await listComponentsFallbackByNumber(pkg.package_number)
      const comps = [...(compsById || []), ...(compsByNum || [])]
      const seen = new Set()
      for (const c of comps) {
        if (!c || !c._id) continue
        if (seen.has(c._id)) continue
        seen.add(c._id)
        try {
          await db.collection('components').doc(c._id).update({ data: { package_id: '', package_number: '', status: 'pending' } })
          affected_components++
        } catch (e) {}
      }
      // 删除包裹
      await db.collection('packages').doc(pkg._id).remove()
      removed++
    } catch (e) {}
  }
  return { removed, affected_components }
}

async function deletePallets(items) {
  let removed = 0, affected_packages = 0
  for (const it of items) {
    const num = String(it.pallet_number || '').trim()
    if (!num) continue
    const pal = await findPalletByNumber(num)
    if (!pal || !pal._id) continue
    try {
      // 解除包裹与托盘关联（按托盘ID与编号兜底）
      const pkgsById = await listPackagesOnPallet(pal._id)
      const pkgsByNum = await listPackagesFallbackByNumber(pal.pallet_number)
      const pkgs = [...(pkgsById || []), ...(pkgsByNum || [])]
      const seen = new Set()
      for (const p of pkgs) {
        if (!p || !p._id) continue
        if (seen.has(p._id)) continue
        seen.add(p._id)
        try {
          await db.collection('packages').doc(p._id).update({ data: { pallet_id: '', pallet_number: '' } })
          affected_packages++
        } catch (e) {}
      }
      // 删除托盘
      await db.collection('pallets').doc(pal._id).remove()
      removed++
    } catch (e) {}
  }
  return { removed, affected_packages }
}

async function clearCollections(collections) {
  const targets = Array.isArray(collections) && collections.length > 0 ? collections : ['components','packages','pallets']
  const cleared = {}
  for (const name of targets) {
    let removed = 0
    try {
      const BATCH = 1000
      let skip = 0
      while (true) {
        const res = await db.collection(name).where({}).skip(skip).limit(BATCH).get()
        const list = res.data || []
        if (list.length === 0) break
        for (const it of list) {
          if (!it || !it._id) continue
          try { await db.collection(name).doc(it._id).remove(); removed++ } catch (e) {}
        }
        skip += list.length
        if (list.length < BATCH) break
      }
    } catch (e) {}
    cleared[name] = removed
  }
  return { cleared }
}

exports.main = async (event, context) => {
  // 预检请求（CORS）
  if (event.httpMethod === 'OPTIONS') {
    return response(204, {})
  }

  // 鉴权
  if (!checkAuth(event)) {
    return response(401, { error: 'Unauthorized' })
  }

  const method = (event.httpMethod || '').toUpperCase()
  const path = event.path || '/'
  const qs = event.queryStringParameters || {}
  // 兼容仅映射到 /packOps 的情况下，通过查询参数或请求体传递子路径
  const body = parseJson(event.body)
  const queryPath = (qs && qs.path) ? String(qs.path) : ''
  const bodyPath = (body && body.path) ? String(body.path) : ''
  let subPath = queryPath || bodyPath
  subPath = subPath ? (subPath.startsWith('/') ? subPath : '/' + subPath) : ''
  const routePath = subPath ? (path + subPath) : path

  try {
    // 搜索接口
    if (method === 'GET' && routePath.endsWith('/search')) {
      const code = String(qs.code || (body && body.code) || '').trim()
      if (!code) return response(400, { error: '缺少参数 code' })
      const data = await searchByCodeCloud(code)
      return response(200, { ok: true, data })
    }

    // 批量同步
    if (method === 'POST' && routePath.endsWith('/sync/pallets')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await syncPallets(items)
      return response(200, { ok: true, ...ret })
    }
    if (method === 'POST' && routePath.endsWith('/sync/packages')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await syncPackages(items)
      return response(200, { ok: true, ...ret })
    }
    if (method === 'POST' && routePath.endsWith('/sync/components')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await syncComponents(items)
      return response(200, { ok: true, ...ret })
    }

    // 新增：删除与清空集合接口
    if (method === 'POST' && routePath.endsWith('/delete/components')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await deleteComponents(items)
      return response(200, { ok: true, ...ret })
    }
    if (method === 'POST' && routePath.endsWith('/delete/packages')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await deletePackages(items)
      return response(200, { ok: true, ...ret })
    }
    if (method === 'POST' && routePath.endsWith('/delete/pallets')) {
      const items = Array.isArray(body.items) ? body.items : []
      const ret = await deletePallets(items)
      return response(200, { ok: true, ...ret })
    }
    if (method === 'POST' && routePath.endsWith('/clear')) {
      const collections = Array.isArray(body.collections) ? body.collections : null
      const ret = await clearCollections(collections)
      return response(200, { ok: true, ...ret })
    }

    // 一次性迁移：补齐标准字段并解析关联（dryRun 可选）
    if (method === 'POST' && routePath.endsWith('/migrate')) {
      const dryRun = !!(body && (body.dryRun === true || body.dry === true))
      const ret = await migrateAll({ dryRun })
      return response(200, { ok: true, ...ret })
    }

    // 未匹配的路由
    return response(404, { error: 'Not Found', path: routePath, method })
  } catch (err) {
    // 统一错误处理
    console.error('packOps error:', err)
    const msg = err && err.message ? err.message : 'Internal Server Error'
    return response(500, { error: msg })
  }
}

// 下面是一次性迁移工具：用于修复云端已有记录的字段命名与关联

function pickField(obj, keys, normalizeStr = true) {
  for (const k of keys) {
    if (obj.hasOwnProperty(k) && obj[k] != null) {
      const v = obj[k]
      if (typeof v === 'string') {
        const s = normalizeStr ? String(v).trim() : v
        if (s) return s
      } else {
        return v
      }
    }
  }
  return ''
}

async function migrateComponents({ dryRun = false } = {}) {
  const BATCH = 1000
  let skip = 0, updated = 0, scanned = 0
  while (true) {
    const res = await db.collection('components').where({}).skip(skip).limit(BATCH).get()
    const list = res.data || []
    if (list.length === 0) break
    for (const it of list) {
      scanned++
      const update = {}
      // 标准字段补齐
      if (!it.component_code) update.component_code = pickField(it, ['code','componentCode','编号','q_code','a_code','b_code'])
      if (!it.component_name) update.component_name = pickField(it, ['component_name','name','componentName','板件名','title'])
      if (!it.order_number) update.order_number = pickField(it, ['order_number','order_no','orderNumber','订单号'])
      if (!it.material) update.material = pickField(it, ['material','材质'])
      if (!it.finished_size) update.finished_size = pickField(it, ['finished_size','size','成品尺寸'])
      if (!it.room_number) update.room_number = pickField(it, ['room_number','room','roomNo','房间号'])
      if (!it.cabinet_number) update.cabinet_number = pickField(it, ['cabinet_number','cabinet','cabinetNo','柜号'])
      if (!it.customer_address) update.customer_address = pickField(it, ['customer_address','address','客户地址','收货地址'])
      if (!it.status) update.status = pickField(it, ['status','state','状态']) || 'pending'

      // 解析包裹关联
      let package_number = it.package_number || pickField(it, ['package_number','pack_no','packageNo','pkg_no','包裹号'])
      const invalidPkgId = (!it.package_id) || (typeof it.package_id === 'string' && (/^\d+$/.test(it.package_id) || it.package_id.length < 16)) || (typeof it.package_id === 'number')
      if (invalidPkgId) {
        let pkg = null
        // 优先通过包裹编号
        if (package_number) {
          pkg = await findPackageByNumber(String(package_number).trim())
        }
        // 若编号不可用，则尝试通过本地数值 id 映射
        if (!pkg && (typeof it.package_id === 'number' || /^\d+$/.test(String(it.package_id || '')))) {
          const numId = typeof it.package_id === 'number' ? it.package_id : Number(String(it.package_id))
          const byLocal = await db.collection('packages').where({ id: numId }).limit(1).get()
          pkg = byLocal.data && byLocal.data[0]
        }
        if (pkg) {
          update.package_id = pkg._id
          update.package_number = pkg.package_number
        } else if (package_number && !it.package_number) {
          update.package_number = String(package_number).trim()
        }
      } else if (!it.package_number && package_number) {
        update.package_number = String(package_number).trim()
      }

      const hasUpdates = Object.keys(update).length > 0
      if (hasUpdates && !dryRun) {
        await db.collection('components').doc(it._id).update({ data: update })
        updated++
      } else if (hasUpdates) {
        updated++
      }
    }
    skip += list.length
    if (list.length < BATCH) break
  }
  return { scanned, updated }
}

async function migratePackages({ dryRun = false } = {}) {
  const BATCH = 1000
  let skip = 0, updated = 0, scanned = 0
  while (true) {
    const res = await db.collection('packages').where({}).skip(skip).limit(BATCH).get()
    const list = res.data || []
    if (list.length === 0) break
    for (const it of list) {
      scanned++
      const update = {}
      if (!it.package_number) update.package_number = pickField(it, ['package_number','number','code','packageNo','pkg_no','包裹号'])
      if (!it.order_number) update.order_number = pickField(it, ['order_number','order_no','orderNumber','订单号'])
      if (!it.customer_address) update.customer_address = pickField(it, ['customer_address','address','客户地址','收货地址'])
      if (!it.status) update.status = pickField(it, ['status','state','状态']) || 'open'

      let pallet_number = it.pallet_number || pickField(it, ['pallet_number','palletNo','number','code','托盘号'])
      const invalidPalId = (!it.pallet_id) || (typeof it.pallet_id === 'string' && (/^\d+$/.test(it.pallet_id) || it.pallet_id.length < 16)) || (typeof it.pallet_id === 'number')
      if (invalidPalId) {
        let pal = null
        if (pallet_number) {
          pal = await findPalletByNumber(String(pallet_number).trim())
        }
        if (!pal && (typeof it.pallet_id === 'number' || /^\d+$/.test(String(it.pallet_id || '')))) {
          const numId = typeof it.pallet_id === 'number' ? it.pallet_id : Number(String(it.pallet_id))
          const byLocal = await db.collection('pallets').where({ id: numId }).limit(1).get()
          pal = byLocal.data && byLocal.data[0]
        }
        if (pal) {
          update.pallet_id = pal._id
          update.pallet_number = pal.pallet_number
        } else if (pallet_number && !it.pallet_number) {
          update.pallet_number = String(pallet_number).trim()
        }
      } else if (!it.pallet_number && pallet_number) {
        update.pallet_number = String(pallet_number).trim()
      }

      // 兜底板件数量与地址
      if (typeof it.component_count !== 'number') {
        let comps = await listComponentsInPackage(it._id)
        if ((!comps || comps.length === 0) && (it.package_number || update.package_number)) {
          const num = it.package_number || update.package_number
          comps = await listComponentsFallbackByNumber(num)
        }
        update.component_count = Array.isArray(comps) ? comps.length : 0
        if (!it.customer_address && Array.isArray(comps) && comps[0] && comps[0].customer_address) {
          update.customer_address = comps[0].customer_address
        }
      }

      const hasUpdates = Object.keys(update).length > 0
      if (hasUpdates && !dryRun) {
        await db.collection('packages').doc(it._id).update({ data: update })
        updated++
      } else if (hasUpdates) {
        updated++
      }
    }
    skip += list.length
    if (list.length < BATCH) break
  }
  return { scanned, updated }
}

async function migratePallets({ dryRun = false } = {}) {
  const BATCH = 1000
  let skip = 0, updated = 0, scanned = 0
  while (true) {
    const res = await db.collection('pallets').where({}).skip(skip).limit(BATCH).get()
    const list = res.data || []
    if (list.length === 0) break
    for (const it of list) {
      scanned++
      const update = {}
      if (!it.pallet_number) update.pallet_number = pickField(it, ['pallet_number','number','code','palletNo','托盘号'])
      if (!it.pallet_type) update.pallet_type = pickField(it, ['pallet_type','type','托盘类型']) || 'physical'
      if (!it.order_number) update.order_number = pickField(it, ['order_number','order_no','orderNumber','订单号'])
      if (!it.customer_address) update.customer_address = pickField(it, ['customer_address','address','客户地址','收货地址'])
      if (!it.status) update.status = pickField(it, ['status','state','状态']) || 'open'

      if (typeof it.package_count !== 'number') {
        let pkgs = await listPackagesOnPallet(it._id)
        if ((!pkgs || pkgs.length === 0) && (it.pallet_number || update.pallet_number)) {
          const num = it.pallet_number || update.pallet_number
          pkgs = await listPackagesFallbackByNumber(num)
        }
        update.package_count = Array.isArray(pkgs) ? pkgs.length : 0
        if (!it.customer_address && Array.isArray(pkgs) && pkgs[0]) {
          const firstPkg = pkgs[0]
          // 进一步取板件地址
          let comps = await listComponentsInPackage(firstPkg._id)
          if ((!comps || comps.length === 0) && firstPkg.package_number) {
            comps = await listComponentsFallbackByNumber(firstPkg.package_number)
          }
          if (comps && comps[0] && comps[0].customer_address) {
            update.customer_address = comps[0].customer_address
          }
        }
      }

      const hasUpdates = Object.keys(update).length > 0
      if (hasUpdates && !dryRun) {
        await db.collection('pallets').doc(it._id).update({ data: update })
        updated++
      } else if (hasUpdates) {
        updated++
      }
    }
    skip += list.length
    if (list.length < BATCH) break
  }
  return { scanned, updated }
}

async function migrateAll({ dryRun = false } = {}) {
  const pal = await migratePallets({ dryRun })
  const pkg = await migratePackages({ dryRun })
  const comp = await migrateComponents({ dryRun })
  return { pallets: pal, packages: pkg, components: comp, dryRun }
}