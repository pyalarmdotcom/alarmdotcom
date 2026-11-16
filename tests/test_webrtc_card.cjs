// Exercise the real card lifecycle without a camera or browser credentials.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");

function loadCard() {
  const timers = new Map();
  let serial = 0;
  let Card;
  const document = {};
  const context = {
    HTMLElement: class {}, document, console,
    setTimeout: (fn) => { timers.set(++serial, fn); return serial; },
    clearTimeout: (id) => timers.delete(id),
    clearInterval: () => {},
    customElements: { get: () => undefined, define: (_name, cls) => { Card = cls; } },
  };
  vm.runInNewContext(fs.readFileSync("custom_components/alarmdotcom/www/alarm-webrtc-card.js", "utf8"), context);
  const card = new Card();
  card.isConnected = true;
  return { card, timers, document, context };
}

test("rotation preserves the current stream and resumes the same video", () => {
  const { card, timers } = loadCard();
  let played = 0;
  const video = { srcObject: {}, paused: true, play: () => { played++; return Promise.resolve(); } };
  card.querySelector = () => video;
  card.pc = { close: () => assert.fail("rotation must not close the peer") };
  card.disconnectedCallback();
  assert.equal(timers.size, 1);
  card.connectedCallback();
  assert.equal(timers.size, 0);
  assert.equal(played, 1);
});

test("actual card removal closes transports and invalidates outstanding credentials", () => {
  const { card, timers } = loadCard();
  let closed = 0;
  card.pc = { close: () => { closed++; } };
  card.ws = { close: () => { closed++; } };
  card._secureConfig = { private: "token" };
  card.isConnected = false;
  card.disconnectedCallback();
  [...timers.values()][0]();
  assert.equal(closed, 2);
  assert.equal(card._secureConfig, null);
  assert.equal(card._requestSerial, 1);
});

test("fullscreen uses standard API and falls back to the iPhone player", async () => {
  const { card, document } = loadCard();
  let entered = 0;
  card.querySelector = (name) => name === "ha-card" ? { requestFullscreen: async () => { entered++; } } : {};
  await card._toggleFullscreen();
  assert.equal(entered, 1);
  let exited = 0;
  document.fullscreenElement = {};
  document.exitFullscreen = async () => { exited++; };
  await card._toggleFullscreen();
  assert.equal(exited, 1);
  document.fullscreenElement = null;
  card.querySelector = (name) => name === "video" ? { webkitEnterFullscreen: () => { entered++; } } : {};
  await card._toggleFullscreen();
  assert.equal(entered, 2);
});

test("Janus websocket opening resolves after an open event", async () => {
  const { card, context } = loadCard();
  let socket;
  context.WebSocket = class { constructor() { socket = this; } close() {} };
  const connection = card._connectJanusWebSocket("wss://example.test");
  socket.onopen();
  assert.equal(await connection, socket);
});

test("late Janus connection cannot replace the current stream", async () => {
  const { card, context } = loadCard();
  context.RTCPeerConnection = class {};
  card.querySelector = () => ({});
  let resolveSocket;
  card._openJanusWebSocket = () => new Promise((resolve) => { resolveSocket = resolve; });
  const opening = card._startJanus({});
  card._streamGeneration++;
  let closed = false;
  resolveSocket({ close: () => { closed = true; } });
  await opening;
  assert.equal(closed, true);
  assert.equal(card.ws, null);
});


test("legacy token rejection closes transports and retries with newly requested credentials", async () => {
  const { card, context, timers } = loadCard();
  let closed = 0;
  context.RTCPeerConnection = class { close() { closed++; } };
  let socket;
  context.WebSocket = class { constructor() { socket = this; } close() { closed++; } };
  card.querySelector = () => ({});
  card.renderPlaceholder = () => {};
  card.config = { entity: "camera.test" };
  const oldConfig = { signallingServerUrl: "wss://example.test", signallingServerToken: "old", cameraAuthToken: "old" };
  card._secureConfig = oldConfig;
  card._currentConfig = oldConfig;
  card._connecting = true;
  await card._startLegacy(oldConfig);
  const lateMessage = socket.onmessage;
  await socket.onmessage({ data: JSON.stringify({ error: "Invalid token!" }) });
  assert.equal(closed, 2);
  assert.equal(card._secureConfig, null);
  assert.equal(card._currentConfig, null);
  assert.equal(card._connecting, false);
  assert.equal(timers.size, 1);
  // A queued close/error from the old stream must not consume another retry.
  await lateMessage({ data: JSON.stringify({ error: "Invalid token!" }) });
  assert.equal(card._retryCount, 1);
  let requested = 0;
  card._requestTokens = () => { requested++; };
  [...timers.values()][0]();
  assert.equal(requested, 1);
});

test("identical refreshed configuration can restart a closed stream", () => {
  const { card } = loadCard();
  const config = { signallingServerUrl: "wss://example.test", signallingServerToken: "same", cameraAuthToken: "same" };
  card.config = { entity: "camera.test" };
  card._secureConfig = config;
  card._currentConfig = config;
  card.renderVideo = () => {};
  let started = 0;
  card.startStream = () => { started++; };
  card.hass = { states: { "camera.test": {} } };
  assert.equal(started, 1);
});

