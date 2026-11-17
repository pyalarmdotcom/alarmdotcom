// Alarm.com WebRTC card: tokens are retrieved over authenticated HA websocket.

class AlarmWebRTCCard extends HTMLElement {
  constructor() {
    super();
    this._connected = false;
    this._connecting = false;
    this._requesting = false;
    this._currentConfig = null;
    this._secureConfig = null;
    this._requestSerial = 0;
    this._requestTimeout = null;
    this._retryTimer = null;
    this._retryCount = 0;
    this._maxRetries = 5;
    this._retryDelayMs = 4000;
    this.pc = null;
    this.ws = null;
    this.remoteId = null;
    this._janusKeepalive = null;
    this._entityId = null;
    this._disconnectGrace = null;
    this._streamGeneration = 0;
  }

  _log(...args) {
    // Never print stream configuration, tokens, or signaling payloads.
    if (this.config?.debug) console.debug(`[AlarmWebRTC ${this._entityId || "unknown"}]`, args.length ? String(args[0]) : "event");
  }

  // Several Alarm.com camera models offer H.264 at a profile-level-id (e.g. 4d4028,
  // Main Profile Level 4.0) that iOS/Safari's hardware decoder either rejects outright
  // or accepts without ever actually rendering frames, producing a black video element
  // with no error anywhere in the pipeline. Chrome/Android are unaffected. Forcing the
  // offer to 42e01f (Constrained Baseline Profile, Level 3.1) is the profile most
  // consistently supported across Apple's decoders and resolves this for the majority
  // of camera models. See #38.
  //
  // Detection intentionally covers Safari on both iOS and macOS, not just iOS: some
  // users only saw the black screen on macOS Safari while Chrome on the same Mac worked
  // fine, so gating on iOS alone misses real cases.
  _isAppleClient() {
    const ua = navigator.userAgent.toLowerCase();
    const isIOS =
      /ipad|iphone|ipod/.test(ua) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const isSafari = ua.includes("safari") && !ua.includes("chrome") && !ua.includes("chromium");
    const isMac = navigator.platform.toLowerCase().includes("mac");
    return isIOS || isSafari || isMac;
  }

  // Match any profile-level-id, not just the specific 4d4028 value one camera model was
  // observed sending. Different Alarm.com camera models encode at different profiles, and
  // matching only the literal value seen on one test camera silently does nothing for
  // every other model - matching the mixed results reported in #38, where the original
  // fix worked for some users' cameras but not others'.
  // Some models (ADC-V724x, ADC-VDB770) send an H.264 fmtp line with no profile-level-id
  // at all, which the decoder reads as the RFC 6184 default (Baseline 1.0) and iOS renders
  // black, so the id is also added to any H.264 payload that lacks one (#112).
  _patchAppleOfferSdp(sdp) {
    if (!sdp) return sdp;
    sdp = sdp.replace(/profile-level-id=[0-9a-fA-F]{6}/g, "profile-level-id=42e01f");
    for (const m of [...sdp.matchAll(/a=rtpmap:(\d+) H264\/90000/gi)]) {
      const pt = m[1];
      const fmtp = new RegExp(`a=fmtp:${pt} ([^\\r\\n]*)`);
      const f = sdp.match(fmtp);
      if (f) {
        if (!/profile-level-id/i.test(f[1])) sdp = sdp.replace(fmtp, `a=fmtp:${pt} ${f[1]};profile-level-id=42e01f`);
      } else {
        sdp = sdp.replace(m[0], `${m[0]}\r\na=fmtp:${pt} profile-level-id=42e01f`);
      }
    }
    return sdp;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Entity required");
    this.config = config;
    this._entityId = config.entity;
    this._requestSerial += 1;
    this._secureConfig = null;
    this._log("setConfig");
  }

