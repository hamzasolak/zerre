/* ============================================================
   ui.js — Anime.js Tabanlı UI Animasyon Modülü
   Giriş animasyonları, lazer hatları, dalga barları, glitch
   ============================================================ */

const ZerreUI = (() => {

  // ─── Sayfa Yüklendi: Giriş (Stagger) Animasyonu ──────────
  function runEntrance() {
    // ── Üst çubuk kayar ──
    anime({
      targets: '#topbar',
      translateY: [-30, 0],
      opacity: [0, 1],
      duration: 800,
      easing: 'easeOutExpo',
      delay: 100,
    });

    // ── Sol panel kartları stagger olarak girer ──
    anime({
      targets: '#left-panel .ui-card',
      translateX: [-40, 0],
      opacity: [0, 1],
      duration: 700,
      easing: 'easeOutCubic',
      delay: anime.stagger(120, { start: 300 }),
    });

    // ── Sağ panel kartları ──
    anime({
      targets: '#right-panel .ui-card',
      translateX: [40, 0],
      opacity: [0, 1],
      duration: 700,
      easing: 'easeOutCubic',
      delay: anime.stagger(120, { start: 400 }),
    });

    // ── Merkez sahne yukarıdan iner ──
    anime({
      targets: '#center-stage',
      scale: [0.92, 1],
      opacity: [0, 1],
      duration: 1000,
      easing: 'easeOutQuart',
      delay: 500,
    });

    // ── Dalga barları idle animasyonu başlat ──
    setTimeout(startWaveBars, 1200);

    // ── Metrik sayaçlarını başlat ──
    setTimeout(animateIdleMetrics, 1400);

    // ── Kanal barlarını başlat ──
    setTimeout(updateChannels, 1600);
  }

  // ─── Dalga Barları — Sürekli Titreşim ────────────────────
  function startWaveBars() {
    anime({
      targets: '.wave-bar',
      scaleX: () => [
        0.1 + Math.random() * 0.3,
        0.4 + Math.random() * 0.6,
      ],
      duration: () => 600 + Math.random() * 800,
      easing: 'easeInOutSine',
      loop: true,
      direction: 'alternate',
      delay: anime.stagger(80),
    });
  }

  // ─── Boşta: Metrik Titreşimi ──────────────────────────────
  function animateIdleMetrics() {
    // Sıcaklık: 38-42 °C
    _tickCounter('temp-value', 38, 42, 1800, '°C');
    // Enerji: 2.1-2.8 W
    _tickCounter('power-value', 2.1, 2.8, 2200, ' W', 1);
    // Frekans: 145-155 THz
    _tickCounter('freq-value', 145, 155, 1500, ' THz');
  }

  // ─── Lazer Ateşleme Animasyonu ────────────────────────────
  function fireLaserUI(callback) {
    // ── Giriş lazer hattı ──
    const leftLine = document.getElementById('laser-line-left');
    if (leftLine) {
      anime({
        targets: leftLine,
        scaleX: [0, 1],
        opacity: [0, 1],
        duration: 350,
        easing: 'easeOutExpo',
      });
    }

    // ── Buton glitch ──
    const btn = document.getElementById('fire-btn');
    if (btn) {
      btn.disabled = true;
      anime({
        targets: btn,
        translateX: [-2, 2, -2, 0],
        duration: 300,
        easing: 'easeInOutSine',
      });
    }

    // ── Sol panel flash ──
    anime({
      targets: '#left-panel',
      boxShadow: [
        '0 0 12px #00f5ff18',
        '0 0 30px #39ff1455',
        '0 0 12px #00f5ff18',
      ],
      duration: 800,
      easing: 'easeInOutSine',
    });

    // ── Processing süresince pulse ──
    const pulse = anime({
      targets: '#center-stage',
      boxShadow: [
        '0 0 20px #39ff1422',
        '0 0 50px #39ff1466',
        '0 0 20px #39ff1422',
      ],
      duration: 600,
      loop: true,
      easing: 'easeInOutSine',
      direction: 'alternate',
    });

    // ── Metrik artışı ──
    _tickCounter('temp-value', 42, 67, 2500, '°C');
    _tickCounter('power-value', 2.8, 5.4, 2500, ' W', 1);
    _tickCounter('freq-value', 155, 219, 2500, ' THz');

    // ── Dalga barları hızlanır ──
    anime.remove('.wave-bar');
    anime({
      targets: '.wave-bar',
      scaleX: () => [0.1, 0.9 + Math.random() * 0.1],
      duration: () => 150 + Math.random() * 200,
      easing: 'easeInOutSine',
      loop: true,
      direction: 'alternate',
      delay: anime.stagger(30),
    });

    // ── Kanal aktivasyonu ──
    _activateChannels();

    // ── Sağ lazer hattı gecikmeli ──
    setTimeout(() => {
      const rightLine = document.getElementById('laser-line-right');
      if (rightLine) {
        anime({
          targets: rightLine,
          scaleX: [0, 1],
          opacity: [0, 0.9],
          duration: 500,
          easing: 'easeOutExpo',
        });
      }
    }, 2400);

    // ── Tamamlanma ──
    setTimeout(() => {
      pulse.pause();

      // Lazer hatlarını kapat
      anime({
        targets: ['#laser-line-left', '#laser-line-right'],
        scaleX: [1, 0],
        opacity: [1, 0],
        duration: 400,
        easing: 'easeInExpo',
      });

      // Metrikler normale döner
      setTimeout(() => {
        _tickCounter('temp-value', 67, 41, 1200, '°C');
        _tickCounter('power-value', 5.4, 2.3, 1200, ' W', 1);
        _tickCounter('freq-value', 219, 148, 1200, ' THz');

        // Dalga barları normalize olur
        anime.remove('.wave-bar');
        startWaveBars();
        updateChannels();
      }, 400);

      if (btn) btn.disabled = false;
      if (callback) callback();

    }, 3400);
  }

  // ─── Decoded Text Yazma Efekti ────────────────────────────
  // Not: Render idempotenttir — metin her tik'te text.slice(0, i)
  // olarak yeniden yazılır. Glitch karakteri ayrı bir değişkende
  // tutulur; böylece 60ms'lik geri alma, aradaki gerçek
  // karakterleri silemez (eski sürümdeki yarış durumu düzeltildi).
  function typewriterEffect(elementId, text, speed = 40) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = '';
    el.style.opacity = '1';

    let i = 0;
    let glitch = '';
    const render = () => { el.textContent = text.slice(0, i) + glitch; };

    const blink = setInterval(() => {
      if (i < text.length) {
        i++;
        // Zaman zaman geçici glitch karakteri göster (60ms sonra kaybolur)
        if (glitch === '' && Math.random() < 0.08) {
          glitch = String.fromCharCode(0x2588 + Math.floor(Math.random() * 8));
          setTimeout(() => { glitch = ''; render(); }, 60);
        }
        render();
      } else {
        clearInterval(blink);
        glitch = '';
        el.textContent = text; // glitch kalıntısı bırakma
        // Son parıltı
        anime({
          targets: '#' + elementId,
          textShadow: [
            '0 0 0px transparent',
            '0 0 12px #00f5ff',
            '0 0 4px #00f5ff66',
          ],
          duration: 600,
          easing: 'easeOutExpo',
        });
      }
    }, speed);
  }

  // ─── Binary Akış Animasyonu ───────────────────────────────
  function showBinaryStream(binaryStr) {
    const el = document.getElementById('binary-output');
    if (!el) return;

    el.textContent = '';
    anime({
      targets: el,
      opacity: [0, 1],
      duration: 300,
      easing: 'easeOutQuad',
    });

    // Parçalar halinde yaz
    let pos = 0;
    const chunk = 16;
    const iv = setInterval(() => {
      if (pos >= binaryStr.length) { clearInterval(iv); return; }
      el.textContent += binaryStr.slice(pos, pos + chunk) + ' ';
      pos += chunk;
      el.scrollTop = el.scrollHeight;
    }, 40);
  }

  // ─── Gauge Halka Animasyonu ───────────────────────────────
  function animateGauge(circleId, percent, color) {
    const circle = document.getElementById(circleId);
    if (!circle) return;
    const r = parseFloat(circle.getAttribute('r') || 22);
    const circumference = 2 * Math.PI * r;
    circle.style.strokeDasharray  = circumference;
    circle.style.strokeDashoffset = circumference;

    anime({
      targets: circle,
      strokeDashoffset: [circumference, circumference * (1 - percent / 100)],
      duration: 1200,
      easing: 'easeInOutCubic',
    });
  }

  // ─── Kanal Barları (Tek Dalga Boyu 532 nm Baskın Kanal) ──────
  function updateChannels(boost = false) {
    const levels = boost ? [92, 18, 12, 8] : [65, 10, 8, 5];
    document.querySelectorAll('.channel-bar-fill').forEach((bar, i) => {
      const base = levels[i % levels.length];
      anime({
        targets: bar,
        width: base + '%',
        duration: 800,
        easing: 'easeOutQuart',
      });
    });
  }

  function _activateChannels() {
    document.querySelectorAll('.channel-bar-fill').forEach(bar => {
      anime({
        targets: bar,
        width: [
          { value: '95%', duration: 400 },
          { value: (30 + Math.random() * 60) + '%', duration: 800 },
        ],
        easing: 'easeOutElastic(1, 0.5)',
      });
    });
  }

  // ─── Status Dot Titreşimi ─────────────────────────────────
  function setStatusActive(dotId, active) {
    const dot = document.getElementById(dotId);
    if (!dot) return;
    dot.className = 'status-dot ' + (active ? 'active' : 'idle');
  }

  // ─── Basit Counter (sayaç) ────────────────────────────────
  function _tickCounter(id, from, to, dur, unit = '', decimals = 0) {
    const el = document.getElementById(id);
    if (!el) return;
    const obj = { val: from };
    anime({
      targets: obj,
      val: to,
      duration: dur,
      easing: 'easeInOutQuad',
      update() {
        el.textContent = obj.val.toFixed(decimals) + unit;
      },
    });
  }

  // ─── Hata / Glitch Flash ──────────────────────────────────
  function glitchFlash(elementId) {
    anime({
      targets: '#' + elementId,
      opacity: [1, 0.2, 1, 0.5, 1],
      translateX: [0, -3, 3, -1, 0],
      duration: 300,
      easing: 'linear',
    });
  }

  // ─── Dışa Aç ─────────────────────────────────────────────
  return {
    runEntrance,
    startWaveBars,
    animateIdleMetrics,
    fireLaserUI,
    typewriterEffect,
    showBinaryStream,
    animateGauge,
    updateChannels,
    setStatusActive,
    glitchFlash,
  };
})();
