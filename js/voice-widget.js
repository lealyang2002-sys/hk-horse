(function () {
  // Only show when logged in
  const user = JSON.parse(sessionStorage.getItem('cmhk_auth_user') || 'null');
  if (!user) return;

  // ── Styles ────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #vc-fab { position:fixed; bottom:32px; right:32px; z-index:9990; }
    #vc-fab-btn {
      width:56px; height:56px; border-radius:50%;
      background:#fcd535; border:none; cursor:pointer;
      display:flex; align-items:center; justify-content:center;
      box-shadow:0 4px 24px rgba(0,0,0,.5);
      transition:transform .15s, background .15s;
    }
    #vc-fab-btn:hover { transform:scale(1.08); }
    .vc-icon {
      font-family:'Material Symbols Outlined';
      font-variation-settings:'FILL' 1;
      font-style:normal; line-height:1; display:inline-block;
    }
    #vc-fab-btn .vc-icon { font-size:26px; color:#181a20; }
    #vc-ptt .vc-icon     { font-size:30px; color:#181a20; }
    @keyframes vc-pulse {
      0%   { box-shadow:0 0 0 0   rgba(246,70,93,.6); }
      70%  { box-shadow:0 0 0 14px rgba(246,70,93,0);  }
      100% { box-shadow:0 0 0 0   rgba(246,70,93,0);  }
    }
    #vc-fab-btn.recording { background:#f6465d; animation:vc-pulse 1.1s infinite; }
    @keyframes vc-wave {
      0%,100% { transform:scaleY(.3); } 50% { transform:scaleY(1); }
    }
    .vc-bar { display:inline-block; width:3px; border-radius:2px;
               background:#fcd535; animation:vc-wave 1s ease-in-out infinite;
               transform-origin:bottom; }
    .vc-bar:nth-child(2){animation-delay:.1s}
    .vc-bar:nth-child(3){animation-delay:.2s}
    .vc-bar:nth-child(4){animation-delay:.3s}
    .vc-bar:nth-child(5){animation-delay:.2s}
    @keyframes vc-dot {
      0%,80%,100%{opacity:0} 40%{opacity:1}
    }
    .vc-dot{animation:vc-dot 1.4s ease-in-out infinite;font-size:18px;line-height:1}
    .vc-dot:nth-child(2){animation-delay:.2s}
    .vc-dot:nth-child(3){animation-delay:.4s}
    #vc-panel {
      position:fixed; z-index:9989; width:300px;
      background:#1e2329; border:1px solid #2b3139;
      border-radius:14px; box-shadow:0 12px 40px rgba(0,0,0,.6);
      display:none; flex-direction:column; overflow:hidden;
    }
    #vc-panel.open { display:flex; }
    #vc-log {
      flex:1; overflow-y:auto; padding:12px;
      display:flex; flex-direction:column; gap:8px;
      max-height:220px; min-height:60px;
    }
    #vc-log::-webkit-scrollbar { width:4px; }
    #vc-log::-webkit-scrollbar-track { background:transparent; }
    #vc-log::-webkit-scrollbar-thumb { background:#2b3139; border-radius:4px; }
    .vc-bubble-user {
      align-self:flex-end; background:rgba(252,213,53,.15);
      border:1px solid rgba(252,213,53,.25); color:#eae2d1;
      padding:6px 10px; border-radius:10px 10px 2px 10px;
      font-size:12px; max-width:80%;
    }
    .vc-bubble-ai {
      align-self:flex-start; background:#2b3139;
      border:1px solid #3a3f47; color:#eae2d1;
      padding:6px 10px; border-radius:10px 10px 10px 2px;
      font-size:12px; max-width:80%;
    }
    .vc-bubble-err {
      align-self:center; color:#f6465d; font-size:11px;
    }
  `;
  document.head.appendChild(style);

  // ── DOM ───────────────────────────────────────────────────────────────────
  const fab = document.createElement('div');
  fab.id = 'vc-fab';
  fab.innerHTML = `
    <button id="vc-fab-btn" title="語音助手">
      <span class="vc-icon">mic</span>
    </button>`;
  document.body.appendChild(fab);

  const panel = document.createElement('div');
  panel.id = 'vc-panel';
  panel.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding:12px 14px;border-bottom:1px solid #2b3139;flex-shrink:0">
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-family:'Material Symbols Outlined';font-size:18px;
                     color:#fcd535;font-variation-settings:'FILL' 1;font-style:normal">
          record_voice_over</span>
        <span style="color:#eae2d1;font-size:13px;font-weight:600">賽馬AI語音助手</span>
      </div>
      <button id="vc-close" style="background:none;border:none;color:#707a8a;
              cursor:pointer;font-size:18px;line-height:1;padding:0"
              title="關閉">✕</button>
    </div>
    <div id="vc-log">
      <div style="text-align:center;color:#707a8a;font-size:12px;padding:8px 0">
        按住按鈕說話，鬆開發送
      </div>
    </div>
    <div style="padding:14px;border-top:1px solid #2b3139;flex-shrink:0;
                display:flex;flex-direction:column;align-items:center;gap:10px">
      <div id="vc-status" style="height:20px;display:flex;align-items:center;
                                  gap:4px;color:#707a8a;font-size:12px">
        按住說話
      </div>
      <button id="vc-ptt"
        style="width:64px;height:64px;border-radius:50%;background:#fcd535;
               border:none;cursor:pointer;display:flex;align-items:center;
               justify-content:center;box-shadow:0 2px 12px rgba(0,0,0,.3);
               transition:transform .1s,background .1s;touch-action:none"
        title="按住說話">
        <span id="vc-ptt-icon" class="vc-icon" style="font-size:30px">mic</span>
      </button>
    </div>`;
  document.body.appendChild(panel);

  const fabBtn  = document.getElementById('vc-fab-btn');
  const fabIcon = fabBtn.querySelector('.vc-icon');
  const pttBtn  = document.getElementById('vc-ptt');
  const pttIcon = document.getElementById('vc-ptt-icon');
  const vcLog   = document.getElementById('vc-log');
  const vcStatus = document.getElementById('vc-status');
  document.getElementById('vc-close').addEventListener('click', closePanel);

  // ── Click to toggle ───────────────────────────────────────────────────────
  fabBtn.addEventListener('click', togglePanel);

  // ── Panel positioning ─────────────────────────────────────────────────────
  function positionPanel() {
    const r = fab.getBoundingClientRect();
    const pw = 300, ph = 360;
    let left = r.right  - pw;
    let top  = r.top    - ph - 10;
    left = Math.max(8, Math.min(window.innerWidth  - pw - 8, left));
    top  = Math.max(8, Math.min(window.innerHeight - ph - 8, top));
    panel.style.left = left + 'px';
    panel.style.top  = top  + 'px';
  }

  function togglePanel() {
    if (panel.classList.contains('open')) {
      closePanel();
    } else {
      positionPanel();
      panel.classList.add('open');
      fabIcon.textContent = 'close';
    }
  }

  function closePanel() {
    panel.classList.remove('open');
    fabIcon.textContent = 'mic';
  }

  // ── Audio state ───────────────────────────────────────────────────────────
  const MIN_PCM_BYTES = 16000; // 500 ms at 16 kHz 16-bit mono

  let audioCtx = null, mediaStream = null;
  let scriptProc = null, silentGain = null;
  let pcmChunks = [], recording = false, busy = false, currentAudio = null;

  function setStatus(state, msg) {
    const waveHtml = `<div style="display:flex;align-items:flex-end;gap:3px;height:18px">
      ${[14,20,18,24,18,20,14].map(h =>
        `<div class="vc-bar" style="height:${h}px"></div>`).join('')}
    </div>`;
    const dotsHtml = `<span class="vc-dot">·</span><span class="vc-dot">·</span><span class="vc-dot">·</span>`;

    if (state === 'idle') {
      vcStatus.innerHTML = '<span style="color:#707a8a">按住說話</span>';
      pttIcon.textContent = 'mic';
      pttBtn.style.background = '#fcd535';
      fabBtn.classList.remove('recording');
      fabIcon.textContent = panel.classList.contains('open') ? 'close' : 'mic';
    } else if (state === 'recording') {
      vcStatus.innerHTML = waveHtml;
      pttIcon.textContent = 'stop';
      pttBtn.style.background = '#f6465d';
      fabBtn.classList.add('recording');
      fabIcon.textContent = 'mic';
    } else if (state === 'thinking') {
      vcStatus.innerHTML = `<span style="color:#707a8a;display:flex;align-items:center;gap:2px">AI 思考中 ${dotsHtml}</span>`;
      pttIcon.textContent = 'hourglass_empty';
      pttBtn.style.background = '#2b3139';
    } else if (state === 'playing') {
      vcStatus.innerHTML = '<span style="color:#0ecb81">▶ AI 回覆播放中</span>';
      pttIcon.textContent = 'volume_up';
      pttBtn.style.background = '#0ecb81';
      fabBtn.classList.remove('recording');
    } else if (state === 'error') {
      vcStatus.innerHTML = `<span style="color:#f6465d">${msg || '發生錯誤'}</span>`;
      pttIcon.textContent = 'mic';
      pttBtn.style.background = '#fcd535';
    }
  }

  function addBubble(cls, html) {
    // Remove placeholder text
    const placeholder = vcLog.querySelector('div[style*="text-align"]');
    if (placeholder) placeholder.remove();
    const d = document.createElement('div');
    d.className = cls;
    d.innerHTML = html;
    vcLog.appendChild(d);
    vcLog.scrollTop = vcLog.scrollHeight;
    return d;
  }

  // ── Recording ─────────────────────────────────────────────────────────────
  async function ensureAudio() {
    if (!mediaStream) {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 }
      });
    }
    if (!audioCtx || audioCtx.state === 'closed') {
      audioCtx = new AudioContext({ sampleRate: 16000 });
    }
    if (audioCtx.state === 'suspended') await audioCtx.resume();
  }

  function startCapture() {
    pcmChunks = [];
    recording = true;
    const src = audioCtx.createMediaStreamSource(mediaStream);
    scriptProc = audioCtx.createScriptProcessor(4096, 1, 1);
    silentGain = audioCtx.createGain();
    silentGain.gain.value = 0;
    scriptProc.onaudioprocess = (e) => {
      if (!recording) return;
      const f32 = e.inputBuffer.getChannelData(0);
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++)
        i16[i] = Math.max(-32768, Math.min(32767, Math.round(f32[i] * 32768)));
      pcmChunks.push(i16.buffer.slice(0));
    };
    src.connect(scriptProc);
    scriptProc.connect(silentGain);
    silentGain.connect(audioCtx.destination);
  }

  function stopCapture() {
    recording = false;
    if (scriptProc) { scriptProc.disconnect(); scriptProc = null; }
    if (silentGain)  { silentGain.disconnect();  silentGain = null; }
    const total = pcmChunks.reduce((s, b) => s + b.byteLength, 0);
    if (!total) return null;
    const out = new Uint8Array(total);
    let off = 0;
    for (const c of pcmChunks) { out.set(new Uint8Array(c), off); off += c.byteLength; }
    pcmChunks = [];
    return out.buffer;
  }

  // ── PTT events ────────────────────────────────────────────────────────────
  pttBtn.addEventListener('pointerdown', async (e) => {
    e.preventDefault();
    // Stop anything in-flight and allow a fresh recording
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    if (scriptProc)   { scriptProc.disconnect(); scriptProc = null; }
    if (silentGain)   { silentGain.disconnect();  silentGain = null; }
    busy = false; recording = false;

    try { await ensureAudio(); } catch (err) {
      setStatus('error', '麥克風錯誤'); return;
    }
    startCapture();
    setStatus('recording');
    pttBtn.setPointerCapture(e.pointerId);
  });

  pttBtn.addEventListener('pointerup', async (e) => {
    e.preventDefault();
    if (!recording) return;
    const pcm = stopCapture();
    if (!pcm || pcm.byteLength < MIN_PCM_BYTES) { setStatus('idle'); return; }

    busy = true;
    setStatus('thinking');
    addBubble('vc-bubble-user', '🎤 語音訊息');
    const aiBubble = addBubble('vc-bubble-ai',
      `<span class="vc-dot">·</span><span class="vc-dot">·</span><span class="vc-dot">·</span>`);

    try {
      const resp = await fetch('/api/voice-chat', {
        method: 'POST', headers: { 'Content-Type': 'audio/pcm' }, body: pcm
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        throw new Error(j.error || `HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      const url  = URL.createObjectURL(blob);

      aiBubble.innerHTML = `<button onclick="(function(u){
        var a=new Audio(u);a.play()})('${url}')"
        style="background:none;border:none;color:#0ecb81;cursor:pointer;
               font-size:12px;display:flex;align-items:center;gap:4px;padding:0">
        <span style="font-family:'Material Symbols Outlined';font-size:16px;
                     font-variation-settings:'FILL' 1">play_circle</span>語音回覆
      </button>`;

      setStatus('playing');
      const audio = new Audio(url);
      currentAudio = audio;
      audio.onended = () => { URL.revokeObjectURL(url); currentAudio = null; busy = false; setStatus('idle'); };
      audio.onerror = () => { currentAudio = null; busy = false; setStatus('idle'); };
      audio.play().catch(() => { busy = false; setStatus('idle'); });

    } catch (err) {
      aiBubble.className = 'vc-bubble-err';
      aiBubble.textContent = '⚠ ' + err.message;
      busy = false;
      setStatus('error', err.message);
    }
  });

  // Cancel if pointer leaves button while recording
  pttBtn.addEventListener('pointercancel', () => {
    if (recording) { stopCapture(); setStatus('idle'); busy = false; }
  });

})();
