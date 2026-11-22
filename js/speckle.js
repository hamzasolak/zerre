/* ============================================================
   speckle.js — CMOS Sensör & Dalga Optiği Alan Görselleştirici
   Gerçek ASM dijital ikiz haritalarını (CMOS |E|², Z1 Kırınım,
   ITO Faz) çizer; sunucusuz modda FBM simülasyonuna düşer.
   ============================================================ */

const SpeckleEngine = (() => {
  let canvas, ctx;
  let width, height;
  let animId;
  let isActive = false;
  let phase = 0;
  let intensity = 0;

  // Gerçek dijital ikizden gelen haritalar: { cmos, diffract, phase, input28 }
  let physicalMaps = null;
  let viewMode = 'cmos'; // 'cmos' | 'diffract' | 'phase'
  let persistStrength = 0; // İşlem bittikten sonra son gerçek haritayı ekranda tutar

  // ─── Basit permütasyon tablosu (çevrimdışı FBM yedek modu için) ───
  const perm = (() => {
    const p = [];
    for (let i = 0; i < 256; i++) p[i] = i;
    for (let i = 255; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [p[i], p[j]] = [p[j], p[i]];
    }
    return [...p, ...p];
  })();

  function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  function lerp(a, b, t) { return a + t * (b - a); }
  function grad(hash, x, y) {
    const h = hash & 3;
    const u = h < 2 ? x : y;
    const v = h < 2 ? y : x;
    return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
  }

  function perlin(x, y) {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    x -= Math.floor(x);
    y -= Math.floor(y);
    const u = fade(x);
    const v = fade(y);
    const a  = perm[X] + Y;
    const aa = perm[a], ab = perm[a + 1];
    const b  = perm[X + 1] + Y;
    const ba = perm[b], bb = perm[b + 1];
    return lerp(
      lerp(grad(perm[aa], x, y),     grad(perm[ba], x - 1, y),     u),
      lerp(grad(perm[ab], x, y - 1), grad(perm[bb], x - 1, y - 1), u),
      v
    );
  }

  function fbm(x, y, octaves = 5) {
    let val = 0, amp = 0.5, freq = 1, max = 0;
    for (let i = 0; i < octaves; i++) {
      val += perlin(x * freq, y * freq) * amp;
      max += amp;
      amp  *= 0.5;
      freq *= 2.1;
    }
    return val / max;
  }

  // ─── Bilimsel Renk Haritaları ─────────────────────────────
  function _colormap(v, mode) {
    const t = Math.max(0, Math.min(1, v));
    if (mode === 'diffract') {
      // Viridis / Camgöbeği dalga genliği paleti
      const r = Math.min(255, Math.pow(t, 2.2) * 140);
      const g = Math.min(255, Math.pow(t, 0.85) * 245);
      const b = Math.min(255, (0.25 + 0.75 * Math.sin(Math.min(1, t * 1.2) * Math.PI * 0.5)) * 255 * Math.pow(t, 0.45));
      return [r, g, b];
    }
    if (mode === 'phase') {
      // Plasma / ITO Faz gecikmesi paleti (mor → turuncu → sarı)
      const r = Math.min(255, (0.15 + 0.95 * Math.pow(t, 0.65)) * 255);
      const g = Math.min(255, Math.pow(t, 1.8) * 235);
      const b = Math.min(255, Math.sin((1 - t * 0.85) * Math.PI * 0.85) * 240);
      return [r, g, b];
    }
    // Varsayılan 'cmos': 532nm lazer yoğunluğu (koyu siyah → neon yeşil → parlak camgöbeği/beyaz)
    const r = Math.min(255, Math.pow(t, 2.6) * 210);
    const g = Math.min(255, Math.pow(t, 0.78) * 255);
    const b = Math.min(255, Math.pow(t, 1.35) * 195);
    return [r, g, b];
  }

  // ─── 2B Matristen Bilinear Örnekleme ──────────────────────
  function _sampleGrid(grid, u, v, nearest) {
    const H = grid.length;
    const W = grid[0].length;
    if (nearest) {
      const yi = Math.min(H - 1, Math.max(0, Math.floor(v * H)));
      const xi = Math.min(W - 1, Math.max(0, Math.floor(u * W)));
      return grid[yi][xi];
    }
    const gy = v * (H - 1);
    const gx = u * (W - 1);
    const y0 = Math.floor(gy), x0 = Math.floor(gx);
    const y1 = Math.min(y0 + 1, H - 1), x1 = Math.min(x0 + 1, W - 1);
    const wy = gy - y0, wx = gx - x0;
    return grid[y0][x0] * (1 - wy) * (1 - wx)
         + grid[y0][x1] * (1 - wy) * wx
         + grid[y1][x0] * wy * (1 - wx)
         + grid[y1][x1] * wy * wx;
  }

  // ─── Gerçek ASM / Dijital İkiz Alan Çizimi ────────────────
  function _drawPhysicalMap(t, strength) {
    const mapGrid = physicalMaps[viewMode] || physicalMaps.cmos;
    if (!mapGrid || !mapGrid.length) return;

    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;
    const isPhase = (viewMode === 'phase');

    // Kare optik açıklığı dikdörtgen tuvalin ortasına hizala
    const padX = (width - height) * 0.5;

    for (let y = 0; y < height; y++) {
      const v = y / (height - 1);
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        if (x < padX || x >= width - padX) {
          // Sensör kenar karanlığı + çok hafif okuma gürültüsü
          const dark = Math.random() * 6;
          data[idx] = dark * 0.5;
          data[idx + 1] = dark;
          data[idx + 2] = dark * 1.3;
          data[idx + 3] = 255;
          continue;
        }
        const u = (x - padX) / (height - 1);
        let val = _sampleGrid(mapGrid, u, v, isPhase);

        // Aktif lazer sırasında gerçekçi foton shot-noise titreşimi
        if (isActive) {
          val = Math.max(0, val + (Math.random() - 0.5) * 0.035 * Math.sqrt(val + 0.02));
        }

        const [r, g, b] = _colormap(val * strength, viewMode);
        data[idx]     = r;
        data[idx + 1] = g;
        data[idx + 2] = b;
        data[idx + 3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);

    // Aktif optik çerçeve çizgisi
    ctx.strokeStyle = 'rgba(0, 245, 255, 0.25)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padX + 0.5, 0.5, height - 1, height - 1);
  }

  // ─── Başlatma ─────────────────────────────────────────────
  function init(canvasId) {
    canvas = document.getElementById(canvasId);
    if (!canvas) return;
    ctx    = canvas.getContext('2d');
    width  = canvas.width  = 240;
    height = canvas.height = 160;
    _drawIdle();
    _loop();
  }

  function _drawIdle() {
    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const n = Math.random() * 12;
        data[idx]     = n;
        data[idx + 1] = n * 1.2;
        data[idx + 2] = n * 1.5;
        data[idx + 3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }

  function _drawSpeckleFallback(t, strength) {
    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;
    const cx = width / 2, cy = height / 2;
    const maxR = Math.sqrt(cx * cx + cy * cy);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const sx = x / width  * 5.0 + t * 0.18;
        const sy = y / height * 5.0 + t * 0.12;
        let n = (fbm(sx, sy) + 1) * 0.5;
        const dx = x - cx, dy = y - cy;
        const r  = Math.sqrt(dx * dx + dy * dy) / maxR;
        const ang = Math.atan2(dy, dx);
        const rings = Math.sin(r * 28 - t * 3.5) * 0.5 + 0.5;
        const rays  = Math.abs(Math.sin(ang * 6 + t * 0.8)) * 0.5;
        const speckle = n * 0.5 + rings * 0.3 + rays * 0.2;
        const vignette = Math.max(0, 1 - r * 1.4);
        const final = speckle * vignette * strength;

        data[idx]     = Math.min(255, final * 60);
        data[idx + 1] = Math.min(255, final * 255);
        data[idx + 2] = Math.min(255, final * 140);
        data[idx + 3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }

  function _loop() {
    phase += 0.02;

    if (isActive) {
      intensity = Math.min(intensity + 0.08, 1.0);
    } else {
      intensity = Math.max(intensity - 0.04, 0.0);
    }

    if (physicalMaps) {
      const s = isActive ? Math.max(0.35, intensity) : persistStrength;
      _drawPhysicalMap(phase, s);
    } else if (intensity > 0.01) {
      _drawSpeckleFallback(phase, intensity);
    } else {
      if (Math.floor(phase * 8) % 4 === 0) _drawIdle();
    }

    animId = requestAnimationFrame(_loop);
  }

  function setPhysicalMaps(maps) {
    physicalMaps = maps;
    persistStrength = 0.92;
    if (canvas && physicalMaps) _drawPhysicalMap(phase, persistStrength);
  }

  function setViewMode(mode) {
    viewMode = mode;
    if (canvas && physicalMaps) _drawPhysicalMap(phase, isActive ? 1.0 : persistStrength);
  }

  function activate()   { isActive = true;  }
  function deactivate() { isActive = false; }

  return { init, activate, deactivate, setPhysicalMaps, setViewMode };
})();