test("dashboard return requests credentials and ignores the removed card's pending response", async () => {
  const { card, timers } = loadCard();
  card.config = { entity: "camera.test" };
  card.renderPlaceholder = () => {};
  card.querySelector = () => null;
  let resolveOld;
  let calls = 0;
  const hass = { states: { "camera.test": {} }, connection: { sendMessagePromise: () => {
    calls++;
    return new Promise((resolve) => { resolveOld = resolve; });
  } } };
  card.hass = hass;
  const staleResolve = resolveOld;
  card.isConnected = false;
  card.disconnectedCallback();
  timers.get(card._disconnectGrace)();
  // HA state updates while absent must not start new sessions.
  card.hass = hass;
  assert.equal(calls, 1);
  card.isConnected = true;
  card.connectedCallback();
  assert.equal(calls, 2);
  staleResolve({ signallingServerUrl: "wss://example.test", signallingServerToken: "stale", cameraAuthToken: "stale" });
  await Promise.resolve();
  assert.equal(card._secureConfig, null);
  assert.equal(card._requesting, true);
});

test("retry budget survives state updates and stops repeated token failures", () => {
  const { card, timers } = loadCard();
  card.config = { entity: "camera.test" };
  card.renderPlaceholder = () => {};
  let exhausted = 0;
  card._showReconnectButton = () => { exhausted++; };
  card._retryCount = card._maxRetries;
  card._scheduleRetry("Signaling rejected session");
  card._hass = { states: { "camera.test": {} }, connection: { sendMessagePromise: () => assert.fail("retry budget exhausted") } };
  card.hass = card._hass;
  assert.equal(exhausted, 1);
  assert.equal(timers.size, 0);
});


test("Janus rejection also discards credentials before retrying", async () => {
  const { card, context, timers } = loadCard();
  context.RTCPeerConnection = class { close() {} };
  context.WebSocket = { OPEN: 1 };
  const socket = { readyState: 1, send() {}, close() {} };
  card._openJanusWebSocket = async () => socket;
  card.querySelector = () => ({});
  card.renderPlaceholder = () => {};
  card._secureConfig = { janusToken: "synthetic-old" };
  await card._startJanus(card._secureConfig);
  await socket.onmessage({ data: JSON.stringify({ janus: "error", error: { code: 403, reason: "synthetic" } }) });
  assert.equal(card._secureConfig, null);
  assert.equal(card.ws, null);
  assert.equal(card.pc, null);
  assert.equal(timers.size, 1);
});

test("brief connections cannot renew the retry budget indefinitely", () => {
  const { card, timers } = loadCard();
  card.config = { entity: "camera.test" };
  card.renderPlaceholder = () => {};
  let exhausted = 0;
  card._showReconnectButton = () => { exhausted++; };
  for (let attempt = 0; attempt < 6; attempt++) {
    card.pc = { iceConnectionState: "connected", close() {} };
    card._markConnected();
    card._scheduleRetry("Stream ended");
    if (card._retryTimer) {
      clearTimeout(card._retryTimer);
      timers.delete(card._retryTimer);
      card._retryTimer = null;
    }
  }
  assert.equal(card._retryCount, 5);
  assert.equal(exhausted, 1);
  assert.equal(card._stableTimer, null);
});

test("retry count resets only after a stable live connection", () => {
  const { card, timers } = loadCard();
  card._retryCount = 3;
  card.pc = { iceConnectionState: "connected", close() {} };
  card._markConnected();
  assert.equal(card._retryCount, 3);
  timers.get(card._stableTimer)();
  assert.equal(card._retryCount, 0);
});

test("late stability callback cannot reset a replacement stream's budget", () => {
  const { card, timers } = loadCard();
  card._retryCount = 3;
  card.pc = { iceConnectionState: "connected", close() {} };
  card._markConnected();
  const stale = timers.get(card._stableTimer);
  card._teardownStream();
  card._retryCount = 4;
  stale();
  assert.equal(card._retryCount, 4);
});

test("frequent recoveries have a rolling cap even after stable periods", () => {
  const { card, timers } = loadCard();
  card.renderPlaceholder = () => {};
  let exhausted = 0;
  card._showReconnectButton = () => { exhausted++; };
  for (let attempt = 0; attempt < 11; attempt++) {
    card._retryCount = 0; // Simulate each connection surviving the stability period.
    card._scheduleRetry("Stream ended");
    if (card._retryTimer) {
      timers.delete(card._retryTimer);
      card._retryTimer = null;
    }
  }
  assert.equal(card._retryWindow.length, 10);
  assert.equal(exhausted, 1);
});

test("brief dashboard reparenting cannot reset an exhausted retry budget", () => {
  const { card } = loadCard();
  card.querySelector = () => null;
  card._retryCount = 5;
  card.disconnectedCallback();
  card.connectedCallback();
  assert.equal(card._retryCount, 5);
});
