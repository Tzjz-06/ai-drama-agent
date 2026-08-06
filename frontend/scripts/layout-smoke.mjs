const socketUrl = process.env.CDP_WS;
if (!socketUrl) throw new Error("CDP_WS is required");

const socket = new WebSocket(socketUrl);
const pending = new Map();
let sequence = 0;
const guard = setTimeout(() => {
  console.error("CDP layout smoke timed out");
  process.exitCode = 1;
  socket.close();
}, 10000);

function send(method, params = {}) {
  return new Promise((resolve) => {
    const id = ++sequence;
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });
}

socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  const resolve = pending.get(message.id);
  if (!resolve) return;
  pending.delete(message.id);
  resolve(message);
};

socket.onerror = (event) => {
  console.error("CDP WebSocket failed", event.message || "unknown error");
};

socket.onopen = async () => {
  await send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await send("Page.reload");
  await new Promise((resolve) => setTimeout(resolve, 2500));
  const expression = `JSON.stringify({
    innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    stylesheets: [...document.styleSheets].map((sheet) => sheet.href).filter(Boolean),
    panel: document.querySelector('.auth-panel').getBoundingClientRect().toJSON(),
    form: document.querySelector('.auth-form').getBoundingClientRect().toJSON(),
    tform: document.querySelector('.t-form').getBoundingClientRect().toJSON(),
    controls: document.querySelector('.t-form__controls').getBoundingClientRect().toJSON(),
    input: document.querySelector('.t-input').getBoundingClientRect().toJSON()
  })`;
  const response = await send("Runtime.evaluate", { expression, returnByValue: true });
  console.log(response.result.result.value);
  clearTimeout(guard);
  socket.close();
};
