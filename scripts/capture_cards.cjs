const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const stage = process.argv[2];
const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const binary = process.env.CHROME_BIN || (process.platform === 'darwin' ? macChrome : 'google-chrome');
const chrome = spawn(binary, [
  '--headless', '--remote-debugging-pipe', '--no-first-run',
  '--disable-background-networking', '--disable-component-update',
  '--no-default-browser-check', '--disable-sync', '--disable-gpu',
  `--user-data-dir=${stage}/chrome`,
], {stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});

let requestId = 0;
const calls = new Map();
const events = new Map();
let pending = '';
const deadline = setTimeout(() => {
  console.error('Chrome capture timed out');
  chrome.kill();
  process.exit(1);
}, 50000);
chrome.on('error', error => {
  console.error(error.message);
  process.exit(1);
});
chrome.on('exit', (code, signal) => {
  if (calls.size || events.size) {
    console.error(`Chrome ended before capture (${signal || code})`);
    process.exit(1);
  }
});
chrome.stdio[4].on('data', data => {
  pending += data.toString();
  const messages = pending.split('\0');
  pending = messages.pop();
  for (const raw of messages) {
    const message = JSON.parse(raw);
    if (calls.has(message.id)) {
      const {resolve, reject} = calls.get(message.id);
      calls.delete(message.id);
      if (message.error) reject(Error(JSON.stringify(message.error)));
      else resolve(message.result);
    }
    if (events.has(message.method)) {
      events.get(message.method)();
      events.delete(message.method);
    }
  }
});
function call(method, params = {}, sessionId) {
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    calls.set(id, {resolve, reject});
    chrome.stdio[3].write(JSON.stringify({id, method, params, sessionId}) + '\0');
  });
}

async function capture() {
  const {targetId} = await call('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await call('Target.attachToTarget', {targetId, flatten: true});
  const send = (method, params) => call(method, params, sessionId);
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1080, height: 1350, deviceScaleFactor: 1, mobile: false,
  });
  const slides = path.join(stage, 'slides');
  for (const slide of fs.readdirSync(slides).filter(name => name.endsWith('.html')).sort()) {
    const loaded = new Promise(resolve => events.set('Page.loadEventFired', resolve));
    await send('Page.navigate', {url: pathToFileURL(path.join(slides, slide)).href});
    await loaded;
    const {result: {value: fits}} = await send('Runtime.evaluate', {
      expression: `document.fonts.ready.then(() => {
        const frame = document.querySelector('.frame');
        const footer = document.querySelector('.foot').getBoundingClientRect();
        const last = frame.querySelector('.copy,.cover-rule').getBoundingClientRect();
        return frame.scrollWidth === 1080 && frame.scrollHeight === 1350
          && footer.top - last.bottom >= 20 && footer.bottom <= 1350;
      })`, awaitPromise: true, returnByValue: true,
    });
    if (!fits) throw Error(`Content exceeds card bounds: ${slide}`);
    const {data} = await send('Page.captureScreenshot', {format: 'png'});
    fs.writeFileSync(path.join(stage, 'package', slide.replace('.html', '.png')), data, 'base64');
    console.log(slide.replace('.html', '.png'));
  }
}

capture().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
}).finally(() => {
  clearTimeout(deadline);
  chrome.kill();
});
