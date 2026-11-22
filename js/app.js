/* ============================================================
   app.js — Ana Uygulama Kontrolcüsü + Canlı Dijital İkiz Köprüsü
   Zerre v2.7 — 3B Sahne, mSLA 28×28 Giriş ve ASM Dalga Motoru
   ============================================================ */

const ZerreApp = (() => {

  // ─── Durum ───────────────────────────────────────────────
  let state = {
    isProcessing: false,
    processCount: 0,
    inputMode:    'lcd',   // 'lcd' (28x28 mSLA çizim) | 'text' (SLM metin)
    apiLive:      false,
    twinStatus:   null,
    uptime:       0,
    lastSampleLabel: null,
  };

  // 28×28 mSLA LCD piksel matrisi [0..1]
  const N_PAD = 28;
  let padGrid = Array.from({ length: N_PAD }, () => new Float32Array(N_PAD));
  let padCanvas = null, padCtx = null, isDrawing = false, lastPt = null;

  // ─── UTF-8 Uyumlu Metin → 8-Bit Binary Dönüşüm ───────────
  function textToBinary(text) {
    const bytes = new TextEncoder().encode(text);
    return Array.from(bytes)
      .map(b => b.toString(2).padStart(8, '0'))
      .join(' ');
  }

  function gridToBinarySummary() {
    let active = 0;
    const sampleBytes = [];
    for (let y = 0; y < N_PAD; y++) {
      for (let x = 0; x < N_PAD; x++) {
        if (padGrid[y][x] > 0.15) active++;
        if ((y * N_PAD + x) % 32 === 0 && sampleBytes.length < 10) {
          const v = Math.round(padGrid[y][x] * 255);
          sampleBytes.push(v.toString(2).padStart(8, '0'));
        }
      }
    }
    return `[28×28 mSLA · ${active} aktif px] ` + sampleBytes.join(' ');
  }

  // ─── Çevrimdışı Yedek Yanıt Üreteci ──────────────────────
  function generateFallbackResponse(inputDesc) {
    const responses = [
      `[SIM::DECODE] ${inputDesc} → E7 Δn=0.225 | Ortak-yol ASM yayılımı: Z1=Z2=5cm`,
      `[OPTOFLUIDIC::OK] Paket işlendi (çevrimdışı mod). Canlı ikiz için: python start_server.py`,
    ];
    return responses[state.processCount % responses.length];
  }

  // ─── Process Log Ekle ─────────────────────────────────────
  function appendLog(msg, type = 'info') {
    const log = document.getElementById('process-log');
    if (!log) return;
    const colors = {
      info:    '#00f5ff',
      success: '#39ff14',
      warn:    '#ffaa00',
      error:   '#ff3366',
    };
    const ts = new Date().toISOString().slice(11, 23);
    const line = document.createElement('div');
    line.style.cssText = `color:${colors[type] || colors.info}; font-size:0.62rem; line-height:1.7; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;`;
    line.textContent = `[${ts}] ${msg}`;
    log.appendChild(line);
    while (log.children.length > 8) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
  }

  // ─── 28×28 mSLA LCD Çizim Tuvali ─────────────────────────
  function _renderPad() {
    if (!padCtx) return;
    const W = padCanvas.width, H = padCanvas.height;
    const cw = W / N_PAD, ch = H / N_PAD;

    padCtx.fillStyle = '#020806';
    padCtx.fillRect(0, 0, W, H);

    for (let y = 0; y < N_PAD; y++) {
      for (let x = 0; x < N_PAD; x++) {
        const v = padGrid[y][x];
        if (v > 0.01) {
          const g = Math.min(255, Math.round(v * 255));
          const b = Math.min(255, Math.round(v * 145));
          padCtx.fillStyle = `rgb(${Math.round(v * 45)}, ${g}, ${b})`;
          padCtx.fillRect(x * cw, y * ch, cw - 0.4, ch - 0.4);
        }
      }
    }

    // İnce piksel ızgarası
    padCtx.strokeStyle = 'rgba(0, 245, 255, 0.06)';
    padCtx.lineWidth = 0.5;
    for (let i = 0; i <= N_PAD; i += 4) {
      padCtx.beginPath();
      padCtx.moveTo(i * cw, 0); padCtx.lineTo(i * cw, H);
      padCtx.moveTo(0, i * ch); padCtx.lineTo(W, i * ch);
      padCtx.stroke();
    }
  }

  function _stampBrush(gx, gy) {
    const r = 2;
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        const ny = Math.round(gy) + dy;
        const nx = Math.round(gx) + dx;
        if (ny < 0 || ny >= N_PAD || nx < 0 || nx >= N_PAD) continue;
        const distSq = (nx - gx) * (nx - gx) + (ny - gy) * (ny - gy);
        const w = Math.exp(-distSq / 1.35);
        if (w > 0.05) {
          padGrid[ny][nx] = Math.min(1.0, padGrid[ny][nx] + w * 0.85);
        }
      }
    }
  }

  function _drawSegment(p0, p1) {
    const steps = Math.max(1, Math.ceil(Math.hypot(p1.x - p0.x, p1.y - p0.y) * 2));
    for (let s = 0; s <= steps; s++) {
      const t = s / steps;
      _stampBrush(p0.x + (p1.x - p0.x) * t, p0.y + (p1.y - p0.y) * t);
    }
    _renderPad();
  }

  function _eventToGrid(e) {
    const rect = padCanvas.getBoundingClientRect();
    const touch = e.touches && e.touches[0];
    const cx = touch ? touch.clientX : e.clientX;
    const cy = touch ? touch.clientY : e.clientY;
    return {
      x: ((cx - rect.left) / rect.width)  * (N_PAD - 1),
      y: ((cy - rect.top)  / rect.height) * (N_PAD - 1),
    };
  }

  function initLcdPad() {
    padCanvas = document.getElementById('lcd-canvas');
    if (!padCanvas) return;
    padCtx = padCanvas.getContext('2d');

    const start = e => {
      e.preventDefault();
      isDrawing = true;
      state.lastSampleLabel = null;
      lastPt = _eventToGrid(e);
      _stampBrush(lastPt.x, lastPt.y);
      _renderPad();
    };
    const move = e => {
      if (!isDrawing) return;
      e.preventDefault();
      const pt = _eventToGrid(e);
      _drawSegment(lastPt, pt);
      lastPt = pt;
    };
    const end = () => { isDrawing = false; lastPt = null; };

    padCanvas.addEventListener('mousedown', start);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', end);
    padCanvas.addEventListener('touchstart', start, { passive: false });
    padCanvas.addEventListener('touchmove', move, { passive: false });
    window.addEventListener('touchend', end);

    _renderPad();
  }

  function clearPad() {
    for (let y = 0; y < N_PAD; y++) padGrid[y].fill(0);
    state.lastSampleLabel = null;
    _renderPad();
  }

  function _padHasInk() {
    let sum = 0;
    for (let y = 0; y < N_PAD; y++) {
      for (let x = 0; x < N_PAD; x++) sum += padGrid[y][x];
    }
    return sum > 1.5;
  }

  // Çevrimdışı mod için basit yerleşik 7-segment rakam çizici
  function _drawOfflineDigit(d) {
    clearPad();
    const segs = {
      0: [0,1,2,4,5,6], 1: [2,5], 2: [0,2,3,4,6], 3: [0,2,3,5,6], 4: [1,2,3,5],
      5: [0,1,3,5,6],   6: [0,1,3,4,5,6], 7: [0,2,5], 8: [0,1,2,3,4,5,6], 9: [0,1,2,3,5,6]
    }[d] || [0,2,3,5,6];
    const coords = [
      [{x:9,y:5},{x:18,y:5}],   [{x:9,y:5},{x:9,y:13}],   [{x:18,y:5},{x:18,y:13}],
      [{x:9,y:13},{x:18,y:13}], [{x:9,y:13},{x:9,y:22}],  [{x:18,y:13},{x:18,y:22}],
      [{x:9,y:22},{x:18,y:22}],
    ];
    segs.forEach(idx => _drawSegment(coords[idx][0], coords[idx][1]));
    state.lastSampleLabel = d;
  }

  async function loadSampleDigit(digit = null) {
    try {
      const q = (digit !== null && digit !== undefined) ? `?digit=${digit}` : '';
      const r = await fetch(`/api/sample${q}`);
      if (!r.ok) throw new Error('API yok');
      const data = await r.json();
      for (let y = 0; y < N_PAD; y++) {
        for (let x = 0; x < N_PAD; x++) {
          padGrid[y][x] = data.pixels[y][x];
        }
      }
      state.lastSampleLabel = data.label;
      _renderPad();
      appendLog(`${data.source} yüklendi (gerçek etiket: ${data.label})`, 'info');
    } catch (_) {
      const d = (digit !== null && digit !== undefined) ? digit : Math.floor(Math.random() * 10);
      _drawOfflineDigit(d);
      appendLog(`Çevrimdışı örnek rakam çizildi: ${d}`, 'warn');
    }
  }

  function setInputMode(mode) {
    state.inputMode = mode;
    document.querySelectorAll('.mode-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
    const lcdBox = document.getElementById('lcd-mode-box');
    const txtBox = document.getElementById('text-mode-box');
    if (lcdBox) lcdBox.style.display = (mode === 'lcd') ? 'block' : 'none';
    if (txtBox) txtBox.style.display = (mode === 'text') ? 'block' : 'none';
  }

  function setSpeckleView(mode, btnEl) {
    SpeckleEngine.setViewMode(mode);
    document.querySelectorAll('.speckle-view-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');
  }

  // ─── Canlı Dijital İkiz Durum Kontrolü ───────────────────
  async function checkBackendStatus() {
    const badge = document.getElementById('sim-badge');
    try {
      const r = await fetch('/api/status');
      if (!r.ok) throw new Error('status ' + r.status);
      const st = await r.json();
      state.apiLive = true;
      state.twinStatus = st;
      if (badge) {
        badge.textContent = st.is_trained_model ? 'İKİZ CANLI' : 'YEDEK DEMO (EĞİTİMSİZ)';
        badge.classList.toggle('live', Boolean(st.is_trained_model));
      }
      appendLog(
        st.is_trained_model
          ? `Dijital İkiz aktif: ${st.n_ito}×${st.n_ito} ${st.drive_mode} · ${st.head_type}`
          : 'Uyarı: Eğitilmiş zerre_model.npz yok — rastgele yedek demo yüklendi.',
        st.is_trained_model ? 'success' : 'warn'
      );
      await loadSampleDigit(3);
    } catch (_) {
      state.apiLive = false;
      _drawOfflineDigit(3);
      appendLog('Sunucu bulunamadı — simülasyon yedek modu aktif.', 'warn');
    }
  }

  // ─── Olasılık Sonucunu Sağ Panele Bas ─────────────────────
  function _renderPredictionResult(res) {
    const outEl = document.getElementById('decoded-output');
    if (!outEl) return;

    const pairs = res.probs.map((p, idx) => ({ idx, p })).sort((a, b) => b.p - a.p).slice(0, 3);
    const matchInfo = (state.lastSampleLabel !== null && res.input_mode === 'lcd_draw')
      ? (res.prediction === state.lastSampleLabel
          ? `<span style="color:#39ff14;">✓ DOĞRU (Etiket: ${state.lastSampleLabel})</span>`
          : `<span style="color:#ffaa00;">⚠ Etiket: ${state.lastSampleLabel}</span>`)
      : `<span style="color:#4a7a8a;">${res.head_type}</span>`;

    const barsHtml = pairs.map((item, rank) => {
      const pct = (item.p * 100).toFixed(1);
      const col = rank === 0 ? '#39ff14' : '#00f5ff';
      return `
        <div class="prob-row">
          <span style="width:42px; color:${col};">SINIF ${item.idx}</span>
          <div class="prob-bar-bg"><div class="prob-bar-fill" style="width:${pct}%;"></div></div>
          <span style="width:40px; text-align:right; color:${col};">%${pct}</span>
        </div>`;
    }).join('');

    outEl.innerHTML = `
      <div class="flex justify-between items-center" style="margin-bottom:4px;">
        <span style="color:#39ff14; font-weight:700; font-size:0.86rem;">
          TAHMİN: ${res.prediction}
        </span>
        <span style="font-size:0.64rem;">${matchInfo}</span>
      </div>
      ${barsHtml}
      <div style="font-size:0.56rem; color:#4a7a8a; margin-top:5px;">
        ASM ${res.grid}² · ${res.n_ito}×${res.n_ito} ${res.drive_mode.toUpperCase()} · Simülasyon Süresi (CPU): ${res.compute_ms} ms
      </div>
    `;

    const corrEl = document.getElementById('speckle-corr');
    if (corrEl) corrEl.textContent = (res.confidence * 100).toFixed(1) + '%';
  }

  // ─── Ana İşlem Akışı (Tek Merkez) ─────────────────────────
  async function processInput() {
    if (state.isProcessing) return;

    let payload = null;
    let binaryStr = '';

    if (state.inputMode === 'lcd') {
      if (!_padHasInk()) {
        appendLog('mSLA LCD matrisi boş — önce bir rakam çizin veya örnek seçin.', 'warn');
        ZerreUI.glitchFlash('lcd-canvas');
        return;
      }
      const pixels = padGrid.map(row => Array.from(row, v => Number(v.toFixed(3))));
      payload = { pixels };
      binaryStr = gridToBinarySummary();
      appendLog('28×28 mSLA genlik maskesi 532nm lazer hattına yüklendi.', 'info');
    } else {
      const promptEl = document.getElementById('prompt-input');
      const text = promptEl ? promptEl.value.trim() : '';
      if (!text) {
        appendLog('Metin girişi boş — veri paketi girin.', 'warn');
        return;
      }
      payload = { text };
      binaryStr = textToBinary(text);
      appendLog(`UTF-8 paket kodlandı: "${text.slice(0, 18)}" (${binaryStr.split(' ').length * 8} bit)`, 'info');
    }

    state.isProcessing = true;
    state.processCount++;
    const tUiStart = performance.now();

    ZerreUI.showBinaryStream(binaryStr);
    ZerreUI.setStatusActive('status-slm', true);
    const stText = document.getElementById('status-text');
    if (stText) { stText.textContent = 'PROCESSING'; stText.style.color = '#39ff14'; }

    const overlay = document.getElementById('processing-overlay');
    if (overlay) overlay.classList.add('active');

    // Arka planda gerçek Python ASM dijital ikiz çıkarımını başlat
    let apiResult = null;
    const apiPromise = fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
      .then(data => {
        apiResult = data;
        if (data.maps) SpeckleEngine.setPhysicalMaps(data.maps);
        appendLog(`ASM Z1/Z2 yayılımı tamamlandı (${data.compute_ms} ms).`, 'success');
      })
      .catch(() => {
        apiResult = null;
      });

    // 3B Lazer ve Speckle senkronizasyonu
    ZerreScene.fireLaser(() => {});

    setTimeout(() => {
      SpeckleEngine.activate();
      ZerreUI.setStatusActive('status-cmos', true);
      appendLog('CMOS |E|² kırınım yoğunluğu okunuyor…', 'info');
    }, 1400);

    ZerreUI.fireLaserUI(async () => {
      await apiPromise;
      SpeckleEngine.deactivate();

      const sc = document.getElementById('stat-count');
      const sl = document.getElementById('stat-latency');
      if (sc) sc.textContent = String(state.processCount);

      if (apiResult) {
        _renderPredictionResult(apiResult);
        if (sl) sl.textContent = apiResult.compute_ms + 'ms';
        appendLog(
          `İşlem #${state.processCount} → Sınıf ${apiResult.prediction} (%${(apiResult.confidence * 100).toFixed(1)})`,
          'success'
        );
      } else {
        const desc = state.inputMode === 'lcd' ? '28×28 matris' : payload.text;
        ZerreUI.typewriterEffect('decoded-output', generateFallbackResponse(desc), 22);
        if (sl) sl.textContent = '—';
        appendLog(`İşlem #${state.processCount} (çevrimdışı demo — sunucu bağlı değil).`, 'warn');
      }

      ZerreUI.setStatusActive('status-slm', false);
      ZerreUI.setStatusActive('status-cmos', false);
      if (stText) { stText.textContent = 'STANDBY'; stText.style.color = '#00f5ff'; }
      if (overlay) overlay.classList.remove('active');
      state.isProcessing = false;
    });
  }

  // ─── Saatler & Telemetri ──────────────────────────────────
  function startUptimeClock() {
    setInterval(() => {
      state.uptime++;
      const h = String(Math.floor(state.uptime / 3600)).padStart(2, '0');
      const m = String(Math.floor((state.uptime % 3600) / 60)).padStart(2, '0');
      const s = String(state.uptime % 60).padStart(2, '0');
      const el = document.getElementById('uptime');
      if (el) el.textContent = `${h}:${m}:${s}`;
    }, 1000);
  }

  function startSystemClock() {
    const update = () => {
      const now = new Date();
      const el = document.getElementById('sys-time');
      if (el) {
        el.textContent = now.toLocaleTimeString('tr-TR', { hour12: false })
          + '.' + String(now.getMilliseconds()).padStart(3, '0').slice(0, 2);
      }
    };
    update();
    setInterval(update, 100);
  }

  function startTelemetry() {
    // Sabit nominal simülasyon referans parametreleri (rastgele sahte telemetri kaldırıldı)
    ZerreUI.animateGauge('gauge-temp', 25, '#ff6600');
    ZerreUI.animateGauge('gauge-power', 20, '#00f5ff');
  }

  // ─── Başlat ───────────────────────────────────────────────
  function init() {
    ZerreScene.init('center-stage');
    SpeckleEngine.init('speckle-canvas');
    initLcdPad();

    setTimeout(() => {
      ZerreUI.animateGauge('gauge-temp', 25, '#ff6600');
      ZerreUI.animateGauge('gauge-power', 20, '#00f5ff');
    }, 1200);

    ZerreUI.runEntrance();
    startSystemClock();
    startUptimeClock();
    startTelemetry();

    setTimeout(() => {
      appendLog('Zerre v2.7 başlatıldı — dijital ikiz kontrol ediliyor…', 'info');
      checkBackendStatus();
    }, 600);

    const fireBtn = document.getElementById('fire-btn');
    if (fireBtn) fireBtn.addEventListener('click', processInput);

    window.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        processInput();
      }
    });

    ZerreUI.setStatusActive('status-slm', false);
    ZerreUI.setStatusActive('status-cmos', false);
  }

  return {
    init,
    clearPad,
    loadSampleDigit,
    setInputMode,
    setSpeckleView,
  };
})();

window.addEventListener('DOMContentLoaded', () => ZerreApp.init());
