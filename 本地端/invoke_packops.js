// invoke_packops.js
const { spawn } = require('child_process');
const fs = require('fs');

const envId = 'cloud1-7grjr7usb5d86f59';
const jsonPath = 'e:\\Trae\\021\\invoke_packops_get_search.json';

try {
  // 将 JSON 压平为单行，避免换行导致 shell 解析问题
  const jsonString = fs.readFileSync(jsonPath, 'utf8').replace(/\r?\n/g, '').trim();

  const args = ['fn', 'invoke', 'packOps', '-e', envId, '--params', jsonString];
  console.log('Spawning:', 'tcb', args.join(' '));

  // 在 Windows 上通过 shell 执行以解析 tcb.cmd
  const child = spawn('tcb', args, { shell: true });

  child.stdout.on('data', (data) => {
    process.stdout.write(data);
  });

  child.stderr.on('data', (data) => {
    process.stderr.write(data);
  });

  child.on('exit', (code) => {
    console.log(`tcb exited with code ${code}`);
    process.exit(code);
  });
} catch (err) {
  console.error('Failed to read JSON or spawn tcb:', err);
  process.exit(1);
}