  set hass(hass) {
    this._hass = hass;
    const entityId = this.config?.entity;
    if (!entityId) return;

    this._entityId = entityId;

    const stateObj = hass.states[entityId];
    if (!stateObj) {
      this._log("Entity not found");
      return;
    }

    let config = this._secureConfig;
    // Allow card config to override the Janus stream ID (useful for cameras
    // where the API doesn't expose the correct mountpoint ID).
    if (config && this.config?.janusStreamId != null) {
      config = { ...config, janusStreamId: this.config.janusStreamId };
    }
    const isValid = this.isConfigValid(config);

    this._log(
      "hass update",
      "streamType=",
      config?.streamType,
      "valid=",
      isValid,
      "connected=",
      this._connected,
      "connecting=",
      this._connecting,
      "requesting=",
      this._requesting
    );

    if (!isValid) {
      if (!this._requesting && !this._connecting) {
        this._requestTokens("No valid config");
      }
      return;
    }

    const hasNoCurrentConfig = !this._currentConfig;
    const isNewConfig =
      JSON.stringify(config) !== JSON.stringify(this._currentConfig);
    const streamTypeChanged =
      config?.streamType !== this._currentConfig?.streamType;

    // Only restart for structural changes (URL/stream type), not token rotation.
    const isStructuralChange = streamTypeChanged ||
      config?.signallingServerUrl !== this._currentConfig?.signallingServerUrl ||
      config?.janusGatewayUrl !== this._currentConfig?.janusGatewayUrl ||
      config?.janusStreamId !== this._currentConfig?.janusStreamId;

    const shouldStartFresh =
      !this._connected &&
      !this._connecting &&
      (hasNoCurrentConfig || isNewConfig || streamTypeChanged);

    const shouldRestart =
      isStructuralChange &&
      (this._connected || this._connecting);

    if (shouldRestart) {
      this._log("Config changed, restarting stream");
      this._teardownStream(false);
      this.renderVideo();
      this.startStream(config);
      return;
    }

    if (shouldStartFresh) {
      this._log("Valid config present, starting fresh stream");
      this.renderVideo();
      this.startStream(config);
      return;
    }
  }

  isConfigValid(config) {
    if (!config) return false;

    if (config.streamType === "janus" || config.janusGatewayUrl) {
      return !!(config.janusGatewayUrl && config.janusToken);
    }

    return !!(
      config.signallingServerUrl &&
      config.signallingServerToken &&
      config.cameraAuthToken
    );
  }

  renderPlaceholder(msg) {
    if (this._connected) return;
    this.innerHTML = `<ha-card><div style="padding:16px;text-align:center">${msg}</div></ha-card>`;
  }

  renderVideo() {
    this.innerHTML = `
      <ha-card style="position:relative;background:#000">
        <style>
          ha-card:fullscreen { width:100vw; height:100vh; display:flex; align-items:center; }
          ha-card:fullscreen video { max-height:100vh; object-fit:contain; }
        </style>
        <video autoplay playsinline muted style="width:100%;height:auto;background:#000;display:block"></video>
        <button type="button" aria-label="Toggle fullscreen" title="Toggle fullscreen"
          style="position:absolute;right:8px;bottom:8px;padding:8px;border:0;border-radius:4px;background:#0009;color:#fff;cursor:pointer">⛶</button>
      </ha-card>
    `;
    this.querySelector("button").addEventListener("click", () => this._toggleFullscreen());
  }

