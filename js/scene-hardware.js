/* scene-hardware.js — Fiziksel Donanım Geometrileri
 * window._ZH_build(scene, C) → donanım referanslarını döndürür
 *   C = { LASER_COLOR, ITO_COLOR, ALUM_COLOR, STEEL_COLOR, CARBON_COLOR, COPPER_COLOR }
 */
(function () {
  'use strict';

  window._ZH_build = function (scene, C) {
    const LASER_COLOR  = C.LASER_COLOR;
    const ITO_COLOR    = C.ITO_COLOR;
    const ALUM_COLOR   = C.ALUM_COLOR;
    const STEEL_COLOR  = C.STEEL_COLOR;
    const CARBON_COLOR = C.CARBON_COLOR;
    const COPPER_COLOR = C.COPPER_COLOR;

    // ── Paylaşılan durum değişkenleri ──────────────────────
    let baseGroup, flaskGroup, innerCrystalMesh, glassBottle;
    let cageGroup, electrodes = [];
    let laserModuleLeft, laserModuleRight, laserModulePump;
    let pcbGroup, cameraModuleObj;
    let laserBeamLeft, laserBeamRight, laserBeamCore, laserBeamPump;
    let laserBeamSegments = [], particles = [];
    let laserPointLight, lcPointLight, itoGlowLights = [];

    // ── Yardımcı ────────────────────────────────────────────
    function _mesh(geo, mat, pos) {
      const m = new THREE.Mesh(geo, mat);
      if (pos) m.position.set(...pos);
      m.castShadow = true; m.receiveShadow = true;
      return m;
    }

  // ── Işıklar ─────────────────────────────────────────────
  function _buildLights() {
    scene.add(new THREE.AmbientLight(0x112233, 2.5));

    const key = new THREE.DirectionalLight(0x88bbdd, 2.0);
    key.position.set(4, 8, 5);
    key.castShadow = true;
    scene.add(key);

    const fill = new THREE.DirectionalLight(0x003322, 0.8);
    fill.position.set(-4, -2, 3);
    scene.add(fill);

    const back = new THREE.DirectionalLight(0x001144, 0.5);
    back.position.set(0, -5, -6);
    scene.add(back);

    laserPointLight = new THREE.PointLight(0x39ff14, 0, 7);
    laserPointLight.position.set(0, 0.35, 0);
    scene.add(laserPointLight);

    // LC içini her zaman aydınlatan sabit iç ışık
    lcPointLight = new THREE.PointLight(0x00ff88, 0.6, 3.0);
    lcPointLight.position.set(0, 0.35, 0);
    scene.add(lcPointLight);

    [[2.5,0,0],[-2.5,0,0],[0,2.5,0],[0,-2.5,0],[0,0,2.5],[0,0,-2.5]].forEach(p => {
      const gl = new THREE.PointLight(0x00aaff, 0, 4);
      gl.position.set(...p);
      scene.add(gl);
      itoGlowLights.push(gl);
    });
  }

  // ── Karbon Fiber Taban ───────────────────────────────────
  function _buildBase() {
    baseGroup = new THREE.Group();

    const baseMat  = new THREE.MeshStandardMaterial({ color: CARBON_COLOR, metalness: 0.1, roughness: 0.3 });
    const alumMat  = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.85, roughness: 0.15 });
    const steelMat = new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.92, roughness: 0.12 });
    const rubbMat  = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.95 });

    baseGroup.add(_mesh(new THREE.BoxGeometry(8.2, 0.18, 6.8), baseMat, [0,-3,0]));
    baseGroup.add(_mesh(new THREE.BoxGeometry(0.12,0.22,6.7), alumMat, [-4.05,-3,0]));
    baseGroup.add(_mesh(new THREE.BoxGeometry(0.12,0.22,6.7), alumMat, [ 4.05,-3,0]));
    [[-3.8,-3.1,-3],[ 3.8,-3.1,-3],[-3.8,-3.1,3],[ 3.8,-3.1,3]].forEach(p => {
      baseGroup.add(_mesh(new THREE.CylinderGeometry(0.17,0.21,0.14,12), rubbMat, p));
    });
    // Destek sütunu: tabandan küre ALTINA kadar (küre altı world y=-1.70, sütun üst ucu y=-1.95)
    // Uzunluk: base üstü y≈-2.91 → y=-1.95 => uzunluk ~0.96, merkez y=-2.43
    baseGroup.add(_mesh(new THREE.CylinderGeometry(0.14,0.18,1.0,16), steelMat, [0,-2.41,0]));
    // Montaj flanşı: kürenin hemen altında, dışarıda
    baseGroup.add(_mesh(new THREE.CylinderGeometry(0.52,0.52,0.10,24), alumMat, [0,-1.95,0]));

    scene.add(baseGroup);
  }

  // ── Borosilikat Balon + E7 Likit Kristal ────────────────
  function _buildFlask() {
    flaskGroup = new THREE.Group();
    flaskGroup.position.y = 0.35;

    // ─ Dış cam kabuk: çok ince, sadece kenarlarda görünür ─
    // r128'de transmission çalışmaz — additive+düşük opacity ile cam etkisi
    const glassMat = new THREE.MeshStandardMaterial({
      color: 0xaad4ee,
      emissive: new THREE.Color(0x0a1e2a),
      emissiveIntensity: 0.3,
      metalness: 0.05,
      roughness: 0.0,
      transparent: true,
      opacity: 0.10,
      depthWrite: false,
      side: THREE.DoubleSide
    });
    glassBottle = new THREE.Mesh(new THREE.SphereGeometry(2.05, 64, 64), glassMat);
    flaskGroup.add(glassBottle);

    // Cam kenar parlaması (wireframe benzeri ama mesh)
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0x44aacc,
      transparent: true,
      opacity: 0.18,
      wireframe: false,
      side: THREE.BackSide,
      depthWrite: false
    });
    const glowShell = new THREE.Mesh(new THREE.SphereGeometry(2.08, 48, 48), glowMat);
    flaskGroup.add(glowShell);

    // ─ İç E7 Likit Kristal dolumu ─
    // Gerçekte LC şeffaf-sarımsı sıvı ama optikte polarize ışıkla teal/yeşil renk verir
    const lcMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(0x0d3d22),
      emissive: new THREE.Color(0x05ff88),
      emissiveIntensity: 0.55,
      metalness: 0.0,
      roughness: 0.35,
      transparent: true,
      opacity: 0.82,
      depthWrite: false,
      side: THREE.FrontSide
    });
    innerCrystalMesh = new THREE.Mesh(new THREE.SphereGeometry(1.90, 56, 56), lcMat);
    innerCrystalMesh.renderOrder = 1;
    flaskGroup.add(innerCrystalMesh);

    // LC yüzey parıltısı (ince iç glow katmanı)
    const lcGlowMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88,
      transparent: true,
      opacity: 0.06,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    flaskGroup.add(new THREE.Mesh(new THREE.SphereGeometry(1.85, 32, 32), lcGlowMat));

    // ─ Boyun ─
    const neckMat = new THREE.MeshStandardMaterial({
      color: 0x88bbcc,
      transparent: true, opacity: 0.14,
      roughness: 0.0, metalness: 0.05,
      depthWrite: false, side: THREE.DoubleSide
    });
    flaskGroup.add(new THREE.Mesh(new THREE.CylinderGeometry(0.26,0.40,1.6,32,1,true), neckMat));
    const p = new THREE.Mesh(new THREE.CylinderGeometry(0.26,0.40,1.6,32,1,true), neckMat);
    p.position.y = 2.65; flaskGroup.add(p);

    // rim ve junc torus'ları kaldırıldı — küre çevresinde yüzen halka görünümü yapıyordu

    scene.add(flaskGroup);
  }

  // ── Alüminyum Kafes + ITO Elektrotlar ───────────────────
  function _buildCage() {
    cageGroup = new THREE.Group();
    cageGroup.position.y = 0.35;

    const frameMat = new THREE.MeshStandardMaterial({ color: 0x1c2530, metalness: 0.6, roughness: 0.55 });
    const darkMat  = new THREE.MeshStandardMaterial({ color: 0x18222c, metalness: 0.7, roughness: 0.45 });

    // ── 3 ortogonal halka — her biri farklı düzlemde, küre dışında ──
    // Küre yarıçapı 2.05. Halka yarıçapı 2.55 (küre yüzeyinden 0.50 dışarıda)
    const R = 2.55;

    // Halka 1: XZ düzlemi — yatay (ekvator)
    const ring_xz = new THREE.Mesh(new THREE.TorusGeometry(R, 0.032, 12, 72), frameMat);
    // varsayılan yatay, değiştirme yok
    cageGroup.add(ring_xz);

    // Halka 2: XY düzlemi — dikey, Z ekseni etrafında döndür
    const ring_xy = new THREE.Mesh(new THREE.TorusGeometry(R, 0.032, 12, 72), frameMat);
    ring_xy.rotation.x = Math.PI / 2;
    cageGroup.add(ring_xy);

    // Halka 3: YZ düzlemi — dikey, Y ekseni etrafında döndür
    const ring_yz = new THREE.Mesh(new THREE.TorusGeometry(R, 0.032, 12, 72), frameMat);
    ring_yz.rotation.z = Math.PI / 2;
    cageGroup.add(ring_yz);

    // ── 6 ince bağlantı kolu — halkaların kesişim noktalarına oturur ──
    // ±X, ±Y, ±Z yönlerinde birer kısa dikey/yatay desteği
    const stubMat = new THREE.MeshStandardMaterial({ color: 0x243040, metalness: 0.8, roughness: 0.3 });
    // +X/-X ekseni boyunca yatay çubuk (ring_xz ile ring_yz birleşim)
    [[R,0,0],[-R,0,0]].forEach(p => {
      const s = _mesh(new THREE.CylinderGeometry(0.042,0.042,0.28,8), stubMat, p);
      s.rotation.z = Math.PI/2; cageGroup.add(s);
    });
    // +Y/-Y ekseni boyunca dikey çubuk
    [[0,R,0],[0,-R,0]].forEach(p => {
      cageGroup.add(_mesh(new THREE.CylinderGeometry(0.042,0.042,0.28,8), stubMat, p));
    });
    // +Z/-Z ekseni boyunca derinlik çubuğu
    [[0,0,R],[0,0,-R]].forEach(p => {
      const s = _mesh(new THREE.CylinderGeometry(0.042,0.042,0.28,8), stubMat, p);
      s.rotation.x = Math.PI/2; cageGroup.add(s);
    });

    // 6 eksen ITO elektrot
    const axisDefs = [
      { d:[1,0,0], c:0x3399ff }, { d:[-1,0,0], c:0x3399ff },
      { d:[0,1,0], c:0x33ff99 }, { d:[0,-1,0], c:0x33ff99 },
      { d:[0,0,1], c:0xff9933 }, { d:[0,0,-1], c:0xff9933 },
    ];
    axisDefs.forEach(ax => {
      const [dx,dy,dz] = ax.d;
      // Balon yarıçapı 2.05 — tüm metal parçalar kesinlikle dışarıda olmalı
      // Elektrot kolu: merkez 3.10, iç uç 3.10-0.575=2.525 (balondan 0.47 dışarıda)
      const armMat = new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.95, roughness: 0.08 });
      const eArm = _mesh(new THREE.CylinderGeometry(0.026,0.026,1.15,10), armMat,
                         [dx*3.10, dy*3.10, dz*3.10]);
      if (Math.abs(dx)>0.5) eArm.rotation.z = Math.PI/2;
      if (Math.abs(dz)>0.5) eArm.rotation.x = Math.PI/2;
      cageGroup.add(eArm);

      // ITO pad: dikdörtgen elektrot — küre yüzeyinden 0.75 birim uzakta
      // BoxGeometry(en, kalınlık, derinlik) → rotasyonla yüzeye dik duruyor
      const itoMat = new THREE.MeshPhysicalMaterial({
        color: ITO_COLOR, metalness: 0.15, roughness: 0.08,
        transparent: true, opacity: 0.45,
        emissive: new THREE.Color(ax.c), emissiveIntensity: 0.04
      });
      const disk = _mesh(new THREE.BoxGeometry(0.42, 0.04, 0.42), itoMat,
                         [dx*2.80, dy*2.80, dz*2.80]);
      if (Math.abs(dx)>0.5) disk.rotation.z = Math.PI/2;
      if (Math.abs(dz)>0.5) disk.rotation.x = Math.PI/2;
      disk.userData.itoMat = itoMat;
      cageGroup.add(disk);
      electrodes.push(disk);

      // Pad ile kol arasında ince bağlantı çubuğu (pad@2.80 → kol@3.10)
      const rodLen = 0.28;
      const rodMat = new THREE.MeshStandardMaterial({ color: 0x1a2030, metalness: 0.88, roughness: 0.18 });
      const rod = _mesh(new THREE.CylinderGeometry(0.016,0.016,rodLen,8), rodMat,
                        [dx*2.96, dy*2.96, dz*2.96]);
      if (Math.abs(dx)>0.5) rod.rotation.z = Math.PI/2;
      if (Math.abs(dz)>0.5) rod.rotation.x = Math.PI/2;
      cageGroup.add(rod);

      const cableMat = new THREE.MeshStandardMaterial({ color: ax.c, emissive: new THREE.Color(ax.c), emissiveIntensity: 0.18 });
      const cable = _mesh(new THREE.CylinderGeometry(0.009,0.009,0.75,6), cableMat,
                          [dx*3.9, dy*3.9, dz*3.9]);
      if (Math.abs(dx)>0.5) cable.rotation.z = Math.PI/2;
      if (Math.abs(dz)>0.5) cable.rotation.x = Math.PI/2;
      cageGroup.add(cable);
    });

    // Lazer tünel
    const tMat = new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.88, roughness: 0.14 });
    [-1,1].forEach(s => {
      const t = _mesh(new THREE.CylinderGeometry(0.11,0.11,0.48,16), tMat, [s*2.9,0,0]);
      t.rotation.z = Math.PI/2; cageGroup.add(t);
    });

    scene.add(cageGroup);
  }

  // ── SLM Modülatör + Kondenser Lens ─────────────────────
  function _buildSLMCondenser() {
    // SLM (Spatial Light Modulator) — 532nm lazeri ile kafes giriş arasında
    const slmGroup = new THREE.Group();
    slmGroup.position.set(-4.55, 0.35, 0);
    // Panel Y ekseni etrafında 90° döner → yüzü lazere bakıyor
    slmGroup.rotation.y = Math.PI / 2;

    const frameMat  = new THREE.MeshStandardMaterial({ color: 0x121a22, metalness: 0.85, roughness: 0.22 });
    const accentMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.9, roughness: 0.15 });

    // Ana gövde kutusu
    slmGroup.add(_mesh(new THREE.BoxGeometry(0.10, 1.12, 1.12), frameMat, [0, 0, 0]));

    // Aktif LCOS piksel yüzeyi
    const screenMat = new THREE.MeshStandardMaterial({
      color: 0x001810,
      emissive: new THREE.Color(0x00ff44),
      emissiveIntensity: 0.28,
      roughness: 0.08, metalness: 0.02
    });
    slmGroup.add(_mesh(new THREE.BoxGeometry(0.025, 0.90, 0.90), screenMat, [0.055, 0, 0]));

    // Piksel ızgarası (wireframe glow)
    const gridGeo = new THREE.BoxGeometry(0.025, 0.88, 0.88);
    const gridMat = new THREE.MeshBasicMaterial({
      color: 0x00ff44, wireframe: true,
      transparent: true, opacity: 0.07,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const gridMesh = new THREE.Mesh(gridGeo, gridMat);
    gridMesh.position.set(0.060, 0, 0);
    slmGroup.add(gridMesh);

    // Çerçeve köşe takviye parçaları
    [[-0.44, -0.44],[-0.44, 0.44],[0.44, -0.44],[0.44, 0.44]].forEach(([y, z]) => {
      slmGroup.add(_mesh(new THREE.BoxGeometry(0.12, 0.07, 0.07), accentMat, [0, y, z]));
    });

    // Alt montaj kolu (optik raya bağlanır)
    const mountMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.88, roughness: 0.18 });
    slmGroup.add(_mesh(new THREE.BoxGeometry(0.065, 0.65, 0.065), mountMat, [0, -0.86, 0]));
    slmGroup.add(_mesh(new THREE.BoxGeometry(0.28, 0.065, 0.28), mountMat, [0, -1.18, 0]));

    // SLM kontrol kablosu (arkadan çıkar)
    const cblMat = new THREE.MeshStandardMaterial({ color: 0x330066, roughness: 0.75 });
    const slmCable = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, -0.80, -0.56),
      new THREE.Vector3(-0.4, -1.5, -0.5),
      new THREE.Vector3(0.6, -2.0, 0.4)
    ]);
    slmGroup.add(new THREE.Mesh(
      new THREE.TubeGeometry(slmCable, 14, 0.022, 6, false),
      cblMat
    ));

    scene.add(slmGroup);

    // ── Kondenser Lens — lazer çıkışından küre girişine ──
    const lensGroup = new THREE.Group();
    lensGroup.position.set(-2.82, 0.35, 0);
    lensGroup.rotation.z = Math.PI / 2; // tüp Y→X ekseni boyunca

    // Tutucu halka (lens barrel ring)
    const ringMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.88, roughness: 0.18 });
    lensGroup.add(new THREE.Mesh(new THREE.TorusGeometry(0.205, 0.030, 10, 32), ringMat));

    // Servis vidaları (3 adet)
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2;
      const screw = _mesh(
        new THREE.CylinderGeometry(0.018, 0.018, 0.055, 6),
        new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.95, roughness: 0.08 }),
        [Math.cos(a) * 0.205, 0, Math.sin(a) * 0.205]
      );
      screw.rotation.x = Math.PI / 2;
      lensGroup.add(screw);
    }

    // Bikonveks cam (iki yarım küre)
    const lensMat = new THREE.MeshPhysicalMaterial({
      color: 0x8ac8e8, transmission: 0.88, roughness: 0.0,
      transparent: true, opacity: 0.52,
      emissive: new THREE.Color(0x002211), emissiveIntensity: 0.08
    });
    const lensF = new THREE.Mesh(
      new THREE.SphereGeometry(0.19, 22, 22, 0, Math.PI * 2, 0, Math.PI * 0.48), lensMat);
    lensF.rotation.z = -Math.PI / 2;
    lensGroup.add(lensF);

    const lensB = new THREE.Mesh(
      new THREE.SphereGeometry(0.19, 22, 22, 0, Math.PI * 2, 0, Math.PI * 0.48), lensMat);
    lensB.rotation.z = Math.PI / 2;
    lensGroup.add(lensB);

    // Lens barrel tüp (şeffaf duvarlar)
    lensGroup.add(new THREE.Mesh(
      new THREE.CylinderGeometry(0.225, 0.225, 0.14, 20, 1, true),
      new THREE.MeshStandardMaterial({
        color: 0x1a2030, metalness: 0.78, roughness: 0.3,
        side: THREE.DoubleSide, transparent: true, opacity: 0.72
      })
    ));

    scene.add(lensGroup);
  }

  // ── Lazer Modülleri ─────────────────────────────────────
  function _buildLaserModules() {
    // Sol: 532nm Nd:YAG pump/input lazeri
    laserModuleLeft  = _makeLaserModule(0x2b3840, 0x39ff14, true);
    laserModuleLeft.position.set(-6.2, 0.35, 0);
    laserModuleLeft.rotation.z = -Math.PI/2;
    scene.add(laserModuleLeft);

    // Sağ: Küre çıkış tarafında kollimator / toplayıcı objektif tüpü
    // Lazer değil — kürenin çıkış ışığını odaklayıp kameraya gönderir
    laserModuleRight = _buildCollimatorTube();
    laserModuleRight.position.set(8.2, 0.35, 0);
    laserModuleRight.rotation.z = Math.PI / 2; // tüp -X'e (küreye) baksın
    scene.add(laserModuleRight);

    // Üst: 405nm violet pump lazeri — LC'yi yukarıdan uyarır (gerçek Freedericksz)
    // Gerçekte 405nm mor/UV ama simülasyonda violet olarak gösteriyoruz
    laserModulePump = _makeLaserModule(0x1e1a2e, 0xaa44ff, false);
    laserModulePump.position.set(0, 7.0, 0.3);
    laserModulePump.rotation.z = 0; // zaten dikey
    laserModulePump.rotation.x = Math.PI; // aşağıya baksın
    laserModulePump.scale.setScalar(0.6);
    scene.add(laserModulePump);
  }

  function _makeLaserModule(bodyColor, emitColor, hasMount) {
    const g = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({ color: bodyColor, metalness: 0.85, roughness: 0.18 });
    g.add(_mesh(new THREE.CylinderGeometry(0.52,0.56,2.8,20), bodyMat, [0,0,0]));

    const lensMat = new THREE.MeshPhysicalMaterial({
      color: 0x112233, transmission: 0.82, roughness: 0.0, transparent: true, opacity: 0.65,
      emissive: new THREE.Color(emitColor), emissiveIntensity: 0.0
    });
    const lens = new THREE.Mesh(new THREE.SphereGeometry(0.35,24,24,0,Math.PI*2,0,Math.PI*0.5), lensMat);
    lens.position.y = -1.4; lens.rotation.x = Math.PI;
    g.add(lens);

    const frameMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.9, roughness: 0.12 });
    const finMat   = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.7, roughness: 0.3 });
    const fRing = new THREE.Mesh(new THREE.TorusGeometry(0.36,0.038,10,32), frameMat);
    fRing.position.y = -1.4; g.add(fRing);

    for (let i = 0; i < 8; i++) {
      const a = (i/8)*Math.PI*2;
      const fin = _mesh(new THREE.BoxGeometry(0.04,0.55,0.16), finMat,
                        [Math.cos(a)*0.60, 0.5, Math.sin(a)*0.60]);
      fin.rotation.y = a; g.add(fin);
    }
    g.add(_mesh(new THREE.CylinderGeometry(0.11,0.13,0.85,10),
          new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 }), [0,1.85,0]));
    if (hasMount) {
      g.add(_mesh(new THREE.BoxGeometry(0.85,0.14,0.85),
            new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.8, roughness: 0.2 }), [0,0.7,0]));
    }
    g.userData.lensMesh = lens;
    return g;
  }

  // ── Kollimator / Toplayıcı Objektif Tüpü ────────────────
  // Küre çıkışındaki dağılmış ışığı odaklayıp kameraya yönlendiren optik
  // rotation.z=PI/2 ile: local+Y → world-X (küreye doğru)
  function _buildCollimatorTube() {
    const g = new THREE.Group();
    const alumMat  = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.90, roughness: 0.14 });
    const blackMat = new THREE.MeshStandardMaterial({ color: 0x0c0c0c, metalness: 0.78, roughness: 0.20 });
    const steelMat = new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.94, roughness: 0.10 });
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0x88ccee, transmission: 0.88, roughness: 0.0,
      transparent: true, opacity: 0.55,
      emissive: new THREE.Color(0x002233), emissiveIntensity: 0.10
    });

    // ─ Ana tüp gövdesi (ince, uzun silindir — lazer değil) ─
    g.add(_mesh(new THREE.CylinderGeometry(0.18, 0.18, 2.40, 24), blackMat, [0, 0, 0]));

    // ─ Lens mount flanşları (4 adet halka) ─
    [-0.90, -0.20, 0.40, 0.95].forEach(y => {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.20, 0.022, 10, 32), alumMat);
      ring.position.y = y;
      g.add(ring);
    });

    // ─ Ön lens grubu (küreye bakan taraf — local +Y) ─
    // Bikonveks toplama lensi
    const lensF = new THREE.Mesh(
      new THREE.SphereGeometry(0.165, 22, 22, 0, Math.PI*2, 0, Math.PI*0.46), glassMat);
    lensF.rotation.x = -Math.PI/2;
    lensF.position.y = 1.22;
    g.add(lensF);

    const lensB = new THREE.Mesh(
      new THREE.SphereGeometry(0.165, 22, 22, 0, Math.PI*2, 0, Math.PI*0.46), glassMat);
    lensB.rotation.x = Math.PI/2;
    lensB.position.y = 1.26;
    g.add(lensB);

    // Ön lens retainer halkası
    const retainer = new THREE.Mesh(new THREE.TorusGeometry(0.185, 0.028, 10, 32), alumMat);
    retainer.position.y = 1.24;
    g.add(retainer);

    // Ön kapak (lens koruyucu çerçeve)
    g.add(_mesh(
      new THREE.CylinderGeometry(0.205, 0.205, 0.065, 24, 1, true),
      alumMat, [0, 1.33, 0]
    ));

    // ─ Arka uç — çıkış adaptörü (kameraya bağlantı) ─
    // Adaptör flanş (geniş)
    g.add(_mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.10, 24), alumMat, [0, -1.25, 0]));
    // T-thread dönüştürücü (M42 filişi simülasyonu)
    g.add(_mesh(new THREE.CylinderGeometry(0.20, 0.20, 0.18, 24), steelMat, [0, -1.38, 0]));
    // Arka cam (AR kaplama)
    const backGlass = new THREE.Mesh(
      new THREE.CylinderGeometry(0.155, 0.155, 0.012, 20),
      new THREE.MeshPhysicalMaterial({
        color: 0x001a2a, transmission: 0.92, roughness: 0.0,
        transparent: true, opacity: 0.45
      })
    );
    backGlass.position.y = -1.46;
    g.add(backGlass);

    // ─ Optik ray adaptörü (alt montaj) ─
    // Post holder: tabana bağlanan dikey çubuk
    g.add(_mesh(new THREE.CylinderGeometry(0.058, 0.058, 1.35, 12), steelMat, [0, -1.85, 0]));
    // Ray klipsi
    g.add(_mesh(new THREE.BoxGeometry(0.58, 0.12, 0.30), alumMat, [0, -2.55, 0]));
    // Vida-yuvaları (2 adet)
    [-0.18, 0.18].forEach(dx => {
      g.add(_mesh(
        new THREE.CylinderGeometry(0.020, 0.020, 0.14, 8),
        steelMat, [dx, -2.55, 0]
      ));
    });

    // ─ Yan ayar vidaları (focus/zoom ring vidaları, 3 adet) ─
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2 + 0.5;
      const screw = _mesh(
        new THREE.CylinderGeometry(0.015, 0.015, 0.065, 6),
        steelMat,
        [Math.cos(a) * 0.195, 0.40, Math.sin(a) * 0.195]
      );
      screw.rotation.x = Math.PI / 2;
      screw.rotation.z = a;
      g.add(screw);
    }

    // userData.lensMesh null bırak — fireLaser'da null check var
    g.userData.lensMesh = null;
    return g;
  }

  // ── PCB Elektronik Kart (ESP32 + MCP4728 + Güç) ─────────
  function _buildPCB() {
    pcbGroup = new THREE.Group();
    pcbGroup.position.set(0.8, -2.45, 1.2);
    pcbGroup.rotation.y = -0.25;

    const pcbMat   = new THREE.MeshStandardMaterial({ color: 0x0b2e0b, roughness: 0.72, metalness: 0.08 });
    const tracMat  = new THREE.MeshStandardMaterial({ color: COPPER_COLOR, metalness: 0.92, roughness: 0.28 });
    const chipMat  = new THREE.MeshStandardMaterial({ color: 0x0d0d0d, roughness: 0.78 });
    const icMat    = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.8 });
    const standMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.88, roughness: 0.22 });
    const capMat   = new THREE.MeshStandardMaterial({ color: 0x8a5c00, roughness: 0.6, metalness: 0.2 });
    const resMat   = new THREE.MeshStandardMaterial({ color: 0x2a1a0a, roughness: 0.85 });

    // ─ Ana FR4 PCB tahtası ─
    pcbGroup.add(_mesh(new THREE.BoxGeometry(3.90, 0.09, 2.60), pcbMat, [0, 0, 0]));

    // Köşe montaj delikleri
    [[-1.80,-1.18],[-1.80,1.18],[1.80,-1.18],[1.80,1.18]].forEach(([x, z]) => {
      pcbGroup.add(_mesh(
        new THREE.CylinderGeometry(0.055, 0.055, 0.11, 10),
        new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.9 }),
        [x, 0, z]
      ));
    });

    // ─ Montaj dikmecikleri (4 adet alüm standoff) ─
    [[-1.80,-1.18],[-1.80,1.18],[1.80,-1.18],[1.80,1.18]].forEach(([x, z]) => {
      pcbGroup.add(_mesh(new THREE.CylinderGeometry(0.052, 0.052, 0.50, 10), standMat, [x, -0.30, z]));
    });

    // ─ ESP32 modülü (büyük, soldaki merkezi IC) ─
    // Gövde
    pcbGroup.add(_mesh(new THREE.BoxGeometry(0.62, 0.072, 0.42), chipMat, [-0.85, 0.082, 0.15]));
    // Metal shield (ESP32'nin karakteristik metal kapağı)
    pcbGroup.add(_mesh(
      new THREE.BoxGeometry(0.55, 0.045, 0.36),
      new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.92, roughness: 0.18 }),
      [-0.85, 0.128, 0.15]
    ));
    // Wi-Fi anten bloğu (yandan çıkar)
    pcbGroup.add(_mesh(
      new THREE.BoxGeometry(0.055, 0.038, 0.20),
      new THREE.MeshStandardMaterial({ color: 0x555555, metalness: 0.5, roughness: 0.4 }),
      [-0.60, 0.12, 0.15]
    ));
    // ESP32 bağlantı pinleri (iki sıra)
    for (let i = 0; i < 8; i++) {
      const px = -1.10 + i * 0.046;
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.016, 0.055, 0.016),
        new THREE.MeshStandardMaterial({ color: COPPER_COLOR, metalness: 0.95 }),
        [px, 0.055, 0.37]
      ));
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.016, 0.055, 0.016),
        new THREE.MeshStandardMaterial({ color: COPPER_COLOR, metalness: 0.95 }),
        [px, 0.055, -0.08]
      ));
    }

    // ─ MCP4728 DAC (küçük IC, sağ üst köşe) ─
    pcbGroup.add(_mesh(new THREE.BoxGeometry(0.28, 0.060, 0.20), icMat, [0.65, 0.075, 0.52]));
    // SOP8 pinler
    for (let i = 0; i < 4; i++) {
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.010, 0.030, 0.040),
        tracMat,
        [0.52 + i * 0.055, 0.058, 0.52]
      ));
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.010, 0.030, 0.040),
        tracMat,
        [0.52 + i * 0.055, 0.058, 0.64]
      ));
    }

    // ─ LDO voltaj regülatörü (SOT-223) ─
    pcbGroup.add(_mesh(new THREE.BoxGeometry(0.16, 0.065, 0.12), icMat, [1.10, 0.077, -0.62]));
    pcbGroup.add(_mesh(  // heat tab
      new THREE.BoxGeometry(0.16, 0.012, 0.06),
      tracMat,
      [1.10, 0.056, -0.70]
    ));

    // ─ Descoupling kapasitörler (6 adet — ESP32 çevresi) ─
    [
      [-0.46, 0.32], [-0.36, 0.32], [-0.50, -0.20],
      [-0.90, -0.30], [-1.12, 0.40], [-0.28, 0.58]
    ].forEach(([x, z]) => {
      pcbGroup.add(_mesh(new THREE.BoxGeometry(0.038, 0.058, 0.026), capMat, [x, 0.074, z]));
    });

    // ─ I2C pull-up dirençleri (2x0402 SMD) ─
    [[0.30, 0.42], [0.42, 0.42]].forEach(([x, z]) => {
      pcbGroup.add(_mesh(new THREE.BoxGeometry(0.028, 0.028, 0.018), resMat, [x, 0.064, z]));
    });

    // ─ Pin header konektör (6-pin — ITO kablo bağlantısı) ─
    const hdrMat = new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.9 });
    pcbGroup.add(_mesh(new THREE.BoxGeometry(0.36, 0.072, 0.12), hdrMat, [0.10, 0.081, -0.88]));
    for (let i = 0; i < 6; i++) {
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.016, 0.14, 0.016),
        new THREE.MeshStandardMaterial({ color: COPPER_COLOR, metalness: 0.95 }),
        [-0.12 + i * 0.055, 0.082, -0.88]
      ));
    }

    // ─ USB Micro-B konnektör (güç girişi) ─
    pcbGroup.add(_mesh(
      new THREE.BoxGeometry(0.10, 0.065, 0.20),
      new THREE.MeshStandardMaterial({ color: 0x444444, metalness: 0.85 }),
      [-1.78, 0.075, 0.0]
    ));

    // ─ Bakır izler (düzenli, PCB üstünde) ─
    const traceData = [
      [0.8, 0.04, 0.012, -0.80, 0.050, -0.60],
      [0.6, 0.04, 0.012,  0.00, 0.050,  0.00],
      [1.2, 0.04, 0.012,  0.10, 0.050,  0.90],
      [0.7, 0.04, 0.012, -0.40, 0.050, -1.00],
      [0.5, 0.04, 0.012,  1.00, 0.050,  0.20],
      [1.0, 0.04, 0.012, -0.20, 0.050,  0.70],
    ];
    traceData.forEach(([lx, ly, lz, px, py, pz]) => {
      pcbGroup.add(_mesh(new THREE.BoxGeometry(lx, ly, lz), tracMat, [px, py, pz]));
    });
    // Dikey izler
    [[0.012, 0.04, 0.55, 0.65, 0.050, -0.35],[0.012, 0.04, 0.40, -0.10, 0.050, 0.30]].forEach(([lx,ly,lz,px,py,pz]) => {
      pcbGroup.add(_mesh(new THREE.BoxGeometry(lx, ly, lz), tracMat, [px, py, pz]));
    });

    // ─ Durum LED'leri (köşede — yeşil power, sarı TX, kırmızı fault) ─
    [
      [0x00ff44, [1.78, 0.075,  0.95]],
      [0xffcc00, [1.78, 0.075,  0.72]],
      [0xff2200, [1.78, 0.075,  0.49]],
    ].forEach(([c, p]) => {
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.040, 0.040, 0.040),
        new THREE.MeshBasicMaterial({ color: c }),
        p
      ));
    });

    // ─ Bypass kapasitör sıraları (küçük, simetrik) ─
    for (let i = 0; i < 8; i++) {
      pcbGroup.add(_mesh(
        new THREE.BoxGeometry(0.030, 0.028, 0.020),
        capMat,
        [-1.60 + i * 0.30, 0.064, 1.10]
      ));
    }

    scene.add(pcbGroup);
  }

  // ── CMOS Kamera (RPi Camera Module 3 — Detaylı) ─────────
  function _buildCMOSCamera() {
    cameraModuleObj = new THREE.Group();
    // Speckle kamera — küreye z+ köşesinden açısal bakış
    // Three.js: lens local -Z yönü. rotation.y = atan2(px, pz) → lens (0,0,0)'a bakar
    // Doğrulama: (-sin(ry), 0, -cos(ry)) = normalize(−3.2, 0, −4.6) ✓
    const CAM_X = 3.2, CAM_Z = 4.6;
    cameraModuleObj.position.set(CAM_X, 0.35, CAM_Z);
    cameraModuleObj.rotation.y = Math.atan2(CAM_X, CAM_Z); // ~34.8° — lens tam küre merkezine

    const pcbMat  = new THREE.MeshStandardMaterial({ color: 0x0a1a40, roughness: 0.62, metalness: 0.12 });
    const sensMat = new THREE.MeshStandardMaterial({
      color: 0x0d0d0d, metalness: 0.25, roughness: 0.38,
      emissive: new THREE.Color(0x001122), emissiveIntensity: 0.7
    });
    const braMat  = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.90, roughness: 0.14 });
    const glsMat  = new THREE.MeshPhysicalMaterial({
      color: 0x001122, transmission: 0.90, roughness: 0.0,
      transparent: true, opacity: 0.60
    });
    const barrelMat = new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.84, roughness: 0.16 });
    const blackMat  = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.82 });

    // ─ Ana PCB kartı (mavi, daha büyük + belirgin) ─
    cameraModuleObj.add(_mesh(new THREE.BoxGeometry(0.98, 0.068, 0.98), pcbMat, [0, 0, 0]));

    // Köşe montaj delikleri (4 adet delik simülasyonu — koyu halkalar)
    [[-0.40,-0.40],[-0.40,0.40],[0.40,-0.40],[0.40,0.40]].forEach(([x,z]) => {
      cameraModuleObj.add(_mesh(
        new THREE.CylinderGeometry(0.022, 0.022, 0.085, 10),
        new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.9 }),
        [x, 0.005, z]
      ));
    });

    // ─ IMX708 Sensör çipi (belirgin dikdörtgen) ─
    cameraModuleObj.add(_mesh(new THREE.BoxGeometry(0.38, 0.048, 0.38), sensMat, [0, 0.058, 0]));
    // Sensör aktif alan çerçevesi (ince çizgi)
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.32, 0.02, 0.32),
      new THREE.MeshBasicMaterial({ color: 0x002233, wireframe: true }),
      [0, 0.078, 0]
    ));
    // Wirebond çeperi (altın sarısı çerçeve)
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.40, 0.012, 0.40),
      new THREE.MeshStandardMaterial({ color: 0xd4a020, metalness: 0.9, roughness: 0.15 }),
      [0, 0.084, 0]
    ));

    // ─ Lens barrel (uzun, profilli) ─
    const barrel = _mesh(new THREE.CylinderGeometry(0.17, 0.20, 0.56, 24), barrelMat, [0, 0, -0.30]);
    barrel.rotation.x = Math.PI / 2;
    cameraModuleObj.add(barrel);

    // Focus ring (alüm çizgi)
    const fRing = new THREE.Mesh(new THREE.TorusGeometry(0.185, 0.016, 8, 30), braMat);
    fRing.rotation.y = Math.PI / 2;
    fRing.position.z = -0.24;
    cameraModuleObj.add(fRing);

    // Zoom / aperture ring
    const zRing = new THREE.Mesh(new THREE.TorusGeometry(0.185, 0.012, 8, 30), braMat);
    zRing.rotation.y = Math.PI / 2;
    zRing.position.z = -0.42;
    cameraModuleObj.add(zRing);

    // ─ Lens ön camı (bikonveks) ─
    const lensF = new THREE.Mesh(
      new THREE.SphereGeometry(0.155, 22, 22, 0, Math.PI * 2, 0, Math.PI * 0.48), glsMat);
    lensF.rotation.x = Math.PI / 2;
    lensF.position.z = -0.60;
    cameraModuleObj.add(lensF);

    // Lens glow (aperture mavi parıltı)
    const glowCircle = new THREE.Mesh(
      new THREE.CircleGeometry(0.13, 28),
      new THREE.MeshBasicMaterial({
        color: 0x0044cc, transparent: true, opacity: 0.10,
        blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
      })
    );
    glowCircle.rotation.x = Math.PI / 2;
    glowCircle.position.z = -0.62;
    cameraModuleObj.add(glowCircle);

    // IR cut filtre
    const filt = _mesh(
      new THREE.CylinderGeometry(0.22, 0.22, 0.042, 22),
      new THREE.MeshPhysicalMaterial({
        color: 0x001a0a, transmission: 0.62, roughness: 0.02,
        transparent: true, opacity: 0.55
      }),
      [0, 0, -0.64]
    );
    filt.rotation.x = Math.PI / 2;
    cameraModuleObj.add(filt);

    // ─ Lens hood (ön şapka — karanlık tüp) ─
    const hood = _mesh(
      new THREE.CylinderGeometry(0.27, 0.23, 0.28, 22, 1, true),
      new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.9 }),
      [0, 0, -0.80]
    );
    hood.rotation.x = Math.PI / 2;
    cameraModuleObj.add(hood);

    // ─ Şerit kablo (FPC flat cable — tabana iner) ─
    const ribbonMat = new THREE.MeshStandardMaterial({ color: 0xf0c060, metalness: 0.22, roughness: 0.58 });
    cameraModuleObj.add(_mesh(new THREE.BoxGeometry(0.14, 0.026, 1.20), ribbonMat, [0, -0.046, 0.82]));
    // FPC konnektör (PCB'de)
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.18, 0.042, 0.14),
      new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.6 }),
      [0, -0.046, 0.46]
    ));

    // ─ Montaj braketi (L-profil alüm, optik raya bağlanır) ─
    // Yatay kol: X boyunca tutucudan aşağı
    cameraModuleObj.add(_mesh(new THREE.BoxGeometry(0.10, 0.10, 2.10), braMat, [0, -0.20, 0.72]));
    // Dikey kol: tabana iner
    cameraModuleObj.add(_mesh(new THREE.BoxGeometry(0.10, 1.70, 0.10), braMat, [0, -1.06, 1.80]));
    // Opitk ray tabanı montaj plakaları
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.58, 0.16, 0.58),
      new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.92, roughness: 0.10 }),
      [0, -1.90, 1.80]
    ));
    // Plaka vidaları
    [[-0.20, -0.20],[0.20, -0.20],[-0.20, 0.20],[0.20, 0.20]].forEach(([x, z]) => {
      cameraModuleObj.add(_mesh(
        new THREE.CylinderGeometry(0.018, 0.018, 0.10, 8),
        new THREE.MeshStandardMaterial({ color: STEEL_COLOR, metalness: 0.96 }),
        [x, -1.82, 1.80 + z]
      ));
    });

    // Durum LED'leri (yeşil aktif, kırmızı power)
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.038, 0.038, 0.038),
      new THREE.MeshBasicMaterial({ color: 0x00ff44 }),
      [0.36, 0.055, 0.40]
    ));
    cameraModuleObj.add(_mesh(
      new THREE.BoxGeometry(0.038, 0.038, 0.038),
      new THREE.MeshBasicMaterial({ color: 0xff2200 }),
      [0.36, 0.055, 0.25]
    ));

    // Kamera PointLight (sahne aydınlatması — görünürlük)
    const camLight = new THREE.PointLight(0x2244aa, 0.35, 2.2);
    cameraModuleObj.add(camLight);

    scene.add(cameraModuleObj);
  }

  // ── Voltaj Kablo Sistemi (PCB → ITO Elektrotlar) ──────────────────
  // Gerçek cihazda MCP4728 DAC → ince esnek kablolar → ITO pad’lar
  function _buildVoltageWiring() {
    // Kablo renkleri: kablo eksenlerine göre
    // PCB dünya konumu: (1.2, -2.4, 1.0)
    // cageGroup.y = 0.35 — elektrot kablosu uçları (cage local):
    //   ±X: (±3.9, 0, 0) + cage offset → world (±3.9, 0.35, 0)
    //   ±Y: (0, ±3.9, 0) → world (0, 4.25, 0) ve (0, -3.55, 0)
    //   ±Z: (0, 0, ±3.9) → world (0, 0.35, ±3.9)
    const pcb = new THREE.Vector3(1.2, -2.35, 1.0);

    const wireDefs = [
      // [kablo rengi, başlangıç world pos, ara kontrol noktası
      { c: 0x3399ff, s: new THREE.Vector3( 3.9, 0.35, 0),   m: new THREE.Vector3( 3.2, -1.0,  0.8) },
      { c: 0x3399ff, s: new THREE.Vector3(-3.9, 0.35, 0),   m: new THREE.Vector3(-3.0, -1.0,  0.6) },
      { c: 0x33ff99, s: new THREE.Vector3( 0,   4.25, 0),   m: new THREE.Vector3( 0.8,  2.0,  0.5) },
      { c: 0x33ff99, s: new THREE.Vector3( 0,  -3.55, 0),   m: new THREE.Vector3( 0.6, -2.8,  0.8) },
      { c: 0xff9933, s: new THREE.Vector3( 0,  0.35,  3.9), m: new THREE.Vector3( 0.8, -0.8,  3.0) },
      { c: 0xff9933, s: new THREE.Vector3( 0,  0.35, -3.9), m: new THREE.Vector3( 0.6, -0.8, -2.8) },
    ];

    wireDefs.forEach(w => {
      const curve = new THREE.CatmullRomCurve3([
        w.s,
        w.m,
        pcb.clone().add(new THREE.Vector3(
          (Math.random()-0.5)*0.4, (Math.random()-0.5)*0.2, (Math.random()-0.5)*0.4
        ))
      ]);
      const geo = new THREE.TubeGeometry(curve, 20, 0.018, 6, false);
      const mat = new THREE.MeshStandardMaterial({
        color: w.c,
        emissive: new THREE.Color(w.c),
        emissiveIntensity: 0.12,
        roughness: 0.7, metalness: 0.1
      });
      scene.add(new THREE.Mesh(geo, mat));
    });

    // PCB üzerine konnektör blokları (MCP4728 DAC çıkışları)
    const connMat = new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.6 });
    const pinMat  = new THREE.MeshStandardMaterial({ color: COPPER_COLOR, metalness: 0.95, roughness: 0.1 });
    // 6 kablo için 2 konnektör satırı (3’er pi)
    [[-0.3, 0], [0.3, 0]].forEach(([ox, oz]) => {
      const cx = pcb.x + ox, cy = pcb.y + 0.06, cz = pcb.z + oz;
      scene.add(_mesh(new THREE.BoxGeometry(0.20, 0.06, 0.08), connMat, [cx, cy, cz]));
      [-0.06, 0, 0.06].forEach(dx => {
        scene.add(_mesh(new THREE.BoxGeometry(0.014, 0.04, 0.01), pinMat, [cx+dx, cy+0.05, cz]));
      });
    });
  }

  // ── Lazer Işın Geometrisi ────────────────────────────────
  function _buildLaserBeams() {
    const add = THREE.AdditiveBlending;
    const mk = (geo, color, opacity) => new THREE.Mesh(geo,
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: add, depthWrite: false }));

    laserBeamLeft = mk(new THREE.CylinderGeometry(0.020,0.013,3.3,8), 0x39ff14, 0);
    laserBeamLeft.rotation.z = Math.PI/2;
    laserBeamLeft.position.set(-3.7, 0.35, 0);
    scene.add(laserBeamLeft);

    laserBeamCore = mk(new THREE.SphereGeometry(0.075,14,14), 0x99ff44, 0);
    laserBeamCore.position.set(0, 0.35, 0);
    scene.add(laserBeamCore);

    // Sağ çıkış demeti — küreden (x≈2.1) lazerModuleRight (x≈7.15) arası
    // Merkez x=4.6, uzunluk 5.1
    laserBeamRight = mk(new THREE.CylinderGeometry(0.024,0.042,5.1,8), 0x00f5ff, 0);
    laserBeamRight.rotation.z = Math.PI/2;
    laserBeamRight.position.set(4.65, 0.35, 0);
    scene.add(laserBeamRight);

    // 3. pump lazeri — yukarıdan aşağıya violet (405nm)
    laserBeamPump = mk(new THREE.CylinderGeometry(0.016,0.012,4.2,8), 0xaa44ff, 0);
    laserBeamPump.position.set(0, 2.8, 0.3);
    // dikey — zaten CylinderGeometry Y ekseninde, döndürme gerekmez
    scene.add(laserBeamPump);

    const seg = [[0,0.35,0,0.5,0.9,0.55],[0,0.35,0,-0.5,0.9,-0.55],[0,0.35,0,0.8,-0.45,0.45],
                 [0,0.35,0,-0.8,-0.45,-0.45],[0.5,0.75,0.4,1.75,0.35,0.08],[-0.5,0.75,-0.4,-1.7,0.35,-0.08]];
    seg.forEach(([ax,ay,az,bx,by,bz]) => {
      const s=new THREE.Vector3(ax,ay,az), e=new THREE.Vector3(bx,by,bz);
      const d=e.clone().sub(s), l=d.length(), m=s.clone().add(d.clone().multiplyScalar(0.5));
      const beam = mk(new THREE.CylinderGeometry(0.007,0.007,l,6), 0x55ff22, 0);
      beam.position.copy(m);
      beam.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), d.clone().normalize());
      scene.add(beam); laserBeamSegments.push(beam);
    });
  }

  // ── Partiküller (LC molekülleri) ─────────────────────────
  function _buildParticles() {
    const geo = new THREE.SphereGeometry(0.014, 4, 4);
    const cols = [0x39ff14, 0x00f5ff, 0xaaff66, 0x44ffaa];
    for (let i = 0; i < 400; i++) {
      const r = Math.random()*1.7, th = Math.random()*Math.PI, ph = Math.random()*Math.PI*2;
      const mat = new THREE.MeshBasicMaterial({
        color: cols[i%4], transparent: true, opacity: 0,
        blending: THREE.AdditiveBlending, depthWrite: false
      });
      const p = new THREE.Mesh(geo, mat);
      p.position.set(r*Math.sin(th)*Math.cos(ph), r*Math.sin(th)*Math.sin(ph)+0.35, r*Math.cos(th));
      p.userData = { base: p.position.clone(), speed: 0.2+Math.random()*0.6, phase: Math.random()*Math.PI*2 };
      scene.add(p); particles.push(p);
    }
  }

  // ── Animasyon Döngüsü ────────────────────────────────────

    // ── Tümünü İnşa Et ──────────────────────────────────────
    _buildLights();
    _buildBase();
    _buildFlask();
    _buildCage();
    _buildSLMCondenser();
    _buildLaserModules();
    _buildPCB();
    _buildCMOSCamera();
    _buildVoltageWiring();
    _buildLaserBeams();
    _buildParticles();

    // ── Referansları Döndür ────────────────────────────────
    return {
      baseGroup, flaskGroup, innerCrystalMesh, glassBottle,
      cageGroup, electrodes,
      laserModuleLeft, laserModuleRight, laserModulePump,
      pcbGroup, cameraModuleObj,
      laserBeamLeft, laserBeamRight, laserBeamCore, laserBeamPump, laserBeamSegments,
      particles,
      laserPointLight, lcPointLight, itoGlowLights
    };
  };

})();
