/* ═══════════════════════════════════════════════════════════════════════════
   scene-proposals.js  —  Zerre Elektrot Öneri Geometrileri
   Requires: THREE (global, loaded before this file)
   Exposes:  window._ZP_build(scene, proposalGroups, ALUM_COLOR, CARBON_COLOR, COPPER_COLOR)
             window._ZP_fly(camera, controls, toPos, toLook, duration)
             window._ZP_set(n, camera, controls, proposalGroups)
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  let _flyAnimId = null;
  let _stageLight = null;
  let _fireStart = -1;

  // ── Yerel mesh yardımcısı (scene.js'deki _mesh ile aynı) ─────────────────
  function _mesh(geo, mat, pos) {
    const m = new THREE.Mesh(geo, mat);
    if (pos) m.position.set(pos[0], pos[1], pos[2]);
    return m;
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  PROPOSALS BUILD — scene.js'den çağrılır
  // ═══════════════════════════════════════════════════════════════════════
  window._ZP_build = function (scene, proposalGroups, ALUM_COLOR, CARBON_COLOR, COPPER_COLOR) {

    const rootG = new THREE.Group();
    rootG.name = 'proposalRoot';

    // Seçili senaryoyu kristal netliğinde aydınlatan sahne takip ışığı
    _stageLight = new THREE.PointLight(0x99ddff, 0.0, 26);
    _stageLight.position.set(0, 6.5, 6.0);
    scene.add(_stageLight);

    // ─ Ortak malzemeler ─────────────────────────────────────────────────
    const alumMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.88, roughness: 0.15 });
    const baseMat = new THREE.MeshStandardMaterial({ color: CARBON_COLOR, metalness: 0.1, roughness: 0.3 });
    const glassMat = new THREE.MeshStandardMaterial({
      color: 0xaad4ee, emissive: new THREE.Color(0x0a1e2a), emissiveIntensity: 0.4,
      metalness: 0.05, roughness: 0.0, transparent: true, opacity: 0.12,
      depthWrite: false, side: THREE.DoubleSide
    });
    const lcMat = new THREE.MeshStandardMaterial({
      color: 0x001a33, emissive: new THREE.Color(0x00aaff), emissiveIntensity: 0.22,
      metalness: 0.0, roughness: 0.2, transparent: true, opacity: 0.70, depthWrite: false
    });
    const topGlassMat = new THREE.MeshStandardMaterial({
      color: 0x88ccff, metalness: 0.1, roughness: 0.0,
      transparent: true, opacity: 0.20, depthWrite: false, side: THREE.DoubleSide
    });
    const copperMat = new THREE.MeshStandardMaterial({ color: 0xb87333, metalness: 0.92, roughness: 0.18 });
    const ribbonMat = new THREE.MeshStandardMaterial({ color: 0xf0c050, metalness: 0.30, roughness: 0.55 });

    // ─ Fibonacci küre noktaları ──────────────────────────────────────────
    function fibPts(n, r) {
      const pts = [], phi = Math.PI * (3 - Math.sqrt(5));
      for (let i = 0; i < n; i++) {
        const y = 1 - (i / (n - 1)) * 2;
        const rad = Math.sqrt(Math.max(0, 1 - y * y));
        const th  = phi * i;
        pts.push(new THREE.Vector3(Math.cos(th) * rad * r, y * r, Math.sin(th) * rad * r));
      }
      return pts;
    }

    // ─ Ölçü çizgisi yardımcısı ──────────────────────────────────────────
    function _ruler(g, a, b, col) {
      const v = [a.x, a.y, a.z, b.x, b.y, b.z];
      const dx = b.x - a.x, dz = b.z - a.z;
      const tx = dz !== 0 ? 0.20 : 0, tz = dx !== 0 ? 0.20 : 0;
      [a, b].forEach(p => v.push(p.x - tx, p.y, p.z - tz, p.x + tx, p.y, p.z + tz));
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
      g.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.75 })));
    }

    // ════════════════════════════════════════════════════════════════════
    // ÖNERİ A — Dış Kafes Dizisi (32 ITO Çubuk)  •  x = -18
    // ════════════════════════════════════════════════════════════════════
    const gA = new THREE.Group(); gA.name = 'proposalA';
    gA.position.set(-18, 0, 0);
    proposalGroups.push(gA);

    gA.add(_mesh(new THREE.CylinderGeometry(3.2, 3.4, 0.18, 48), baseMat, [0, -3.1, 0]));
    gA.add(_mesh(new THREE.CylinderGeometry(0.18, 0.22, 1.02, 16), alumMat, [0, -2.55, 0]));
    gA.add(_mesh(new THREE.SphereGeometry(2.05, 48, 32), glassMat, [0, 0.35, 0]));
    gA.add(_mesh(new THREE.SphereGeometry(1.90, 32, 24), lcMat, [0, 0.35, 0]));

    const ringA1 = new THREE.Mesh(new THREE.TorusGeometry(4.0, 0.06, 12, 64), alumMat);
    ringA1.position.set(0, 0.35, 0);
    gA.add(ringA1);
    const ringA2 = new THREE.Mesh(new THREE.TorusGeometry(4.0, 0.06, 12, 64), alumMat);
    ringA2.position.set(0, 0.35, 0); ringA2.rotation.x = Math.PI / 2;
    gA.add(ringA2);
    const ringA3 = new THREE.Mesh(new THREE.TorusGeometry(4.0, 0.06, 12, 64), alumMat);
    ringA3.position.set(0, 0.35, 0); ringA3.rotation.z = Math.PI / 2;
    gA.add(ringA3);

    const itoRodMat = new THREE.MeshStandardMaterial({
      color: 0x44ddff, emissive: new THREE.Color(0x00aaff), emissiveIntensity: 0.65,
      metalness: 0.6, roughness: 0.2
    });
    const itoTipMat = new THREE.MeshStandardMaterial({
      color: 0x88eeff, emissive: new THREE.Color(0x00ccff), emissiveIntensity: 0.9,
      metalness: 0.7, roughness: 0.1
    });
    const up = new THREE.Vector3(0, 1, 0);
    fibPts(32, 2.85).forEach(p => {
      const dir    = p.clone().normalize();
      const rodLen = 0.55;
      const center = p.clone().add(dir.clone().multiplyScalar(rodLen * 0.5 + 0.04));
      center.y += 0.35;
      const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, rodLen, 8), itoRodMat);
      rod.position.copy(center);
      rod.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(up, dir));
      gA.add(rod);
      const tip = p.clone().add(dir.clone().multiplyScalar(rodLen + 0.09));
      tip.y += 0.35;
      const tipDot = new THREE.Mesh(new THREE.SphereGeometry(0.052, 8, 8), itoTipMat);
      tipDot.position.copy(tip);
      gA.add(tipDot);
      const wireEnd = dir.clone().multiplyScalar(3.96);
      wireEnd.y += 0.35;
      const wDir = new THREE.Vector3().subVectors(wireEnd, tip).normalize();
      const wLen = wireEnd.distanceTo(tip);
      const wMid = new THREE.Vector3().addVectors(wireEnd, tip).multiplyScalar(0.5);
      const wire = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, wLen, 4), copperMat);
      wire.position.copy(wMid);
      wire.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(up, wDir));
      gA.add(wire);
    });
    // Öneri A optik ışın ekseni (sol giriş → küre → sağ çıkış)
    const beamMatA = new THREE.MeshBasicMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const beamA = _mesh(new THREE.CylinderGeometry(0.026, 0.026, 9.2, 8), beamMatA, [0, 0.35, 0]);
    beamA.rotation.z = Math.PI / 2;
    gA.add(beamA);
    gA.userData.anim = { beamMat: beamMatA, rodMat: itoRodMat, tipMat: itoTipMat };
    rootG.add(gA);

    // ════════════════════════════════════════════════════════════════════
    // ÖNERİ B — Düzlem Paralel Plakalı ITO Matris (16×16 = 256)  •  x = -30
    // ════════════════════════════════════════════════════════════════════
    const gB = new THREE.Group(); gB.name = 'proposalB';
    gB.position.set(-30, 0, 0);
    proposalGroups.push(gB);

    gB.add(_mesh(new THREE.BoxGeometry(7.2, 0.18, 7.2), baseMat, [0, -3.1, 0]));
    [[-2.6, -2.6], [-2.6, 2.6], [2.6, -2.6], [2.6, 2.6]].forEach(([x, z]) => {
      gB.add(_mesh(new THREE.CylinderGeometry(0.14, 0.18, 1.18, 16), alumMat, [x, -2.55, z]));
    });

    const itoGlassMat = new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.35, roughness: 0.06, transparent: true, opacity: 0.78 });
    gB.add(_mesh(new THREE.CylinderGeometry(3.1, 3.1, 0.12, 48), itoGlassMat, [0, -0.06, 0]));

    const lcFlatMat = new THREE.MeshStandardMaterial({
      color: 0x001a33, emissive: new THREE.Color(0x00aaff), emissiveIntensity: 0.18,
      transparent: true, opacity: 0.55, depthWrite: false
    });
    gB.add(_mesh(new THREE.CylinderGeometry(3.05, 3.05, 0.90, 48), lcFlatMat, [0, 0.51, 0]));
    gB.add(_mesh(new THREE.CylinderGeometry(3.1, 3.1, 0.08, 48), topGlassMat, [0, 1.0, 0]));

    const dotMatB = new THREE.MeshStandardMaterial({ color: 0x44ddff, emissive: new THREE.Color(0x00aaff), emissiveIntensity: 1.0, metalness: 0.5, roughness: 0.1 });
    const dotGeoB = new THREE.SphereGeometry(0.048, 6, 6);
    const gridSpan = 5.2, stepB = gridSpan / 15;
    for (let i = 0; i < 16; i++) {
      for (let j = 0; j < 16; j++) {
        const xd = -gridSpan / 2 + i * stepB;
        const zd = -gridSpan / 2 + j * stepB;
        if (Math.sqrt(xd * xd + zd * zd) <= 2.85) {
          const dot = new THREE.Mesh(dotGeoB, dotMatB);
          dot.position.set(xd, 0.08, zd);
          gB.add(dot);
        }
      }
    }
    const linVerts = [];
    for (let i = 0; i <= 15; i++) {
      const p = -gridSpan / 2 + i * stepB;
      linVerts.push(-2.85, 0.09, p, 2.85, 0.09, p);
      linVerts.push(p, 0.09, -2.85, p, 0.09, 2.85);
    }
    const lineGeoB = new THREE.BufferGeometry();
    lineGeoB.setAttribute('position', new THREE.Float32BufferAttribute(linVerts, 3));
    gB.add(new THREE.LineSegments(lineGeoB, new THREE.LineBasicMaterial({ color: 0x004466, transparent: true, opacity: 0.3 })));

    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      gB.add(_mesh(new THREE.CylinderGeometry(0.024, 0.024, 1.12, 6), copperMat, [Math.cos(a) * 3.26, 0.5, Math.sin(a) * 3.26]));
    }
    const frameRingA = new THREE.Mesh(new THREE.TorusGeometry(3.18, 0.058, 10, 64), alumMat);
    frameRingA.position.set(0, 0.0, 0);
    gB.add(frameRingA);
    const frameRingB_m = new THREE.Mesh(new THREE.TorusGeometry(3.18, 0.058, 10, 64), alumMat);
    frameRingB_m.position.set(0, 1.02, 0);
    gB.add(frameRingB_m);
    const beamMatB = new THREE.MeshBasicMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    gB.add(_mesh(new THREE.CylinderGeometry(0.04, 0.04, 5.6, 10), beamMatB, [0, 0.6, 0]));
    gB.userData.anim = { beamMat: beamMatB, dotMat: dotMatB, lcMat: lcFlatMat };
    rootG.add(gB);

    // ════════════════════════════════════════════════════════════════════
    // ÖNERİ C — Yarı-Küre LC Kase (8×8 = 64)  •  x = -42
    // ════════════════════════════════════════════════════════════════════
    const gC = new THREE.Group(); gC.name = 'proposalC';
    gC.position.set(-42, 0, 0);
    proposalGroups.push(gC);

    gC.add(_mesh(new THREE.CylinderGeometry(3.2, 3.4, 0.18, 48), baseMat, [0, -3.1, 0]));
    gC.add(_mesh(new THREE.CylinderGeometry(0.18, 0.22, 1.02, 16), alumMat, [0, -2.55, 0]));

    const bowlGlassMat = new THREE.MeshStandardMaterial({
      color: 0xbbd8ee, emissive: new THREE.Color(0x0a1e2a), emissiveIntensity: 0.25,
      metalness: 0.05, roughness: 0.0, transparent: true, opacity: 0.15,
      depthWrite: false, side: THREE.DoubleSide
    });
    const bowl = new THREE.Mesh(new THREE.SphereGeometry(2.2, 48, 24, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), bowlGlassMat);
    bowl.position.set(0, 0.35, 0);
    gC.add(bowl);

    const lcBowlMat = new THREE.MeshStandardMaterial({
      color: 0x001a33, emissive: new THREE.Color(0x00aaff), emissiveIntensity: 0.20,
      transparent: true, opacity: 0.60, depthWrite: false
    });
    const lcBowl = new THREE.Mesh(new THREE.SphereGeometry(2.08, 32, 16, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), lcBowlMat);
    lcBowl.position.set(0, 0.35, 0);
    gC.add(lcBowl);

    gC.add(_mesh(new THREE.CylinderGeometry(2.2, 2.2, 0.10, 48),
      new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.4, roughness: 0.1, transparent: true, opacity: 0.82 }),
      [0, 0.35, 0]));

    const dotMatC = new THREE.MeshStandardMaterial({ color: 0xffcc00, emissive: new THREE.Color(0xff9900), emissiveIntensity: 1.1, metalness: 0.5, roughness: 0.1 });
    const dotGeoC = new THREE.SphereGeometry(0.076, 6, 6);
    const gsC = 3.4, gstep = gsC / 7;
    for (let i = 0; i < 8; i++) {
      for (let j = 0; j < 8; j++) {
        const xd = -gsC / 2 + i * gstep;
        const zd = -gsC / 2 + j * gstep;
        if (Math.sqrt(xd * xd + zd * zd) <= 1.88) {
          const dc = new THREE.Mesh(dotGeoC, dotMatC);
          dc.position.set(xd, 0.45, zd);
          gC.add(dc);
        }
      }
    }
    gC.add(_mesh(new THREE.CylinderGeometry(2.28, 2.28, 0.06, 48), topGlassMat, [0, 2.58, 0]));

    const ringC = new THREE.Mesh(new THREE.TorusGeometry(2.26, 0.08, 12, 48), alumMat);
    ringC.position.set(0, 0.35, 0);
    gC.add(ringC);
    const flexRing = new THREE.Mesh(new THREE.TorusGeometry(2.60, 0.24, 8, 48),
      new THREE.MeshStandardMaterial({ color: 0x0a3020, roughness: 0.4, metalness: 0.2 }));
    flexRing.position.set(0, 2.00, 0);
    gC.add(flexRing);
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      gC.add(_mesh(new THREE.CylinderGeometry(0.030, 0.030, 2.26, 6), copperMat, [Math.cos(a) * 2.36, 1.58, Math.sin(a) * 2.36]));
    }
    const beamMatC = new THREE.MeshBasicMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.22,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    gC.add(_mesh(new THREE.CylinderGeometry(0.04, 0.09, 5.2, 10), beamMatC, [0, 1.4, 0]));
    gC.userData.anim = { beamMat: beamMatC, dotMat: dotMatC, lcMat: lcBowlMat };
    rootG.add(gC);

    // ════════════════════════════════════════════════════════════════════
    // ÖNERİ D — Tek Plaka Detaylı (ITO Matris + 7 Malzeme Katmanı)
    // x = -57  |  1 birim ≈ 10 mm  |  LC görsel yüksekliği abartılmış (7μm→0.9u)
    // ════════════════════════════════════════════════════════════════════
    const gD = new THREE.Group(); gD.name = 'proposalD';
    gD.position.set(-57, 0, 0);
    proposalGroups.push(gD);

    // Katman Y koordinatları
    const D_BOT_GLASS_Y = -1.10;
    const D_PI_BOT_Y    = -0.87;
    const D_ITO_BOT_Y   = -0.82;
    const D_LC_Y        = -0.35;
    const D_ITO_TOP_Y   =  0.14;
    const D_PI_TOP_Y    =  0.20;
    const D_TOP_GLASS_Y =  0.44;
    const D_LC_H        = 0.90;
    const D_GLASS_H     = 0.38;
    const D_PI_H        = 0.10;

    // Malzemeler (D'ye özel)
    const dBotGlassMat = new THREE.MeshStandardMaterial({
      color: 0x0a2040, metalness: 0.15, roughness: 0.04, transparent: true, opacity: 0.78,
      emissive: new THREE.Color(0x001122), emissiveIntensity: 0.25
    });
    const dTopGlassMat = new THREE.MeshStandardMaterial({
      color: 0xaad8ee,
      emissive: new THREE.Color(0x3366aa),
      emissiveIntensity: 0.55,
      metalness: 0.18, roughness: 0.02,
      transparent: true, opacity: 0.60
    });
    const dPiMat = new THREE.MeshStandardMaterial({
      color: 0xe88c00, roughness: 0.6, metalness: 0.0, transparent: true, opacity: 0.80
    });
    const dItoPixelMat = new THREE.MeshStandardMaterial({
      color: 0x00ddff, metalness: 0.55, roughness: 0.05,
      emissive: new THREE.Color(0x00aaff), emissiveIntensity: 1.40
    });
    const dItoGndMat = new THREE.MeshStandardMaterial({
      color: 0x00ff88, metalness: 0.55, roughness: 0.05,
      emissive: new THREE.Color(0x00cc44), emissiveIntensity: 0.90,
      transparent: true, opacity: 0.70
    });
    const dLcMat = new THREE.MeshStandardMaterial({
      color: 0x001020, roughness: 0.1, metalness: 0.0,
      emissive: new THREE.Color(0x0055cc), emissiveIntensity: 0.70,
      transparent: true, opacity: 0.60, depthWrite: false
    });
    const dUvMat = new THREE.MeshStandardMaterial({
      color: 0xffaa00, roughness: 0.35, metalness: 0.0, transparent: true, opacity: 0.82
    });
    const dFrMat = new THREE.MeshStandardMaterial({ color: 0x0b2e0b, roughness: 0.72, metalness: 0.10 });

    // Platform + ayak — ortası AÇIK çerçeve (lazer ışını merkezden geçer)
    // 4 kenar şeridi: N/S/E/W, merkez [−2.5,+2.5] × [−2.5,+2.5] boş
    const plateH = 0.22, plateW = 10.0, apW = 5.2; // apW = aperture genişliği
    const sideW = (plateW - apW) / 2; // ~2.4 birim
    // +X şeridi
    gD.add(_mesh(new THREE.BoxGeometry(sideW, plateH, plateW), baseMat, [ (apW + sideW)/2, -3.5, 0]));
    // -X şeridi
    gD.add(_mesh(new THREE.BoxGeometry(sideW, plateH, plateW), baseMat, [-(apW + sideW)/2, -3.5, 0]));
    // +Z şeridi (merkez boşluk içinde kalan kısım)
    gD.add(_mesh(new THREE.BoxGeometry(apW, plateH, sideW), baseMat, [0, -3.5,  (apW + sideW)/2]));
    // -Z şeridi
    gD.add(_mesh(new THREE.BoxGeometry(apW, plateH, sideW), baseMat, [0, -3.5, -(apW + sideW)/2]));
    // Aperture gösterge halkası (nerede delik olduğunu vurgular)
    const apRing = new THREE.Mesh(new THREE.TorusGeometry(2.20, 0.042, 8, 48),
      new THREE.MeshStandardMaterial({ color: 0x224433, metalness: 0.70, roughness: 0.30 }));
    apRing.rotation.x = Math.PI / 2;
    apRing.position.y = -3.40;
    gD.add(apRing);
    [[-3.2, -3.2], [-3.2, 3.2], [3.2, -3.2], [3.2, 3.2]].forEach(([x, z]) => {
      gD.add(_mesh(new THREE.CylinderGeometry(0.13, 0.16, 2.56, 14), alumMat, [x, -2.22, z]));
    });
    gD.add(_mesh(new THREE.BoxGeometry(7.8, 0.14, 7.8), alumMat, [0, -1.33, 0]));

    // KATMAN 1 — Alt Borosilikat Cam (koyu mavi)
    gD.add(_mesh(new THREE.BoxGeometry(7.0, D_GLASS_H, 7.0), dBotGlassMat, [0, D_BOT_GLASS_Y, 0]));

    // KATMAN 2 — Alt Polyimide (turuncu ince şerit)
    gD.add(_mesh(new THREE.BoxGeometry(6.80, D_PI_H, 6.80), dPiMat, [0, D_PI_BOT_Y, 0]));

    // KATMAN 3 — 16×16 ITO Piksel Elektrot Matris
    gD.add(_mesh(new THREE.BoxGeometry(6.80, 0.055, 6.80), dItoPixelMat, [0, D_ITO_BOT_Y, 0]));
    const pgSpan = 5.8, pgStep = pgSpan / 15;
    for (let i = 0; i < 16; i++) {
      for (let j = 0; j < 16; j++) {
        const pd = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.07, 0.28), dItoPixelMat);
        pd.position.set(-pgSpan / 2 + i * pgStep, D_ITO_BOT_Y + 0.05, -pgSpan / 2 + j * pgStep);
        gD.add(pd);
      }
    }
    for (let i = 0; i < 16; i++) {
      gD.add(_mesh(new THREE.BoxGeometry(0.06, 0.025, pgSpan),
        new THREE.MeshStandardMaterial({ color: 0x0088bb, metalness: 0.90, roughness: 0.08 }),
        [-pgSpan / 2 + i * pgStep, D_ITO_BOT_Y + 0.038, 0]));
    }

    // KATMAN 4 — UV Epoksi Sealant (amber kenar)
    const SEAL_W = 0.28;
    [[3.40, 0, 0, SEAL_W, D_LC_H, 6.80], [-3.40, 0, 0, SEAL_W, D_LC_H, 6.80],
     [0, 0, 3.40, 6.80, D_LC_H, SEAL_W], [0, 0, -3.40, 6.80, D_LC_H, SEAL_W]].forEach(([x, y, z, lx, ly, lz]) => {
      gD.add(_mesh(new THREE.BoxGeometry(lx, ly, lz), dUvMat, [x, D_LC_Y, z]));
    });
    // E7 LC içi (derin mavi glow)
    gD.add(_mesh(new THREE.BoxGeometry(6.50, D_LC_H, 6.50), dLcMat, [0, D_LC_Y, 0]));

    // SiO₂ Spacer boncuklar (56 adet kenar boyunca)
    const spacMat2 = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.20, emissive: new THREE.Color(0x888888), emissiveIntensity: 0.4 });
    for (let i = 0; i < 56; i++) {
      const a = (i / 56) * Math.PI * 2;
      const rv = 3.30 + (i % 3 === 0 ? 0.05 : -0.05);
      const sp = new THREE.Mesh(new THREE.SphereGeometry(0.06, 7, 7), spacMat2);
      sp.position.set(Math.cos(a) * rv, D_LC_Y + (Math.random() - 0.5) * D_LC_H * 0.7, Math.sin(a) * rv);
      gD.add(sp);
    }

    // KATMAN 5 — Üst ITO GND Elektrot (yeşil)
    gD.add(_mesh(new THREE.BoxGeometry(6.80, 0.055, 6.80), dItoGndMat, [0, D_ITO_TOP_Y, 0]));

    // KATMAN 6 — Üst Polyimide
    gD.add(_mesh(new THREE.BoxGeometry(6.80, D_PI_H, 6.80), dPiMat, [0, D_PI_TOP_Y, 0]));

    // KATMAN 7 — Üst Borosilikat Cam (çok şeffaf)
    gD.add(_mesh(new THREE.BoxGeometry(7.0, D_GLASS_H, 7.0), dTopGlassMat, [0, D_TOP_GLASS_Y, 0]));
    gD.add(_mesh(new THREE.BoxGeometry(7.8, 0.14, 7.8), alumMat, [0, D_TOP_GLASS_Y + D_GLASS_H / 2 + 0.08, 0]));

    // 4 köşe vida kolonu
    const BOLT_Y_BOT = -1.26, BOLT_Y_TOP = D_TOP_GLASS_Y + D_GLASS_H / 2 + 0.15;
    const BOLT_H = BOLT_Y_TOP - BOLT_Y_BOT;
    [[-3.4, -3.4], [-3.4, 3.4], [3.4, -3.4], [3.4, 3.4]].forEach(([x, z]) => {
      gD.add(_mesh(new THREE.CylinderGeometry(0.095, 0.095, BOLT_H, 8), alumMat, [x, BOLT_Y_BOT + BOLT_H / 2, z]));
      gD.add(_mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.12, 8), alumMat, [x, BOLT_Y_TOP + 0.06, z]));
    });

    // ── PCB SÜRÜCÜ KARTI (kenarda, z=+7.5 — optik ekseni bloke etmez) ─
    const PCB_Z = 7.5;
    gD.add(_mesh(new THREE.BoxGeometry(6.2, 0.10, 3.8), dFrMat, [0, -0.80, PCB_Z]));
    [[-2.0, 0], [-1.0, 0], [0.2, 0], [1.4, 0]].forEach(([x, dz]) => {
      gD.add(_mesh(new THREE.BoxGeometry(0.56, 0.068, 0.40),
        new THREE.MeshStandardMaterial({ color: 0x111111 }), [x, -0.735, PCB_Z + dz]));
    });
    // ESP32 modülü (belirgin metal shield)
    gD.add(_mesh(new THREE.BoxGeometry(0.62, 0.075, 0.44),
      new THREE.MeshStandardMaterial({ color: 0x0d0d0d }), [2.2, -0.730, PCB_Z]));
    gD.add(_mesh(new THREE.BoxGeometry(0.58, 0.048, 0.40),
      new THREE.MeshStandardMaterial({ color: 0x999999, metalness: 0.92 }), [2.2, -0.706, PCB_Z]));
    // PCB montaj ayakları (platformun kenarına bağlanır)
    [[-2.8, PCB_Z - 1.6], [2.8, PCB_Z - 1.6], [-2.8, PCB_Z + 1.6], [2.8, PCB_Z + 1.6]].forEach(([x, z]) => {
      gD.add(_mesh(new THREE.CylinderGeometry(0.048, 0.048, 0.66, 8),
        new THREE.MeshStandardMaterial({ color: 0x707070, metalness: 0.88 }), [x, -1.15, z]));
    });

    // Ribbon kablo (cam +Z kenarından PCB'ye — hiçbir zaman z=0'dan geçmezler)
    for (let i = 0; i < 6; i++) {
      const xi = -1.8 + i * 0.72;
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(xi, D_ITO_BOT_Y + 0.05,  3.62),   // plaka +Z kenarı
        new THREE.Vector3(xi, -0.12, 5.40),                   // düz çıkış
        new THREE.Vector3(xi, -0.80, PCB_Z - 2.00)           // PCB
      ]);
      gD.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 14, 0.035, 4, false), ribbonMat));
    }
    // GND ribbon (ITO GND +Z kenarından PCB'ye)
    for (let i = 0; i < 4; i++) {
      const xi = -0.9 + i * 0.6;
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(xi, D_ITO_TOP_Y + 0.05, 3.62),
        new THREE.Vector3(xi,  0.40, 5.40),
        new THREE.Vector3(xi, -0.80, PCB_Z - 2.00)
      ]);
      gD.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 14, 0.025, 4, false),
        new THREE.MeshStandardMaterial({ color: 0x226622, roughness: 0.65 })));
    }

    // Edge glow halkası (LC aktif sınırı)
    const edgeGlowMat = new THREE.MeshBasicMaterial({ color: 0x0088ff, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false });
    const edgeRing = new THREE.Mesh(new THREE.TorusGeometry(3.40, 0.08, 8, 64), edgeGlowMat);
    edgeRing.position.y = D_LC_Y;
    edgeRing.rotation.x = Math.PI / 2;
    gD.add(edgeRing);

    // ── LAZER KAYNAĞI (alttan, polarize ışık, 532 nm) ──────────────────
    // Platform tabanı y=-3.5, bacaklar ±3.2 köşede — merkez açık, ışın geçebilir
    const dLaserBodyMat = new THREE.MeshStandardMaterial({ color: 0x1a2b1a, metalness: 0.86, roughness: 0.17 });
    const dLaserFinMat  = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.80, roughness: 0.25 });
    const laserPostMat  = new THREE.MeshStandardMaterial({ color: 0x2a3540, metalness: 0.92, roughness: 0.12 });

    // Lazer gövdesi (yatay bıçak, x ekseni boyunca, lens +Y'ye bakıyor)
    gD.add(_mesh(new THREE.CylinderGeometry(0.42, 0.46, 2.00, 22), dLaserBodyMat, [0, -5.50, 0]));
    // Soğutucu kanatlar (8 adet)
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      const fin = _mesh(new THREE.BoxGeometry(0.045, 0.55, 0.16), dLaserFinMat,
        [Math.cos(a) * 0.56, -5.50 + 0.20, Math.sin(a) * 0.56]);
      fin.rotation.y = a; gD.add(fin);
    }
    // Montaj kaidesi
    gD.add(_mesh(new THREE.BoxGeometry(1.40, 0.12, 1.40), ALUM_COLOR !== undefined ?
      new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.88, roughness: 0.18 }) : dLaserFinMat,
      [0, -6.52, 0]));
    // Direk (platform altına kadar)
    gD.add(_mesh(new THREE.CylinderGeometry(0.072, 0.072, 2.30, 10), laserPostMat, [0, -5.27, 0]));
    // Lens kapağı (yeşil — lens yukarı bakıyor, merkezde hayalet kopya bırakmadan)
    const dLensEm = new THREE.MeshStandardMaterial({
      color: 0x39ff14, emissive: new THREE.Color(0x39ff14), emissiveIntensity: 1.8,
      transparent: true, opacity: 0.90
    });
    const dLensMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.22, 18, 18, 0, Math.PI * 2, 0, Math.PI * 0.5), dLensEm);
    dLensMesh.rotation.x = Math.PI;
    dLensMesh.position.set(0, -4.50, 0);
    gD.add(dLensMesh);

    // Lazer ışını (532nm yeşil, dar Gauss demeti, alttan plate altına)
    // Lens top ~y=-4.28 → alt cam bottom y=D_BOT_GLASS_Y-D_GLASS_H/2 ≈ -1.29
    const beamLenY   = 4.28 - 1.29; // ~2.99
    const beamCenterY = (-4.28 + (-1.29)) / 2; // -2.785
    const beamMatD = new THREE.MeshBasicMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.45,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    // Tek beam mesh — doğru pozisyonda (lens üstü → alt cam altı)
    const beamMeshD = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.040, beamLenY, 8), beamMatD);
    beamMeshD.position.set(0, beamCenterY, 0);
    gD.add(beamMeshD);

    // Işın LC içinden çıkışı (yeşil→sarı tint ile faz kayması)
    const beamTopMat = new THREE.MeshBasicMaterial({
      color: 0x99ffcc, transparent: true, opacity: 0.50,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const beamTopY   = D_TOP_GLASS_Y + D_GLASS_H / 2; // ~0.63
    const detectorY  = 2.80;
    const beamTopLen = detectorY - beamTopY;
    const topBeam = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, beamTopLen, 8), beamTopMat);
    topBeam.position.set(0, (beamTopY + detectorY) / 2, 0);
    gD.add(topBeam);

    // ── POLARİZÖR (alt camın hemen altında, λ/2 plaka) ─────────────
    const polMat = new THREE.MeshStandardMaterial({
      color: 0x888888, metalness: 0.30, roughness: 0.08,
      transparent: true, opacity: 0.60,
      emissive: new THREE.Color(0x224422), emissiveIntensity: 0.20
    });
    gD.add(_mesh(new THREE.BoxGeometry(6.50, 0.055, 6.50), polMat,
      [0, D_BOT_GLASS_Y - D_GLASS_H / 2 - 0.12, 0]));
    // Polarizör çerçevesi
    const polFrameMat = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.85, roughness: 0.18 });
    gD.add(_mesh(new THREE.BoxGeometry(7.20, 0.10, 0.14), polFrameMat,
      [0, D_BOT_GLASS_Y - D_GLASS_H / 2 - 0.12, 3.30]));
    gD.add(_mesh(new THREE.BoxGeometry(7.20, 0.10, 0.14), polFrameMat,
      [0, D_BOT_GLASS_Y - D_GLASS_H / 2 - 0.12, -3.30]));

    // ── ANALİZÖR (üst camın hemen üstünde, 90° döndürülmüş) ────────
    const analMat = new THREE.MeshStandardMaterial({
      color: 0x886688, metalness: 0.30, roughness: 0.08,
      transparent: true, opacity: 0.55,
      emissive: new THREE.Color(0x441144), emissiveIntensity: 0.20
    });
    gD.add(_mesh(new THREE.BoxGeometry(6.50, 0.055, 6.50), analMat,
      [0, beamTopY + 0.12, 0]));

    // ── KAMERA / DEDEKTÖR — GANTRY YAPISI (plaka dışında, optik ekseni kesmez) ─
    const camBodyMat = new THREE.MeshStandardMaterial({ color: 0x0a1a40, roughness: 0.60, metalness: 0.14 });
    const camSensMat = new THREE.MeshStandardMaterial({
      color: 0x0d0d0d, metalness: 0.25, roughness: 0.38,
      emissive: new THREE.Color(0x001122), emissiveIntensity: 0.8
    });
    const camAlum = new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.90, roughness: 0.14 });

    // Gantry: iki dikey kolon x=±5.2 (plaka x=±3.5 dışında)
    const GANTRY_Y = detectorY + 1.60;   // ~4.4
    const GANTRY_X = 5.20;
    const postH    = GANTRY_Y + 3.80;    // platform taban y=-3.5'ten GANTRY_Y'e kadar
    [-GANTRY_X, GANTRY_X].forEach(px => {
      gD.add(_mesh(new THREE.CylinderGeometry(0.08, 0.10, postH, 12), camAlum,
        [px, -3.5 + postH / 2, 0]));
    });
    // Yatay üst kiriş
    gD.add(_mesh(new THREE.BoxGeometry(GANTRY_X * 2 + 0.20, 0.12, 0.12), camAlum,
      [0, GANTRY_Y, 0]));
    // Kısa düşüren kol (kirişten kamera gövdesine)
    const dropH = GANTRY_Y - (detectorY + 0.34);
    gD.add(_mesh(new THREE.CylinderGeometry(0.042, 0.042, dropH, 8), camAlum,
      [0, GANTRY_Y - dropH / 2, 0]));
    // Kamera bağlantı plaka klempi
    gD.add(_mesh(new THREE.BoxGeometry(0.55, 0.09, 0.55), camAlum,
      [0, detectorY + 0.38, 0]));

    // Kamera gövdesi (döndürme yok — barrel doğrudan aşağı bakıyor)
    const camGroup = new THREE.Group();
    camGroup.position.set(0, detectorY + 0.30, 0);
    gD.add(camGroup);
    camGroup.add(new THREE.Mesh(new THREE.BoxGeometry(1.10, 0.08, 1.10), camBodyMat));
    // Sensör
    camGroup.add(new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.055, 0.42), camSensMat));
    // Lens barrel (aşağı yön = -y)
    const dCamBarrel = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.21, 0.60, 20),
      new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.84, roughness: 0.16 })
    );
    dCamBarrel.position.y = -0.35;
    camGroup.add(dCamBarrel);
    // Ön lens dome (aşağı bakan)
    const dCamLens = new THREE.Mesh(
      new THREE.SphereGeometry(0.155, 20, 20, 0, Math.PI * 2, 0, Math.PI * 0.48),
      new THREE.MeshStandardMaterial({ color: 0x001122, transparent: true, opacity: 0.60, roughness: 0.0 })
    );
    dCamLens.rotation.x = -Math.PI / 2;  // dome aşağı
    dCamLens.position.y = -0.68;
    camGroup.add(dCamLens);

    // ── ITO ENERJİLENDİRME: VOLTAJ KAYNAĞI + BAĞLANTILARI ──────────
    // Voltaj kaynağı kutusu (platforma komşu, sağda)
    const vSrcMat = new THREE.MeshStandardMaterial({ color: 0x0d1a0d, roughness: 0.60, metalness: 0.18 });
    const vSrcGrp = new THREE.Group();
    vSrcGrp.position.set(6.2, -0.60, 0);
    gD.add(vSrcGrp);
    vSrcGrp.add(new THREE.Mesh(new THREE.BoxGeometry(1.60, 1.80, 1.00), vSrcMat));
    // Ekran (yeşil LED display)
    vSrcGrp.add(new THREE.Mesh(new THREE.BoxGeometry(1.00, 0.55, 0.06),
      new THREE.MeshStandardMaterial({ color: 0x001a00, emissive: new THREE.Color(0x00ff44), emissiveIntensity: 0.80, roughness: 0.10 })));
    // Knob
    vSrcGrp.add(new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.12, 16),
      new THREE.MeshStandardMaterial({ color: ALUM_COLOR, metalness: 0.90, roughness: 0.14 })));
    // Kleme terminaller (V+ kırmızı, GND siyah)
    const termRed = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.16, 10),
      new THREE.MeshStandardMaterial({ color: 0xff2200, metalness: 0.70 }));
    termRed.rotation.z = Math.PI / 2; termRed.position.set(0.56, -0.70, 0); vSrcGrp.add(termRed);
    const termBlk = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.16, 10),
      new THREE.MeshStandardMaterial({ color: 0x111111, metalness: 0.70 }));
    termBlk.rotation.z = Math.PI / 2; termBlk.position.set(0.56, -0.50, 0); vSrcGrp.add(termBlk);

    // V+ kablosu: voltaj kaynağı → ITO piksel katmanı (kırmızı)
    const vPlusCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(6.20 + 0.80, -0.60 - 0.70, 0),  // terminal
      new THREE.Vector3(5.80, -1.10, 0),
      new THREE.Vector3(3.60, D_ITO_BOT_Y, 0)             // ITO piksel kenarı
    ]);
    gD.add(new THREE.Mesh(new THREE.TubeGeometry(vPlusCurve, 14, 0.038, 6, false),
      new THREE.MeshStandardMaterial({ color: 0xff2200, emissive: new THREE.Color(0xff2200), emissiveIntensity: 0.35, roughness: 0.65 })));

    // GND kablosu: ITO GND katmanı → voltaj kaynağı (siyah)
    const gndCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(3.60, D_ITO_TOP_Y, 0.8),
      new THREE.Vector3(5.40,  0.60, 0.4),
      new THREE.Vector3(6.20 + 0.80, -0.60 - 0.50, 0)   // terminal
    ]);
    gD.add(new THREE.Mesh(new THREE.TubeGeometry(gndCurve, 14, 0.038, 6, false),
      new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.65 })));

    // Elektrik alan çizgileri (LC içinde, V → 5 adet dikey ok, dağılmış kOnumlar)
    const eFieldMat = new THREE.MeshBasicMaterial({
      color: 0xffff00, transparent: true, opacity: 0.55,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const eArrowLen = D_ITO_TOP_Y - D_ITO_BOT_Y; // ~0.96
    [[-1.8, -1.8], [0, -1.8], [1.8, -1.8], [-1.8, 1.8], [0, 0], [1.8, 1.8]].forEach(([fx, fz]) => {
      // Vertical dashed line
      const eLine = new THREE.Mesh(
        new THREE.CylinderGeometry(0.018, 0.018, eArrowLen * 0.85, 5),
        eFieldMat
      );
      eLine.position.set(fx, D_ITO_BOT_Y + eArrowLen / 2, fz);
      gD.add(eLine);
      // Ok başı (tepede)
      const arrow = new THREE.Mesh(
        new THREE.ConeGeometry(0.055, 0.16, 7),
        eFieldMat
      );
      arrow.position.set(fx, D_ITO_TOP_Y - 0.06, fz);
      gD.add(arrow);
    });
    // Elektrik alan etiketi
    const eGlowRing = new THREE.Mesh(
      new THREE.TorusGeometry(2.0, 0.022, 6, 48),
      new THREE.MeshBasicMaterial({ color: 0xffff00, transparent: true, opacity: 0.18, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    eGlowRing.rotation.x = Math.PI / 2;
    eGlowRing.position.y = D_LC_Y;
    gD.add(eGlowRing);

    // ── LC MOLEKÜL DİREKTÖR PROFİLİ (kesit, z=+3.8 ön yüz) ─────────
    // Freedericksz geçişi: PI rubbing → planar (θ=90° XZ'de)
    // Voltaj > Vth → center moleküller dikey (θ≈0° XZ'de → Y ekseni boyunca)
    // Director açısı XZ düzleminden ölçülür; θ=0 → yatay (X), θ=90° → dikey (Y)
    // rotation.z = π/2 - θ_rad
    const lcDirAngles = [5, 38, 72, 38, 5];  // derece (alttan üste, splay profili)
    const lcDirY = [
      D_ITO_BOT_Y + 0.06,
      D_ITO_BOT_Y + 0.26,
      D_ITO_BOT_Y + 0.46,
      D_ITO_BOT_Y + 0.66,
      D_ITO_BOT_Y + 0.86
    ];
    const lcDirColors = [0x00ff99, 0x66ff44, 0xffee00, 0x66ff44, 0x00ff99];
    const lcMolXPos = [-1.8, 0, 1.8];

    const dMolGroups = [];
    lcDirY.forEach((yPos, yi) => {
      const thetaDeg = lcDirAngles[yi];
      const thetaRad = thetaDeg * Math.PI / 180;
      const baseRotZ = Math.PI / 2 - thetaRad;  // 90° → yatay, 0° → dikey
      const molColor = new THREE.Color(lcDirColors[yi]);
      const molMat = new THREE.MeshStandardMaterial({
        color: molColor, emissive: molColor, emissiveIntensity: 0.80, roughness: 0.25
      });
      lcMolXPos.forEach(xPos => {
        const mg = new THREE.Group();
        mg.position.set(xPos, yPos, 3.85);
        mg.rotation.z = baseRotZ;
        mg.userData.baseRotZ = baseRotZ;
        // Molekül çubuğu + uç başları aynı grupta döner (Freedericksz animasyonu için)
        mg.add(new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.34, 7), molMat));
        [-0.17, 0.17].forEach(dy => {
          const head = new THREE.Mesh(new THREE.SphereGeometry(0.038, 7, 7), molMat);
          head.position.set(0, dy, 0);
          mg.add(head);
        });
        gD.add(mg);
        dMolGroups.push(mg);
      });
    });
    // Kesit çerçevesi (yalnızca ön kesit z=3.85 düzleminde, merkezde kopya yok)
    const sectionFrameMat = new THREE.MeshBasicMaterial({ color: 0x4488ff, transparent: true, opacity: 0.30, depthWrite: false });
    const sf = new THREE.Mesh(new THREE.BoxGeometry(5.20, D_LC_H + 0.10, 0.02), sectionFrameMat);
    sf.position.set(0, D_LC_Y, 3.85);
    gD.add(sf);

    gD.userData.anim = {
      beamMatD: beamMatD,
      beamTopMat: beamTopMat,
      lcMat: dLcMat,
      eFieldMat: eFieldMat,
      itoMat: dItoPixelMat,
      molGroups: dMolGroups
    };

    // ── ÖLÇÜ ÇİZGİLERİ ─────────────────────────────────────────────
    _ruler(gD, new THREE.Vector3(-3.5, -1.55, -4.5), new THREE.Vector3(3.5, -1.55, -4.5), 0x00f5ff);  // 70mm x
    _ruler(gD, new THREE.Vector3(4.5, -1.55, -3.5), new THREE.Vector3(4.5, -1.55, 3.5), 0x00f5ff);   // 70mm z
    _ruler(gD, new THREE.Vector3(-4.5, D_BOT_GLASS_Y - 0.19, 0), new THREE.Vector3(-4.5, D_TOP_GLASS_Y + 0.19, 0), 0xffcc00); // Y katman yüksekliği
    _ruler(gD, new THREE.Vector3(0, -4.28, 0), new THREE.Vector3(0, D_BOT_GLASS_Y - D_GLASS_H/2, 0), 0x39ff14);  // lazer→cam mesafesi
    _ruler(gD, new THREE.Vector3(0, beamTopY, 0), new THREE.Vector3(0, detectorY, 0), 0x99ffcc);                  // cam çıkış→dedektör

    rootG.add(gD);

    // ════════════════════════════════════════════════════════════════════
    // ÖNERİ E — Çok Katmanlı D²NN (3 LC Plaka Seri)  •  x = -72
    // Fresnel yayılım aralığı: ~30mm (3.0 birim)
    // ════════════════════════════════════════════════════════════════════
    const gE = new THREE.Group(); gE.name = 'proposalE';
    gE.position.set(-72, 0, 0);
    proposalGroups.push(gE);

    // Platform + optik ray
    gE.add(_mesh(new THREE.BoxGeometry(20, 0.18, 7.5), baseMat, [0, -3.1, 0]));
    gE.add(_mesh(new THREE.BoxGeometry(18, 0.16, 0.30), alumMat, [0, -2.80, 0]));
    gE.add(_mesh(new THREE.BoxGeometry(18, 0.16, 0.30), alumMat, [0, -2.80, 1.4]));

    // Lazer kaynağı (sol, x=-8.5)
    const lazerGrp = new THREE.Group();
    lazerGrp.position.set(-8.5, 0.35, 0);
    const lazerMat = new THREE.MeshStandardMaterial({ color: 0x2b3840, metalness: 0.85, roughness: 0.18 });
    lazerGrp.add(_mesh(new THREE.CylinderGeometry(0.45, 0.48, 2.2, 20), lazerMat, [0, 0, 0]));
    const lazerLens = new THREE.Mesh(
      new THREE.SphereGeometry(0.30, 20, 20, 0, Math.PI * 2, 0, Math.PI * 0.5),
      new THREE.MeshStandardMaterial({ color: 0x112233, transparent: true, opacity: 0.65, emissive: new THREE.Color(0x39ff14), emissiveIntensity: 0.6 })
    );
    lazerLens.position.y = -1.1; lazerLens.rotation.x = Math.PI;
    lazerGrp.add(lazerLens);
    for (let i = 0; i < 6; i++) {
      const fa = (i / 6) * Math.PI * 2;
      lazerGrp.add(_mesh(new THREE.BoxGeometry(0.04, 0.45, 0.14), alumMat, [Math.cos(fa) * 0.55, 0.3, Math.sin(fa) * 0.55]));
    }
    lazerGrp.rotation.z = -Math.PI / 2;
    gE.add(lazerGrp);

    // Giriş SLM maskesi
    const slmE = new THREE.Group();
    slmE.position.set(-6.5, 0.35, 0);
    slmE.add(_mesh(new THREE.BoxGeometry(0.10, 3.8, 3.8), new THREE.MeshStandardMaterial({ color: 0x121a22, metalness: 0.85, roughness: 0.22 }), [0, 0, 0]));
    slmE.add(_mesh(new THREE.BoxGeometry(0.025, 3.2, 3.2), new THREE.MeshStandardMaterial({ color: 0x001810, emissive: new THREE.Color(0x00ff44), emissiveIntensity: 0.25, roughness: 0.08 }), [0.055, 0, 0]));
    gE.add(slmE);

    // 3 LC plaka katmanı
    const platePosX   = [-4.5, -1.5, 1.5];
    const plateColors = [0x00aaff, 0x00ddaa, 0xaaaaff];
    const plateEmits  = [0x0044cc, 0x008855, 0x4444aa];

    platePosX.forEach((px, ki) => {
      const pGrp = new THREE.Group();
      pGrp.position.set(px, 0.35, 0);

      // Alt ITO cam
      pGrp.add(_mesh(new THREE.BoxGeometry(0.11, 3.8, 3.8),
        new THREE.MeshStandardMaterial({ color: 0x223344, metalness: 0.35, roughness: 0.06, transparent: true, opacity: 0.78 }), [0, 0, 0]));
      // LC katmanı
      pGrp.add(_mesh(new THREE.BoxGeometry(0.14, 3.6, 3.6),
        new THREE.MeshStandardMaterial({ color: plateColors[ki], emissive: new THREE.Color(plateEmits[ki]), emissiveIntensity: 0.28, transparent: true, opacity: 0.52, depthWrite: false }), [0.12, 0, 0]));

      // 16×16 piksel ızgarası
      const pxSpan2 = 3.0, pxStep2 = pxSpan2 / 15;
      const pxDotMat = new THREE.MeshStandardMaterial({ color: plateColors[ki], emissive: new THREE.Color(plateEmits[ki]), emissiveIntensity: 1.2, metalness: 0.4, roughness: 0.1 });
      const pxDotGeo = new THREE.BoxGeometry(0.025, 0.14, 0.14);
      for (let ii = 0; ii < 16; ii++) {
        for (let jj = 0; jj < 16; jj++) {
          const dxt = new THREE.Mesh(pxDotGeo, pxDotMat);
          dxt.position.set(0.20, -pxSpan2 / 2 + ii * pxStep2, -pxSpan2 / 2 + jj * pxStep2);
          pGrp.add(dxt);
        }
      }

      // Üst ITO cam
      pGrp.add(_mesh(new THREE.BoxGeometry(0.08, 3.8, 3.8), topGlassMat, [0.26, 0, 0]));

      // Alüminyum dış çerçeve — yalnızca 4 kenar çubuğu (merkez optik açıklık tamamen şeffaf!)
      [[0.12,  1.95, 0, 0.42, 0.12, 4.02],
       [0.12, -1.95, 0, 0.42, 0.12, 4.02],
       [0.12, 0,  1.95, 0.42, 3.80, 0.12],
       [0.12, 0, -1.95, 0.42, 3.80, 0.12]].forEach(([x, y, z, lx, ly, lz]) => {
        pGrp.add(_mesh(new THREE.BoxGeometry(lx, ly, lz), alumMat, [x, y, z]));
      });

      // Mini PCB sürücü kartı
      const pcbEMat = new THREE.MeshStandardMaterial({ color: ki === 0 ? 0x0b2e0b : ki === 1 ? 0x1a1a0b : 0x0b0b2e, roughness: 0.72, metalness: 0.08 });
      pGrp.add(_mesh(new THREE.BoxGeometry(0.09, 2.2, 1.0), pcbEMat, [0.10, -2.6, 0]));
      pGrp.add(_mesh(new THREE.BoxGeometry(0.075, 0.6, 0.4), new THREE.MeshStandardMaterial({ color: 0x111111 }), [0.15, -2.6, 0.1]));
      pGrp.add(_mesh(new THREE.BoxGeometry(0.028, 1.10, 0.14), ribbonMat, [0.06, -1.95, 0]));

      gE.add(pGrp);

      // Fresnel yayılım konisi (katmanlar arası)
      if (ki < 2) {
        const fresnelMat = new THREE.MeshBasicMaterial({
          color: 0x39ff14, transparent: true, opacity: 0.07,
          blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
        });
        const cone = new THREE.Mesh(new THREE.CylinderGeometry(1.45, 1.75, 2.75, 18, 1, true), fresnelMat);
        cone.rotation.z = Math.PI / 2;
        cone.position.set(px + 1.62, 0.35, 0);
        gE.add(cone);
        if (!gE.userData.cones) gE.userData.cones = [];
        gE.userData.cones.push(fresnelMat);
        const propVerts = [px + 0.3, 0.35, 0, px + 2.95, 0.35, 0];
        const propGeo = new THREE.BufferGeometry();
        propGeo.setAttribute('position', new THREE.Float32BufferAttribute(propVerts, 3));
        gE.add(new THREE.LineSegments(propGeo, new THREE.LineBasicMaterial({ color: 0x39ff14, transparent: true, opacity: 0.65 })));
      }
    });

    // Giriş (Lazer→SLM→Katman1) ve Çıkış (Katman3→CMOS) ışınları
    const eBeamInMat = new THREE.MeshBasicMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.48,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const eBeamOutMat = new THREE.MeshBasicMaterial({
      color: 0x00f5ff, transparent: true, opacity: 0.48,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const eb1 = _mesh(new THREE.CylinderGeometry(0.036, 0.036, 3.0, 8), eBeamInMat, [-6.0, 0.35, 0]);
    eb1.rotation.z = Math.PI / 2; gE.add(eb1);
    const eb2 = _mesh(new THREE.CylinderGeometry(0.042, 0.028, 2.3, 8), eBeamOutMat, [2.95, 0.35, 0]);
    eb2.rotation.z = Math.PI / 2; gE.add(eb2);

    // CMOS Kamera (sağ, x=+4.5 — dikey montajlı ve tam -X gelen ışına bakıyor!)
    const camGrpE = new THREE.Group();
    camGrpE.position.set(4.5, 0.35, 0);
    camGrpE.add(_mesh(new THREE.BoxGeometry(0.10, 1.15, 1.15), new THREE.MeshStandardMaterial({ color: 0x0a1a40, roughness: 0.55 }), [0.22, 0, 0]));
    camGrpE.add(_mesh(new THREE.BoxGeometry(0.05, 0.44, 0.44), new THREE.MeshStandardMaterial({ color: 0x0d0d0d, emissive: new THREE.Color(0x002244), emissiveIntensity: 0.8 }), [0.15, 0, 0]));
    const barrelE = _mesh(new THREE.CylinderGeometry(0.20, 0.24, 0.62, 24), new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.85, roughness: 0.2 }), [-0.16, 0, 0]);
    barrelE.rotation.z = Math.PI / 2;
    camGrpE.add(barrelE);
    // Optik raya inen kamera dikmesi
    camGrpE.add(_mesh(new THREE.CylinderGeometry(0.06, 0.07, 2.55, 10), alumMat, [0.22, -1.85, 0]));
    gE.add(camGrpE);
    gE.userData.anim = { beamIn: eBeamInMat, beamOut: eBeamOutMat, cones: gE.userData.cones || [] };

    // Ölçü çizgileri — katmanlar arası Fresnel mesafesi (30mm = 3.0 birim)
    _ruler(gE, new THREE.Vector3(-4.5, -2.2, 2.8), new THREE.Vector3(-1.5, -2.2, 2.8), 0x00f5ff);
    _ruler(gE, new THREE.Vector3(-1.5, -2.2, 2.8), new THREE.Vector3(1.5, -2.2, 2.8), 0x00f5ff);
    // Toplam sistem genişliği
    _ruler(gE, new THREE.Vector3(-8.5, 2.8, 0), new THREE.Vector3(4.5, 2.8, 0), 0xffcc00);

    rootG.add(gE);

    // ══════════════════════════════════════════════════════════════════════
    //  MODEL F — FOTODIOD ADRESLEMELİ KÜRE  (x = -87)
    // ══════════════════════════════════════════════════════════════════════
    const gF = new THREE.Group();
    gF.name = 'proposalF';
    gF.position.set(-87, 0, 0);
    proposalGroups.push(gF);

    const _PI      = Math.PI;
    const F_R      = 2.05;    // borosilikat küre dış yarıçap
    const F_LC_R   = 1.90;    // LC iç yarıçap
    const F_CY     = 0.35;    // küre merkezi Y    (taban üstü hizalı)
    const yAxisF   = new THREE.Vector3(0, 1, 0);

    // ── Optik Taban (ortası alt 532nm lazer geçişi için AÇIK çerçeve!) ──
    gF.add(_mesh(new THREE.BoxGeometry(5.2, 0.30, 10), baseMat, [-4.4, -2.90, 0]));
    gF.add(_mesh(new THREE.BoxGeometry(5.2, 0.30, 10), baseMat, [ 4.4, -2.90, 0]));
    gF.add(_mesh(new THREE.BoxGeometry(3.6, 0.30, 3.2), baseMat, [0, -2.90,  3.4]));
    gF.add(_mesh(new THREE.BoxGeometry(3.6, 0.30, 3.2), baseMat, [0, -2.90, -3.4]));
    const fApRing = new THREE.Mesh(new THREE.TorusGeometry(1.55, 0.045, 8, 40), alumMat);
    fApRing.rotation.x = _PI / 2;
    fApRing.position.set(0, -2.74, 0);
    gF.add(fApRing);

    // Gantry: 2 dikey kolon
    gF.add(_mesh(new THREE.BoxGeometry(0.25, 6.60, 0.25), alumMat, [-5.2, F_CY, 0]));
    gF.add(_mesh(new THREE.BoxGeometry(0.25, 6.60, 0.25), alumMat, [ 5.2, F_CY, 0]));
    // Gantry: yatay kiriş (üstte)
    gF.add(_mesh(new THREE.BoxGeometry(10.65, 0.22, 0.22), alumMat, [0, F_CY + 3.3, 0]));

    // ── LC Dolgu — E7 tam küre ─────────────────────────────────────────
    const lcSphF = new THREE.Mesh(
      new THREE.SphereGeometry(F_LC_R, 48, 32),
      lcMat
    );
    lcSphF.position.set(0, F_CY, 0);
    gF.add(lcSphF);

    // ── Alt yarım küre — homojen ITO GND tabakası (iç yüzey) ──────────
    const itoGndMat = new THREE.MeshStandardMaterial({
      color: 0x00cc55, transparent: true, opacity: 0.28,
      side: THREE.DoubleSide, depthWrite: false
    });
    const botHalfF = new THREE.Mesh(
      new THREE.SphereGeometry(F_R, 48, 24, 0, _PI * 2, _PI / 2, _PI / 2),
      itoGndMat
    );
    botHalfF.position.set(0, F_CY, 0);
    gF.add(botHalfF);

    // ── Üst yarım küre — borosilikat cam (şeffaf) ─────────────────────
    const topHalfF = new THREE.Mesh(
      new THREE.SphereGeometry(F_R, 48, 24, 0, _PI * 2, 0, _PI / 2),
      glassMat
    );
    topHalfF.position.set(0, F_CY, 0);
    gF.add(topHalfF);

    // ── Ekvator GND halkası (bakır/iletken) ───────────────────────────
    const gndRingMatF = new THREE.MeshStandardMaterial({ color: 0xb87333, metalness: 0.92, roughness: 0.20 });
    const gndRingF = new THREE.Mesh(
      new THREE.TorusGeometry(F_R + 0.02, 0.048, 16, 80),
      gndRingMatF
    );
    gndRingF.position.set(0, F_CY, 0);
    gF.add(gndRingF);

    // ── UV Epoksi birleşme hattı ───────────────────────────────────────
    const epMatF = new THREE.MeshStandardMaterial({
      color: 0xffaa00, transparent: true, opacity: 0.60,
      emissive: new THREE.Color(0x553300), emissiveIntensity: 0.40
    });
    const epRingF = new THREE.Mesh(
      new THREE.TorusGeometry(F_R + 0.01, 0.030, 8, 80),
      epMatF
    );
    epRingF.position.set(0, F_CY + 0.07, 0);
    gF.add(epRingF);

    // ── 32 Fibonacci Fotodiod + ITO Yama + Via Telleri ────────────────
    const fptsF         = fibPts(32, F_R);
    const itoPatchMatF  = new THREE.MeshStandardMaterial({
      color: 0x00ffee, transparent: true, opacity: 0.78,
      emissive: new THREE.Color(0x004444), emissiveIntensity: 0.55
    });
    const photodMatF = new THREE.MeshStandardMaterial({
      color: 0x8800ff, metalness: 0.60, roughness: 0.28,
      emissive: new THREE.Color(0x440088), emissiveIntensity: 0.70
    });
    const viaMatF = new THREE.MeshStandardMaterial({ color: 0xb87333, metalness: 0.88, roughness: 0.18 });

    fptsF.forEach(function(pt) {
      var dir = pt.clone().normalize();

      // İç ITO yama — LC_R + epsilon konumunda, küre iç yüzeyine teğet
      var innerR = F_LC_R + 0.045;
      var innerPos = dir.clone().multiplyScalar(innerR);
      var patch = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.022, 0.22), itoPatchMatF);
      patch.position.set(innerPos.x, innerPos.y + F_CY, innerPos.z);
      patch.quaternion.setFromUnitVectors(yAxisF, dir);
      gF.add(patch);

      // Dış fotodiod — sphere dışında, dışa teğet
      var outerR = F_R + 0.04;
      var outerPos = dir.clone().multiplyScalar(outerR);
      var pd = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.065, 0.17), photodMatF);
      pd.position.set(outerPos.x, outerPos.y + F_CY, outerPos.z);
      pd.quaternion.setFromUnitVectors(yAxisF, dir);
      gF.add(pd);

      // Via teli — cam kalınlığını geçen ince silindir
      var vsStart = dir.clone().multiplyScalar(F_LC_R + 0.07);
      var vsEnd   = dir.clone().multiplyScalar(F_R + 0.01);
      var viaLen  = vsEnd.clone().sub(vsStart).length();
      var viaMid  = vsStart.clone().add(vsEnd).multiplyScalar(0.5);
      var via = new THREE.Mesh(new THREE.CylinderGeometry(0.013, 0.013, viaLen, 6), viaMatF);
      via.position.set(viaMid.x, viaMid.y + F_CY, viaMid.z);
      via.quaternion.setFromUnitVectors(yAxisF, dir);
      gF.add(via);
    });

    // ── Galvo Ayna / 805nm IR Aktivasyon Lazer Sistemi ────────────────
    // 805nm diod lazer: Si fotodiod (~0.5V/diod, ×4 seri = ~2V) için uygun
    // Işın MUTLAKA küre dış yüzeyindeki fotodioda vurur, içe girmez.
    var lazerBodyF = new THREE.Mesh(
      new THREE.CylinderGeometry(0.14, 0.14, 1.10, 16),
      alumMat
    );
    lazerBodyF.rotation.x = _PI / 2;
    lazerBodyF.position.set(-3.5, F_CY + 2.9, -5.7);
    gF.add(lazerBodyF);
    // Lazer uç feneri (kırmızı IR gözü)
    gF.add(_mesh(
      new THREE.CylinderGeometry(0.07, 0.10, 0.12, 12),
      new THREE.MeshStandardMaterial({ color: 0xff1100, emissive: new THREE.Color(0xcc0000), emissiveIntensity: 1.8 }),
      [-3.5, F_CY + 2.9, -5.10]
    ));

    // Galvo ayna gövdesi
    gF.add(_mesh(new THREE.BoxGeometry(0.38, 0.36, 0.38), alumMat, [-3.5, F_CY + 2.9, -4.3]));

    // Galvo ayna yüzeyi
    var galvoMirrorF = new THREE.Mesh(
      new THREE.BoxGeometry(0.52, 0.07, 0.36),
      new THREE.MeshStandardMaterial({ color: 0xddeeff, metalness: 0.97, roughness: 0.03 })
    );
    galvoMirrorF.position.set(-3.5, F_CY + 2.9, -4.1);
    galvoMirrorF.rotation.x = -0.42;
    galvoMirrorF.rotation.y =  0.28;
    gF.add(galvoMirrorF);

    // 805nm IR: kırmızımsı karanlık renk (gerçekte görünmez, koyu kırmızı temsil)
    var actMatF = new THREE.MeshStandardMaterial({
      color: 0xdd2200, transparent: true, opacity: 0.72,
      emissive: new THREE.Color(0x991100), emissiveIntensity: 1.40
    });

    // Ana aktivasyon ışını: galvo → küre DIŞ YÜZEYİ (fotodiod noktası)
    // Hedef: galvoya bakan dış yüzey noktası  dir=normalize(-3.5, 2.9, -4.1)×F_R
    var actCurveF = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-3.5,  F_CY + 2.9,  -4.1),   // galvo ayna çıkışı
      new THREE.Vector3(-2.34, F_CY + 1.94, -2.74),  // orta yay noktası
      new THREE.Vector3(-1.17, F_CY + 0.97, -1.37)   // dış yüzey fotodiod → DURUR
    ]);
    gF.add(new THREE.Mesh(new THREE.TubeGeometry(actCurveF, 16, 0.022, 6, false), actMatF));

    // 3 örnek tarama ışını — her biri dış yüzeydeki farklı fotodioda VURUR, geçmez
    [4, 12, 22].forEach(function(idx) {
      var tp = fptsF[idx];
      if (!tp) return;
      // tgt = dış yüzey noktası (R = F_R)
      var tgt = tp.clone().normalize().multiplyScalar(F_R);
      var scanCurve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-3.5, F_CY + 2.9,  -4.1),
        new THREE.Vector3(
          (-3.5 + tgt.x) * 0.5,
          (F_CY + 2.9 + tgt.y + F_CY) * 0.5,
          (-4.1 + tgt.z) * 0.5
        ),
        new THREE.Vector3(tgt.x, tgt.y + F_CY, tgt.z)  // dış yüzey — SON NOKTA
      ]);
      gF.add(new THREE.Mesh(new THREE.TubeGeometry(scanCurve, 10, 0.015, 4, false), actMatF));
    });

    // ── 532nm Sinyal Lazeri (alttan) ──────────────────────────────────
    var sigMatF = new THREE.MeshStandardMaterial({
      color: 0x39ff14, transparent: true, opacity: 0.62,
      emissive: new THREE.Color(0x00aa00), emissiveIntensity: 1.35
    });
    // Lazer gövdesi (alt)
    var sigBodyF = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 1.1, 16), alumMat);
    sigBodyF.position.set(0, -5.2, 0);
    gF.add(sigBodyF);
    // Işın (ince, yeşil — taban açıklığından küre altına kadar kesintisiz ulaşır!)
    var sigRayF = new THREE.Mesh(new THREE.CylinderGeometry(0.030, 0.030, 3.05, 8), sigMatF);
    sigRayF.position.set(0, -3.15, 0);
    gF.add(sigRayF);
    // Işın halosu (geniş saçılım)
    var sigHaloF = new THREE.Mesh(new THREE.CylinderGeometry(0.060, 0.025, 2.55, 8), sigMatF);
    sigHaloF.position.set(0, -2.95, 0);
    gF.add(sigHaloF);
    // Küre üstünden CMOS dedektöre çıkan saçılma konisi
    var fOutConeMat = new THREE.MeshBasicMaterial({
      color: 0x00f5ff, transparent: true, opacity: 0.11,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
    });
    gF.add(_mesh(new THREE.CylinderGeometry(0.18, 0.85, 0.95, 16, 1, true), fOutConeMat, [0, F_CY + 2.55, 0]));
    gF.userData.anim = { sigMat: sigMatF, actMat: actMatF, photodMat: photodMatF, outCone: fOutConeMat };

    // ── CMOS Dedektör (gantry kirisine monte, küreye bakıyor) ─────────
    var cmosBodyF = new THREE.Mesh(
      new THREE.BoxGeometry(0.96, 0.072, 0.96),
      new THREE.MeshStandardMaterial({ color: 0x0a1a40 })
    );
    cmosBodyF.position.set(0, F_CY + 3.65, 0);
    gF.add(cmosBodyF);
    var cmosSensorF = new THREE.Mesh(
      new THREE.BoxGeometry(0.38, 0.052, 0.38),
      new THREE.MeshStandardMaterial({ color: 0x0d0d0d, emissive: new THREE.Color(0x001122), emissiveIntensity: 0.85 })
    );
    cmosSensorF.position.set(0, F_CY + 3.61, 0);
    gF.add(cmosSensorF);
    var barrelBodyF = new THREE.Mesh(
      new THREE.CylinderGeometry(0.17, 0.20, 0.55, 20),
      new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.85 })
    );
    barrelBodyF.position.set(0, F_CY + 3.36, 0);
    gF.add(barrelBodyF);

    // ── Ölçü Çizgileri ────────────────────────────────────────────────
    _ruler(gF,
      new THREE.Vector3(-F_R, F_CY, 0),
      new THREE.Vector3( F_R, F_CY, 0),
      0xffcc00);
    _ruler(gF,
      new THREE.Vector3(0, F_CY - F_R, 0),
      new THREE.Vector3(0, F_CY + F_R, 0),
      0x00f5ff);

    rootG.add(gF);

    // ══════════════════════════════════════════════════════════════════════
    //  MODEL G — ITO IZGARA MATRİS KÜRESİ  (x = -102)
    // ══════════════════════════════════════════════════════════════════════
    const gG = new THREE.Group();
    gG.name = 'proposalG';
    gG.position.set(-102, 0, 0);
    proposalGroups.push(gG);

    if (typeof window._ZG_build === 'function') {
      window._ZG_build(gG, {
        R: 2.05, LC: 1.90, CY: 0.35,
        NM: 16,  NP: 16,
        alumMat: alumMat,
        baseMat: baseMat
      });
    }

    rootG.add(gG);

    // ══════════════════════════════════════════════════════════════════════
    //  MODEL H — OPTİMUM MVP (SENTEZ)  •  x = -117
    //  İnce hücre ITO 16×16 + SLM yerine mSLA yazıcı LCD'si (giriş maskesi)
    //  Yatay optik sıra: Lazer → Genişletici → Polarizör → LCD → LC Hücre
    //                    → Analizör → CMOS.  Ayrıntı: RESEARCH.md §18
    // ══════════════════════════════════════════════════════════════════════
    const gH = new THREE.Group();
    gH.name = 'proposalH';
    gH.position.set(-117, 0, 0);
    proposalGroups.push(gH);

    (function () {
      const AXIS_Y = 0.35;                 // optik eksen yüksekliği
      const RAIL_Y = -1.39;                // ray üst yüzeyi

      // ── Taban + optik ray ────────────────────────────────────────────
      gH.add(_mesh(new THREE.BoxGeometry(12.6, 0.18, 4.8), baseMat, [-0.6, -1.62, 0]));
      gH.add(_mesh(new THREE.BoxGeometry(11.8, 0.14, 0.62), alumMat, [-0.6, -1.46, 0]));

      // Bileşen dikmesi: raydan bileşen altına
      function _post(x, bottomY) {
        const h = bottomY - RAIL_Y;
        if (h <= 0) return;
        gH.add(_mesh(new THREE.CylinderGeometry(0.05, 0.062, h, 10), alumMat, [x, RAIL_Y + h / 2, 0]));
      }

      // ── 532nm DPSS lazer modülü (sol) ────────────────────────────────
      const lasBodyH = _mesh(new THREE.CylinderGeometry(0.24, 0.24, 1.15, 20), alumMat, [-5.2, AXIS_Y, 0]);
      lasBodyH.rotation.z = Math.PI / 2;
      gH.add(lasBodyH);
      const lasApH = _mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.06, 12),
        new THREE.MeshStandardMaterial({ color: 0x39ff14, emissive: new THREE.Color(0x00cc00), emissiveIntensity: 1.6 }),
        [-4.60, AXIS_Y, 0]);
      lasApH.rotation.z = Math.PI / 2;
      gH.add(lasApH);
      _post(-5.2, AXIS_Y - 0.24);

      // ── Işın genişletici (2 lens) ────────────────────────────────────
      [[-4.30, 0.20], [-3.82, 0.32]].forEach(([lx, lr]) => {
        const lens = _mesh(new THREE.CylinderGeometry(lr, lr, 0.07, 20), topGlassMat, [lx, AXIS_Y, 0]);
        lens.rotation.z = Math.PI / 2;
        gH.add(lens);
        const hold = new THREE.Mesh(new THREE.TorusGeometry(lr + 0.07, 0.045, 10, 28), alumMat);
        hold.position.set(lx, AXIS_Y, 0);
        hold.rotation.y = Math.PI / 2;
        gH.add(hold);
        _post(lx, AXIS_Y - lr - 0.11);
      });

      // ── Polarizör (0°) ve Analizör (90°) ─────────────────────────────
      [[-3.10, 0x223a55], [1.75, 0x3a2255]].forEach(([px, tint]) => {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.05, 10, 30), alumMat);
        ring.position.set(px, AXIS_Y, 0);
        ring.rotation.y = Math.PI / 2;
        gH.add(ring);
        const film = _mesh(new THREE.CylinderGeometry(0.44, 0.44, 0.03, 24),
          new THREE.MeshStandardMaterial({
            color: tint, transparent: true, opacity: 0.55,
            emissive: new THREE.Color(tint), emissiveIntensity: 0.25
          }), [px, AXIS_Y, 0]);
        film.rotation.z = Math.PI / 2;
        gH.add(film);
        _post(px, AXIS_Y - 0.51);
      });

      // ── mSLA LCD panel — GİRİŞ MASKESİ (SLM yerine, ~40 USD) ─────────
      gH.add(_mesh(new THREE.BoxGeometry(0.10, 2.50, 3.70),
        new THREE.MeshStandardMaterial({ color: 0x101418, metalness: 0.4, roughness: 0.5 }),
        [-2.10, AXIS_Y, 0]));
      gH.add(_mesh(new THREE.BoxGeometry(0.05, 2.26, 3.46),
        new THREE.MeshStandardMaterial({
          color: 0x0a1226, emissive: new THREE.Color(0x1133aa), emissiveIntensity: 0.5,
          transparent: true, opacity: 0.92
        }), [-2.04, AXIS_Y, 0]));
      // Piksel dokusu izlenimi — seyrek ızgara çizgileri
      (function () {
        const v = [], hy = 1.05, hz = 1.65, n = 8;
        for (let i = 0; i <= n; i++) {
          const cy = -hy + (2 * hy * i) / n, cz = -hz + (2 * hz * i) / n;
          v.push(0, cy, -hz, 0, cy, hz);
          v.push(0, -hy, cz, 0, hy, cz);
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
        const grid = new THREE.LineSegments(geo,
          new THREE.LineBasicMaterial({ color: 0x2255cc, transparent: true, opacity: 0.30 }));
        grid.position.set(-2.01, AXIS_Y, 0);
        gH.add(grid);
      })();
      _post(-2.10, AXIS_Y - 1.25);

      // ── LC HÜCRE — ITO 16×16 ince hücre (dik sandviç) ────────────────
      gH.add(_mesh(new THREE.BoxGeometry(0.09, 2.05, 2.05), topGlassMat, [0.26, AXIS_Y, 0]));  // ön cam
      gH.add(_mesh(new THREE.BoxGeometry(0.09, 2.05, 2.05), glassMat,    [0.46, AXIS_Y, 0]));  // arka cam
      gH.add(_mesh(new THREE.BoxGeometry(0.035, 1.92, 1.92), lcMat,      [0.36, AXIS_Y, 0]));  // E7 katmanı
      // 16×16 ITO piksel ızgarası (parlayan cyan çizgiler)
      (function () {
        const v = [], half = 0.93, n = 16;
        for (let i = 0; i <= n; i++) {
          const c = -half + (2 * half * i) / n;
          v.push(0, c, -half, 0, c, half);
          v.push(0, -half, c, 0, half, c);
        }
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
        const grid = new THREE.LineSegments(geo,
          new THREE.LineBasicMaterial({ color: 0x44ddff, transparent: true, opacity: 0.55 }));
        grid.position.set(0.31, AXIS_Y, 0);
        gH.add(grid);
      })();
      // Alt kenar kontak pedleri (bakır)
      for (let i = 0; i < 8; i++) {
        gH.add(_mesh(new THREE.BoxGeometry(0.10, 0.05, 0.14), copperMat,
          [0.36, AXIS_Y - 1.08, -0.84 + i * 0.24]));
      }
      _post(0.36, AXIS_Y - 1.14);

      // ── CMOS kamera (sağ) ────────────────────────────────────────────
      const camTubeH = _mesh(new THREE.CylinderGeometry(0.20, 0.24, 0.72, 20),
        new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.85, roughness: 0.25 }),
        [3.30, AXIS_Y, 0]);
      camTubeH.rotation.z = Math.PI / 2;
      gH.add(camTubeH);
      gH.add(_mesh(new THREE.BoxGeometry(0.55, 0.92, 0.92),
        new THREE.MeshStandardMaterial({ color: 0x0a1a40 }), [3.95, AXIS_Y, 0]));
      gH.add(_mesh(new THREE.BoxGeometry(0.06, 0.40, 0.40),
        new THREE.MeshStandardMaterial({ color: 0x0d0d0d, emissive: new THREE.Color(0x001122), emissiveIntensity: 0.85 }),
        [3.66, AXIS_Y, 0]));
      _post(3.95, AXIS_Y - 0.46);

      // ── PCB'ler + şerit kablolar ─────────────────────────────────────
      function _ribbon(from, to) {
        const dir = new THREE.Vector3().subVectors(to, from);
        const len = dir.length();
        const rb = new THREE.Mesh(new THREE.BoxGeometry(0.55, len, 0.045), ribbonMat);
        rb.position.copy(from.clone().add(to).multiplyScalar(0.5));
        rb.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
        gH.add(rb);
      }
      // STM32 + AD5370 DAC kartı (hücre sürücüsü)
      gH.add(_mesh(new THREE.BoxGeometry(1.70, 0.08, 1.05),
        new THREE.MeshStandardMaterial({ color: 0x0a3a1a, roughness: 0.6 }), [0.36, -1.33, 1.55]));
      gH.add(_mesh(new THREE.BoxGeometry(0.30, 0.06, 0.30),
        new THREE.MeshStandardMaterial({ color: 0x151515 }), [0.02, -1.27, 1.40]));
      gH.add(_mesh(new THREE.BoxGeometry(0.36, 0.05, 0.36),
        new THREE.MeshStandardMaterial({ color: 0x101020 }), [0.78, -1.27, 1.66]));
      _ribbon(new THREE.Vector3(0.36, -0.70, 0.06), new THREE.Vector3(0.36, -1.28, 1.25));
      // HDMI/MIPI sürücü kartı (LCD girişi)
      gH.add(_mesh(new THREE.BoxGeometry(1.35, 0.08, 0.90),
        new THREE.MeshStandardMaterial({ color: 0x0a3a1a, roughness: 0.6 }), [-2.10, -1.33, 1.45]));
      gH.add(_mesh(new THREE.BoxGeometry(0.26, 0.06, 0.26),
        new THREE.MeshStandardMaterial({ color: 0x151515 }), [-2.35, -1.27, 1.35]));
      _ribbon(new THREE.Vector3(-2.10, -0.88, 0.06), new THREE.Vector3(-2.10, -1.28, 1.18));
      // Raspberry Pi 5 (eğitim döngüsü koordinatörü)
      gH.add(_mesh(new THREE.BoxGeometry(1.15, 0.08, 0.80),
        new THREE.MeshStandardMaterial({ color: 0x0a3a1a, roughness: 0.6 }), [3.55, -1.33, 1.65]));
      gH.add(_mesh(new THREE.BoxGeometry(0.30, 0.06, 0.30),
        new THREE.MeshStandardMaterial({ color: 0x151515 }), [3.55, -1.27, 1.55]));

      // ── Işın segmentleri ─────────────────────────────────────────────
      const beamRaw = new THREE.MeshStandardMaterial({
        color: 0x39ff14, transparent: true, opacity: 0.60,
        emissive: new THREE.Color(0x00aa00), emissiveIntensity: 1.35
      });
      const beamMod = new THREE.MeshStandardMaterial({
        color: 0x39ff14, transparent: true, opacity: 0.38,
        emissive: new THREE.Color(0x008800), emissiveIntensity: 0.95
      });
      const beamOut = new THREE.MeshStandardMaterial({
        color: 0x00f5ff, transparent: true, opacity: 0.48,
        emissive: new THREE.Color(0x0088aa), emissiveIntensity: 1.1
      });
      // Lazer → LCD (ham, parlak yeşil)
      const b1 = _mesh(new THREE.CylinderGeometry(0.030, 0.030, 2.44, 8), beamRaw, [-3.37, AXIS_Y, 0]);
      b1.rotation.z = Math.PI / 2;
      gH.add(b1);
      // LCD → hücre (genlik-modüleli, soluk yeşil)
      const b2 = _mesh(new THREE.CylinderGeometry(0.028, 0.028, 2.30, 8), beamMod, [-0.90, AXIS_Y, 0]);
      b2.rotation.z = Math.PI / 2;
      gH.add(b2);
      // Hücre → analizör → kamera (faz→yoğunluk sonrası, cyan)
      const b3 = _mesh(new THREE.CylinderGeometry(0.026, 0.026, 2.86, 8), beamOut, [1.90, AXIS_Y, 0]);
      b3.rotation.z = Math.PI / 2;
      gH.add(b3);

      // Lazer ateşlendiğinde optik eksen boyunca akan canlı foton paketi (pulse)
      const pulseMat = new THREE.MeshBasicMaterial({
        color: 0x66ffaa, transparent: true, opacity: 0.0,
        blending: THREE.AdditiveBlending, depthWrite: false
      });
      const photonPulse = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), pulseMat);
      photonPulse.scale.set(2.4, 0.85, 0.85);
      photonPulse.position.set(-4.5, AXIS_Y, 0);
      gH.add(photonPulse);

      gH.userData.anim = {
        beamRaw: beamRaw,
        beamMod: beamMod,
        beamOut: beamOut,
        pulse: photonPulse,
        pulseMat: pulseMat,
        axisY: AXIS_Y
      };

      // ── Ölçü çizgisi (optik yol) ─────────────────────────────────────
      _ruler(gH,
        new THREE.Vector3(-5.20, -0.62, 2.25),
        new THREE.Vector3( 3.95, -0.62, 2.25),
        0xffcc00);
    })();

    rootG.add(gH);
    scene.add(rootG);
  }; // _ZP_build sonu

  // ═══════════════════════════════════════════════════════════════════════
  //  SENARYO HUD METİNLERİ (Üst şerit & köşe göstergeleri dinamik günceller)
  // ═══════════════════════════════════════════════════════════════════════
  const STAGE_META = [
    {
      code: 'ANA SİSTEM · KÜRESEL KONSEPT',
      flow: '532nm Lazer → LCOS SLM → Kondenser → E7 Küre (6 Eksen ITO + 405nm Pump) → CMOS',
      tl: ['TARGET: LC-FLASK-01', 'MODE: 3D OPTOFLUIDIC', 'REFRACTION: n=1.58'],
      tr: ['Ø 250ml BOROSILICATE', 'PUMP: 405nm VIOLET', 'CHANNELS: 6-AXIS ITO'],
    },
    {
      code: 'ÖNERİ A · FİBONACCİ DIŞ KAFES (32 ELEKTROT)',
      flow: '532nm Giriş → Küre Dışı 32 ITO Çubuk (Fibonacci Dizilim) → Elektrik Alan → Speckle Çıkış',
      tl: ['TARGET: CAGE-ARRAY-A', 'ELECTRODES: 32 FIBONACCI', 'GAP: AIR + GLASS'],
      tr: ['Ø 250ml BOROSILICATE', 'DRIVE: 8–15V HIGH-V', 'EFFICIENCY: ~40%'],
    },
    {
      code: 'ÖNERİ B · DÜZLEM PARALEL PLAKA (256 PİKSEL)',
      flow: 'Düzlem Dalga → Alt ITO 16×16 Matris → İnce E7 LC Katmanı → Üst Referans Cam → Dedektör',
      tl: ['TARGET: FLAT-CELL-B', 'MATRIX: 16×16 (256 PX)', 'TYPE: PLANAR ITO'],
      tr: ['SUBSTRATE: ITO GLASS', 'SCATTERING: LOW', 'PHASE: Δφ(V) MOD'],
    },
    {
      code: 'ÖNERİ C · YARI-KÜRE HİBRİT KASE (64 PİKSEL)',
      flow: 'Giriş Işını → 8×8 Alt Ped Matrisi → Yarı-Küre E7 LC Hacmi → Düz Üst ITO Cam → Dedektör',
      tl: ['TARGET: BOWL-HYBRID-C', 'MATRIX: 8×8 (64 PX)', 'FRAME: FLEX PCB'],
      tr: ['HYBRID 3D + PIXEL', 'TOP REF: FLAT ITO', 'OPTICAL CHAOS: ON'],
    },
    {
      code: 'ÖNERİ D · TEK PLAKA 7-KATMAN MÜHENDİSLİK KESİTİ',
      flow: '532nm Alt Lazer → Polarizör (0°) → Cam/PI/ITO → 7μm E7 (Freedericksz) → Analizör (90°) → CMOS',
      tl: ['TARGET: CELL-STACK-D', 'GAP: 7μm SiO₂ SPACER', 'LC: MERCK E7 (Δn=0.225)'],
      tr: ['70×70×1.1mm BOROFLOAT', 'ALIGNMENT: RUBBED PI', 'COST: ~300 USD'],
    },
    {
      code: 'ÖNERİ E · ÇOK KATMANLI DİFRAKTİF AĞ (3× D²NN)',
      flow: '532nm Lazer → SLM → LC Katman 1 → Fresnel (30mm) → Katman 2 → Fresnel → Katman 3 → CMOS',
      tl: ['TARGET: D2NN-3LAYER-E', 'WEIGHTS: 3×256 = 768', 'FRESNEL Z: 30mm'],
      tr: ['CASCADED DIFFRACTION', 'WAVELENGTH: 532nm', 'COST: ~700 USD'],
    },
    {
      code: 'ÖNERİ F · KABLOSUZ FOTODİOD ADRESLEMELİ KÜRE',
      flow: '805nm IR Galvo Tarama → 32 Dış Si Fotodiod → Cam Via → İç ITO Yama | Alttan 532nm Sinyal → CMOS',
      tl: ['TARGET: PHOTODIODE-F', 'ADDRESS: 805nm IR GALVO', 'HOLD CAP: 10nF (500ms)'],
      tr: ['WIRELESS OPTICAL DRIVE', '32× Si PHOTODIODE', 'SIGNAL: 532nm BOTTOM'],
    },
    {
      code: 'ÖNERİ G · KÜRESEL ITO IZGARA MATRİSİ (16×16)',
      flow: 'Sağdan 532nm Lazer → SLM → 16 Boylam × 16 Enlem ITO Küre → Kutup Ring/AD5370 → Üst CMOS',
      tl: ['TARGET: ITO-SPHERE-G', 'GRID: 16×16 MERIDIAN/LAT', 'DAC: 32-LINE MATRIX'],
      tr: ['GANTRY MOUNT 6061-T6', 'UPDATE: ~40μs SPI', 'PSU: ±12V DUAL'],
    },
    {
      code: 'MODEL H · ORTAK-YOL DİJİTAL İKİZ MİMARİSİ',
      flow: '532nm DPSS → Genişletici → mSLA 2K LCD (Giriş) → Z₁ Kırınım → Aktif LC/2.LCD → Analizör → CMOS |E|²',
      tl: ['TARGET: MODEL-H (v0.4)', 'COMMON-PATH ASM OPTICS', 'TRAINING: PAT + HYBRID'],
      tr: ['INPUT: mSLA 2K (~40$)', 'MNIST 3-SEED: 94.37%', 'CPU SIM: 0.78ms'],
    },
  ];

  function _updateStageHUD(n) {
    const m = STAGE_META[n] || STAGE_META[0];
    const bannerTitle = document.getElementById('stage-banner-title');
    const bannerFlow  = document.getElementById('stage-banner-flow');
    if (bannerTitle) bannerTitle.textContent = m.code;
    if (bannerFlow)  bannerFlow.textContent  = m.flow;

    const tl = document.querySelector('.scene-hud.top-left');
    const tr = document.querySelector('.scene-hud.top-right');
    if (tl) tl.innerHTML = m.tl.map(s => `<div>${s}</div>`).join('');
    if (tr) tr.innerHTML = m.tr.map(s => `<div>${s}</div>`).join('');
  }

  // ═══════════════════════════════════════════════════════════════════════
  //  AKICI & İPTAL EDİLEBİLİR KAMERA UÇUŞU
  // ═══════════════════════════════════════════════════════════════════════
  window._ZP_fly = function (camera, controls, toPos, toLook, duration) {
    if (_flyAnimId !== null) {
      cancelAnimationFrame(_flyAnimId);
      _flyAnimId = null;
    }
    const fromPos    = camera.position.clone();
    const fromTarget = controls ? controls.target.clone() : new THREE.Vector3(0, 0.5, 0);
    const toPosV     = new THREE.Vector3(...toPos);
    const toLookV    = new THREE.Vector3(...toLook);
    const t0 = performance.now();

    function easeInOutQuart(x) {
      return x < 0.5 ? 8 * x * x * x * x : 1 - Math.pow(-2 * x + 2, 4) / 2;
    }

    (function step() {
      const t = Math.min((performance.now() - t0) / duration, 1);
      const e = easeInOutQuart(t);
      camera.position.lerpVectors(fromPos, toPosV, e);
      if (controls) {
        controls.target.lerpVectors(fromTarget, toLookV, e);
        controls.update();
      }
      if (t < 1) {
        _flyAnimId = requestAnimationFrame(step);
      } else {
        _flyAnimId = null;
      }
    })();
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  ÖNERİ SEÇİCİ
  // ═══════════════════════════════════════════════════════════════════════
  window._ZP_set = function (n, camera, controls, proposalGroups) {
    const camData = [
      { pos: [3,      3.5,  9.2], look: [0,      0.4,  0] },   // 0: Ana Sistem
      { pos: [-18,    4.4,  9.2], look: [-18,    0.35, 0] },   // 1: Öneri A
      { pos: [-30,    4.6,  8.8], look: [-30,    0.35, 0] },   // 2: Öneri B
      { pos: [-42,    4.6,  8.8], look: [-42,    0.85, 0] },   // 3: Öneri C
      { pos: [-53.5,  3.2, 10.6], look: [-57,   -0.4,  0] },   // 4: Öneri D
      { pos: [-72,    3.8, 13.8], look: [-72,    0.35, 0] },   // 5: Öneri E
      { pos: [-84.5,  4.4, 11.6], look: [-87,    0.35, 0] },   // 6: Öneri F
      { pos: [-95.0,  5.4,  9.4], look: [-101.2, 0.35, 0] },   // 7: Öneri G
      { pos: [-117.4, 3.3, 11.2], look: [-117.4, 0.0,  0] },   // 8: Öneri H
    ];
    const d = camData[n] || camData[0];
    window._ZP_fly(camera, controls, d.pos, d.look, 1250);

    // Sahne takip ışığını aktif senaryoya taşı
    if (_stageLight) {
      _stageLight.position.set(d.look[0] + 2.5, 6.2, 6.5);
      _stageLight.intensity = (n === 0) ? 0.0 : 1.65;
    }

    _updateStageHUD(n);

    document.querySelectorAll('.prop-btn').forEach((b, i) => {
      b.classList.toggle('active', i === n);
    });
    document.querySelectorAll('.prop-info-card').forEach((c, i) => {
      c.style.display = (i === n - 1) ? 'block' : 'none';
    });
    const pi = document.getElementById('proposal-info');
    if (pi) {
      pi.style.opacity = n === 0 ? '0' : '1';
      pi.style.pointerEvents = n === 0 ? 'none' : 'auto';
    }
  };

  // ═══════════════════════════════════════════════════════════════════════
  //  SENARYO ATEŞLEME & SÜREKLİ ANİMASYON MOTORU (A–H)
  // ═══════════════════════════════════════════════════════════════════════
  window._ZP_fire = function () {
    _fireStart = performance.now();
  };

  window._ZP_tick = function (t, isProc, currentProp, proposalGroups) {
    if (currentProp <= 0 || !proposalGroups || !proposalGroups[currentProp - 1]) return;
    const grp = proposalGroups[currentProp - 1];
    const an  = grp.userData && grp.userData.anim;
    if (!an) return;

    // Ateşleme ilerleme oranı u ∈ [0, 1] (~3.4 saniye)
    let u = -1;
    if (_fireStart > 0) {
      u = (performance.now() - _fireStart) / 3400;
      if (u > 1.0) { _fireStart = -1; u = -1; }
    }
    const env = u >= 0 ? Math.sin(Math.min(1, u) * Math.PI) : 0; // yumuşak zarf 0→1→0

    if (currentProp === 1) { // A: Fibonacci Dış Kafes
      an.beamMat.opacity = 0.18 + env * 0.65;
      an.tipMat.emissiveIntensity = 0.8 + Math.sin(t * 2.5) * 0.15 + env * 1.6;
    } else if (currentProp === 2) { // B: Paralel Plaka
      an.beamMat.opacity = 0.18 + env * 0.65;
      an.dotMat.emissiveIntensity = 0.9 + Math.sin(t * 2.5) * 0.15 + env * 1.5;
      an.lcMat.emissiveIntensity  = 0.18 + env * 0.75;
    } else if (currentProp === 3) { // C: Yarı-Küre Kase
      an.beamMat.opacity = 0.18 + env * 0.65;
      an.dotMat.emissiveIntensity = 1.0 + Math.sin(t * 2.5) * 0.2 + env * 1.5;
      an.lcMat.emissiveIntensity  = 0.20 + env * 0.75;
    } else if (currentProp === 4) { // D: Tek Plaka Detaylı — Freedericksz Molekül Dikleşmesi!
      an.beamMatD.opacity   = 0.40 + env * 0.50;
      an.beamTopMat.opacity = 0.42 + env * 0.50;
      an.eFieldMat.opacity  = 0.40 + Math.sin(t * 3.0) * 0.10 + env * 0.50;
      an.lcMat.emissiveIntensity = 0.65 + env * 0.95;
      // Voltaj darbesinde LC molekülleri elektrik alan yönüne (rotZ → 0 dikey) döner!
      an.molGroups.forEach((mg, idx) => {
        const idleWobble = Math.sin(t * 1.6 + idx * 0.4) * 0.03;
        mg.rotation.z = mg.userData.baseRotZ * (1.0 - 0.78 * env) + idleWobble;
      });
    } else if (currentProp === 5) { // E: 3 Katmanlı D²NN
      an.beamIn.opacity  = 0.42 + env * 0.50;
      an.beamOut.opacity = 0.42 + env * 0.50;
      an.cones.forEach((cm, idx) => {
        const wave = u >= 0 ? Math.max(0, Math.sin((u * 1.4 - idx * 0.22) * Math.PI)) : 0;
        cm.opacity = 0.06 + wave * 0.24;
      });
    } else if (currentProp === 6) { // F: Fotodiod Küre
      an.sigMat.emissiveIntensity    = 1.25 + env * 1.5;
      an.actMat.emissiveIntensity    = 1.25 + Math.sin(t * 8.0) * 0.25 + env * 1.2;
      an.photodMat.emissiveIntensity = 0.65 + env * 1.4;
      an.outCone.opacity             = 0.09 + env * 0.30;
    } else if (currentProp === 7) { // G: ITO Izgara Küre
      an.sigEmit.emissiveIntensity   = 1.40 + env * 1.6;
      an.activeMat.emissiveIntensity = 1.60 + Math.sin(t * 3.0) * 0.25 + env * 1.6;
      an.upConeMat.opacity           = 0.09 + env * 0.32;
      an.spkMeshes.forEach((sm, i) => {
        const s = 1.0 + Math.sin(t * 4.0 + i) * 0.12 + env * 0.45;
        sm.scale.setScalar(s);
      });
    } else if (currentProp === 8) { // H: Optimum MVP ★ — Kademeli Dalga & Foton Paketi Akışı!
      const s1 = u >= 0 && u < 0.38 ? Math.sin((u / 0.38) * Math.PI) : 0;
      const s2 = u >= 0.25 && u < 0.70 ? Math.sin(((u - 0.25) / 0.45) * Math.PI) : 0;
      const s3 = u >= 0.55 ? Math.sin(((u - 0.55) / 0.45) * Math.PI) : 0;
      an.beamRaw.opacity = 0.55 + s1 * 0.42;
      an.beamMod.opacity = 0.36 + s2 * 0.52;
      an.beamOut.opacity = 0.45 + s3 * 0.52;

      if (u >= 0) {
        const px = -4.55 + u * 8.15; // Lazer (-4.55) → LCD (-2.1) → Hücre (+0.36) → CMOS (+3.6)
        an.pulse.position.set(px, an.axisY, 0);
        an.pulseMat.opacity = 0.90 * Math.sin(u * Math.PI);
        // Hücreden sonra renk yeşilden (532nm) camgöbeğine (analizör çıkışı) döner
        an.pulseMat.color.setHex(px < 0.36 ? 0x39ff14 : 0x00f5ff);
      } else {
        an.pulseMat.opacity = 0.0;
      }
    }
  };

})();
