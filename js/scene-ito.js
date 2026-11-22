/* ═══════════════════════════════════════════════════════════════════════════
   scene-ito.js  —  Zerre ITO Izgara Matrisi Görselleştirici  (v2)
   Exposes: window._ZG_build(group, opts)
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ── Yardımcılar ─────────────────────────────────────────────────────────
  function _m(geo, mat, px, py, pz) {
    var mesh = new THREE.Mesh(geo, mat);
    if (px !== undefined) mesh.position.set(px, py, pz);
    return mesh;
  }

  function _wire(p0, p1, r, mat) {
    var dir = new THREE.Vector3().subVectors(p1, p0);
    var len = dir.length();
    if (len < 0.001) return new THREE.Object3D();
    var mid = new THREE.Vector3().addVectors(p0, p1).multiplyScalar(0.5);
    var cyl = _m(new THREE.CylinderGeometry(r, r, len, 6), mat, mid.x, mid.y, mid.z);
    cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    return cyl;
  }

  // Meridian yayı: küre yüzeyinde kuzey → güney
  function _meridianArc(R, tubeR, mat, rotY) {
    var pts = [];
    for (var i = 0; i <= 36; i++) {
      var a = -Math.PI / 2 + Math.PI * i / 36;
      pts.push(new THREE.Vector3(R * Math.cos(a), R * Math.sin(a), 0));
    }
    var mesh = new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 36, tubeR, 4, false),
      mat
    );
    mesh.rotation.y = rotY;
    return mesh;
  }

  // Enlem halkası
  function _latRing(R, lat, tubeR, CY, mat) {
    var ry = R * Math.sin(lat);
    var rr = R * Math.cos(lat);
    if (rr < tubeR * 3) return null;
    var ring = new THREE.Mesh(new THREE.TorusGeometry(rr, tubeR, 5, 64), mat);
    ring.position.set(0, CY + ry, 0);
    ring.rotation.x = Math.PI / 2;
    return ring;
  }

  // ── Ana builder ─────────────────────────────────────────────────────────
  window._ZG_build = function (grp, opts) {
    var R  = (opts && opts.R)  || 2.05;
    var LC = (opts && opts.LC) || 1.90;
    var CY = (opts && opts.CY) || 0.35;
    var NM = (opts && opts.NM) || 16;
    var NP = (opts && opts.NP) || 16;

    var alumMat = (opts && opts.alumMat) ||
      new THREE.MeshStandardMaterial({ color: 0xb0c4d8, metalness: 0.88, roughness: 0.15 });
    var baseMat = (opts && opts.baseMat) ||
      new THREE.MeshStandardMaterial({ color: 0x1a1a2e, roughness: 0.7 });

    // ── Malzemeler ──────────────────────────────────────────────────────
    var glassMat = new THREE.MeshStandardMaterial({
      color: 0xaad4ee, transparent: true, opacity: 0.14,
      depthWrite: false, side: THREE.DoubleSide
    });
    var lcGndMat = new THREE.MeshStandardMaterial({
      color: 0x00bb44, emissive: new THREE.Color(0x004422), emissiveIntensity: 0.35,
      transparent: true, opacity: 0.55, depthWrite: false, side: THREE.BackSide
    });
    var lcFillMat = new THREE.MeshStandardMaterial({
      color: 0x0044aa, emissive: new THREE.Color(0x002266), emissiveIntensity: 0.40,
      transparent: true, opacity: 0.65, depthWrite: false, side: THREE.BackSide
    });
    var itoYMat = new THREE.MeshStandardMaterial({
      color: 0x00ffcc, emissive: new THREE.Color(0x00ddaa), emissiveIntensity: 0.80,
      transparent: true, opacity: 0.65
    });
    var itoXMat = new THREE.MeshStandardMaterial({
      color: 0xff8822, emissive: new THREE.Color(0xdd5500), emissiveIntensity: 0.70,
      transparent: true, opacity: 0.60
    });
    var activeMat = new THREE.MeshStandardMaterial({
      color: 0xffff33, emissive: new THREE.Color(0xffee00), emissiveIntensity: 1.80,
      transparent: true, opacity: 0.95
    });
    var pcbMat      = new THREE.MeshStandardMaterial({ color: 0x1a4020, roughness: 0.65 });
    var chipMat     = new THREE.MeshStandardMaterial({ color: 0x080808, metalness: 0.25 });
    var wireMat     = new THREE.MeshStandardMaterial({ color: 0x445566, metalness: 0.40 });
    var wirePlusMat = new THREE.MeshStandardMaterial({ color: 0xcc2200, metalness: 0.30 });
    var wireGndMat  = new THREE.MeshStandardMaterial({ color: 0x111111, metalness: 0.20 });
    var psuBodyMat  = new THREE.MeshStandardMaterial({ color: 0x1e1e1e, metalness: 0.35, roughness: 0.75 });
    var termMat     = new THREE.MeshStandardMaterial({ color: 0xccaa00, metalness: 0.85, roughness: 0.12 });
    var sigEmit     = new THREE.MeshStandardMaterial({
      color: 0x39ff14, emissive: new THREE.Color(0x00bb00), emissiveIntensity: 1.60,
      transparent: true, opacity: 0.72
    });
    var slmBodyMat  = new THREE.MeshStandardMaterial({ color: 0x222244, metalness: 0.45, roughness: 0.55 });
    var slmPanelMat = new THREE.MeshStandardMaterial({
      color: 0x0033cc, emissive: new THREE.Color(0x002299), emissiveIntensity: 0.55,
      transparent: true, opacity: 0.82
    });
    var slmPixMat   = new THREE.MeshStandardMaterial({
      color: 0x55bbff, emissive: new THREE.Color(0x3399ff), emissiveIntensity: 1.05,
      transparent: true, opacity: 0.92
    });
    var prismMat    = new THREE.MeshStandardMaterial({
      color: 0xddeeff, metalness: 0.95, roughness: 0.02,
      transparent: true, opacity: 0.50
    });
    var spkMat      = new THREE.MeshStandardMaterial({
      color: 0xaaffaa, emissive: new THREE.Color(0x55ff55), emissiveIntensity: 1.25,
      transparent: true, opacity: 0.58
    });
    var cmosMat     = new THREE.MeshStandardMaterial({ color: 0x0a1840 });
    var sensorMat   = new THREE.MeshStandardMaterial({
      color: 0x080808, emissive: new THREE.Color(0x001122), emissiveIntensity: 0.85
    });
    var lensMat     = new THREE.MeshStandardMaterial({ color: 0x060606, metalness: 0.88 });

    // ── Taban + Gantry ───────────────────────────────────────────────────
    grp.add(_m(new THREE.BoxGeometry(16, 0.28, 10), baseMat, 0, -2.90, 0));
    grp.add(_m(new THREE.BoxGeometry(0.22, 6.40, 0.22), alumMat, -4.8, CY, 0));
    grp.add(_m(new THREE.BoxGeometry(0.22, 6.40, 0.22), alumMat,  4.8, CY, 0));
    grp.add(_m(new THREE.BoxGeometry(10.0, 0.22, 0.22), alumMat, 0, CY + 3.20, 0));

    // ── LC Sıvısı ────────────────────────────────────────────────────────
    // Alt yarım küre: homojen ITO GND kaplama (yeşil)
    grp.add(_m(
      new THREE.SphereGeometry(LC, 40, 24, 0, Math.PI*2, Math.PI/2, Math.PI/2),
      lcGndMat, 0, CY, 0
    ));
    // Üst yarım küre: E7 nematik LC sıvısı (mavi)
    grp.add(_m(
      new THREE.SphereGeometry(LC, 40, 24, 0, Math.PI*2, 0, Math.PI/2),
      lcFillMat, 0, CY, 0
    ));
    // Cam dış küre (şeffaf)
    grp.add(_m(new THREE.SphereGeometry(R, 48, 32), glassMat, 0, CY, 0));

    // ── ITO Izgara Şeritleri ─────────────────────────────────────────────
    var R_ito = R + 0.028;
    var tR    = 0.019;
    var activeMer = [2, 6, 11];
    var activeLat = [4, 8, 12];

    for (var i = 0; i < NM; i++) {
      var mMat = (activeMer.indexOf(i) >= 0) ? activeMat : itoYMat;
      var arc = _meridianArc(R_ito, tR, mMat, i * Math.PI / NM);
      arc.position.set(0, CY, 0);
      grp.add(arc);
    }
    for (var k = 0; k < NP; k++) {
      var lat = -Math.PI * 0.42 + Math.PI * 0.84 * k / (NP - 1);
      var lMat = (activeLat.indexOf(k) >= 0) ? activeMat : itoXMat;
      var ring = _latRing(R_ito, lat, tR, CY, lMat);
      if (ring) grp.add(ring);
    }

    // ── ITO Besleme Telleri (kutup ring terminalleri → PCB) ──────────────
    // Kuzey kutup ring terminali (Y–boylam elektrodu çıkış noktası)
    var tN = _m(new THREE.TorusGeometry(0.28, 0.038, 8, 32), termMat, 0, CY + R_ito + 0.06, 0);
    tN.rotation.x = Math.PI / 2; grp.add(tN);
    // Güney kutup ring terminali (X–enlem elektrodu / GND)
    var tS = _m(new THREE.TorusGeometry(0.28, 0.038, 8, 32), termMat, 0, CY - R_ito - 0.06, 0);
    tS.rotation.x = Math.PI / 2; grp.add(tS);

    // Kuzey terminal → sağ gantry kolu → PCB (teal, Y-elektrot)
    var kuzeyY = CY + R_ito + 0.06;
    grp.add(_wire(new THREE.Vector3(0,   kuzeyY, 0), new THREE.Vector3(4.5, kuzeyY, 0),  0.038, itoYMat));
    grp.add(_wire(new THREE.Vector3(4.5, kuzeyY, 0), new THREE.Vector3(4.5, -1.40,  0),  0.038, itoYMat));
    // Güney terminal → sol gantry kolu → PCB (turuncu, X-elektrot)
    var guneyY = CY - R_ito - 0.06;
    grp.add(_wire(new THREE.Vector3(0,    guneyY, 0), new THREE.Vector3(-4.5, guneyY, 0), 0.038, itoXMat));
    grp.add(_wire(new THREE.Vector3(-4.5, guneyY, 0), new THREE.Vector3(-4.5, -1.40,  0), 0.038, itoXMat));

    // ── PCB Kontrol Kartı (STM32 + AD5370 DAC) ──────────────────────────
    var pcbX = 2.20, pcbY = -1.40, pcbZ = 0;
    grp.add(_m(new THREE.BoxGeometry(4.20, 0.09, 2.80), pcbMat,  pcbX, pcbY, pcbZ));
    grp.add(_m(new THREE.BoxGeometry(0.58, 0.12, 0.58), chipMat, pcbX + 0.8,  pcbY + 0.11,  pcbZ + 0.4));
    grp.add(_m(new THREE.BoxGeometry(0.72, 0.12, 0.72), chipMat, pcbX - 0.5,  pcbY + 0.11,  pcbZ - 0.3));
    for (var p = 0; p < 9; p++) {
      grp.add(_m(new THREE.BoxGeometry(0.06, 0.18, 0.06), alumMat,
        pcbX + 2.05, pcbY + 0.14, pcbZ - 1.10 + p * 0.27));
    }
    // Gantry kolları → PCB veri kabloları
    grp.add(_wire(new THREE.Vector3(4.5,  -1.40, 0), new THREE.Vector3(pcbX + 2.10, pcbY, 0), 0.038, wireMat));
    grp.add(_wire(new THREE.Vector3(-4.5, -1.40, 0), new THREE.Vector3(pcbX - 2.10, pcbY, 0), 0.038, wireMat));

    // ── Güç Kaynağı (±12V) ────────────────────────────────────────────────
    var psuX = pcbX, psuY = pcbY - 0.55, psuZ = -2.4;
    grp.add(_m(new THREE.BoxGeometry(3.60, 1.00, 1.60), psuBodyMat, psuX, psuY, psuZ));
    grp.add(_m(new THREE.BoxGeometry(1.10, 0.44, 0.05),
      new THREE.MeshStandardMaterial({ color: 0x001a33, emissive: new THREE.Color(0x0077ff), emissiveIntensity: 0.85 }),
      psuX - 0.5, psuY + 0.10, psuZ - 0.84));
    grp.add(_m(new THREE.SphereGeometry(0.065, 8, 6),
      new THREE.MeshStandardMaterial({ color: 0x00ff44, emissive: new THREE.Color(0x00ff44), emissiveIntensity: 2.0 }),
      psuX + 1.50, psuY + 0.25, psuZ - 0.84));
    grp.add(_wire(
      new THREE.Vector3(psuX, psuY + 0.50, psuZ + 0.40),
      new THREE.Vector3(psuX, pcbY + 0.05, psuZ + 0.40), 0.034, wirePlusMat));
    grp.add(_wire(
      new THREE.Vector3(psuX + 0.22, psuY + 0.50, psuZ + 0.40),
      new THREE.Vector3(psuX + 0.22, pcbY + 0.05, psuZ + 0.40), 0.030, wireGndMat));

    // ── 532nm Sinyal Lazeri (X+ sağ cephe, yatay — SLM'e bakıyor) ─────────
    // Kamera 45° sağ-önden: lazer SAĞDA yatay, CMOS YUKARDA dikey görünür
    var LX = 6.80, LY = CY;       // X+ sağ taraf, küre eksen yüksekliği
    var standH = LY + 2.90;       // tabandan (Y=-2.90) lazer yüksekliğine
    // Stand: tabandan lazer gövdesine
    grp.add(_m(new THREE.BoxGeometry(0.20, standH, 0.20), alumMat,
      LX, -2.90 + standH * 0.5, 0));
    // Lazer gövdesi: X ekseni boyunca yatay (rotation.z = π/2)
    var lazerBody = _m(new THREE.CylinderGeometry(0.17, 0.19, 1.40, 16), alumMat, LX, LY, 0);
    lazerBody.rotation.z = Math.PI / 2; grp.add(lazerBody);
    // X- yüzü (küreye bakan taraf) mercek halkası
    var lazerLens = _m(new THREE.TorusGeometry(0.17, 0.030, 8, 32), alumMat, LX - 0.72, LY, 0);
    lazerLens.rotation.y = Math.PI / 2; grp.add(lazerLens);
    // Tetik LED (kırmızı), X+ arka yüz
    grp.add(_m(new THREE.SphereGeometry(0.06, 8, 6),
      new THREE.MeshStandardMaterial({ color: 0xff2200, emissive: new THREE.Color(0xff0000), emissiveIntensity: 2.4 }),
      LX + 0.52, LY + 0.20, 0.22));

    // ── SLM Modülatör (X=4.60, lazer ile küre arası) ──────────────────────
    var slmX = 4.60, slmY = LY, slmZ = 0;
    // Gövde: X yönünde ince (0.30), önden görünür yükseklik/genişlik
    grp.add(_m(new THREE.BoxGeometry(0.30, 1.40, 1.80), slmBodyMat,  slmX, slmY, slmZ));
    // Aktif panel (X+ giriş yüzü = lazere bakıyor)
    grp.add(_m(new THREE.BoxGeometry(0.04, 1.00, 1.38), slmPanelMat, slmX + 0.17, slmY, slmZ));
    // Piksel ızgarası (2×2)
    [[-0.24, -0.38], [-0.24, 0.38], [0.24, -0.38], [0.24, 0.38]].forEach(function(d) {
      grp.add(_m(new THREE.BoxGeometry(0.03, 0.30, 0.30), slmPixMat,
        slmX + 0.19, slmY + d[0], slmZ + d[1]));
    });
    // SLM → PCB HDMI kablosu (SLM alt yüzünden PCB'ye)
    grp.add(_wire(
      new THREE.Vector3(slmX, slmY - 0.72, slmZ),
      new THREE.Vector3(slmX, pcbY + 0.05, slmZ), 0.030, wireMat));
    grp.add(_wire(
      new THREE.Vector3(slmX, pcbY + 0.05, slmZ),
      new THREE.Vector3(pcbX + 2.10, pcbY + 0.05, slmZ), 0.030, wireMat));

    // ── Işın Yolu: Lazer → SLM → Küre (X- yönünde yatay, kalın çizgi) ────
    // Lazer çıkış → SLM giriş yüzü
    var beamIn1 = _wire(
      new THREE.Vector3(LX - 0.72, LY, 0),
      new THREE.Vector3(slmX + 0.17, LY, 0), 0.028, sigEmit);
    grp.add(beamIn1);
    // SLM çıkış → küre yüzeyi (X-)
    var beamIn2 = _wire(
      new THREE.Vector3(slmX - 0.17, LY, 0),
      new THREE.Vector3(R_ito, LY, 0), 0.032, sigEmit);
    grp.add(beamIn2);
    // Küre → üst CMOS saçılan koni (hafif parıltı)
    var upConeMat = new THREE.MeshBasicMaterial({
      color: 0x00f5ff, transparent: true, opacity: 0.10,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
    });
    var upCone = _m(new THREE.CylinderGeometry(0.18, 0.95, 1.05, 16, 1, true), upConeMat, 0, CY + 2.35, 0);
    grp.add(upCone);

    // Küre içi speckle (saçılma noktaları)
    var spkMeshes = [];
    [[ 0.55, 0.08,  0.30], [-0.25, 0.25,  0.10], [ 0.20, -0.18, -0.30],
     [-0.40, -0.10, 0.25], [ 0.30, 0.40, -0.15]].forEach(function(d) {
      var sm = _m(new THREE.SphereGeometry(0.052, 7, 5), spkMat, d[0], CY + d[1], d[2]);
      grp.add(sm);
      spkMeshes.push(sm);
    });

    // Animasyon referanslarını dışa aç
    grp.userData.anim = {
      sigEmit: sigEmit,
      activeMat: activeMat,
      slmPixMat: slmPixMat,
      spkMat: spkMat,
      upConeMat: upConeMat,
      spkMeshes: spkMeshes
    };

    // ── CMOS Kamera (üst kiriş ortasında, küreye bakıyor) ─────────────────
    grp.add(_m(new THREE.BoxGeometry(0.95, 0.07, 0.95), cmosMat,   0, CY + 3.28, 0));
    grp.add(_m(new THREE.BoxGeometry(0.38, 0.05, 0.38), sensorMat, 0, CY + 3.24, 0));
    grp.add(_m(new THREE.CylinderGeometry(0.17, 0.20, 0.55, 20), lensMat, 0, CY + 3.01, 0));
    grp.add(_m(new THREE.CylinderGeometry(0.14, 0.14, 0.04, 20),
      new THREE.MeshStandardMaterial({ color: 0x2255cc, transparent: true, opacity: 0.40, roughness: 0.0 }),
      0, CY + 2.74, 0));
    grp.add(_wire(new THREE.Vector3(0.48, CY + 3.28, 0), new THREE.Vector3(4.8, CY + 3.28, 0), 0.028, wireMat));
    grp.add(_wire(new THREE.Vector3(4.8, CY + 3.28, 0), new THREE.Vector3(4.8, pcbY, 0),        0.028, wireMat));
    grp.add(_wire(new THREE.Vector3(4.8, pcbY, 0),       new THREE.Vector3(pcbX + 2.10, pcbY, 0), 0.028, wireMat));

    // ── Ölçü çizgisi ─────────────────────────────────────────────────────
    grp.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-R_ito, CY, 0),
        new THREE.Vector3( R_ito, CY, 0)
      ]),
      new THREE.LineBasicMaterial({ color: 0xffcc00, transparent: true, opacity: 0.65 })
    ));
  };

})();

