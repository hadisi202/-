// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  const { code } = event
  
  if (!code) {
    return {
      code: -1,
      message: '编码不能为空'
    }
  }
  
  try {
    // 查询托盘
    const result = await db.collection('pallets')
      .where({
        pallet_number: code
      })
      .limit(1)
      .get()
    
    if (result.data && result.data.length > 0) {
      return {
        code: 0,
        data: result.data,
        message: '查询成功'
      }
    }
    
    return {
      code: 0,
      data: [],
      message: '未找到匹配的托盘'
    }
  } catch (error) {
    console.error('查询托盘失败:', error)
    return {
      code: -1,
      message: '查询失败: ' + error.message
    }
  }
}