  async _toggleFullscreen() {
    const frame = this.querySelector("ha-card");
    const video = this.querySelector("video");
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (frame?.requestFullscreen) await frame.requestFullscreen();
      else if (video?.webkitEnterFullscreen) video.webkitEnterFullscreen();
    } catch {
      this._log("Fullscreen unavailable");
    }
  }

  _showReconnectButton(message = "Stream unavailable") {
    this.innerHTML = `
      <ha-card>
        <div style="padding:16px;text-align:center">
          <div style="margin-bottom:12px;color:#888">${message}</div>
          <button id="reconnect-btn" style="padding:8px 20px;background:var(--primary-color,#03a9f4);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px">Reconnect</button>
        </div>
      </ha-card>`;

    this.querySelector("#reconnect-btn").addEventListener("click", () => {
      this._log("Manual reconnect");
      this._retryCount = 0;
      this._requesting = false;
      this._connecting = false;
      this._connected = false;
      this._currentConfig = null;

      if (this._retryTimer) {
        clearTimeout(this._retryTimer);
        this._retryTimer = null;
      }

      this._requestTokens("Manual reconnect");
    });
  }

  _scheduleRetry(reason) {
    if (this._retryTimer) return;

    if (this._retryCount >= this._maxRetries) {
      this._log("Max retries reached", reason);
      this._showReconnectButton(`Stream unavailable (${reason})`);
      return;
    }

    this._retryCount += 1;
    this._log(
      `Scheduling retry ${this._retryCount}/${this._maxRetries} in ${this._retryDelayMs}ms`,
      reason
    );

    this.renderPlaceholder(`Reconnecting... (${this._retryCount}/${this._maxRetries})`);

    this._retryTimer = setTimeout(() => {
      this._retryTimer = null;
      this._requestTokens(reason);
    }, this._retryDelayMs);
  }

  _requestTokens(reason) {
    if (this._requesting) return;

    this._log("Requesting tokens", reason);
    this._requesting = true;

    clearTimeout(this._requestTimeout);
    const requestEntity = this.config.entity;
    const requestSerial = ++this._requestSerial;
    this._requestTimeout = setTimeout(() => {
      if (requestSerial !== this._requestSerial) return;
      this._log("Token request timed out");
      this._requestSerial += 1;
      this._requesting = false;
      this._scheduleRetry("Token timeout");
    }, 15000);

    this._hass.connection.sendMessagePromise({
      type: "alarmdotcom/webrtc_config",
      entity_id: requestEntity,
    }).then((config) => {
      if (this.config.entity !== requestEntity || requestSerial !== this._requestSerial) return;
      clearTimeout(this._requestTimeout);
      this._requesting = false;
      if (!this.isConfigValid(config)) {
        this._scheduleRetry("Invalid stream configuration");
        return;
      }
      this._secureConfig = config;
      this.hass = this._hass;
    }).catch(() => {
      if (this.config.entity !== requestEntity || requestSerial !== this._requestSerial) return;
      clearTimeout(this._requestTimeout);
      this._log("WebRTC credential request failed");
      this._requesting = false;
      this._scheduleRetry("Credential request failed");
    });

    this.renderPlaceholder("Refreshing session...");
  }

  _teardownStream(resetConfig = true) {
    // Invalidate old callbacks before closing: a late close must not kill a replacement stream.
    this._streamGeneration += 1;
    if (this._janusKeepalive) {
      clearInterval(this._janusKeepalive);
      this._janusKeepalive = null;
    }

    if (this.pc) {
      try {
        this.pc.ontrack = null;
        this.pc.onicecandidate = null;
        this.pc.oniceconnectionstatechange = null;
        this.pc.close();
      } catch (e) {}
      this.pc = null;
    }

    if (this.ws) {
      try {
        this.ws.onclose = null;
        this.ws.onmessage = null;
        this.ws.onerror = null;
        this.ws.close();
      } catch (e) {}
      this.ws = null;
    }

    this._connected = false;
    this._connecting = false;
    this.remoteId = null;

    if (resetConfig) {
      this._currentConfig = null;
    }
  }

  _markConnected() {
    this._connected = true;
    this._connecting = false;
    this._requesting = false;
    this._retryCount = 0;

    clearTimeout(this._requestTimeout);

    if (this._retryTimer) {
      clearTimeout(this._retryTimer);
      this._retryTimer = null;
    }
  }

  async startStream(config) {
    if (this._connecting) return;

    this._connecting = true;
    const generation = this._streamGeneration;
    this._currentConfig = config;

    this._log("Starting stream");

    try {
      if (config.streamType === "janus" || config.janusGatewayUrl) {
        this._log(">>> USING JANUS <<<");
        await this._startJanus(config);
      } else {
        this._log(">>> USING LEGACY <<<");
        await this._startLegacy(config);
      }
    } catch (err) {
      if (generation !== this._streamGeneration) return;
      this._log("startStream failed", err);
      this._teardownStream(false);
      this._requesting = false;
      this._scheduleRetry("startStream failed");
    }
  }

  async _startLegacy(config) {
    const generation = this._streamGeneration;
    const pc = new RTCPeerConnection({
      iceServers: config.iceServers || [],
    });
    this.pc = pc;

    const video = this.querySelector("video");

    const attemptPlay = async () => {
      if (video && (video.paused || video.ended)) {
        try {
          video.muted = true;
          await video.play();
          this._log("Legacy play success");
        } catch (e) {
          this._log("Legacy play failed", e);
        }
      }
    };

    pc.ontrack = (e) => {
      if (generation !== this._streamGeneration) return;
      if (!video.srcObject) {
        video.srcObject = e.streams[0];
        this._markConnected();
      }
      this._log("Legacy track received");
      attemptPlay();
    };

    pc.oniceconnectionstatechange = () => {
      if (generation !== this._streamGeneration) return;
      const s = pc.iceConnectionState;
      this._log("Legacy ICE state", s);
      if (s === "disconnected" || s === "failed" || s === "closed") {
        this._teardownStream(false);
        this._scheduleRetry(`Legacy ICE ${s}`);
      }
    };

    const ws = new WebSocket(
      `${config.signallingServerUrl}/${config.signallingServerToken}`
    );
    this.ws = ws;

    ws.onopen = () => {
      if (generation !== this._streamGeneration) return;
      this._log("Legacy WS connected");
      ws.send("HELLO 2.0.1");
    };

    ws.onerror = (err) => {
      this._log("Legacy WS error", err);
    };

    ws.onmessage = async (msg) => {
      if (generation !== this._streamGeneration) return;
      if (msg.data.startsWith("HELLO")) {
        ws.send(`START_SESSION ${config.cameraAuthToken}`);
        return;
      }

      if (msg.data.startsWith("SESSION_STARTED")) {
        return;
      }

      let data;
      try {
        data = JSON.parse(msg.data);
      } catch {
        return;
      }

      if (data.sdp?.type === "offer") {
        let remoteOffer = data.sdp;

        if (this._isAppleClient() && remoteOffer?.sdp) {
          this._log("Patching legacy offer SDP for Apple client");
          remoteOffer = {
            type: remoteOffer.type,
            sdp: this._patchAppleOfferSdp(remoteOffer.sdp),
          };
        }

        await pc.setRemoteDescription(remoteOffer);
        if (generation !== this._streamGeneration) return;
        const answer = await pc.createAnswer();
        if (generation !== this._streamGeneration) return;
        await pc.setLocalDescription(answer);
        if (generation !== this._streamGeneration) return;

        // Wait for ICE gathering to complete before sending answer,
        // so the SDP includes TURN relay candidates.
        await new Promise((resolve) => {
          if (pc.iceGatheringState === "complete") {
            resolve();
          } else {
            const onStateChange = () => {
              if (pc.iceGatheringState === "complete") {
                pc.removeEventListener("icegatheringstatechange", onStateChange);
                resolve();
              }
            };
            pc.addEventListener("icegatheringstatechange", onStateChange);
            // Safety timeout: don't wait more than 5s
            setTimeout(resolve, 5000);
          }
        });

        ws.send(
          JSON.stringify({
            to: data.from,
            sdp: pc.localDescription,
          })
        );
      }

      if (data.ice) {
        try {
          await pc.addIceCandidate(data.ice);
        if (generation !== this._streamGeneration) return;
        } catch (e) {
          this._log("Failed to add ICE candidate", e);
        }
      }
    };

    ws.onclose = () => {
      if (generation !== this._streamGeneration) return;
      const wasConnected = this._connected;
      this._log("Legacy WS closed");
      this._connected = false;
      this._connecting = false;
      this._requesting = false;
      this._teardownStream(false);
      this._scheduleRetry(
        wasConnected ? "Legacy stream ended" : "Legacy WS closed before connection"
      );
    };
  }

  _startJanusKeepalive(ws, sessionId, send) {
    // Janus kills sessions after 60s without a keepalive. Ping every 25s.
    const interval = setInterval(() => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        clearInterval(interval);
        return;
      }
      send({ janus: "keepalive", session_id: sessionId });
    }, 25000);
    return interval;
  }


  _buildJanusUrlCandidates(config) {
    return config.janusGatewayUrl ? [config.janusGatewayUrl] : [];
  }

  _connectJanusWebSocket(url) {
    return new Promise((resolve, reject) => {
      let settled = false;
      let ws;

      try {
        ws = new WebSocket(url, ["janus-protocol"]);
      } catch (err) {
        reject(err);
        return;
      }

      const cleanup = () => {
        ws.onopen = null;
        ws.onerror = null;
        ws.onclose = null;
      };

      const fail = (err) => {
        if (settled) return;
        settled = true;
        cleanup();
        try {
          ws.close();
        } catch (e) {}
        reject(err);
      };

      ws.onopen = () => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(ws);
      };

      ws.onerror = (err) => {
        fail(err || new Error("WebSocket error"));
      };

      ws.onclose = () => {
        fail(new Error(`WebSocket closed before open for ${url}`));
      };

      setTimeout(() => {
        fail(new Error(`WebSocket open timeout for ${url}`));
      }, 5000);
    });
  }

  async _openJanusWebSocket(config) {
    const candidates = this._buildJanusUrlCandidates(config);
    let lastError = null;

    for (const url of candidates) {
      this._log("Trying Janus WS URL", url);
      try {
        const ws = await this._connectJanusWebSocket(url);
        this._log("Janus WS opened", url);
        return ws;
      } catch (err) {
        lastError = err;
        this._log("Janus WS candidate failed", url, err);
      }
    }

    throw lastError || new Error("No Janus WebSocket URL could be opened");
  }

  async _startJanus(config) {
    const generation = this._streamGeneration;
    const pc = new RTCPeerConnection({
      iceServers: config.iceServers || [],
    });
    this.pc = pc;

    const video = this.querySelector("video");

    const attemptPlay = async () => {
      if (video && (video.paused || video.ended)) {
        try {
          video.muted = true;
          await video.play();
          this._log("Janus play success");
        } catch (e) {
          this._log("Janus play failed", e);
        }
      }
    };

    pc.ontrack = (e) => {
      if (generation !== this._streamGeneration) return;
      if (!video.srcObject) {
        video.srcObject = e.streams[0];
        this._markConnected();
      }
      this._log("Janus track received");
      attemptPlay();
    };

    pc.oniceconnectionstatechange = () => {
      if (generation !== this._streamGeneration) return;
      const s = pc.iceConnectionState;
      this._log("Janus ICE state", s);
      if (s === "disconnected" || s === "failed" || s === "closed") {
        this._teardownStream(false);
        this._scheduleRetry(`Janus ICE ${s}`);
      }
    };

    const ws = await this._openJanusWebSocket(config);
    if (generation !== this._streamGeneration) {
      ws.close();
      return;
    }
    this.ws = ws;

    let sessionId = null;
    let handleId = null;
    let streamId = config.janusStreamId ?? null;
    // For proxy streams, we need to create the mountpoint first before watching.
    // proxyUrl is the media_uri Janus uses to pull the stream from the camera.
    // Always create the mountpoint for proxy streams — the Janus stream ID is dynamic per session.
    const needsCreate = !!(config.proxyUrl);
    let mountpointCreated = false;

    const send = (msg) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const payload = {
        ...msg,
        token: config.janusToken,
        transaction: Math.random().toString(36).slice(2),
      };
      this._log("Janus send", payload);
      ws.send(JSON.stringify(payload));
    };

    this._log("Janus WS connected");

    send({ janus: "create" });

    ws.onerror = (err) => {
      this._log("Janus WS error", err);
    };

    ws.onmessage = async (event) => {
      if (generation !== this._streamGeneration) return;
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (err) {
        this._log("Janus parse failed", event.data, err);
        return;
      }

      this._log("Janus message", msg);

      if (msg.janus === "success" && !sessionId) {
        sessionId = msg.data?.id;
        this._log("Janus session created", sessionId);
        this._janusKeepalive = this._startJanusKeepalive(ws, sessionId, send);

        send({
          janus: "attach",
          session_id: sessionId,
          plugin: "janus.plugin.streaming",
        });
        return;
      }

      if (msg.janus === "success" && sessionId && !handleId) {
        handleId = msg.data?.id;
        this._log("Janus handle attached", handleId);

        if (needsCreate) {
          // Step 1: create the mountpoint so Janus pulls the stream from the camera.
          // The response will contain the assigned stream ID which we then use to watch.
          this._log("Janus creating proxy mountpoint", config.proxyUrl);
          send({
            janus: "message",
            session_id: sessionId,
            handle_id: handleId,
            body: {
              request: "create",
              type: "rtp",
              media_uri: config.proxyUrl,
              name: `${config.janusToken?.split(",")[0] ?? "stream"}_Live`,
              is_private: true,
              streaming_type: "Live",
              video: true,
              videoport: 0,
              videopt: 126,
              videortpmap: "H264/90000",
              timeout_seconds: 180,
              max_timeout_seconds: 900,
            },
          });
        } else {
          send({
            janus: "message",
            session_id: sessionId,
            handle_id: handleId,
            body: {
              request: "watch",
              id: streamId,
              token: config.janusToken,
              audio: true,
              video: true,
            },
          });
        }
        return;
      }

      // Handle the "create" mountpoint response — extract the assigned stream ID
      // then immediately send the "watch" request with it.
      if (msg.janus === "success" && sessionId && handleId && needsCreate && !mountpointCreated) {
        const createdId = msg.plugindata?.data?.stream?.id ?? msg.data?.id ?? msg.plugindata?.data?.id;
        if (createdId) {
          mountpointCreated = true;
          streamId = createdId;
          this._log("Janus mountpoint created, streamId", streamId);
          send({
            janus: "message",
            session_id: sessionId,
            handle_id: handleId,
            body: {
              request: "watch",
              id: streamId,
              token: config.janusToken,
              audio: true,
              video: true,
            },
          });
          return;
        }
      }

      if (msg.janus === "ack") {
        return;
      }

      if (msg.janus === "event") {
        const pluginData = msg.plugindata?.data;
        if (pluginData?.error) {
          this._log("Janus plugin error", pluginData.error_code, pluginData.error);
          this._teardownStream(false);
          this._scheduleRetry(`Plugin error ${pluginData.error_code}`);
          return;
        }
        // Non-error events (e.g. status updates) — fall through to JSEP check below
      }

      if (msg.jsep) {
        this._log("Janus JSEP received");

        let remoteJsep = msg.jsep;
        if (this._isAppleClient() && remoteJsep?.sdp) {
          this._log("Patching Janus offer SDP for Apple client");
          remoteJsep = { type: remoteJsep.type, sdp: this._patchAppleOfferSdp(remoteJsep.sdp) };
        }

        await pc.setRemoteDescription(remoteJsep);
        if (generation !== this._streamGeneration) return;

        const answer = await pc.createAnswer();
        if (generation !== this._streamGeneration) return;
        await pc.setLocalDescription(answer);
        if (generation !== this._streamGeneration) return;

        send({
          janus: "message",
          session_id: sessionId,
          handle_id: handleId,
          body: { request: "start" },
          jsep: pc.localDescription,
        });
        return;
      }

      if (msg.candidate) {
        try {
          await pc.addIceCandidate(msg.candidate);
        if (generation !== this._streamGeneration) return;
        } catch (err) {
          this._log("Failed to add Janus candidate", err);
        }
        return;
      }

      if (msg.janus === "webrtcup") {
        this._log("Janus WebRTC up");
        return;
      }

      if (msg.janus === "media") {
        this._log("Janus media event", msg);
        return;
      }

      if (msg.janus === "hangup") {
        this._log("Janus hangup", msg);
        this._teardownStream(false);
        this._scheduleRetry("Janus hangup");
        return;
      }

      if (msg.janus === "detached") {
        this._log("Janus detached", msg);
        this._teardownStream(false);
        this._scheduleRetry("Janus detached");
        return;
      }

      if (msg.janus === "error") {
        this._log("Janus error", msg);
        this._teardownStream(false);
        this._scheduleRetry("Janus error");
        return;
      }
    };

    pc.onicecandidate = (e) => {
      if (generation !== this._streamGeneration) return;
      if (e.candidate && sessionId && handleId) {
        send({
          janus: "trickle",
          session_id: sessionId,
          handle_id: handleId,
          candidate: e.candidate,
        });
      }
    };

    ws.onclose = () => {
      if (generation !== this._streamGeneration) return;
      const wasConnected = this._connected;
      this._log("Janus WS closed");
      this._connected = false;
      this._connecting = false;
      this._requesting = false;
      this._teardownStream(false);
      this._scheduleRetry(
        wasConnected ? "Janus stream ended" : "Janus WS closed before connection"
      );
    };
  }

  connectedCallback() {
    // Lovelace reparents cards during phone rotation. Keep the peer connection
    // alive if the same card returns within one second, then resume playback.
    clearTimeout(this._disconnectGrace);
    this._disconnectGrace = null;
    const video = this.querySelector("video");
    if (video?.srcObject && video.paused) video.play().catch(() => {});
    if (this._hass) this.hass = this._hass;
  }

  disconnectedCallback() {
    clearTimeout(this._disconnectGrace);
    this._disconnectGrace = setTimeout(() => {
      this._disconnectGrace = null;
      if (this.isConnected) return;
      clearTimeout(this._requestTimeout);
      clearTimeout(this._retryTimer);
      this._retryTimer = null;
      this._requestSerial += 1;
      this._secureConfig = null;
      this._teardownStream();
      this._requesting = false;
      this._connecting = false;
    }, 1000);
  }
}

if (!customElements.get("alarm-webrtc-card")) {
  customElements.define("alarm-webrtc-card", AlarmWebRTCCard);
}
