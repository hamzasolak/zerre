/* scene.js — Zerre Optofluidik 3D Sahne */
const ZerreScene = (() => {

  let renderer, scene, camera, controls;
  let flaskGroup, innerCrystalMesh, glassBottle;
  let cageGroup, baseGroup, laserModuleLeft, laserModuleRight, pcbGroup, cameraModuleObj;
  let laserBeamLeft, laserBeamRight, laserBeamCore, laserBeamPump;
  let laserModulePump;
  let laserBeamSegments = [];
  let electrodes = [];
  let particles = [];
  let laserPointLight, lcPointLight, itoGlowLights = [];
  let clock, isProcessing = false;
  let labelDefs = [], labelContainer = null, labelsVisible = true, labelContainerEl = null;
  let proposalGroups = [], _currentProposal = 0;

  const LASER_COLOR  = new THREE.Color(0x39ff14);
  const ITO_COLOR    = new THREE.Color(0x88ddff);
  const ALUM_COLOR   = new THREE.Color(0x4a5560);
  const STEEL_COLOR  = new THREE.Color(0x2a3540);
  const CARBON_COLOR = new THREE.Color(0x0d1219);
  const COPPER_COLOR = new THREE.Color(0xb87333);

  // ── Başlat ──────────────────────────────────────────────
  function init(containerId) {
    const container = document.getElementById(containerId);
    if (!container) { console.error('ZerreScene: container yok:', containerId); return; }

    clock = new THREE.Clock();

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const w = container.clientWidth  || 800;
    const h = container.clientHeight || 600;
    renderer.setSize(w, h);
    renderer.domElement.id = 'three-canvas';
    renderer.domElement.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;';
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // Sahne
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020408, 0.015);

    // Kamera
    camera = new THREE.PerspectiveCamera(42, container.clientWidth / container.clientHeight, 0.1, 300);
    camera.position.set(3, 3.5, 9);
    camera.lookAt(0, 0.5, 0);

    // OrbitControls
    if (typeof THREE.OrbitControls !== 'undefined') {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.target.set(0, 0.4, 0);
      controls.enableDamping = true;
      controls.dampingFactor = 0.07;
      controls.minDistance = 4;
      controls.maxDistance = 90;
      controls.maxPolarAngle = Math.PI * 0.8;
    }

    // Yap
    _buildAllHardware();
    _buildElectrodeProposals();
    _buildLabels(container);
    labelContainerEl = container;

    window.addEventListener('resize', () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });

    _animate();
  }

  // ── Donanım (// scene-hardware.js) ────────────────────
  function _buildAllHardware() {
    const hw = window._ZH_build(scene, {
      LASER_COLOR, ITO_COLOR, ALUM_COLOR, STEEL_COLOR, CARBON_COLOR, COPPER_COLOR
    });
    ({ baseGroup, flaskGroup, innerCrystalMesh, glassBottle,
       cageGroup, electrodes,
       laserModuleLeft, laserModuleRight, laserModulePump,
       pcbGroup, cameraModuleObj,
       laserBeamLeft, laserBeamRight, laserBeamCore, laserBeamPump, laserBeamSegments,
       particles,
       laserPointLight, lcPointLight, itoGlowLights } = hw);
  }

  function _animate() {
    requestAnimationFrame(_animate);
    const t = clock.getElapsedTime();

    // LC dolumu yavaş döner + nabız + iç ışık
    if (innerCrystalMesh) {
      innerCrystalMesh.rotation.y = t * 0.03;
      // Opacity sabit yüksek tutulur — LC her zaman görünmeli
      innerCrystalMesh.material.opacity = isProcessing
        ? 0.88 + Math.sin(t*3)*0.06
        : 0.82;
      innerCrystalMesh.material.emissiveIntensity = isProcessing
        ? 0.9 + Math.sin(t*2.2)*0.35
        : 0.55 + Math.sin(t*0.7)*0.08;
    }
    // LC iç ışığı her zaman hafifçe nabız atar
    if (lcPointLight) {
      lcPointLight.intensity = 0.5 + Math.sin(t*0.9)*0.12;
    }

    // ITO elektrot nabzı (işlem sırasında)
    electrodes.forEach((e,i) => {
      if (e.userData.itoMat) {
        e.userData.itoMat.emissiveIntensity = isProcessing
          ? 0.3 + Math.sin(t*2.5 + i*1.05)*0.2
          : 0.04 + Math.sin(t*0.5+i)*0.025;
      }
    });
    itoGlowLights.forEach((gl,i) => {
      if (!isProcessing) gl.intensity = Math.max(0, gl.intensity * 0.93);
    });

    // Partiküller işlem sırasında hareket eder
    if (isProcessing) {
      particles.forEach(p => {
        const ud = p.userData, s = t*ud.speed + ud.phase;
        p.position.x = ud.base.x*(0.93+Math.sin(s)*0.07);
        p.position.y = ud.base.y*(0.93+Math.cos(s*0.8)*0.07);
        p.position.z = ud.base.z*(0.93+Math.sin(s*1.2)*0.07);
        p.material.opacity = 0.3+Math.sin(t*ud.speed*2.5+ud.phase)*0.25;
      });
      if (laserBeamCore) laserBeamCore.scale.setScalar(0.8+Math.sin(t*8)*0.22);
      if (laserPointLight) laserPointLight.intensity = 3.2 + Math.sin(t*7)*0.7;
    }

    if (typeof window._ZP_tick === 'function') {
      window._ZP_tick(t, isProcessing, _currentProposal, proposalGroups);
    }

    if (controls) controls.update();
    _updateLabels();
    renderer.render(scene, camera);
  }

  function _setPipelineStep(stepIdx) {
    for (let k = 1; k <= 3; k++) {
      const el = document.getElementById('stage-step-' + k);
      if (el) el.classList.toggle('active', k === stepIdx);
    }
  }

  // ── Lazer Ateşle (Ana Sistem + A–H Tüm Senaryolar!) ─────
  function fireLaser(callback) {
    if (isProcessing) return;
    isProcessing = true;
    const DUR = 3800;

    if (typeof window._ZP_fire === 'function') window._ZP_fire();
    _setPipelineStep(1);

    // ADIM 1 — giriş demeti
    _tweenOp(laserBeamLeft.material, 0, 0.85, 350);
    if (laserModuleLeft && laserModuleLeft.userData.lensMesh)
      _tweenEmit(laserModuleLeft.userData.lensMesh.material, 0, 1.2, 400);

    // ADIM 2 — LC aktive + pump lazeri açılır
    setTimeout(() => {
      _setPipelineStep(2);
      _tweenOp(laserBeamCore.material, 0, 1.0, 300);
      if (laserBeamPump) _tweenOp(laserBeamPump.material, 0, 0.65, 400);
      if (laserModulePump && laserModulePump.userData.lensMesh)
        _tweenEmit(laserModulePump.userData.lensMesh.material, 0, 0.9, 400);
      laserPointLight.intensity = 5;
      if (lcPointLight) lcPointLight.intensity = 2.5;
      itoGlowLights.forEach((gl,i) => setTimeout(() => { gl.intensity = 1.4; }, i*110));
      laserBeamSegments.forEach((s,i) => setTimeout(() => _tweenOp(s.material,0,0.45+Math.random()*0.3,260),i*70));
      if (innerCrystalMesh) {
        innerCrystalMesh.material.emissive = LASER_COLOR;
        _tweenEmit(innerCrystalMesh.material, 0.55, 3.0, 900);
      }
    }, 450);

    // ADIM 3 — çıkış & CMOS okuma
    setTimeout(() => {
      _setPipelineStep(3);
      _tweenOp(laserBeamRight.material, 0, 0.72, 500);
      if (laserModuleRight && laserModuleRight.userData.lensMesh)
        _tweenEmit(laserModuleRight.userData.lensMesh.material, 0, 0.8, 400);
    }, 1850);

    // ADIM 4 — kapat
    setTimeout(() => {
      _setPipelineStep(0);
      _tweenOp(laserBeamLeft.material, 0.85, 0, 500);
      _tweenOp(laserBeamRight.material, 0.72, 0, 500);
      _tweenOp(laserBeamCore.material, 1.0, 0, 600);
      if (laserBeamPump) _tweenOp(laserBeamPump.material, 0.65, 0, 500);
      laserBeamSegments.forEach(s => _tweenOp(s.material, s.material.opacity, 0, 500));
      particles.forEach(p => { p.material.opacity = 0; });
      itoGlowLights.forEach(gl => { gl.intensity = 0; });
      laserPointLight.intensity = 0;
      if (lcPointLight) lcPointLight.intensity = 0.5; // her zaman hafif kalır
      if (innerCrystalMesh) {
        innerCrystalMesh.material.emissive = new THREE.Color(0x05ff88);
        _tweenEmit(innerCrystalMesh.material, 3.0, 0.55, 800);
      }
      [laserModuleLeft, laserModuleRight, laserModulePump].forEach(m => {
        if (m && m.userData.lensMesh)
          _tweenEmit(m.userData.lensMesh.material, m.userData.lensMesh.material.emissiveIntensity, 0, 500);
      });
      isProcessing = false;
      if (callback) callback();
    }, DUR - 600);
  }

  // ── Yardımcılar ─────────────────────────────────────────
  function _mesh(geo, mat, pos) {
    const m = new THREE.Mesh(geo, mat);
    if (pos) m.position.set(...pos);
    m.castShadow = true; m.receiveShadow = true;
    return m;
  }
  function _tweenOp(mat, from, to, dur) {
    const t0 = performance.now();
    (function s(n){ const tt=Math.min((n-t0)/dur,1); mat.opacity=from+(to-from)*_ease(tt); if(tt<1)requestAnimationFrame(s); })(performance.now());
  }
  function _tweenEmit(mat, from, to, dur) {
    const t0 = performance.now();
    (function s(n){ const tt=Math.min((n-t0)/dur,1); mat.emissiveIntensity=from+(to-from)*_ease(tt); if(tt<1)requestAnimationFrame(s); })(performance.now());
  }
  function _ease(t) { return t<0.5?2*t*t:-1+(4-2*t)*t; }

  // ── Bileşen Etiketleri ───────────────────────────────────
  function _buildLabels(container) {
    labelContainer = document.getElementById('label-layer');
    if (!labelContainer) return;

    // [propIdx, worldX, worldY, worldZ, 'Ad', 'Açıklama', 'renk-sınıf']
    const defs = [
      // Ana Sistem etiketleri (propIdx = 0)
      [0,   0,    2.4,  0,    'LC Küre (E7)',       'Ø250ml Borosilikat · n=1.58',       'v-green'  ],
      [0,   2.8,  2.9,  0,    'Kafes Halkalar',     'Al Alaşım · Ø2.55 · 3×Ortogonal',  'v-gray'   ],
      [0,   3.1,  1.0,  2.0,  'ITO Elektrotlar',   '±X±Y±Z · 6 Eksen · 0–5V DAC',      'v-cyan'   ],
      [0,  -6.2,  1.8,  0,    '532nm Nd:YAG Lazer','Giriş Lazeri · SLM\'den Geçer',     'v-green'  ],
      [0,  -4.55, 1.8,  0,    'SLM Modülatör',     'LCOS · Piksel Veri Modülasyonu',    'v-cyan'   ],
      [0,  -2.82, 1.6,  0,    'Kondenser Lens',    'Bikonveks · Işın Daraltma',         'v-gray'   ],
      [0,   0.3,  6.5,  0.3,  '405nm Pump Lazer',  'Freedericksz Uyarıcı · UV-Violet', 'v-violet' ],
      [0,   3.2,  2.0,  4.6,  'CMOS Kamera',       'RPi Cam3 · 12MP · Speckle Analiz', 'v-cyan'   ],
      [0,   8.2,  1.4,  0,    'Kollimator Tüp',    'Toplayıcı Objektif · M42 · Demet Odak', 'v-gray'   ],
      [0,   0.8, -1.6,  1.2,  'PCB (ESP32+DAC)',   'MCP4728 12-bit · I²C · Wi-Fi',     'v-copper' ],
      [0,   0,   -2.6,  0,    'Optik Taban',       'Karbon Fiber · 250×250mm',          'v-gray'   ],
      // Öneri A etiketleri (propIdx = 1, x=-18)
      [1, -18,    2.5,  0,    'E7 LC Küre',        'Ø250ml Borosilikat · Küre Değişmez','v-green'  ],
      [1, -15.2,  1.9,  1.8,  '32× ITO Çubuk',     'Fibonacci Dizilim · r=2.85 Dış Kafes','v-cyan' ],
      [1, -21.8,  1.6,  0,    'Alüminyum Kafes',   '3× Ortogonal Halka · R=4.0',        'v-gray'   ],
      [1, -16.2, -0.8,  2.8,  'Bakır Besleme',     '32 Bağımsız Yüksek-V Kanal (8–15V)','v-copper' ],
      // Öneri B etiketleri (propIdx = 2, x=-30)
      [2, -30,    1.25, 0,    'Üst Referans Cam',  'Homojen ITO GND · İnce Hücre',      'v-blue'   ],
      [2, -28.2,  0.55, 1.6,  'E7 LC Katmanı',     'Düzlem Paralel · Düşük Saçılma',    'v-yellow' ],
      [2, -31.8,  0.10, 1.6,  '16×16 ITO Matris',  '256 Piksel · Sputter Kaplama',      'v-cyan'   ],
      [2, -26.8,  0.50, 0,    'Bakır Kolonlar',    'Çevre Elektrot İletim Hatları',     'v-copper' ],
      // Öneri C etiketleri (propIdx = 3, x=-42)
      [3, -42,    2.70, 0,    'Düz Üst ITO Cam',   'Referans Elektrot · Optik Çıkış',   'v-cyan'   ],
      [3, -39.6,  2.10, 0,    'Flex PCB Halka',    'Esnek Şerit Sürücü Çerçevesi',      'v-green'  ],
      [3, -43.5,  0.65, 1.2,  '8×8 Alt Ped Matris','64 Altın/ITO Piksel · Hibrit Kontrol','v-orange'],
      [3, -42,   -1.30, 1.6,  'Yarım-Küre Kase',   '3B E7 LC Hacmi + Piksel Adresleme', 'v-yellow' ],
      // Model D etiketleri (propIdx = 4, x=-57)
      [4, -57,    1.2,  3.8,  'Alt ITO Cam',       'Borofloat 33 · 70×70×1.1mm · 100nm ITO',  'v-cyan'   ],
      [4, -57,   -0.2,  3.8,  'E7 LC Katmanı',     'Merck E7 · 7μm · Δn=0.225 · 1–5V',        'v-yellow' ],
      [4, -57,    0.3,  3.8,  'Polyimide (PI)',     'Nissan SE-7492 · 50nm · Ovma Yönlü',      'v-orange' ],
      [4, -57,   -0.8,  7.5,  'FR4 PCB + ESP32',   '16×16 Matris Sürücü · MCP4728×4 DAC · Kenarda', 'v-copper' ],
      [4, -57,    0.6, -4.5,  'UV Epoksi Sealant', 'Norland 61 · 365nm Kürleme · Kenar Mühür', 'v-orange' ],
      [4, -57,   -0.4, -4.5,  'SiO₂ Spacer',       'Ø7μm Boncuk · Cam Plaka Aralığı',         'v-gray'   ],
      [4, -57,   -5.5,  3.2,  '532nm Lazer (Alt)', 'Nd:YAG 532nm · Polarize · Dikey Işın',    'v-green'  ],
      [4, -57,   -1.4, -3.2,  'Polarizör (λ/2)',   'Doğrusal Polarizasyon · 0°',              'v-gray'   ],
      [4, -57,    0.9, -3.2,  'Analizör (90°)',    'Çapraz Polarizör · Faz→Yoğunluk',         'v-violet' ],
      [4, -57,    3.4,  3.2,  'CMOS Dedektör',     'RPi Cam3 · Aşağı Bakıyor · Faz Görüntü',  'v-cyan'   ],
      [4, -50.6, -0.6,  0,    'Voltaj Kaynağı',    'MCP4728 DAC · 0–5V · ITO Piksel/GND',    'v-orange' ],
      // Model E etiketleri (propIdx = 5, x=-72)
      [5, -72,    1.5,  3.2,  'SLM Giriş Maskesi', 'LCOS · Giriş Deseni Kodlama',              'v-cyan'   ],
      [5, -80.5,  2.0,  3.2,  '532nm Lazer',       'Nd:YAG · Giriş Kaynağı · Polarize',        'v-green'  ],
      [5, -76.5,  2.5,  3.2,  'LC Katman 1',       'ITO 16×16 · 70×70mm · Faz Mod.',           'v-cyan'   ],
      [5, -73.5,  2.5,  3.2,  'LC Katman 2',       'ITO 16×16 · Fresnel z=30mm Sonra',         'v-green'  ],
      [5, -70.5,  2.5,  3.2,  'LC Katman 3',       'ITO 16×16 · Çıkış Öncesi Son Dönüşüm',    'v-violet' ],
      [5, -67.5,  2.0,  3.2,  'CMOS Kamera',       'RPi Cam3 · 12MP · Çıkış Okuma',            'v-cyan'   ],
      [5, -76.5, -2.2,  3.2,  'Fresnel Mesafesi',  '30mm Katman Aralığı · z=d²/λ',             'v-gray'   ],
      // Model F etiketleri (propIdx = 6, x=-87)
      [6, -87,    0.35, 0,    'E7 LC Küre',         'Nematik · Ø100mm · 3B Rezervuar',          'v-yellow' ],
      [6, -87,    2.35, 2.8,  'Fotodiod ×32',       'Si · 805nm · 10nF Hold Cap · τ=500ms',     'v-violet' ],
      [6, -87,    1.80, 3.4,  'ITO Piksel Yama',    'İç Yüzey · 100nm · Fotodiod/Yama',         'v-cyan'   ],
      [6, -87,   -0.55, 3.2,  'ITO GND Tabakası',   'Alt Yarım Küre İç Yüzey · Homojen',        'v-green'  ],
      [6, -87,    4.00, 0,    'CMOS Dedektör',       'RPi Cam3 · Speckle Deseni · Aşağı Bakıyor','v-cyan'   ],
      [6, -87,   -5.20, 0,    '532nm Sinyal Lazeri', 'Nd:YAG · Alttan Giriş · Veri Işını',       'v-green'  ],
      [6, -90.5,  3.50,-5.9,  '805nm IR Lazer',     'Si Diod Pump · 300mW · Görünmez IR',       'v-violet' ],
      [6, -90.5,  3.20,-4.2,  'Galvo Ayna',         'Hız: 30kHz · 32 Noktayı Sırayla Tarar',   'v-violet' ],
      [6, -87,    0.42, 0,    'UV Epoksi Hattı',    'Norland 61 · Yarım Küre Birleşimi',         'v-orange' ],
      // Model G etiketleri (propIdx = 7, x=-102)
      [7, -102,   0.35, 0,    'E7 LC Küre',         'Nematik · R=2.05 · 3B Rezervuar',              'v-yellow' ],
      [7, -102,  -1.20, 0,    'ITO GND (Alt Yarım)','Homojen Katot · Yeşil Tab.',                    'v-green'  ],
      [7, -102,   1.80, 0,    'ITO Izgara (16×16)', 'Boylam Y + Enlem X · Şeffaf Elektrot',          'v-cyan'   ],
      [7, -102,   2.55, 0.4,  'Kuzey Kutup Ring',   'Y-Elektrot Çıkış Terminali → PCB',              'v-cyan'   ],
      [7, -102,  -1.85, 0.4,  'Güney Kutup Ring',   'X-Elektrot / GND Referans Terminali → PCB',     'v-green'  ],
      [7, -102,   3.63, 0,    'CMOS Dedektör',       'USB · Speckle Deseni · Aşağı Bakıyor',          'v-cyan'   ],
      [7, -95.20, 0.35, 0,    '532nm Sinyal Lazeri', 'Yatay · X+ Sağdan · SLM\'e Bakıyor',           'v-green'  ],
      [7, -97.40, 0.35, 0,    'SLM Modülatör',       'LCOS · Faz Maskesi · Lazer→Küre Arası',         'v-violet' ],
      [7, -99.80,-1.40, 0,    'PCB (STM32+AD5370)', 'DAC 40-Kanal · 16-bit · ITO Adres Sürücü',      'v-copper' ],
      [7, -99.80,-1.95,-2.4,  'Güç Kaynağı ±12V',  'LCD Gösterge · +12V/GND Kablo → PCB',           'v-orange' ],
      [7, -106.8, 0.35, 0,    'Alüminyum Gantry',   '6061-T6 · Sol/Sağ Kolon + Üst Kiriş',          'v-gray'   ],
      [7, -102,  -2.90, 0,    'Optik Taban (16×10)','Karbon Fiber · 16×10 Birim · Siyah Yüzey',      'v-gray'   ],
      // Model H etiketleri (propIdx = 8, x=-117)
      [8, -122.2, 1.45, 0,    '532nm DPSS Lazer',   '50–100mW · Ø4mm Işın · ~40 USD',                'v-green'  ],
      [8, -121.1,-0.70, 0,    'Genişletici + Polarizör','2 Lens · Doğrusal Pol. (0°)',               'v-gray'   ],
      [8, -119.1, 2.10, 0,    'mSLA LCD — Giriş',   '5.5" 2K Mono · ~40 USD · SLM Yerine',           'v-cyan'   ],
      [8, -116.64,1.95, 0,    'Aktif LC / 2.LCD',   'E7 7μm · Aktif/TFT Sürüş · Alt-Pleshko Yok',    'v-yellow' ],
      [8, -115.25,-0.70,0,    'Analizör (90°)',     'Faz → Yoğunluk Dönüşümü',                       'v-violet' ],
      [8, -113.1, 1.45, 0,    'CMOS Kamera',        'RPi Cam3 12MP · |E|² Okuma',                    'v-cyan'   ],
      [8, -116.64,-1.60,1.6,  'Ağırlık Sürücüsü',   'PWM/TFT Aktif Sürüş · 1kHz AC',                 'v-copper' ],
      [8, -119.1,-1.60, 1.5,  'HDMI Sürücü',        'MIPI→HDMI · LCD Giriş Kartı',                   'v-copper' ],
      [8, -113.45,-1.60,1.7,  'Raspberry Pi 5',     'Canlı Dijital İkiz · PAT Koordinatör',          'v-copper' ],
    ];

    defs.forEach(([propIdx, wx, wy, wz, name, desc, colorCls]) => {
      const div = document.createElement('div');
      div.className = 'comp-label ' + colorCls;
      div.innerHTML =
        '<div class="comp-label-inner">' +
          '<div class="comp-label-name">' + name + '</div>' +
          '<div class="comp-label-desc">' + desc + '</div>' +
        '</div>';
      labelContainer.appendChild(div);
      labelDefs.push({ el: div, propIdx: propIdx, worldPos: new THREE.Vector3(wx, wy, wz) });
    });
  }

  function _updateLabels() {
    if (!labelContainer || !labelsVisible || !labelContainerEl) return;
    const rect = labelContainerEl.getBoundingClientRect();
    const w = rect.width  || 800;
    const h = rect.height || 600;
    const v = new THREE.Vector3();
    labelDefs.forEach(ld => {
      if (ld.propIdx !== _currentProposal) {
        ld.el.style.opacity = '0';
        return;
      }
      v.copy(ld.worldPos).project(camera);
      if (v.z > 1) { ld.el.style.opacity = '0'; return; }
      const x = (v.x *  0.5 + 0.5) * w;
      const y = (v.y * -0.5 + 0.5) * h;
      if (x < -80 || x > w + 80 || y < -60 || y > h + 60) {
        ld.el.style.opacity = '0';
        return;
      }
      ld.el.style.opacity = '1';
      ld.el.style.left = x + 'px';
      ld.el.style.top  = y + 'px';
    });
  }

  function toggleLabels() {
    labelsVisible = !labelsVisible;
    if (labelContainer) {
      labelContainer.style.display = labelsVisible ? 'block' : 'none';
    }
    const btn = document.getElementById('label-toggle');
    if (btn) btn.textContent = labelsVisible ? 'ETİKETLER ⊙' : 'ETİKETLER ○';
  }

  // ── Elektrot Öneri Görsel Sistemleri ─────────────────────
  // -- Elektrot Oneri Gorsel Sistemleri ─────────────────────
  // Geometri: js/scene-proposals.js dosyasina tasindi
  function _buildElectrodeProposals() {
    window._ZP_build(scene, proposalGroups, ALUM_COLOR, CARBON_COLOR, COPPER_COLOR);
  }

  // ── Kamera Uçuş Animasyonu ───────────────────────────────
  // -- Kamera Ucus Animasyonu -- tasindi: scene-proposals.js
  function _flyCamera(toPos, toLook, duration) {
    window._ZP_fly(camera, controls, toPos, toLook, duration);
  }

  // ── Elektrot Öneri Seçici ────────────────────────────────
  // -- Oneri Secici -- tasindi: scene-proposals.js
  function setProposal(n) {
    _currentProposal = Math.max(0, Math.min(8, n));
    window._ZP_set(_currentProposal, camera, controls, proposalGroups);
  }

  function stepProposal(delta) {
    setProposal((_currentProposal + delta + 9) % 9);
  }

  // Klavye ok tuşları (← / →) ile hızlı senaryo gezintisi
  window.addEventListener('keydown', e => {
    const tag = (e.target && e.target.tagName) || '';
    if (tag === 'TEXTAREA' || tag === 'INPUT') return;
    if (e.key === 'ArrowRight') { e.preventDefault(); stepProposal(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); stepProposal(-1); }
  });

  return { init, fireLaser, toggleLabels, setProposal, stepProposal };
})();