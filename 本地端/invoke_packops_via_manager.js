// invoke_packops_via_manager.js
const CloudBase = require('@cloudbase/manager-node');
const fs = require('fs');

(async () => {
  try {
    // 从 CLI env:list 结果中选取 envId
    const envId = 'cloud1-7grjr7usb5d86f59';
    // 从环境变量读取密钥，避免硬编码
    const secretId = process.env.SECRET_ID;
    const secretKey = process.env.SECRET_KEY;
    const region = process.env.TCB_REGION; // 可选：如 ap-shanghai / ap-guangzhou

    if (!secretId || !secretKey) {
      console.error('缺少 SECRET_ID 或 SECRET_KEY 环境变量，已停止。');
      process.exit(1);
    }

    const app = new CloudBase({ secretId, secretKey, envId, ...(region ? { region } : {}) });
    const { functions } = app;

    // 读取事件参数
    const event = JSON.parse(fs.readFileSync('invoke_packops_get_search.json', 'utf-8'));

    // 管理端 SDK 的 invokeFunction 第二个参数会作为云函数的 event 传入
    const res = await functions.invokeFunction('packOps', event);

    // SDK 返回的数据结构一般包含 RetMsg（字符串）或 Result（对象），不同版本略有差异
    const output = res.Result || res.RetMsg || res;
    if (typeof output === 'string') {
      console.log(output);
    } else {
      console.log(JSON.stringify(output, null, 2));
    }
  } catch (err) {
    console.error('Invoke via manager-node failed:', err);
    process.exit(1);
  }
})();