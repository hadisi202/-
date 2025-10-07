// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const wxContext = cloud.getWXContext()
  
  try {
    // 获取统计数据
    const componentsCount = await db.collection('components').count()
    const packagesCount = await db.collection('packages').count()
    const palletsCount = await db.collection('pallets').count()
    
    return {
      code: 0,
      data: {
        components: componentsCount.total,
        packages: packagesCount.total,
        pallets: palletsCount.total
      },
      message: '统计成功'
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
    return {
      code: -1,
      message: '获取统计数据失败: ' + error.message
    }
  }
}