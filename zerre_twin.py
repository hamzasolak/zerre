#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zerre_twin.py — Model H Dijital İkizi (v0.5)
════════════════════════════════════════════════════════════════════
Model H optik zincirinin skaler dalga simülasyonu, fiziksel kısıt
modelleri ve analitik Wirtinger-Adjoint PAT/SPSA eğitimi:

  [532nm düzlem dalga]
        │
  [mSLA LCD — GENLİK maskesi]          ← giriş verisi (28×28 görüntü)
        │  Z1 = 5cm serbest uzay       ← Açısal Spektrum Yöntemi (ASM)
  [ITO / 2.LCD — Jones maskesi]        ← ağırlıklar (aktif veya pasif matris)
        │  Z2 = 5cm serbest uzay          çapraz polarizör: t=sin(φ/2)e^{iφ/2}
  [CMOS — |E|² yoğunluk]               ← havuzlanmış özellik vektörü
        │
  [Okuma Kafası: Ridge veya MLP]       ← dijital karar katmanı

v0.4 → v0.5 (bağımsız hakem düzeltmeleri):
  • EŞLEŞMİŞ KAFA ABLASYONU: tüm kontrol satırları artık PAT ile aynı CE-Adam
    lineer kafayı (aynı fit/val bölmesi, epok, lr) kullanır; Ridge yalnız diyagnostik
  • Eğitim bütçesi eşitliği: PAT+MLP epokları kıyas MLP'lerinkiyle aynı (Tablo II: 45)
  • Kenar-kayıplı kaydırma (shift_crop): np.roll sarmal artefaktı kaldırıldı
  • PHI_SCALE global durumu kaldırıldı → phi_scale/phi_tab parametreleri
  • Zernike demet zarfı artık pv=0'da da uygulanır (süreksizlik yok)
  • Fashion-MNIST: rastgele kontrol gürültü asimetrisi giderildi, N=6000 (5280/720)
  • Ridge α düzenlileme taraması (doğrulamada seçilir)
  • YAPISAL model-uyumsuzluğu planti: pertürbe LC LUT + kamera gamması + benek
  • paper_results.json artık bölüm-bölüm checkpoint'lenir (paper_results_partial.json)

v0.4 Yenilikleri:
  • Tam sızıntısız train/val/test ayrımı (run_ablation doğrulama seti X_tr'den bölünür)
  • Adil 32×32 gerçek alan-ortalaması (pool_area) ve train-only PCA-64 baz çizgileri
  • Çift sd_floor uygulama hatası giderildi (yalnız fit_standardizer uygular)
  • Fiziksel tek-eksenli 47μm mekanik kayma ve gerçekçi 16-kare gürültülü karanlık-kare
  • Zernike + 3·Z1 Fresnel (0.04) Fabry-Pérot hayalet modeli + kafa-yeniden-eğitim kontrolü
  • Çoklu-tohum (multi-seed) --paper-benchmark ile doğrudan paper_results.json üretimi

Kullanım:
  python zerre_twin.py                         # sentetik 5-sınıf hızlı demo
  python zerre_twin.py --grad-check            # analitik adjoint türev testi
  python zerre_twin.py --ablation              # MNIST kontrollü ablasyon (sızıntısız)
  python zerre_twin.py --mnist --pat --hybrid  # PAT + Hibrit MLP tam eğitim
  python zerre_twin.py --predict demo_rakam_8.png
  python zerre_twin.py --robust                # mekanik hizasızlık analizi
  python zerre_twin.py --env                   # sıcaklık / ışık / drift analizi
  python zerre_twin.py --hw-realism            # donanım gerçekçilik & Fashion-MNIST paketi
  python zerre_twin.py --paper-benchmark       # çoklu-tohum makale kıyaslama JSON üreticisi
════════════════════════════════════════════════════════════════════
"""

import os
import sys
import gc
import json
import time
import platform
import argparse

# Windows konsolunda (cp1252) Türkçe/Unicode çıktı çökmesin
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

# Matplotlib önbellek dizini uyarısını önle
if "MPLCONFIGDIR" not in os.environ:
    _mpl_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "zerre_mpl_cache")
    os.makedirs(_mpl_tmp, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = _mpl_tmp

import numpy as np

# ─────────────────────────────────────────────────────────────────
#  FİZİKSEL PARAMETRELER
# ─────────────────────────────────────────────────────────────────
LAMBDA  = 532e-9      # lazer dalga boyu (m)
PIX     = 47e-6       # simülasyon örnekleme adımı = LCD piksel adımı (m)
Z1      = 0.05        # LCD → LC hücre mesafesi (m)
Z2      = 0.05        # LC hücre → CMOS mesafesi (m)
N_ITO   = 16          # varsayılan ITO matris boyutu (16×16 = 256 ağırlık)
CAM_N   = 16          # varsayılan kamera özellik ızgarası (16×16 = 256 özellik)
N_CLS   = 5           # sınıf sayısı (sentetik veri kümesi)

# Tek-mertebe nematik LC voltaj → faz gecikmesi tablosu (Δφ_max=4.97 rad, λ=532nm; florlu TFT-LC Δn_eff≈0.060 d=7μm veya ince E7 d≈1.87μm)
V_TAB     = np.array([0.0, 1.0, 1.2, 2.0, 3.0, 5.0])       # volt (RMS)
PHI_TAB   = np.array([4.97, 4.97, 4.20, 2.87, 1.22, 0.11]) # radyan
PHI_SLOPE = np.diff(PHI_TAB) / np.diff(V_TAB)              # dφ/dV parçalı eğimler

# ─────────────────────────────────────────────────────────────────
#  ELEKTRO-OPTİK VE PASİF MATRİS FİZİĞİ
# ─────────────────────────────────────────────────────────────────
def lc_phase(V, phi_scale=1.0, phi_tab=None):
    """Voltaj (V_rms) → faz gecikmesi Δφ (rad). §5.8.4 tablosunda interpolasyon.
    phi_scale: Haller Δn(T) sıcaklık ölçeği vb. dış etken çarpanı (vekil ikizde 1.0).
    phi_tab  : alternatif/pertürbe LUT (yapısal uyumsuzluk planti; None → PHI_TAB)."""
    if phi_tab is None:
        phi_tab = PHI_TAB
    return np.interp(np.clip(V, 0.0, 5.0), V_TAB, phi_tab) * phi_scale


def lc_phase_grad(V, phi_scale=1.0):
    """d(Δφ)/dV analitik parçalı türevi (rad/V). V ∈ (1.0, 5.0) aktif bölgedir."""
    V_arr = np.asarray(V, dtype=float)
    idx = np.clip(np.searchsorted(V_TAB, V_arr, side="right") - 1, 0, len(PHI_SLOPE) - 1)
    grad = PHI_SLOPE[idx] * phi_scale
    grad = np.where((V_arr <= 0.0) | (V_arr >= 5.0), 0.0, grad)
    return grad


def lc_jones(V, phi_scale=1.0, phi_tab=None):
    """Çapraz polarizörler arasında 45° hizalı LC retarder Jones geçişi:
    t(Δφ) = sin(Δφ/2) · exp(i·Δφ/2)."""
    phi = lc_phase(V, phi_scale, phi_tab)
    return np.sin(phi / 2.0) * np.exp(1j * phi / 2.0)


def lc_jones_dphi(phi):
    """dt/d(Δφ) analitik kompleks türevi:
    d/dφ [sin(φ/2) e^{iφ/2}] = (1/2) e^{iφ}."""
    return 0.5 * np.exp(1j * phi)


def passive_matrix_rms(U_ctrl, v_off_target=1.0):
    """Alt & Pleshko (1974) zaman-bölümlemeli N×N pasif matris RMS voltaj modeli.

    Parametreler:
      U_ctrl       : (N, N) boyutlu normalize kontrol matrisi, [-1, +1] aralığında.
                     -1 → kapalı (eşik altı), +1 → maksimum seçili.
      v_off_target : Tüm pikseller -1 iken hedeflenen eşik-altı RMS voltaj (vars: 1.0V).

    Fizik:
      N satır sırayla 1/N görev döngüsüyle taranır. Optimum Alt-Pleshko oranında
      V_sel / V_data = √N seçilir. Piksel (i,j) üzerindeki gerçek RMS voltaj:
        V_rms²(i,j) = (1/N)·(V_sel + U_ij·V_data)² + (1/N)·∑_{r≠i} (U_rj·V_data)²
      N=16 için maksimum kontrast oranı V_on / V_off = √((√16+1)/(√16-1)) = 1.291'dir
      ve aynı sütundaki diğer satırların değerleri dikey crosstalk yaratır.
    """
    U = np.clip(np.asarray(U_ctrl, dtype=float), -1.0, 1.0)
    N = U.shape[0]
    ratio = np.sqrt(float(N))  # optimum V_sel / V_data = √N
    # U = -1 iken V_rms² = (1/N)*(ratio - 1)²*Vd² + ((N-1)/N)*Vd² = ((ratio² - 2*ratio + N)/N)*Vd²
    norm_off = (ratio ** 2 - 2.0 * ratio + N) / N
    v_data = v_off_target / np.sqrt(norm_off)
    v_sel  = ratio * v_data

    col_sq_sum = np.sum((U * v_data) ** 2, axis=0, keepdims=True)  # (1, N)
    other_rows = col_sq_sum - (U * v_data) ** 2                    # ∑_{r≠i} (U_rj V_data)²
    v_rms_sq   = ((v_sel + U * v_data) ** 2 + other_rows) / N
    return np.sqrt(np.maximum(v_rms_sq, 1e-12))


def passive_matrix_rms_backward(U_ctrl, grad_V_rms, v_off_target=1.0):
    """passive_matrix_rms fonksiyonunun U_ctrl'ye göre tam analitik jakobyen-vektör çarpımı."""
    U = np.clip(np.asarray(U_ctrl, dtype=float), -1.0, 1.0)
    N = U.shape[0]
    ratio = np.sqrt(float(N))
    norm_off = (ratio ** 2 - 2.0 * ratio + N) / N
    v_data = v_off_target / np.sqrt(norm_off)
    v_sel  = ratio * v_data

    V_rms = passive_matrix_rms(U, v_off_target)
    # dL / d(V_rms²) = grad_V_rms / (2 * V_rms)
    g_sq = grad_V_rms / (2.0 * V_rms)

    # 1) Doğrudan terim (k = i): d/dU_ij [(1/N)(v_sel + U_ij v_data)²]
    grad_direct = g_sq * (2.0 / N) * (v_sel + U * v_data) * v_data
    # 2) Crosstalk terimi (k ≠ i): d/dU_ij [(1/N) ∑_{k≠i} g_sq[k,j] * U_ij² v_data²]
    col_g_sum = np.sum(g_sq, axis=0, keepdims=True) - g_sq
    grad_cross = col_g_sum * (2.0 / N) * U * (v_data ** 2)
    return grad_direct + grad_cross


def passive_selection_ratio(n_rows):
    """Alt & Pleshko (1974) teorik maksimum RMS seçim oranı V_on,rms / V_off,rms."""
    sq = np.sqrt(float(n_rows))
    return float(np.sqrt((sq + 1.0) / (sq - 1.0)))


# ─────────────────────────────────────────────────────────────────
#  DALGA OPTİĞİ ÇEKİRDEĞİ (İLERİ + ANALİTİK ADJOINT GERİ GEÇİŞ)
# ─────────────────────────────────────────────────────────────────
try:
    import scipy.fft as _sp_fft
    def _fft2(x):
        return _sp_fft.fft2(x, axes=(-2, -1), workers=-1)
    def _ifft2(x):
        return _sp_fft.ifft2(x, axes=(-2, -1), workers=-1)
except ImportError:
    def _fft2(x):
        return np.fft.fft2(x, axes=(-2, -1))
    def _ifft2(x):
        return np.fft.ifft2(x, axes=(-2, -1))


class AngularSpectrum:
    """Açısal Spektrum Yöntemi ile serbest uzay yayılımı ve Hermitik eşleniği (adjoint).
    Hem tekil (N,N) hem mini-batch (B,N,N) karmaşık alanları destekler."""

    def __init__(self, n_grid, pix, wavelength, z):
        k  = 2.0 * np.pi / wavelength
        fx = np.fft.fftfreq(n_grid, d=pix)
        FX, FY = np.meshgrid(fx, fx, indexing="xy")
        arg = 1.0 - (wavelength * FX) ** 2 - (wavelength * FY) ** 2
        kz  = k * np.sqrt(np.maximum(arg, 0.0))
        self.H = np.exp(1j * kz * z) * (arg > 0.0)   # evanescent bileşenler kesilir
        self.H_conj = np.conj(self.H)
        self.H64 = self.H.astype(np.complex64)
        self.H64_conj = self.H_conj.astype(np.complex64)

    def __call__(self, E):
        H = self.H64 if E.dtype == np.complex64 else self.H
        return _ifft2(_fft2(E) * H)

    def adjoint(self, G):
        """Standart kompleks iç çarpım <a, b> = Re ∑ a* b altında P†(G):
        P(E) = ifft2(H · fft2(E))  ⇒  P†(G) = ifft2(H* · fft2(G))."""
        Hc = self.H64_conj if G.dtype == np.complex64 else self.H_conj
        return _ifft2(_fft2(G) * Hc)


class ZerreTwin:
    """Model H optik zincirinin dijital ikizi (aktif/pasif matris + analitik adjoint)."""

    def __init__(self, n_grid=256, n_ito=N_ITO, cam_n=CAM_N, drive_mode="active"):
        """
        drive_mode:
          'active'  : Her piksel bağımsız RMS voltaj alır (TFT-LCD veya doğrudan fan-out)
          'passive' : 16×16 pasif matris Alt-Pleshko RMS kısıtı ve sütun crosstalk'u uygulanır
          'none'    : ITO hücre yok (yalnız serbest uzay kırınımı Z1+Z2 ablasyon kontrolü)
        """
        self.N = int(n_grid)
        self.n_ito = int(n_ito)
        self.cam_n = int(cam_n)
        self.drive_mode = drive_mode

        self.prop1 = AngularSpectrum(self.N, PIX, LAMBDA, Z1)
        self.prop2 = AngularSpectrum(self.N, PIX, LAMBDA, Z2)

        # ITO / ağırlık hücre aktif alanı: ızgaranın ortasında %75 kare
        cell_px  = int(self.N * 0.75)
        self.rep = max(1, cell_px // self.n_ito)
        side     = self.rep * self.n_ito
        self.o_cell = (self.N - side) // 2
        self.side   = side

        # LCD giriş alanı: 28×28 görüntü → up×up büyütme, merkezde
        self.up   = max(1, int(self.N * 0.55) // 28)
        gsz       = self.up * 28
        self.o_in = (self.N - gsz) // 2
        self.gsz  = gsz

    def effective_voltage(self, W_param):
        """Kontrol parametresinden fiziksel hücre piksellerinin gördüğü RMS voltajı hesaplar."""
        if self.drive_mode == "passive":
            return passive_matrix_rms(W_param)
        return np.clip(W_param, 0.0, 5.0)

    # ── Giriş kodlama: görüntü(ler) → LCD genlik maskesi ─────────
    def encode_lcd(self, img28):
        img = np.asarray(img28, dtype=float)
        if img.ndim == 2:
            A = np.zeros((self.N, self.N), dtype=complex)
            big = np.repeat(np.repeat(img, self.up, axis=0), self.up, axis=1)
            A[self.o_in:self.o_in + self.gsz, self.o_in:self.o_in + self.gsz] = big
            return A
        # Batch (B, 28, 28)
        B = img.shape[0]
        A = np.zeros((B, self.N, self.N), dtype=complex)
        big = np.repeat(np.repeat(img, self.up, axis=1), self.up, axis=2)
        A[:, self.o_in:self.o_in + self.gsz, self.o_in:self.o_in + self.gsz] = big
        return A

    # ── Ağırlık kodlama: parametre → hücre Jones maskesi ─────────
    def ito_mask(self, W_param, phi_scale=1.0, phi_tab=None):
        if self.drive_mode == "none":
            M = np.zeros((self.N, self.N), dtype=complex)
            M[self.o_cell:self.o_cell + self.side,
              self.o_cell:self.o_cell + self.side] = 1.0
            return M
        V_eff = self.effective_voltage(W_param)
        t_px  = lc_jones(V_eff, phi_scale, phi_tab)
        tile  = np.repeat(np.repeat(t_px, self.rep, axis=0), self.rep, axis=1)
        M = np.zeros((self.N, self.N), dtype=complex)
        M[self.o_cell:self.o_cell + self.side,
          self.o_cell:self.o_cell + self.side] = tile
        return M

    # ── Ara alan (LCD sonrası hücre düzlemine yayılmış) ──────────
    def field_at_cell(self, img28):
        return self.prop1(self.encode_lcd(img28))

    # ── Kamera: yoğunluk + ortalama havuzlama → özellik vektörü ──
    def camera(self, E):
        I = np.abs(E) ** 2
        p = self.N // self.cam_n
        lim = p * self.cam_n
        if I.ndim == 2:
            feat = I[:lim, :lim].reshape(self.cam_n, p, self.cam_n, p).mean(axis=(1, 3))
            return feat.ravel()
        B = I.shape[0]
        feat = I[:, :lim, :lim].reshape(B, self.cam_n, p, self.cam_n, p).mean(axis=(2, 4))
        return feat.reshape(B, -1)

    # ── Tam ileri geçiş (tekil veya batch) ───────────────────────
    def forward(self, img28, W_param, phi_scale=1.0, phi_tab=None):
        E = self.field_at_cell(img28)
        E = E * self.ito_mask(W_param, phi_scale, phi_tab)
        E = self.prop2(E)
        return self.camera(E)

    def forward_batch(self, X, W_param, batch_size=128, phi_scale=1.0, phi_tab=None):
        out = []
        M = self.ito_mask(W_param, phi_scale, phi_tab).astype(np.complex64)
        for i in range(0, len(X), batch_size):
            E_in = self.encode_lcd(X[i:i + batch_size]).astype(np.complex64)
            E = self.prop1(E_in)
            E = self.prop2(E * M)
            out.append(self.camera(E).astype(float))
        return np.vstack(out)

    # ── Önbellekli ileri geçiş (Z1 yayılımı W'den bağımsız) ──────
    def forward_cached(self, E_cell, W_param, phi_scale=1.0, phi_tab=None):
        E = E_cell * self.ito_mask(W_param, phi_scale, phi_tab)
        E = self.prop2(E)
        return self.camera(E)

    # ── ANALİTİK WIRTINGER ADJOINT GERİ GEÇİŞ (PAT Vekil Gradyanı) ──
    def backward_cached(self, E_cell_batch, W_param, grad_feat_batch, E_cam_override=None):
        """Özellik gradyanı dL/dF'den optik kontrol parametresi dL/dW_param'ı hesaplar.

        Physics-Aware Training (Wright et al., Nature 2022) desteği:
          İleri geçiş fiziksel sistemden (veya kusurlu simülatörden) alınmışsa bile,
          geri geçiş bu türevlenebilir vekil model üzerinden analitik olarak akar.
        """
        if self.drive_mode == "none":
            return np.zeros((self.n_ito, self.n_ito))

        B = E_cell_batch.shape[0]
        p = self.N // self.cam_n
        lim = p * self.cam_n

        # Vekil ileri alan (E_cam) — PAT'de vekilin iç durumu faz bilgisini taşır
        M = self.ito_mask(W_param)
        if E_cell_batch.dtype == np.complex64:
            M = M.astype(np.complex64)
        E_cam = E_cam_override if E_cam_override is not None else self.prop2(E_cell_batch * M)
        # NOT: Geri geçiş her zaman NOMİNAL vekil modelde akar (PAT tanımı);
        # plant'in phi_scale/phi_tab kusurları gradyana girmez.

        # 1) Ortalama havuzlama geri geçişi: dL/dI
        g_pool = grad_feat_batch.reshape(B, self.cam_n, self.cam_n) / float(p * p)
        g_dtype = np.float32 if E_cam.dtype == np.complex64 else float
        g_I = np.zeros((B, self.N, self.N), dtype=g_dtype)
        g_I[:, :lim, :lim] = np.repeat(np.repeat(g_pool.astype(g_dtype), p, axis=1), p, axis=2)

        # 2) Yoğunluk I = |E_cam|² Wirtinger türevi: G_cam = 2 · (dL/dI) · E_cam
        G_cam = 2.0 * g_I * E_cam

        # 3) Serbest uzay Z2 adjoint yayılımı: G_after_mask = P2†(G_cam)
        G_mask_plane = self.prop2.adjoint(G_cam)

        # 4) Maske çarpımı E_after = E_cell · M → G_M = ∑_b conj(E_cell[b]) · G_mask_plane[b]
        G_M = np.sum(np.conj(E_cell_batch) * G_mask_plane, axis=0)  # (N, N)

        # 5) Aktif hücre penceresini al ve (rep × rep) blokları topla → G_t (n_ito, n_ito)
        G_sub = G_M[self.o_cell:self.o_cell + self.side,
                    self.o_cell:self.o_cell + self.side]
        G_t = G_sub.reshape(self.n_ito, self.rep, self.n_ito, self.rep).sum(axis=(1, 3))

        # 6) Jones faz türevi: dL/dφ = Re( conj(G_t) · dt/dφ )
        V_eff = self.effective_voltage(W_param)
        phi   = lc_phase(V_eff)
        dt_dphi = lc_jones_dphi(phi)
        grad_phi = np.real(np.conj(G_t) * dt_dphi)

        # 7) Faz → Voltaj türevi: dL/dV_eff = dL/dφ · dφ/dV
        grad_V_eff = grad_phi * lc_phase_grad(V_eff)

        # 8) Pasif matris ise Alt-Pleshko RMS jakobyeninden geçir
        if self.drive_mode == "passive":
            return passive_matrix_rms_backward(W_param, grad_V_eff)
        return grad_V_eff

    # ── Web Arayüzü için Zenginleştirilmiş Tekil Çıkarım ─────────
    def inspect_forward(self, img28, W_param, phi_scale=1.0, phi_tab=None):
        """Giriş, Z1 kırınım genliği, ITO faz haritası, CMOS yoğunluğu ve özellikleri döner."""
        E_in   = self.encode_lcd(img28)
        E_cell = self.prop1(E_in)
        M      = self.ito_mask(W_param, phi_scale, phi_tab)
        E_cam  = self.prop2(E_cell * M)
        I_cam  = np.abs(E_cam) ** 2
        feat   = self.camera(E_cam)
        V_eff  = self.effective_voltage(W_param)
        return {
            "E_cell_amp": np.abs(E_cell),
            "ito_phase":  lc_phase(V_eff, phi_scale, phi_tab),
            "ito_volt":   V_eff,
            "I_cam":      I_cam,
            "feat":       feat,
        }


def shift_crop(arr, dy, dx):
    """Kenar-kayıplı yanal kaydırma (son iki eksende; tekil veya toplu dizi).
    np.roll'dan farklı olarak taşan ışık kenardan kaybolur ve boşalan kenar
    sıfır kalır — sarmal (wrap-around) artefaktı üretmez. Pozitif dy aşağı,
    pozitif dx sağa kaydırır."""
    H, W = arr.shape[-2], arr.shape[-1]
    out = np.zeros_like(arr)
    sy = slice(max(0, -dy), min(H, H - dy))
    ty = slice(max(0, dy), min(H, H + dy))
    sx = slice(max(0, -dx), min(W, W - dx))
    tx = slice(max(0, dx), min(W, W + dx))
    if (sy.stop - sy.start) > 0 and (sx.stop - sx.start) > 0:
        out[..., ty, tx] = arr[..., sy, sx]
    return out


# ─────────────────────────────────────────────────────────────────
#  VERİ KÜMELERİ (SENTETİK ŞEKİLLER & GERÇEK MNIST)
# ─────────────────────────────────────────────────────────────────
def make_shapes(n_per_class, rng):
    X, y = [], []
    for c in range(5):
        for _ in range(n_per_class):
            img = np.zeros((28, 28))
            if c == 0:                                    # dikey çizgi
                col = rng.integers(6, 22)
                img[4:24, max(0, col - 1):col + 1] = 1.0
            elif c == 1:                                  # yatay çizgi
                row = rng.integers(6, 22)
                img[max(0, row - 1):row + 1, 4:24] = 1.0
            elif c == 2:                                  # çapraz çizgi
                off = rng.integers(-5, 6)
                sgn = rng.choice([-1, 1])
                for i in range(4, 24):
                    j = i if sgn > 0 else 27 - i
                    jj = int(np.clip(j + off, 0, 27))
                    img[i, max(0, jj - 1):jj + 1] = 1.0
            elif c == 3:                                  # halka
                yy, xx = np.mgrid[:28, :28]
                cy, cx = rng.integers(11, 17, 2)
                r = rng.integers(6, 9)
                d = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
                img[(d > r - 1.5) & (d < r + 1.5)] = 1.0
            else:                                         # artı (dikey+yatay)
                col = rng.integers(9, 19)
                row = rng.integers(9, 19)
                img[4:24, max(0, col - 1):col + 1] = 1.0
                img[max(0, row - 1):row + 1, 4:24] = 1.0
            img += rng.normal(0.0, 0.15, (28, 28))
            X.append(np.clip(img, 0.0, 1.0))
            y.append(c)
    X, y = np.array(X), np.array(y)
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


def load_mnist(n_train, n_test, rng, cache_dir):
    import gzip
    import struct
    import urllib.request

    base = "https://ossci-datasets.s3.amazonaws.com/mnist/"
    os.makedirs(cache_dir, exist_ok=True)

    def fetch(name):
        p = os.path.join(cache_dir, name)
        if not os.path.exists(p):
            print(f"[MNIST] indiriliyor: {name}")
            urllib.request.urlretrieve(base + name, p)
        return p

    def read_images(p):
        with gzip.open(p, "rb") as f:
            _, n, r, c = struct.unpack(">IIII", f.read(16))
            return np.frombuffer(f.read(), np.uint8).reshape(n, r, c) / 255.0

    def read_labels(p):
        with gzip.open(p, "rb") as f:
            _, n = struct.unpack(">II", f.read(8))
            return np.frombuffer(f.read(), np.uint8).astype(int)

    Xtr = read_images(fetch("train-images-idx3-ubyte.gz"))
    ytr = read_labels(fetch("train-labels-idx1-ubyte.gz"))
    Xte = read_images(fetch("t10k-images-idx3-ubyte.gz"))
    yte = read_labels(fetch("t10k-labels-idx1-ubyte.gz"))

    itr = rng.permutation(len(ytr))[:n_train]
    ite = rng.permutation(len(yte))[:n_test]
    X = np.concatenate([Xtr[itr], Xte[ite]])
    y = np.concatenate([ytr[itr], yte[ite]])
    return X, y, n_train


def load_fashion_mnist(n_train, n_test, rng, cache_dir):
    """Zalando Fashion-MNIST (10 sınıf, 28×28 gri doku/kıyafet görüntüleri) yükleyici."""
    import gzip
    import struct
    import urllib.request

    mirrors = [
        "https://github.com/zalandoresearch/fashion-mnist/raw/master/data/fashion/",
        "http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/",
    ]
    os.makedirs(cache_dir, exist_ok=True)

    def fetch(name):
        p = os.path.join(cache_dir, name)
        if not os.path.exists(p):
            last_err = None
            for base in mirrors:
                try:
                    print(f"[Fashion-MNIST] indiriliyor: {base + name}")
                    urllib.request.urlretrieve(base + name, p)
                    break
                except Exception as exc:
                    last_err = exc
            if not os.path.exists(p):
                raise RuntimeError(f"Fashion-MNIST indirilemedi ({name}): {last_err}")
        return p

    def read_images(p):
        with gzip.open(p, "rb") as f:
            _, n, r, c = struct.unpack(">IIII", f.read(16))
            return np.frombuffer(f.read(), np.uint8).reshape(n, r, c) / 255.0

    def read_labels(p):
        with gzip.open(p, "rb") as f:
            _, n = struct.unpack(">II", f.read(8))
            return np.frombuffer(f.read(), np.uint8).astype(int)

    Xtr = read_images(fetch("train-images-idx3-ubyte.gz"))
    ytr = read_labels(fetch("train-labels-idx1-ubyte.gz"))
    Xte = read_images(fetch("t10k-images-idx3-ubyte.gz"))
    yte = read_labels(fetch("t10k-labels-idx1-ubyte.gz"))

    itr = rng.permutation(len(ytr))[:n_train]
    ite = rng.permutation(len(yte))[:n_test]
    X = np.concatenate([Xtr[itr], Xte[ite]])
    y = np.concatenate([ytr[itr], yte[ite]])
    return X, y, n_train


# ─────────────────────────────────────────────────────────────────
#  ÖLÇEKLEME VE KAFALAR (VERİ SIZINTISIZ STANDARDİZASYON)
# ─────────────────────────────────────────────────────────────────
def sd_floor(sd):
    """Sıfır-varyanslı karanlık köşe özelliklerinin gürültü patlamasını önler."""
    return np.maximum(sd, 0.05 * float(np.mean(sd)))


def fit_standardizer(F_train):
    """Yalnızca eğitim verisi üzerinden mu ve sd hesaplar (veri sızıntısı önlenir)."""
    mu = F_train.mean(axis=0)
    sd = sd_floor(F_train.std(axis=0) + 1e-12)
    return mu, sd


def apply_standardizer(F, mu, sd):
    return (F - mu) / sd


def standardize_split(F, n_tr):
    """F[:n_tr] üzerinde ölçekleyiciyi kurar, tüm F'e uygular."""
    mu, sd = fit_standardizer(F[:n_tr])
    return apply_standardizer(F, mu, sd), mu, sd


def fit_ridge(F, y, n_cls, alpha=1e-3):
    Fb = np.hstack([F, np.ones((F.shape[0], 1))])
    Y  = np.eye(n_cls)[y]
    A  = Fb.T @ Fb + alpha * np.trace(Fb.T @ Fb) / Fb.shape[1] * np.eye(Fb.shape[1])
    W  = np.linalg.solve(A, Fb.T @ Y)
    return W


RIDGE_ALPHAS = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)


def fit_ridge_val(F, y, n_cls, alphas=RIDGE_ALPHAS, val_frac=0.12):
    """α düzenlileme katsayısını son %val_frac doğrulama diliminde seçen Ridge kafa.
    Adaylar arasından en yüksek val doğruluğunu veren α ile (fit alt kümesinde
    eğitilmiş) ağırlıkları ve seçilen α'yı döndürür."""
    n_val = max(50, int(round(val_frac * len(y))))
    Ff, yf = F[:-n_val], y[:-n_val]
    Fv, yv = F[-n_val:], y[-n_val:]
    best_a, best_acc, best_W = alphas[0], -1.0, None
    for a in alphas:
        W = fit_ridge(Ff, yf, n_cls, alpha=a)
        acc = float((predict_ridge(Fv, W) == yv).mean())
        if acc > best_acc:
            best_a, best_acc, best_W = a, acc, W
    return best_W, best_a


def predict_ridge(F, W):
    Fb = np.hstack([F, np.ones((F.shape[0], 1))])
    return np.argmax(Fb @ W, axis=1)


def _fit_ce_linear_head(X_tr_norm, y_tr, X_val_norm, y_val, n_cls=10,
                        epochs=16, bs=256, lr_head=2.5e-2, rng=None):
    """PAT ile birebir aynı optimizer paritesinde lineer softmax kafa eğitir."""
    if rng is None:
        rng = np.random.default_rng(7)
    d_feat = X_tr_norm.shape[1]
    W_lin = np.zeros((d_feat, n_cls))
    b_lin = np.zeros(n_cls)
    m_wl, v_wl = np.zeros_like(W_lin), np.zeros_like(W_lin)
    m_bl, v_bl = np.zeros_like(b_lin), np.zeros_like(b_lin)
    t_step = 0
    best_val_acc = -1.0
    best_W, best_b = W_lin.copy(), b_lin.copy()

    for _ep in range(epochs):
        idx = rng.permutation(len(y_tr))
        for i in range(0, len(y_tr), bs):
            j = idx[i:i + bs]
            t_step += 1
            Xb = X_tr_norm[j]
            Yb = np.eye(n_cls)[y_tr[j]]
            z = Xb @ W_lin + b_lin
            z -= z.max(axis=1, keepdims=True)
            P = np.exp(z)
            P /= P.sum(axis=1, keepdims=True)
            dz = (P - Yb) / float(len(j))
            gW_lin = Xb.T @ dz + 1e-4 * W_lin
            gb_lin = dz.sum(axis=0)

            m_wl = 0.9 * m_wl + 0.1 * gW_lin
            v_wl = 0.999 * v_wl + 0.001 * (gW_lin ** 2)
            W_lin -= lr_head * (m_wl / (1.0 - 0.9 ** t_step)) / (np.sqrt(v_wl / (1.0 - 0.999 ** t_step)) + 1e-8)

            m_bl = 0.9 * m_bl + 0.1 * gb_lin
            v_bl = 0.999 * v_bl + 0.001 * (gb_lin ** 2)
            b_lin -= lr_head * (m_bl / (1.0 - 0.9 ** t_step)) / (np.sqrt(v_bl / (1.0 - 0.999 ** t_step)) + 1e-8)

        preds = np.argmax(X_val_norm @ W_lin + b_lin, axis=1)
        val_acc = float((preds == y_val).mean())
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_W, best_b = W_lin.copy(), b_lin.copy()

    return np.vstack([best_W, best_b[None, :]])


class MLPHead:
    """Tek gizli katmanlı MLP (ReLU + softmax), Adam ile eğitilir. Saf NumPy."""

    def __init__(self, d_in, d_hid, n_cls, rng):
        self._rng = rng
        self.W1 = rng.normal(0.0, np.sqrt(2.0 / d_in), (d_in, d_hid))
        self.b1 = np.zeros(d_hid)
        self.W2 = rng.normal(0.0, np.sqrt(2.0 / d_hid), (d_hid, n_cls))
        self.b2 = np.zeros(n_cls)
        self._adam = {k: [np.zeros_like(v), np.zeros_like(v)]
                      for k, v in self.params().items()}
        self._t = 0

    def params(self):
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2}

    def n_params(self):
        return sum(v.size for v in self.params().values())

    def logits(self, X):
        h = np.maximum(0.0, X @ self.W1 + self.b1)
        return h @ self.W2 + self.b2, h

    def predict(self, X):
        z, _ = self.logits(X)
        return np.argmax(z, axis=1)

    def backward_and_grads(self, Xb, yb):
        """Logitleri, CE kaybını, parametre gradyanlarını ve dL/dXb giriş gradyanını döner."""
        n_cls = self.W2.shape[1]
        Yb = np.eye(n_cls)[yb]
        z, h = self.logits(Xb)
        z_shift = z - z.max(axis=1, keepdims=True)
        P = np.exp(z_shift)
        P /= P.sum(axis=1, keepdims=True)
        loss = -float(np.mean(np.sum(Yb * np.log(np.maximum(P, 1e-12)), axis=1)))

        dz = (P - Yb) / float(len(yb))
        gW2 = h.T @ dz
        gb2 = dz.sum(axis=0)
        dh  = dz @ self.W2.T
        dh_relu = np.where(h > 0.0, dh, 0.0)
        gW1 = Xb.T @ dh_relu
        gb1 = dh_relu.sum(axis=0)
        gX  = dh_relu @ self.W1.T
        grads = {"W1": gW1, "b1": gb1, "W2": gW2, "b2": gb2}
        return loss, grads, gX

    def adam_step(self, grads, lr):
        self._t += 1
        b1m, b2m, eps = 0.9, 0.999, 1e-8
        for k, v in self.params().items():
            m, s = self._adam[k]
            g = grads[k]
            m[:] = b1m * m + (1.0 - b1m) * g
            s[:] = b2m * s + (1.0 - b2m) * (g * g)
            mh = m / (1.0 - b1m ** self._t)
            sh = s / (1.0 - b2m ** self._t)
            v -= lr * mh / (np.sqrt(sh) + eps)

    def train(self, X, y, X_val, y_val, epochs=60, bs=128, lr=1e-3, verbose=True):
        n, best_acc, best = len(y), -1.0, None
        for ep in range(epochs):
            idx = self._rng.permutation(n)
            for i in range(0, n, bs):
                j = idx[i:i + bs]
                _, grads, _ = self.backward_and_grads(X[j], y[j])
                self.adam_step(grads, lr)
            acc = (self.predict(X_val) == y_val).mean()
            if acc > best_acc:
                best_acc = acc
                best = {k: v.copy() for k, v in self.params().items()}
            if verbose and (ep + 1) % 10 == 0:
                print(f"  MLP epok {ep + 1:3d}/{epochs} · val dogruluk %{acc * 100:.1f}")
        if best is not None:
            self.W1, self.b1 = best["W1"], best["b1"]
            self.W2, self.b2 = best["W2"], best["b2"]
        return best_acc


# ─────────────────────────────────────────────────────────────────
#  PHYSICS-AWARE TRAINING (PAT — Wright et al., Nature 601, 2022)
# ─────────────────────────────────────────────────────────────────
def _make_speckle(n_grid, sigma, rng):
    """Sabit çarpımsal benek perdesi: düşük-geçişli Gauss alanının üstel çarpanı.
    Vekilin modellemediği kısmi-koherans yoğunluk dalgalanmasının yerine geçer;
    ortalaması 1'e normalize edilir (enerji kazancı yok)."""
    w = rng.normal(0.0, 1.0, (n_grid, n_grid))
    fx = np.fft.fftfreq(n_grid)
    FX, FY = np.meshgrid(fx, fx, indexing="xy")
    low = np.exp(-((FX ** 2 + FY ** 2) / (2.0 * (6.0 / n_grid) ** 2)))
    s = np.real(np.fft.ifft2(np.fft.fft2(w) * low))
    s /= (s.std() + 1e-12)
    m = np.exp(sigma * s)
    return m / m.mean()


class PhysicalPlantSimulator:
    """Gerçek donanımın kusurlarını taklit eden 'fiziksel' ileri geçiş kutusu.
    Vekil dijital ikiz (surrogate) bu kusurlardan habersizdir!
      • 1px (47μm) LCD ve kamera yanal montaj kayması (kenar-kayıplı)
      • +1.2mm Z1 mesafe tolerans sapması
      • 29°C çalışma sıcaklığı (Haller Δn kayması)
      • %2 lazer güç sapması + CMOS okuma gürültüsü

    structural=True iken parametre-pertürbasyonuna ek YAPISAL uyumsuzluk eklenir
    (vekilin modellemediği fizik):
      • Pertürbe LC LUT: PHI_TAB her noktada ±%10 düzgün bozulur
        (gerçek TN/ECB eğrisi vekilin parçalı-doğrusal tablosundan farklıdır)
      • CMOS gamma doğrusalsızlığı: I → I^0.90
      • Çarpımsal benek perdesi: sabit düşük-frekanslı yoğunluk dokusu
    """

    def __init__(self, twin_ref, seed=42, structural=False):
        self.N = twin_ref.N
        self.cam_n = twin_ref.cam_n
        self.twin_ref = twin_ref
        self.prop1_real = AngularSpectrum(self.N, PIX, LAMBDA, Z1 + 1.2e-3)
        self.prop2_real = AngularSpectrum(self.N, PIX, LAMBDA, Z2 - 0.8e-3)
        self.temp_scale = haller_scale(29.0)
        self.laser_gain = 1.02
        self.noise_std  = 2e-4
        self.rng = np.random.default_rng(seed)
        self.structural = structural
        if structural:
            rng_m = np.random.default_rng(seed + 777)
            self.phi_tab_real = PHI_TAB * (1.0 + 0.10 * rng_m.uniform(-1.0, 1.0, PHI_TAB.shape))
            self.cam_gamma = 0.90
            self.speckle = _make_speckle(self.N, 0.10, rng_m)
        else:
            self.phi_tab_real = None
            self.cam_gamma = 1.0
            self.speckle = None

    def precompute_cells(self, X, batch_size=128):
        out = []
        for i in range(0, len(X), batch_size):
            E = self.twin_ref.encode_lcd(X[i:i + batch_size]).astype(np.complex64)
            E = shift_crop(E, 1, 0)                        # 47μm LCD montaj kayması
            out.append(self.prop1_real(E))
        return np.concatenate(out, axis=0)

    def forward_cached(self, E_cell_real, W_param, noisy=True):
        M = self.twin_ref.ito_mask(W_param, phi_scale=self.temp_scale,
                                   phi_tab=self.phi_tab_real)
        if E_cell_real.dtype == np.complex64:
            M = M.astype(np.complex64)
        E = self.prop2_real(E_cell_real * M)
        I = (np.abs(E) ** 2) * self.laser_gain
        I = shift_crop(I, 0, 1)                            # 47μm kamera kayması
        if self.speckle is not None:
            I = I * self.speckle
        if self.cam_gamma != 1.0:
            I = np.power(np.maximum(I, 0.0), self.cam_gamma)
        p = self.N // self.cam_n
        lim = p * self.cam_n
        B = I.shape[0]
        feat = I[:, :lim, :lim].reshape(B, self.cam_n, p, self.cam_n, p).mean(axis=(2, 4)).reshape(B, -1)
        if noisy:
            feat = np.maximum(0.0, feat + self.rng.normal(0.0, self.noise_std, feat.shape))
        return feat.astype(float)


def pat_train(surrogate_twin, X_tr, y_tr, X_val, y_val, W_init, n_cls,
              epochs=25, bs=64, lr_opt=0.08, lr_head=2e-2,
              physical_plant=None, use_mlp=False, rng=None, verbose=True,
              precomputed=None, polish_head=False):
    """Physics-Aware Training (PAT) uçtan uca eğitim döngüsü:
      • İLERİ GEÇİŞ  : physical_plant varsa kusurlu fiziksel sistemden, yoksa ikizden
      • GERİ GEÇİŞ   : kusursuz surrogate_twin'in analitik Wirtinger adjoint operatöründen
      • OPTİMİZASYON : Optik parametreler W_param + dijital okuma kafası Adam ile birlikte güncellenir
    """
    if rng is None:
        rng = np.random.default_rng(0)
    pre = precomputed or {}

    # Bellek bütçesi <= 2.0GB ise önbellekle, büyükse mini-batch akış (streaming) kullan
    est_bytes = len(X_tr) * (surrogate_twin.N ** 2) * 8 * (2 if physical_plant is not None else 1)
    use_cache = est_bytes <= 2_000_000_000

    if use_cache:
        E_sur_tr = pre.get("E_sur_tr")
        if E_sur_tr is None:
            E_sur_tr = np.concatenate(
                [surrogate_twin.prop1(surrogate_twin.encode_lcd(X_tr[i:i + 128]).astype(np.complex64))
                 for i in range(0, len(X_tr), 128)], axis=0
            )
        get_sur = lambda j: E_sur_tr[j]
        if physical_plant is not None:
            E_phy_tr = pre.get("E_phy_tr")
            if E_phy_tr is None:
                E_phy_tr = physical_plant.precompute_cells(X_tr)
            E_phy_val = pre.get("E_phy_val")
            if E_phy_val is None:
                E_phy_val = physical_plant.precompute_cells(X_val)
            get_phy_tr  = lambda j: E_phy_tr[j]
            get_phy_val = lambda sl: E_phy_val[sl]
        else:
            E_phy_val = pre.get("E_phy_val")
            if E_phy_val is None:
                E_phy_val = np.concatenate(
                    [surrogate_twin.prop1(surrogate_twin.encode_lcd(X_val[i:i + 128]).astype(np.complex64))
                     for i in range(0, len(X_val), 128)], axis=0
                )
            get_phy_tr  = get_sur
            get_phy_val = lambda sl: E_phy_val[sl]
    else:
        get_sur = lambda j: surrogate_twin.prop1(surrogate_twin.encode_lcd(X_tr[j]).astype(np.complex64))
        if physical_plant is not None:
            get_phy_tr  = lambda j: physical_plant.precompute_cells(X_tr[j], batch_size=128)
            get_phy_val = lambda sl: physical_plant.precompute_cells(X_val[sl], batch_size=128)
        else:
            get_phy_tr  = get_sur
            get_phy_val = lambda sl: surrogate_twin.prop1(surrogate_twin.encode_lcd(X_val[sl]).astype(np.complex64))

    if physical_plant is not None:
        fwd_fn = lambda Ec, W, noisy: physical_plant.forward_cached(Ec, W, noisy=noisy)
    else:
        fwd_fn = lambda Ec, W, noisy: surrogate_twin.forward_cached(Ec, W)

    W = W_init.copy().astype(float)
    w_bounds = (-1.0, 1.0) if surrogate_twin.drive_mode == "passive" else (1.05, 4.95)

    # Başlangıç ölçekleyicisi (yalnız eğitim verisi üzerinde!)
    F0 = np.vstack([fwd_fn(get_phy_tr( slice(i, i + 128) ), W, False) for i in range(0, len(X_tr), 128)])
    mu, sd = fit_standardizer(F0)
    d_feat = F0.shape[1]

    # Dijital kafa: Lineer Softmax veya MLP
    if use_mlp:
        head = MLPHead(d_feat, 256, n_cls, rng)
    else:
        W_lin = np.zeros((d_feat, n_cls))
        b_lin = np.zeros(n_cls)
        m_wl, v_wl = np.zeros_like(W_lin), np.zeros_like(W_lin)
        m_bl, v_bl = np.zeros_like(b_lin), np.zeros_like(b_lin)

    # Optik ağırlıklar için Adam momentleri
    m_W, v_W = np.zeros_like(W), np.zeros_like(W)
    t_step = 0
    best_val_acc = -1.0
    best_state = None
    history = []

    for ep in range(epochs):
        idx = rng.permutation(len(y_tr))
        ep_loss = 0.0
        n_batches = 0

        for i in range(0, len(y_tr), bs):
            j = idx[i:i + bs]
            t_step += 1
            n_batches += 1

            # 1) FİZİKSEL İLERİ GEÇİŞ
            F_phys = fwd_fn(get_phy_tr(j), W, True)
            X_norm = (F_phys - mu) / sd

            # 2) KAFA İLERİ + GERİ GEÇİŞİ
            if use_mlp:
                loss, grads_h, g_Xnorm = head.backward_and_grads(X_norm, y_tr[j])
                head.adam_step(grads_h, lr_head)
            else:
                Yb = np.eye(n_cls)[y_tr[j]]
                z = X_norm @ W_lin + b_lin
                z -= z.max(axis=1, keepdims=True)
                P = np.exp(z)
                P /= P.sum(axis=1, keepdims=True)
                loss = -float(np.mean(np.sum(Yb * np.log(np.maximum(P, 1e-12)), axis=1)))
                dz = (P - Yb) / float(len(j))
                gW_lin = X_norm.T @ dz + 1e-4 * W_lin
                gb_lin = dz.sum(axis=0)
                g_Xnorm = dz @ W_lin.T

                # Lineer kafa Adam güncellemesi
                m_wl = 0.9 * m_wl + 0.1 * gW_lin
                v_wl = 0.999 * v_wl + 0.001 * (gW_lin ** 2)
                W_lin -= lr_head * (m_wl / (1 - 0.9 ** t_step)) / (np.sqrt(v_wl / (1 - 0.999 ** t_step)) + 1e-8)

                m_bl = 0.9 * m_bl + 0.1 * gb_lin
                v_bl = 0.999 * v_bl + 0.001 * (gb_lin ** 2)
                b_lin -= lr_head * (m_bl / (1 - 0.9 ** t_step)) / (np.sqrt(v_bl / (1 - 0.999 ** t_step)) + 1e-8)

            ep_loss += loss

            # 3) VEKİL İKİZ ÜZERİNDEN OPTİK GERİ YAYILIM (PAT Adjoint)
            g_F = g_Xnorm / sd
            g_W = surrogate_twin.backward_cached(get_sur(j), W, g_F)

            m_W = 0.9 * m_W + 0.1 * g_W
            v_W = 0.999 * v_W + 0.001 * (g_W ** 2)
            mh = m_W / (1.0 - 0.9 ** t_step)
            vh = v_W / (1.0 - 0.999 ** t_step)
            W = np.clip(W - lr_opt * mh / (np.sqrt(vh) + 1e-8), w_bounds[0], w_bounds[1])

        # Her 5 epokta bir çalışan ölçekleyiciyi eğitim kümesinden tazele
        if (ep + 1) % 5 == 0:
            F_tr_cur = np.vstack([fwd_fn(get_phy_tr(slice(i, i + 128)), W, False) for i in range(0, len(X_tr), 128)])
            mu, sd = fit_standardizer(F_tr_cur)

        # Doğrulama
        F_val = np.vstack([fwd_fn(get_phy_val(slice(i, i + 128)), W, False) for i in range(0, len(X_val), 128)])
        Xv = (F_val - mu) / sd
        if use_mlp:
            preds = head.predict(Xv)
        else:
            preds = np.argmax(Xv @ W_lin + b_lin, axis=1)
        val_acc = float((preds == y_val).mean())
        history.append(ep_loss / max(1, n_batches))

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            if use_mlp:
                best_state = {
                    "W": W.copy(), "mu": mu.copy(), "sd": sd.copy(),
                    "mlp": {k: v.copy() for k, v in head.params().items()}
                }
            else:
                best_state = {
                    "W": W.copy(), "mu": mu.copy(), "sd": sd.copy(),
                    "W_lin": W_lin.copy(), "b_lin": b_lin.copy()
                }

        if verbose and ((ep + 1) % 5 == 0 or ep == 0 or ep == epochs - 1):
            tag = "PAT-Donanim" if physical_plant is not None else "Adjoint-Ikiz"
            print(f"  [{tag}] epok {ep + 1:2d}/{epochs} · CE kayip {history[-1]:.4f} · val %{val_acc * 100:.1f}", flush=True)

    # En iyi durumu geri yükle
    W_best = best_state["W"]
    mu_best, sd_best = best_state["mu"], best_state["sd"]
    if use_mlp:
        head.W1, head.b1 = best_state["mlp"]["W1"], best_state["mlp"]["b1"]
        head.W2, head.b2 = best_state["mlp"]["W2"], best_state["mlp"]["b2"]
        Wout_pack = None
    else:
        Wout_pack = np.vstack([best_state["W_lin"], best_state["b_lin"][None, :]])
        head = None
        if polish_head:
            F_tr_pol = np.vstack([
                fwd_fn(get_phy_tr(slice(i, i + 128)), W_best, False)
                for i in range(0, len(X_tr), 128)
            ])
            F_val_pol = np.vstack([
                fwd_fn(get_phy_val(slice(i, i + 128)), W_best, False)
                for i in range(0, len(X_val), 128)
            ])
            mu_best, sd_best = fit_standardizer(F_tr_pol)
            Wout_pack = _fit_ce_linear_head(
                apply_standardizer(F_tr_pol, mu_best, sd_best), y_tr,
                apply_standardizer(F_val_pol, mu_best, sd_best), y_val,
                n_cls, epochs=16, bs=bs, lr_head=lr_head, rng=rng,
            )

    get_sur = get_phy_tr = get_phy_val = None
    return W_best, mu_best, sd_best, Wout_pack, head, history, fwd_fn


# ─────────────────────────────────────────────────────────────────
#  v0.6 ÇÖZÜM 1: KATLANMIŞ ÇOK-KATMANLI KOVUK + DİFERANSİYEL OKUMA
# ─────────────────────────────────────────────────────────────────
class FoldedMultiPassTwin:
    """Tek bir 2K/4K mSLA panelin farklı bölgelerini ayna katlamasıyla L ardışık
    faz/Jones düzlemi olarak kullanan çok-katmanlı ikiz + işaretli diferansiyel
    (I_+ - I_-) CMOS okuma (aynı K² özellik sayısı, dijital ağırlık artışı yok)."""

    def __init__(self, n_grid=128, n_ito=32, cam_n=8, n_layers=2,
                 modulation="jones", differential=True, z_list=None):
        self.N = int(n_grid)
        self.n_ito = int(n_ito)
        self.cam_n = int(cam_n)
        self.n_layers = int(n_layers)
        if modulation not in ("jones", "phase"):
            raise ValueError(f"Desteklenmeyen modulation='{modulation}' (jones|phase)")
        self.modulation = modulation
        self.differential = bool(differential)

        if z_list is None:
            if self.n_layers == 1:
                z_list = [0.05, 0.05]
            elif self.n_layers == 2:
                z_list = [0.035, 0.035, 0.035]
            elif self.n_layers == 3:
                z_list = [0.025, 0.025, 0.025, 0.025]
            else:
                z_step = 0.10 / float(self.n_layers + 1)
                z_list = [z_step] * (self.n_layers + 1)
        if len(z_list) != self.n_layers + 1:
            raise ValueError("z_list uzunlugu n_layers + 1 olmalidir.")
        self.z_list = [float(z) for z in z_list]
        self.props = [AngularSpectrum(self.N, PIX, LAMBDA, z) for z in self.z_list]

        cell_px = int(self.N * 0.75)
        self.rep = max(1, cell_px // self.n_ito)
        self.side = self.rep * self.n_ito
        self.o_cell = (self.N - self.side) // 2

        self.up = max(1, int(self.N * 0.55) // 28)
        self.gsz = self.up * 28
        self.o_in = (self.N - self.gsz) // 2

    def encode_lcd(self, img28, dtype=np.complex128):
        img = np.asarray(img28, dtype=float)
        if img.ndim == 2:
            A = np.zeros((self.N, self.N), dtype=dtype)
            big = np.repeat(np.repeat(img, self.up, axis=0), self.up, axis=1)
            A[self.o_in:self.o_in + self.gsz, self.o_in:self.o_in + self.gsz] = big
            return A
        B = img.shape[0]
        A = np.zeros((B, self.N, self.N), dtype=dtype)
        big = np.repeat(np.repeat(img, self.up, axis=1), self.up, axis=2)
        A[:, self.o_in:self.o_in + self.gsz, self.o_in:self.o_in + self.gsz] = big
        return A

    def mask_layer(self, W_l, phi_scale=1.0, phi_tab=None, dtype=np.complex128):
        V = np.clip(W_l, 0.0, 5.0)
        phi = lc_phase(V, phi_scale, phi_tab)
        if self.modulation == "phase":
            t_px = np.exp(1j * phi)
        else:
            t_px = np.sin(phi / 2.0) * np.exp(1j * phi / 2.0)
        tile = np.repeat(np.repeat(t_px, self.rep, axis=0), self.rep, axis=1)
        M = np.zeros((self.N, self.N), dtype=dtype)
        M[self.o_cell:self.o_cell + self.side, self.o_cell:self.o_cell + self.side] = tile
        return M

    def field_at_cell(self, img28, dtype=np.complex128):
        return self.props[0](self.encode_lcd(img28, dtype=dtype))

    def camera_from_I(self, I):
        is_2d = (I.ndim == 2)
        I3 = I[None, :, :] if is_2d else I
        B = I3.shape[0]
        p = self.N // self.cam_n
        lim = p * self.cam_n
        if not self.differential:
            feat = I3[:, :lim, :lim].reshape(B, self.cam_n, p, self.cam_n, p).mean(axis=(2, 4)).reshape(B, -1)
        else:
            hp = p // 2
            lim_y = 2 * hp * self.cam_n
            blk = I3[:, :lim_y, :lim].reshape(B, self.cam_n, 2, hp, self.cam_n, p)
            f_pos = blk[:, :, 0, :, :, :].mean(axis=(2, 4))
            f_neg = blk[:, :, 1, :, :, :].mean(axis=(2, 4))
            feat = (f_pos - f_neg).reshape(B, -1)
        return feat[0] if is_2d else feat

    def camera_backward(self, grad_feat, dtype=float):
        B = grad_feat.shape[0]
        p = self.N // self.cam_n
        lim = p * self.cam_n
        g_I = np.zeros((B, self.N, self.N), dtype=dtype)
        if not self.differential:
            gp = grad_feat.reshape(B, self.cam_n, self.cam_n) / float(p * p)
            g_I[:, :lim, :lim] = np.repeat(np.repeat(gp.astype(dtype), p, axis=1), p, axis=2)
            return g_I
        hp = p // 2
        lim_y = 2 * hp * self.cam_n
        gp = (grad_feat.reshape(B, self.cam_n, self.cam_n) / float(hp * p)).astype(dtype)
        blk = np.zeros((B, self.cam_n, 2, hp, self.cam_n, p), dtype=dtype)
        blk[:, :, 0, :, :, :] = gp[:, :, None, :, None]
        blk[:, :, 1, :, :, :] = -gp[:, :, None, :, None]
        g_I[:, :lim_y, :lim] = blk.reshape(B, lim_y, lim)
        return g_I

    def forward_cached(self, E_in_cell, W_list, phi_scale=1.0, phi_tab=None, return_cache=False):
        E_before = [E_in_cell]
        M_list = []
        E = E_in_cell
        m_dtype = np.complex64 if E_in_cell.dtype == np.complex64 else np.complex128
        for l in range(self.n_layers):
            M = self.mask_layer(W_list[l], phi_scale, phi_tab, dtype=m_dtype)
            M_list.append(M)
            E = self.props[l + 1](E * M)
            E_before.append(E)
        feat = self.camera_from_I(np.abs(E) ** 2).astype(float)
        if return_cache:
            return feat, E_before, M_list
        return feat

    def forward_batch(self, X, W_list, batch_size=128, phi_scale=1.0, phi_tab=None):
        M_list = [self.mask_layer(W_list[l], phi_scale, phi_tab, dtype=np.complex64)
                  for l in range(self.n_layers)]
        out = []
        for i in range(0, len(X), batch_size):
            E = self.props[0](self.encode_lcd(X[i:i + batch_size], dtype=np.complex64))
            for l in range(self.n_layers):
                E = self.props[l + 1](E * M_list[l])
            out.append(self.camera_from_I(np.abs(E) ** 2).astype(float))
        return np.vstack(out)

    def backward_cached(self, E_before, M_list, W_list, grad_feat):
        E_cam = E_before[-1]
        g_dtype = np.float32 if E_cam.dtype == np.complex64 else float
        g_I = self.camera_backward(grad_feat, dtype=g_dtype)
        G = 2.0 * g_I * E_cam
        grads = [None] * self.n_layers
        for l in range(self.n_layers - 1, -1, -1):
            G_after_mask = self.props[l + 1].adjoint(G)
            G_M = np.sum(np.conj(E_before[l]) * G_after_mask, axis=0)
            G_sub = G_M[self.o_cell:self.o_cell + self.side,
                        self.o_cell:self.o_cell + self.side]
            G_t = G_sub.reshape(self.n_ito, self.rep, self.n_ito, self.rep).sum(axis=(1, 3))
            V_l = np.clip(W_list[l], 0.0, 5.0)
            phi = lc_phase(V_l)
            dt_dphi = (1j * np.exp(1j * phi)) if self.modulation == "phase" else lc_jones_dphi(phi)
            grad_phi = np.real(np.conj(G_t) * dt_dphi)
            grads[l] = grad_phi * lc_phase_grad(V_l)
            if l > 0:
                G = G_after_mask * np.conj(M_list[l])
        return grads


class FoldedMultiPassPlant:
    """Katlanmış L-katmanlı düzeneğin kusurlu fiziksel simülatörü."""

    def __init__(self, mp_ref, seed=42):
        self.ref = mp_ref
        self.props = [
            AngularSpectrum(
                mp_ref.N, PIX, LAMBDA,
                z + (1.2e-3 if i == 0 else (-0.8e-3 if i == len(mp_ref.z_list) - 1 else 0.5e-3)),
            )
            for i, z in enumerate(mp_ref.z_list)
        ]
        self.temp_scale = haller_scale(29.0)
        self.laser_gain = 1.02
        self.noise_std = 2e-4
        self.rng = np.random.default_rng(seed)

    def precompute_cells(self, X, batch_size=128):
        out = []
        for i in range(0, len(X), batch_size):
            E = shift_crop(self.ref.encode_lcd(X[i:i + batch_size], dtype=np.complex64), 1, 0)
            out.append(self.props[0](E))
        return np.concatenate(out, axis=0)

    def forward_cached(self, E_in_phy, W_list, noisy=True):
        E = E_in_phy
        m_dtype = np.complex64 if E_in_phy.dtype == np.complex64 else np.complex128
        for l in range(self.ref.n_layers):
            M = self.ref.mask_layer(W_list[l], phi_scale=self.temp_scale, dtype=m_dtype)
            E = self.props[l + 1](E * M)
        I = (np.abs(E) ** 2) * self.laser_gain
        I = shift_crop(I, 0, 1)
        feat = self.ref.camera_from_I(I).astype(float)
        if noisy:
            feat = feat + self.rng.normal(0.0, self.noise_std, feat.shape)
        return feat


def pat_train_multipass(mp_twin, X_tr, y_tr, X_val, y_val, W_init_list, n_cls=10,
                        epochs=20, bs=256, lr_opt=0.10, lr_head=2.5e-2,
                        physical_plant=None, polish_head=True, val_every=2,
                        rng=None, verbose=False):
    """Katlanmış L-katmanlı optik ağırlıklar + CE-Adam lineer kafa için PAT eğitimi."""
    if rng is None:
        rng = np.random.default_rng(0)

    E_sur_tr = np.concatenate(
        [mp_twin.field_at_cell(X_tr[i:i + 128], dtype=np.complex64) for i in range(0, len(X_tr), 128)],
        axis=0,
    )
    if physical_plant is not None:
        E_phy_tr = physical_plant.precompute_cells(X_tr)
        E_phy_val = physical_plant.precompute_cells(X_val)
        fwd_fn = lambda Ec, Wl, noisy: physical_plant.forward_cached(Ec, Wl, noisy=noisy)
    else:
        E_phy_tr = E_sur_tr
        E_phy_val = np.concatenate(
            [mp_twin.field_at_cell(X_val[i:i + 128], dtype=np.complex64) for i in range(0, len(X_val), 128)],
            axis=0,
        )
        fwd_fn = lambda Ec, Wl, noisy: mp_twin.forward_cached(Ec, Wl)

    W_list = [w.copy().astype(float) for w in W_init_list]
    F0 = np.vstack([fwd_fn(E_phy_tr[i:i + 128], W_list, False) for i in range(0, len(X_tr), 128)])
    mu, sd = fit_standardizer(F0)
    d_feat = F0.shape[1]

    W_lin = np.zeros((d_feat, n_cls))
    b_lin = np.zeros(n_cls)
    m_wl, v_wl = np.zeros_like(W_lin), np.zeros_like(W_lin)
    m_bl, v_bl = np.zeros_like(b_lin), np.zeros_like(b_lin)
    m_W = [np.zeros_like(w) for w in W_list]
    v_W = [np.zeros_like(w) for w in W_list]

    t_step = 0
    best_val_acc = -1.0
    best_state = None

    for ep in range(epochs):
        idx = rng.permutation(len(y_tr))
        for i in range(0, len(y_tr), bs):
            j = idx[i:i + bs]
            t_step += 1
            Fp = fwd_fn(E_phy_tr[j], W_list, True)
            Xn = (Fp - mu) / sd
            Yb = np.eye(n_cls)[y_tr[j]]
            z = Xn @ W_lin + b_lin
            z -= z.max(axis=1, keepdims=True)
            P = np.exp(z)
            P /= P.sum(axis=1, keepdims=True)
            dz = (P - Yb) / float(len(j))
            gWl = Xn.T @ dz + 1e-4 * W_lin
            gbl = dz.sum(axis=0)
            gXn = dz @ W_lin.T

            m_wl = 0.9 * m_wl + 0.1 * gWl
            v_wl = 0.999 * v_wl + 0.001 * (gWl ** 2)
            W_lin -= lr_head * (m_wl / (1.0 - 0.9 ** t_step)) / (np.sqrt(v_wl / (1.0 - 0.999 ** t_step)) + 1e-8)

            m_bl = 0.9 * m_bl + 0.1 * gbl
            v_bl = 0.999 * v_bl + 0.001 * (gbl ** 2)
            b_lin -= lr_head * (m_bl / (1.0 - 0.9 ** t_step)) / (np.sqrt(v_bl / (1.0 - 0.999 ** t_step)) + 1e-8)

            _, E_bef, M_lst = mp_twin.forward_cached(E_sur_tr[j], W_list, return_cache=True)
            gW_list = mp_twin.backward_cached(E_bef, M_lst, W_list, gXn / sd)
            for l in range(mp_twin.n_layers):
                m_W[l] = 0.9 * m_W[l] + 0.1 * gW_list[l]
                v_W[l] = 0.999 * v_W[l] + 0.001 * (gW_list[l] ** 2)
                mh = m_W[l] / (1.0 - 0.9 ** t_step)
                vh = v_W[l] / (1.0 - 0.999 ** t_step)
                W_list[l] = np.clip(W_list[l] - lr_opt * mh / (np.sqrt(vh) + 1e-8), 1.05, 4.95)

        if (ep + 1) % 5 == 0:
            Ft = np.vstack([fwd_fn(E_phy_tr[i:i + 128], W_list, False) for i in range(0, len(X_tr), 128)])
            mu, sd = fit_standardizer(Ft)

        if (ep + 1) % val_every == 0 or ep == epochs - 1:
            Fv = np.vstack([fwd_fn(E_phy_val[i:i + 128], W_list, False) for i in range(0, len(X_val), 128)])
            va = float((np.argmax(((Fv - mu) / sd) @ W_lin + b_lin, axis=1) == y_val).mean())
            if va > best_val_acc:
                best_val_acc = va
                best_state = ([w.copy() for w in W_list], mu.copy(), sd.copy(), W_lin.copy(), b_lin.copy())
            if verbose:
                print(f"  [MultiPass L={mp_twin.n_layers}] ep {ep+1:2d}/{epochs} val=%{va*100:.2f}", flush=True)

    W_best, mu_best, sd_best, Wl_b, bl_b = best_state
    Wout_pack = np.vstack([Wl_b, bl_b[None, :]])
    if polish_head:
        F_tr_p = np.vstack([fwd_fn(E_phy_tr[i:i + 128], W_best, False) for i in range(0, len(X_tr), 128)])
        F_va_p = np.vstack([fwd_fn(E_phy_val[i:i + 128], W_best, False) for i in range(0, len(X_val), 128)])
        mu_best, sd_best = fit_standardizer(F_tr_p)
        Wout_pack = _fit_ce_linear_head(
            apply_standardizer(F_tr_p, mu_best, sd_best), y_tr,
            apply_standardizer(F_va_p, mu_best, sd_best), y_val,
            n_cls, epochs=16, bs=bs, lr_head=lr_head, rng=rng,
        )
    return W_best, mu_best, sd_best, Wout_pack, fwd_fn


# ─────────────────────────────────────────────────────────────────
#  v0.6 ÇÖZÜM 2: KARA-KUTU KALİBRE VEKİL PAT (YAPISAL UYUMSUZLUK)
# ─────────────────────────────────────────────────────────────────
class CalibratedSurrogateTwin:
    """Kara-kutu donanım ölçümlerinden öğrenilen kayma, pertürbe LC faz tablosu,
    kamera gamması ve dedektör kazanç haritasıyla kalibre edilen türevlenebilir ikiz."""

    def __init__(self, base_twin, phi_tab_hat, gamma_hat=1.0, gain_map=None, shifts=(0, 0, 0, 0)):
        self.base = base_twin
        self.N = base_twin.N
        self.n_ito = base_twin.n_ito
        self.cam_n = base_twin.cam_n
        self.drive_mode = base_twin.drive_mode
        self.prop1 = base_twin.prop1
        self.prop2 = base_twin.prop2
        self.phi_tab = np.asarray(phi_tab_hat, dtype=float).copy()
        self.phi_slope = np.diff(self.phi_tab) / np.diff(V_TAB)
        self.gamma = float(gamma_hat)
        self.gain_map = (np.ones(self.cam_n ** 2, dtype=float)
                         if gain_map is None else np.asarray(gain_map, dtype=float).copy())
        self.dy_i, self.dx_i, self.dy_c, self.dx_c = (int(s) for s in shifts)

    def encode_lcd(self, img28):
        E0 = self.base.encode_lcd(img28)
        return shift_crop(E0, self.dy_i, self.dx_i)

    def field_at_cell(self, img28):
        return self.prop1(self.encode_lcd(img28))

    def _eval_intensity(self, E_cell, W_param):
        m_dtype = np.complex64 if E_cell.dtype == np.complex64 else np.complex128
        M = self.base.ito_mask(W_param, phi_scale=1.0, phi_tab=self.phi_tab).astype(m_dtype)
        E_cam = self.prop2(E_cell * M)
        I_sh = shift_crop(np.abs(E_cam) ** 2, self.dy_c, self.dx_c)
        return E_cam, I_sh

    def forward_cached(self, E_cell, W_param):
        is_2d = (E_cell.ndim == 2)
        Ec = E_cell[None, :, :] if is_2d else E_cell
        _, I_sh = self._eval_intensity(Ec, W_param)
        I_gam = np.where(I_sh > 1e-12, np.power(np.maximum(I_sh, 1e-12), self.gamma), 0.0)
        p = self.N // self.cam_n
        lim = p * self.cam_n
        B = I_gam.shape[0]
        feat = (I_gam[:, :lim, :lim].reshape(B, self.cam_n, p, self.cam_n, p)
                .mean(axis=(2, 4)).reshape(B, -1) * self.gain_map[None, :]).astype(float)
        return feat[0] if is_2d else feat

    def backward_cached(self, E_cell_batch, W_param, grad_feat_batch):
        B = E_cell_batch.shape[0]
        p = self.N // self.cam_n
        lim = p * self.cam_n
        E_cam, I_sh = self._eval_intensity(E_cell_batch, W_param)
        g_dtype = np.float32 if E_cam.dtype == np.complex64 else float

        g_feat = grad_feat_batch * self.gain_map[None, :]
        g_pool = g_feat.reshape(B, self.cam_n, self.cam_n) / float(p * p)
        g_I_gam = np.zeros((B, self.N, self.N), dtype=g_dtype)
        g_I_gam[:, :lim, :lim] = np.repeat(np.repeat(g_pool.astype(g_dtype), p, axis=1), p, axis=2)

        d_gam = np.where(
            I_sh > 1e-12,
            self.gamma * np.power(np.maximum(I_sh, 1e-12), self.gamma - 1.0),
            0.0,
        ).astype(g_dtype)
        g_I_sh = g_I_gam * d_gam
        g_I = shift_crop(g_I_sh, -self.dy_c, -self.dx_c)

        G_cam = 2.0 * g_I * E_cam
        G_mask_plane = self.prop2.adjoint(G_cam)
        G_M = np.sum(np.conj(E_cell_batch) * G_mask_plane, axis=0)
        G_sub = G_M[self.base.o_cell:self.base.o_cell + self.base.side,
                    self.base.o_cell:self.base.o_cell + self.base.side]
        G_t = G_sub.reshape(self.n_ito, self.base.rep, self.n_ito, self.base.rep).sum(axis=(1, 3))

        V_eff = np.clip(W_param, 0.0, 5.0)
        phi = lc_phase(V_eff, 1.0, self.phi_tab)
        grad_phi = np.real(np.conj(G_t) * lc_jones_dphi(phi))
        idx = np.clip(np.searchsorted(V_TAB, V_eff, side="right") - 1, 0, len(self.phi_slope) - 1)
        dphi_dV = np.where((V_eff <= 0.0) | (V_eff >= 5.0), 0.0, self.phi_slope[idx])
        return grad_phi * dphi_dV


def calibrate_surrogate_blackbox(base_twin, plant, X_train, seed=42,
                                 n_flat_v=21, n_cal_imgs=32, n_probes=2, maxiter=140):
    """Test verisine veya plant iç değişkenlerine erişmeden yalnızca kara-kutu
    plant.forward_cached(..., noisy=True) çağrılarıyla (85 sorgu) kayma,
    LC LUT eğrisi, kamera gamması ve benek kazanç haritasını kalibre eder."""
    from scipy.optimize import minimize

    rng_c = np.random.default_rng(seed + 999)
    V_cal_grid = np.linspace(1.05, 4.95, n_flat_v)
    X_flat = np.ones((1, 28, 28), dtype=float)
    E_flat_phy = plant.precompute_cells(X_flat)
    I_flat_meas = np.array([
        plant.forward_cached(E_flat_phy, np.full((base_twin.n_ito, base_twin.n_ito), v), noisy=True).mean()
        for v in V_cal_grid
    ])

    k_imgs = min(int(n_cal_imgs), len(X_train))
    cal_idx = rng_c.choice(len(X_train), size=k_imgs, replace=False)
    W_probes = [rng_c.uniform(1.2, 4.8, (base_twin.n_ito, base_twin.n_ito)) for _ in range(n_probes)]
    E_cal_phy = plant.precompute_cells(X_train[cal_idx])
    F_cal_target = np.vstack([plant.forward_cached(E_cal_phy, Wp, noisy=True) for Wp in W_probes])
    E_cal_nom_in = base_twin.encode_lcd(X_train[cal_idx]).astype(np.complex64)

    # 1) Kaba tamsayı kayma araması (ilk min(16, k_imgs) eğitim örneği)
    n_sh = min(16, k_imgs)
    best_shift, best_corr = (0, 0, 0, 0), -1.0
    p = base_twin.N // base_twin.cam_n
    lim = p * base_twin.cam_n
    M0 = base_twin.ito_mask(W_probes[0]).astype(np.complex64)
    t_ref = F_cal_target[:n_sh].ravel()
    for dy_i in (-1, 0, 1):
        for dx_i in (-1, 0, 1):
            E1_try = base_twin.prop1(shift_crop(E_cal_nom_in[:n_sh], dy_i, dx_i))
            I2 = np.abs(base_twin.prop2(E1_try * M0)) ** 2
            for dy_c in (-1, 0, 1):
                for dx_c in (-1, 0, 1):
                    Is = shift_crop(I2, dy_c, dx_c)
                    f = Is[:, :lim, :lim].reshape(n_sh, base_twin.cam_n, p, base_twin.cam_n, p).mean(axis=(2, 4)).ravel()
                    c = float(np.corrcoef(f, t_ref)[0, 1])
                    if c > best_corr:
                        best_corr = c
                        best_shift = (dy_i, dx_i, dy_c, dx_c)

    dy_i, dx_i, dy_c, dx_c = best_shift
    E_cal_cell = base_twin.prop1(shift_crop(E_cal_nom_in, dy_i, dx_i))

    def _eval_preds(phi_hat, gamma_hat):
        preds = []
        for Wp in W_probes:
            M = base_twin.ito_mask(Wp, phi_scale=1.0, phi_tab=phi_hat).astype(np.complex64)
            I = shift_crop(np.abs(base_twin.prop2(E_cal_cell * M)) ** 2, dy_c, dx_c)
            Ig = np.where(I > 1e-12, np.power(np.maximum(I, 1e-12), gamma_hat), 0.0)
            f = Ig[:, :lim, :lim].reshape(k_imgs, base_twin.cam_n, p, base_twin.cam_n, p).mean(axis=(2, 4)).reshape(k_imgs, -1)
            preds.append(f)
        return np.vstack(preds)

    def _cal_loss(theta):
        phi_hat = np.array([theta[0], theta[0], theta[1], theta[2], theta[3], theta[4]])
        gamma_hat = float(np.clip(theta[5], 0.5, 1.5))
        M_fl = np.sin(np.interp(V_cal_grid, V_TAB, phi_hat) / 2.0) ** 2
        pred_fl = np.power(np.maximum(M_fl, 1e-12), gamma_hat)
        s_fl = np.dot(pred_fl, I_flat_meas) / (np.dot(pred_fl, pred_fl) + 1e-12)
        l_fl = np.mean((s_fl * pred_fl - I_flat_meas) ** 2) / (np.var(I_flat_meas) + 1e-12)
        F_pred = _eval_preds(phi_hat, gamma_hat)
        g_map = np.sum(F_pred * F_cal_target, axis=0) / (np.sum(F_pred ** 2, axis=0) + 1e-12)
        l_img = np.mean((F_pred * g_map - F_cal_target) ** 2) / (np.var(F_cal_target) + 1e-12)
        return float(l_fl + 2.0 * l_img)

    theta0 = np.array([PHI_TAB[1], PHI_TAB[2], PHI_TAB[3], PHI_TAB[4], PHI_TAB[5], 1.0])
    res = minimize(_cal_loss, theta0, method="Nelder-Mead",
                   options={"maxiter": int(maxiter), "xatol": 1e-3, "fatol": 1e-4})
    phi_hat = np.array([res.x[0], res.x[0], res.x[1], res.x[2], res.x[3], res.x[4]])
    gamma_hat = float(np.clip(res.x[5], 0.5, 1.5))
    F_pred = _eval_preds(phi_hat, gamma_hat)
    gain_map = np.sum(F_pred * F_cal_target, axis=0) / (np.sum(F_pred ** 2, axis=0) + 1e-12)

    cal_twin = CalibratedSurrogateTwin(base_twin, phi_hat, gamma_hat, gain_map, best_shift)
    cal_info = {
        "n_plant_queries": int(n_flat_v + n_probes * k_imgs),
        "shifts": list(best_shift),
        "shift_corr": round(best_corr, 4),
        "gamma_hat": round(gamma_hat, 4),
        "phi_tab_hat": [round(float(x), 4) for x in phi_hat],
        "cal_loss": round(float(res.fun), 5),
    }
    return cal_twin, cal_info


# ─────────────────────────────────────────────────────────────────
#  v0.6 ÇÖZÜM 3: UZAMSAL PAKETLEME (TEK KAREDE ÇOKLU GÖRÜNTÜ)
# ─────────────────────────────────────────────────────────────────
class SpatialBatchEngine:
    """Tek mSLA LCD + CMOS çerçevesinde grid_k × grid_k bağımsız görüntüyü
    paralel optik koruma bantlarıyla (crosstalk < 1e-6) tek FFT/optik geçişte işler."""

    def __init__(self, base_twin, grid_k=2):
        self.base = base_twin
        self.grid_k = int(grid_k)
        self.tile_n = base_twin.N
        self.N_big = self.tile_n * self.grid_k
        self.n_tiles = self.grid_k * self.grid_k
        self.prop1_big = AngularSpectrum(self.N_big, PIX, LAMBDA, Z1)
        self.prop2_big = AngularSpectrum(self.N_big, PIX, LAMBDA, Z2)

    def forward_frame(self, imgs_batch, W_param, phi_scale=1.0, phi_tab=None):
        n_in = len(imgs_batch)
        if n_in > self.n_tiles:
            raise ValueError(f"En fazla {self.n_tiles} goruntu paketlenebilir ({n_in} verildi).")
        E_big = np.zeros((self.N_big, self.N_big), dtype=np.complex64)
        for idx_t in range(n_in):
            r, c = divmod(idx_t, self.grid_k)
            y0, x0 = r * self.tile_n, c * self.tile_n
            E_big[y0:y0 + self.tile_n, x0:x0 + self.tile_n] = (
                self.base.encode_lcd(imgs_batch[idx_t]).astype(np.complex64)
            )
        M_tile = self.base.ito_mask(W_param, phi_scale, phi_tab).astype(np.complex64)
        M_big = np.tile(M_tile, (self.grid_k, self.grid_k))
        I_big = np.abs(self.prop2_big(self.prop1_big(E_big) * M_big)) ** 2

        p = self.tile_n // self.base.cam_n
        lim = p * self.base.cam_n
        feats = np.zeros((n_in, self.base.cam_n ** 2), dtype=float)
        for idx_t in range(n_in):
            r, c = divmod(idx_t, self.grid_k)
            y0, x0 = r * self.tile_n, c * self.tile_n
            I_t = I_big[y0:y0 + lim, x0:x0 + lim]
            feats[idx_t] = (I_t.reshape(self.base.cam_n, p, self.base.cam_n, p)
                            .mean(axis=(1, 3)).ravel())
        return feats

    def measure_crosstalk(self, img28, W_param):
        """Yalnızca sol-üst karoda görüntü varken komşu karolara sızan toplam enerji oranı."""
        E_one = np.zeros((self.N_big, self.N_big), dtype=np.complex64)
        E_one[:self.tile_n, :self.tile_n] = self.base.encode_lcd(img28).astype(np.complex64)
        M_big = np.tile(self.base.ito_mask(W_param).astype(np.complex64), (self.grid_k, self.grid_k))
        I_one = np.abs(self.prop2_big(self.prop1_big(E_one) * M_big)) ** 2
        e_in = float(I_one[:self.tile_n, :self.tile_n].sum())
        e_leak = float(I_one.sum()) - e_in
        ratio = e_leak / (e_in + 1e-12)
        db = 10.0 * np.log10(max(ratio, 1e-15))
        return {"crosstalk_ratio": ratio, "crosstalk_db": round(float(db), 2)}


def panel_spatial_throughput(tile_n=128, fps=60):
    """Ticari 2K / 4K / 8K mSLA panellerin 60 Hz paralel karo kapasitesi."""
    specs = [
        ('5.5" 2K mSLA (47um)', 1440, 2560),
        ('6.6" 4K mSLA (35um)', 2560, 4098),
        ('10.1" 8K mSLA (28.5um)', 4320, 7680),
    ]
    rows = []
    for name, h, w in specs:
        ny, nx = h // tile_n, w // tile_n
        tiles = ny * nx
        rows.append({
            "panel": name, "grid": f"{ny}x{nx}",
            "tiles_per_frame": int(tiles),
            "imgs_per_sec_60hz": int(tiles * fps),
        })
    return rows


# ─────────────────────────────────────────────────────────────────
#  SONLU FARKLAR İLE ANALİTİK ADJOINT TÜREV DOĞRULAMASI
# ─────────────────────────────────────────────────────────────────
def grad_check():
    """Analitik Wirtinger adjoint optik türevini merkezi sonlu farklarla doğrular."""
    print("═" * 66)
    print("  ANALİTİK WIRTINGER ADJOINT GRADYAN DOĞRULAMA TESTİ")
    print("═" * 66)
    rng = np.random.default_rng(123)
    X, _ = make_shapes(4, rng)
    Xb = X[:6]

    for mode in ["active", "passive"]:
        twin = ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode=mode)
        E_cells = twin.field_at_cell(Xb)
        if mode == "active":
            W = rng.uniform(1.3, 4.5, (8, 8))
        else:
            W = rng.uniform(-0.85, 0.85, (8, 8))

        target = rng.normal(0.0, 1.0, (len(Xb), 64))

        def loss_fn(Wv):
            F = twin.forward_cached(E_cells, Wv)
            return 0.5 * float(np.sum((F - target) ** 2)), F

        _, F0 = loss_fn(W)
        g_analytic = twin.backward_cached(E_cells, W, F0 - target)

        eps = 1e-6
        g_num = np.zeros_like(W)
        for i in range(8):
            for j in range(8):
                Wp = W.copy(); Wp[i, j] += eps
                Wm = W.copy(); Wm[i, j] -= eps
                lp, _ = loss_fn(Wp)
                lm, _ = loss_fn(Wm)
                g_num[i, j] = (lp - lm) / (2.0 * eps)

        rel_err = np.linalg.norm(g_analytic - g_num) / (np.linalg.norm(g_num) + 1e-15)
        durum = "✓ TAM UYUM" if rel_err < 1e-6 else "✗ HATA"
        print(f"  Mod: {mode:8s} · Bağıl L2 türev hatası = {rel_err:.3e}  [{durum}]")

    # v0.6 çok-katmanlı (MultiPass L=2/L=3) ve kalibre vekil (CalibratedSurrogateTwin) adjoint testleri
    for label, n_lay, mod_t in [
        ("mp_L2_j", 2, "jones"),
        ("mp_L3_p", 3, "phase"),
    ]:
        mp = FoldedMultiPassTwin(n_grid=64, n_ito=8, cam_n=8, n_layers=n_lay, modulation=mod_t, differential=True)
        W_lst = [rng.uniform(1.3, 4.5, (8, 8)) for _ in range(n_lay)]
        Ec_mp = mp.field_at_cell(Xb, dtype=np.complex128)
        tgt_mp = rng.normal(0.0, 1.0, (len(Xb), 64))
        F0_mp, E_bef, M_lst = mp.forward_cached(Ec_mp, W_lst, return_cache=True)
        g_mp = mp.backward_cached(E_bef, M_lst, W_lst, F0_mp - tgt_mp)
        eps = 1e-6
        g_num_l = np.zeros((8, 8))
        for i in range(8):
            for j in range(8):
                Wp = W_lst[0].copy(); Wp[i, j] += eps
                Wm = W_lst[0].copy(); Wm[i, j] -= eps
                lp = 0.5 * float(np.sum((mp.forward_cached(Ec_mp, [Wp] + W_lst[1:]) - tgt_mp) ** 2))
                lm = 0.5 * float(np.sum((mp.forward_cached(Ec_mp, [Wm] + W_lst[1:]) - tgt_mp) ** 2))
                g_num_l[i, j] = (lp - lm) / (2.0 * eps)
        err_mp = np.linalg.norm(g_mp[0] - g_num_l) / (np.linalg.norm(g_num_l) + 1e-15)
        durum_mp = "✓ TAM UYUM" if err_mp < 1e-5 else "✗ HATA"
        print(f"  Mod: {label:8s} · Bağıl L2 türev hatası = {err_mp:.3e}  [{durum_mp}]")

    tw_base = ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode="active")
    phi_pert = PHI_TAB * np.array([0.92, 0.94, 1.05, 0.91, 1.07, 0.95])
    cal_tw = CalibratedSurrogateTwin(
        tw_base, phi_pert, gamma_hat=0.88,
        gain_map=rng.uniform(0.7, 1.3, 64), shifts=(1, 0, 0, 1),
    )
    W_c = rng.uniform(1.3, 4.5, (8, 8))
    Ec_c = cal_tw.field_at_cell(Xb)
    tgt_c = rng.normal(0.0, 1.0, (len(Xb), 64))
    F0_c = cal_tw.forward_cached(Ec_c, W_c)
    g_ca = cal_tw.backward_cached(Ec_c, W_c, F0_c - tgt_c)
    g_cn = np.zeros_like(W_c)
    eps = 1e-6
    for i in range(8):
        for j in range(8):
            Wp = W_c.copy(); Wp[i, j] += eps
            Wm = W_c.copy(); Wm[i, j] -= eps
            lp = 0.5 * float(np.sum((cal_tw.forward_cached(Ec_c, Wp) - tgt_c) ** 2))
            lm = 0.5 * float(np.sum((cal_tw.forward_cached(Ec_c, Wm) - tgt_c) ** 2))
            g_cn[i, j] = (lp - lm) / (2.0 * eps)
    err_cal = np.linalg.norm(g_ca - g_cn) / (np.linalg.norm(g_cn) + 1e-15)
    durum_c = "✓ TAM UYUM" if err_cal < 1e-5 else "✗ HATA"
    print(f"  Mod: cal_twin · Bağıl L2 türev hatası = {err_cal:.3e}  [{durum_c}]")

    # Alt-Pleshko teorik üst sınır kontrolü
    U_off = np.full((16, 16), -1.0)
    U_on  = np.full((16, 16), +1.0)
    v_off = passive_matrix_rms(U_off).mean()
    v_on  = passive_matrix_rms(U_on).mean()
    teorik = np.sqrt((np.sqrt(16) + 1.0) / (np.sqrt(16) - 1.0))
    print("─" * 66)
    print(f"  Alt-Pleshko 16×16 RMS kontrolü: V_off={v_off:.4f}V, V_on={v_on:.4f}V")
    print(f"  Ölçülen oran = {v_on / v_off:.6f}  |  Teorik √(5/3) = {teorik:.6f}")
    print(f"  Aktif faz aralığı = {lc_phase(1.0) - lc_phase(5.0):.2f} rad vs "
          f"Pasif matris faz aralığı = {lc_phase(v_off) - lc_phase(v_on):.2f} rad")
    print("═" * 66)


# ─────────────────────────────────────────────────────────────────
#  AŞAMA 2 YEDEK — SPSA (VERİ SIZINTISIZ)
# ─────────────────────────────────────────────────────────────────
def spsa_train(twin, E_cells, y, W0, steps, rng, n_cls=5, lr=0.25, c_pert=0.15):
    n = len(y)
    n_tr = int(n * 0.7)
    Y_val = np.eye(n_cls)[y[n_tr:]]
    W = W0.copy()
    w_bounds = (-1.0, 1.0) if twin.drive_mode == "passive" else (0.0, 5.0)
    history = []

    def loss_of(Wv):
        F = twin.forward_cached(E_cells, Wv)
        F_std, _, _ = standardize_split(F, n_tr)             # sızıntısız!
        Wout = fit_ridge(F_std[:n_tr], y[:n_tr], n_cls)
        Fb   = np.hstack([F_std[n_tr:], np.ones((n - n_tr, 1))])
        P    = Fb @ Wout
        mse  = float(((P - Y_val) ** 2).mean())
        acc  = float((np.argmax(P, axis=1) == y[n_tr:]).mean())
        return mse, acc

    best_W, best_mse = W.copy(), float("inf")
    for k in range(steps):
        a_k = lr / (k + 6) ** 0.602
        c_k = c_pert / (k + 1) ** 0.101
        delta   = rng.choice([-1.0, 1.0], size=W.shape)
        Wp      = np.clip(W + c_k * delta, w_bounds[0], w_bounds[1])
        Wm      = np.clip(W - c_k * delta, w_bounds[0], w_bounds[1])
        Lp, ap  = loss_of(Wp)
        Lm, am  = loss_of(Wm)
        g_hat   = (Lp - Lm) / (2.0 * c_k) * delta
        W       = np.clip(W - a_k * g_hat, w_bounds[0], w_bounds[1])
        cur_mse = min(Lp, Lm)
        if cur_mse < best_mse:
            best_mse = cur_mse
            best_W = (Wp if Lp < Lm else Wm).copy()
        history.append(cur_mse)
        print(f"  SPSA {k + 1:3d}/{steps} · val MSE {cur_mse:.4f} · "
              f"val dogruluk %{max(ap, am) * 100:.1f}")
    return best_W, history


# ─────────────────────────────────────────────────────────────────
#  ABLASYON ÇALIŞMASI (TAM SIZINTISIZ MAKALE KONTROL TABLOSU)
# ─────────────────────────────────────────────────────────────────
def pool_area(imgs, cam_n=8):
    """28×28 girişleri 32×32'ye ortalayıp blok alan ortalaması (area average) ile cam_n×cam_n'e indirger."""
    imgs = np.asarray(imgs, dtype=float)
    B = imgs.shape[0]
    pad = np.zeros((B, 32, 32), dtype=float)
    pad[:, 2:30, 2:30] = imgs
    if 32 % cam_n == 0:
        b = 32 // cam_n
        return pad.reshape(B, cam_n, b, cam_n, b).mean(axis=(2, 4)).reshape(B, -1)
    edges = np.linspace(0, 32, cam_n + 1).astype(int)
    out = np.zeros((B, cam_n, cam_n), dtype=float)
    for r in range(cam_n):
        for c in range(cam_n):
            out[:, r, c] = pad[:, edges[r]:edges[r + 1], edges[c]:edges[c + 1]].mean(axis=(1, 2))
    return out.reshape(B, -1)


def fit_pca_features(X_tr, X_te, k=64):
    """Yalnızca eğitim kümesi (X_tr) üzerinde SVD ile PCA-k izdüşümü kurar (sıfır veri sızıntısı)."""
    Xf_tr = X_tr.reshape(len(X_tr), -1).astype(float)
    Xf_te = X_te.reshape(len(X_te), -1).astype(float)
    mean = Xf_tr.mean(axis=0, keepdims=True)
    Xc_tr = Xf_tr - mean
    Xc_te = Xf_te - mean
    _, _, Vt = np.linalg.svd(Xc_tr, full_matrices=False)
    comp = Vt[:k].T
    return Xc_tr @ comp, Xc_te @ comp


def run_ablation(n_train=3000, n_test=1000, cam_n=8, grid=128, seed=7,
                 epochs_lin=18, epochs_mlp=40, bs=128):
    """Akademik makale için tam sızıntısız kontrollü ablasyon deneyi:
    Doğrulama kümesi (X_val, y_val) yalnızca X_tr içinden ayrılır; X_te sadece son ölçümde kullanılır.
    v0.5: kontrol satırları PAT ile aynı CE-Adam lineer kafayı kullanır (eşleşmiş başlık);
    MLP satırları da aynı epok bütçesini (epochs_mlp) paylaşır."""
    t_ab = time.time()
    rng = np.random.default_rng(seed)
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mnist_cache")
    X, y, n_tr = load_mnist(n_train, n_test, rng, cache)
    X_tr, y_tr = X[:n_tr], y[:n_tr]
    X_te, y_te = X[n_tr:], y[n_tr:]
    n_cls = 10

    n_val = max(100, int(round(0.12 * n_tr)))
    n_fit = n_tr - n_val
    X_fit, y_fit = X_tr[:n_fit], y_tr[:n_fit]
    X_val, y_val = X_tr[n_fit:], y_tr[n_fit:]

    d_feat = cam_n ** 2
    d_lin_params = (d_feat + 1) * n_cls

    print("═" * 82, flush=True)
    print(f"  AKADEMİK ABLASYON DENEYİ · MNIST (Fit={n_fit}, Val={n_val}, Test={n_test}, Seed={seed})", flush=True)
    print(f"  Izgara={grid}² · Dedektör={cam_n}×{cam_n} ({d_feat} özellik) · Tam sızıntısız", flush=True)
    print("═" * 82, flush=True)
    rows = []

    def eval_ridge_feats(F_tr_raw, F_te_raw):
        """Diyagnostik kapalı-form Ridge okuyucu (tüm X_tr üzerinde, α sabit)."""
        mu_f, sd_f = fit_standardizer(F_tr_raw)
        W_f = fit_ridge(apply_standardizer(F_tr_raw, mu_f, sd_f), y_tr, n_cls)
        return float((predict_ridge(apply_standardizer(F_te_raw, mu_f, sd_f), W_f) == y_te).mean())

    def eval_ce_feats(F_tr_raw, F_te_raw, head_rng, F_tr_noisy=None):
        """PAT ile eşleşmiş CE-Adam lineer kafa: aynı 2640/360 fit/val bölmesi,
        aynı epok (epochs_lin), aynı lr_head ve aynı batch boyutu. Ölçekleyici
        gürültüsüz fit özelliklerinden kurulur; kafa gürültülü fit özellikleriyle
        eğitilir (PAT satır 904/873 paritesi), val/test gürültüsüz ölçülür."""
        mu_f, sd_f = fit_standardizer(F_tr_raw[:n_fit])
        F_fit = F_tr_raw[:n_fit] if F_tr_noisy is None else F_tr_noisy[:n_fit]
        W_f = _fit_ce_linear_head(
            apply_standardizer(F_fit, mu_f, sd_f), y_fit,
            apply_standardizer(F_tr_raw[n_fit:], mu_f, sd_f), y_val,
            n_cls, epochs=epochs_lin, bs=bs, lr_head=2.5e-2, rng=head_rng)
        return float((predict_ridge(apply_standardizer(F_te_raw, mu_f, sd_f), W_f) == y_te).mean())

    # 1) Kontrol A: Gerçek 8×8 alan-ortalaması (optik yok) + Lineer (CE)
    F_area_tr = pool_area(X_tr, cam_n)
    F_area_te = pool_area(X_te, cam_n)
    acc_area_lin = eval_ce_feats(F_area_tr, F_area_te, np.random.default_rng(seed + 901))
    rows.append(("digital_area_linear", "1. Dijital Alan Havuzlama (Optik Yok) + Lineer", 0, d_lin_params,
                 acc_area_lin, eval_ridge_feats(F_area_tr, F_area_te)))

    # 2) Kontrol B: Yalnız eğitim verisiyle PCA-64 (optik yok) + Lineer (CE)
    F_pca_tr, F_pca_te = fit_pca_features(X_tr, X_te, k=d_feat)
    acc_pca_lin = eval_ce_feats(F_pca_tr, F_pca_te, np.random.default_rng(seed + 902))
    rows.append(("digital_pca_linear", f"2. Dijital PCA-{d_feat} (Optik Yok) + Lineer", 0, d_lin_params,
                 acc_pca_lin, eval_ridge_feats(F_pca_tr, F_pca_te)))

    # 3) Kontrol C: Yalnız serbest uzay kırınımı (LC yok) + Lineer (CE)
    twin_none = ZerreTwin(grid, n_ito=16, cam_n=cam_n, drive_mode="none")
    F_free_tr = twin_none.forward_batch(X_tr, np.zeros((16, 16)), batch_size=256)
    F_free_te = twin_none.forward_batch(X_te, np.zeros((16, 16)), batch_size=256)
    acc_free = eval_ce_feats(F_free_tr, F_free_te, np.random.default_rng(seed + 903))
    rows.append(("free_space_linear", "3. Yalnız Serbest Uzay Kırınımı (LC Yok) + Lineer", 0, d_lin_params,
                 acc_free, eval_ridge_feats(F_free_tr, F_free_te)))

    # Ortak ön-hesaplama: Z1 yayılımı yalnızca grid ve X'e bağlıdır (tek kopya → düşük RAM, hızlı PAT)
    twin_pas  = ZerreTwin(grid, n_ito=16, cam_n=cam_n, drive_mode="passive")
    twin_act  = ZerreTwin(grid, n_ito=16, cam_n=cam_n, drive_mode="active")
    twin_lcd2 = ZerreTwin(grid, n_ito=32, cam_n=cam_n, drive_mode="active")
    plant_pas  = PhysicalPlantSimulator(twin_pas, seed=seed)
    plant_act  = PhysicalPlantSimulator(twin_act, seed=seed + 1)
    plant_lcd2 = PhysicalPlantSimulator(twin_lcd2, seed=seed + 2)

    E_phy_tr = plant_act.precompute_cells(X_tr, batch_size=256)
    E_phy_te = plant_act.precompute_cells(X_te, batch_size=256)
    E_sur_fit = np.concatenate(
        [twin_act.prop1(twin_act.encode_lcd(X_fit[i:i + 256]).astype(np.complex64))
         for i in range(0, len(X_fit), 256)], axis=0
    )
    pre_pack = {
        "E_sur_tr": E_sur_fit,
        "E_phy_tr": E_phy_tr[:n_fit],
        "E_phy_val": E_phy_tr[n_fit:],
    }

    # 4) Pasif Matris 16×16 (Alt-Pleshko RMS) — Rastgele + Lineer (CE; gürültülü fit / gürültüsüz ölçüm)
    U_rand = rng.uniform(-1.0, 1.0, (16, 16))
    F_pr_tr = plant_pas.forward_cached(E_phy_tr, U_rand, noisy=False)
    F_pr_te = plant_pas.forward_cached(E_phy_te, U_rand, noisy=False)
    F_pr_tr_n = plant_pas.forward_cached(E_phy_tr[:n_fit], U_rand, noisy=True)
    acc_pas_rand = eval_ce_feats(F_pr_tr, F_pr_te, np.random.default_rng(seed + 904), F_tr_noisy=F_pr_tr_n)
    rows.append(("passive_16_random_linear", "4. Pasif Matris 16×16 (Rastgele, Kusurlu) + Lineer", 256, d_lin_params,
                 acc_pas_rand, eval_ridge_feats(F_pr_tr, F_pr_te)))

    # 5) Aktif Matris 16×16 — Rastgele + Lineer (CE)
    V_rand16 = rng.uniform(1.2, 3.5, (16, 16))
    F_ar_tr = plant_act.forward_cached(E_phy_tr, V_rand16, noisy=False)
    F_ar_te = plant_act.forward_cached(E_phy_te, V_rand16, noisy=False)
    F_ar_tr_n = plant_act.forward_cached(E_phy_tr[:n_fit], V_rand16, noisy=True)
    acc_act_rand = eval_ce_feats(F_ar_tr, F_ar_te, np.random.default_rng(seed + 905), F_tr_noisy=F_ar_tr_n)
    rows.append(("active_16_random_linear", "5. Aktif Matris 16×16 (Rastgele, Kusurlu) + Lineer", 256, d_lin_params,
                 acc_act_rand, eval_ridge_feats(F_ar_tr, F_ar_te)))

    # 6) 2. mSLA TFT-LCD 32×32 — Rastgele + Lineer (CE; eşleşmiş kontrol)
    V_rand32 = rng.uniform(1.2, 3.5, (32, 32))
    F_a32_tr = plant_lcd2.forward_cached(E_phy_tr, V_rand32, noisy=False)
    F_a32_te = plant_lcd2.forward_cached(E_phy_te, V_rand32, noisy=False)
    F_a32_tr_n = plant_lcd2.forward_cached(E_phy_tr[:n_fit], V_rand32, noisy=True)
    acc_act32_rand = eval_ce_feats(F_a32_tr, F_a32_te, np.random.default_rng(seed + 906), F_tr_noisy=F_a32_tr_n)
    rows.append(("active_32_random_linear", "6. 2. LCD 32×32 Aktif (Rastgele, Kusurlu) + Lineer", 1024, d_lin_params,
                 acc_act32_rand, eval_ridge_feats(F_a32_tr, F_a32_te)))
    print(f"  [Seed {seed}] Dijital + Rastgele kontroller tamam ({time.time() - t_ab:.1f}s)", flush=True)

    # 7) Pasif Matris 16×16 + PAT (X_val üzerinde erken durdurma)
    W_pat_p, mu_p, sd_p, Wout_p, _, _, fwd_p = pat_train(
        twin_pas, X_fit, y_fit, X_val, y_val, U_rand, n_cls,
        epochs=epochs_lin, bs=bs, lr_opt=0.09, lr_head=2.5e-2,
        physical_plant=plant_pas, use_mlp=False, rng=np.random.default_rng(seed + 101),
        verbose=False, precomputed=pre_pack
    )
    F_te_p = fwd_p(E_phy_te, W_pat_p, False)
    acc_pas_pat = float((predict_ridge((F_te_p - mu_p) / sd_p, Wout_p) == y_te).mean())
    F_tr_p = np.vstack([fwd_p(E_phy_tr[i:i + 256], W_pat_p, False) for i in range(0, n_tr, 256)])
    rows.append(("passive_16_pat_linear", "7. Pasif Matris 16×16 + PAT (Kusurlu) + Lineer", 256, d_lin_params,
                 acc_pas_pat, eval_ridge_feats(F_tr_p, F_te_p)))
    print(f"  [Seed {seed}] Pasif 16×16 PAT tamam: %{acc_pas_pat * 100:.2f} ({time.time() - t_ab:.1f}s)", flush=True)

    # 8) Aktif Matris 16×16 + PAT
    W_pat_a, mu_a, sd_a, Wout_a, _, _, fwd_a = pat_train(
        twin_act, X_fit, y_fit, X_val, y_val, V_rand16, n_cls,
        epochs=epochs_lin, bs=bs, lr_opt=0.09, lr_head=2.5e-2,
        physical_plant=plant_act, use_mlp=False, rng=np.random.default_rng(seed + 202),
        verbose=False, precomputed=pre_pack
    )
    F_te_a = fwd_a(E_phy_te, W_pat_a, False)
    acc_act_pat = float((predict_ridge((F_te_a - mu_a) / sd_a, Wout_a) == y_te).mean())
    F_tr_a = np.vstack([fwd_a(E_phy_tr[i:i + 256], W_pat_a, False) for i in range(0, n_tr, 256)])
    rows.append(("active_16_pat_linear", "8. Aktif Matris 16×16 + PAT (Kusurlu) + Lineer", 256, d_lin_params,
                 acc_act_pat, eval_ridge_feats(F_tr_a, F_te_a)))
    print(f"  [Seed {seed}] Aktif 16×16 PAT tamam: %{acc_act_pat * 100:.2f} ({time.time() - t_ab:.1f}s)", flush=True)

    # 9) 2. LCD 32×32 Aktif + PAT + Lineer
    W_pat_32, mu_32, sd_32, Wout_32, _, _, fwd_32 = pat_train(
        twin_lcd2, X_fit, y_fit, X_val, y_val, V_rand32, n_cls,
        epochs=epochs_lin, bs=bs, lr_opt=0.09, lr_head=2.5e-2,
        physical_plant=plant_lcd2, use_mlp=False, rng=np.random.default_rng(seed + 303),
        verbose=False, precomputed=pre_pack
    )
    F_te_32 = fwd_32(E_phy_te, W_pat_32, False)
    acc_lcd2_pat = float((predict_ridge((F_te_32 - mu_32) / sd_32, Wout_32) == y_te).mean())
    F_tr_32 = np.vstack([fwd_32(E_phy_tr[i:i + 256], W_pat_32, False) for i in range(0, n_tr, 256)])
    rows.append(("active_32_pat_linear", "9. 2. LCD 32×32 Aktif + PAT (Kusurlu) + Lineer", 1024, d_lin_params,
                 acc_lcd2_pat, eval_ridge_feats(F_tr_32, F_te_32)))
    print(f"  [Seed {seed}] Aktif 32×32 PAT Lin tamam: %{acc_lcd2_pat * 100:.2f} ({time.time() - t_ab:.1f}s)", flush=True)

    # 10) Eşleşmiş Dijital Kontrol: 8×8 Alan Havuzlama (Optik Yok) + 256-Nöron MLP
    mu_am, sd_am = fit_standardizer(F_area_tr[:n_fit])
    mlp_area = MLPHead(d_feat, 256, n_cls, np.random.default_rng(seed + 404))
    mlp_area.train(
        apply_standardizer(F_area_tr[:n_fit], mu_am, sd_am), y_fit,
        apply_standardizer(F_area_tr[n_fit:], mu_am, sd_am), y_val,
        epochs=epochs_mlp, bs=bs, lr=2e-3, verbose=False
    )
    acc_area_mlp = float((mlp_area.predict(apply_standardizer(F_area_te, mu_am, sd_am)) == y_te).mean())
    rows.append(("digital_area_mlp", "10. Dijital Alan Havuzlama (Optik Yok) + MLP", 0, mlp_area.n_params(), acc_area_mlp, None))

    # 11) 2. LCD 32×32 Aktif + PAT + Hibrit MLP (epok bütçesi kontrolle eşit)
    W_pat_h, mu_h, sd_h, _, mlp_h, _, fwd_h = pat_train(
        twin_lcd2, X_fit, y_fit, X_val, y_val, V_rand32, n_cls,
        epochs=epochs_mlp, bs=bs, lr_opt=0.07, lr_head=2.5e-3,
        physical_plant=plant_lcd2, use_mlp=True, rng=np.random.default_rng(seed + 505),
        verbose=False, precomputed=pre_pack
    )
    F_te_h = fwd_h(E_phy_te, W_pat_h, False)
    acc_hyb_pat = float((mlp_h.predict((F_te_h - mu_h) / sd_h) == y_te).mean())
    rows.append(("active_32_pat_mlp", "11. 2. LCD 32×32 Aktif + PAT + Hibrit MLP", 1024, mlp_h.n_params(), acc_hyb_pat, None))

    del E_phy_tr, E_phy_te, E_sur_fit, pre_pack
    gc.collect()

    print(f"  {'Mimari / Konfigürasyon':54s} {'Optik W':>7s} {'Dijital W':>9s} {'TEST':>7s}", flush=True)
    print("  " + "─" * 78, flush=True)
    for _, name, ow, dw, acc, _ in rows:
        print(f"  {name:54s} {ow:7d} {dw:9,d} %{acc * 100:5.2f}", flush=True)
    print("═" * 82, flush=True)
    return {
        "config": {"n_train": n_tr, "n_fit": n_fit, "n_val": n_val, "n_test": n_test,
                   "cam_n": cam_n, "grid": grid, "seed": seed,
                   "head": "matched_ce_adam", "ridge_is_diagnostic": True},
        "rows": [
            {"key": k, "label": lbl, "opt_w": ow, "dig_w": dw, "acc_pct": round(acc * 100.0, 2),
             "acc_ridge_pct": (round(acc_r * 100.0, 2) if acc_r is not None else None)}
            for k, lbl, ow, dw, acc, acc_r in rows
        ],
    }


# ─────────────────────────────────────────────────────────────────
#  FOTOĞRAF YÜKLEME, MODEL KAYDI VE WEB ÇIKARIM API'Sİ
# ─────────────────────────────────────────────────────────────────
def load_photo(path):
    """PNG/JPG fotoğrafı yükle → 28×28 MNIST formatına getir."""
    try:
        from PIL import Image
        arr = np.asarray(Image.open(path).convert("L"), dtype=float) / 255.0
    except ImportError:
        import matplotlib.image as mpimg
        arr = mpimg.imread(path)
        if arr.ndim == 3:
            arr = arr[..., :3].mean(axis=-1)

    H, W = arr.shape
    yi = np.linspace(0, H - 1, 28)
    xi = np.linspace(0, W - 1, 28)
    y0 = np.floor(yi).astype(int); x0 = np.floor(xi).astype(int)
    y1 = np.minimum(y0 + 1, H - 1); x1 = np.minimum(x0 + 1, W - 1)
    wy = (yi - y0)[:, None]; wx = (xi - x0)[None, :]
    a = arr[np.ix_(y0, x0)] * (1 - wy) * (1 - wx) + arr[np.ix_(y0, x1)] * (1 - wy) * wx \
      + arr[np.ix_(y1, x0)] * wy * (1 - wx)       + arr[np.ix_(y1, x1)] * wy * wx

    if a.mean() > 0.5:
        a = 1.0 - a
    mn, mx = a.min(), a.max()
    return (a - mn) / (mx - mn + 1e-9)


def save_model(path, W_volt, mu, sd, Wout, mlp, grid, cam_n, n_cls,
               n_ito=N_ITO, drive_mode="active", metadata=None):
    data = dict(
        W_volt=W_volt, mu=mu, sd=sd,
        grid=int(grid), cam_n=int(cam_n), n_cls=int(n_cls),
        n_ito=int(n_ito), drive_mode=str(drive_mode),
    )
    if Wout is not None:
        data["Wout"] = Wout
    if mlp is not None:
        data.update(mlp_W1=mlp.W1, mlp_b1=mlp.b1, mlp_W2=mlp.W2, mlp_b2=mlp.b2)
    if metadata is not None:
        data["metadata_json"] = np.array(json.dumps(metadata, ensure_ascii=False))
    np.savez_compressed(path, **data)
    print(f"[MODEL] kaydedildi: {path} (n_ito={n_ito}, mod={drive_mode})")


def load_twin_from_npz(model_path):
    """Kaydedilmiş .npz modelini ve uyumlu ZerreTwin nesnesini belleğe yükler."""
    with np.load(model_path, allow_pickle=False) as raw:
        d = {k: raw[k] for k in raw.files}
    if "metadata_json" in d:
        try:
            d["metadata"] = json.loads(str(d["metadata_json"]))
        except Exception:
            pass
    grid  = int(d["grid"])
    cam_n = int(d["cam_n"])
    n_cls = int(d["n_cls"])
    W_v   = d["W_volt"]
    n_ito = int(d["n_ito"]) if "n_ito" in d else int(W_v.shape[0])
    mode  = str(d["drive_mode"]) if "drive_mode" in d else "active"
    twin  = ZerreTwin(n_grid=grid, n_ito=n_ito, cam_n=cam_n, drive_mode=mode)
    return twin, d


def downsample_2d(arr, target=64):
    """Görselleştirme için 2B diziyi (target × target) boyutuna hızlıca küçültür."""
    H, W = arr.shape
    if H <= target and W <= target:
        mx = float(arr.max())
        return (arr / (mx + 1e-12)).tolist()
    ph, pw = H // target, W // target
    sub = arr[:ph * target, :pw * target].reshape(target, ph, target, pw).mean(axis=(1, 3))
    mx = float(sub.max())
    return np.round(sub / (mx + 1e-12), 4).tolist()


def infer_array(img28, twin, model_dict, map_size=64):
    """28×28 görüntü üzerinde tam optik zinciri çalıştırır; Web UI ve CLI için
    olasılıkları ve fiziksel alan haritalarını döner."""
    t0 = time.perf_counter()
    img = np.clip(np.asarray(img28, dtype=float), 0.0, 1.0)
    mx, mn = float(img.max()), float(img.min())
    if mx - mn > 1e-6:
        img = (img - mn) / (mx - mn)

    info = twin.inspect_forward(img, model_dict["W_volt"])
    feat = info["feat"]
    f = (feat - model_dict["mu"]) / model_dict["sd"]

    if "mlp_W1" in model_dict:
        h = np.maximum(0.0, f @ model_dict["mlp_W1"] + model_dict["mlp_b1"])
        z = h @ model_dict["mlp_W2"] + model_dict["mlp_b2"]
        head_type = "Hibrit MLP"
    else:
        z = np.hstack([f, 1.0]) @ model_dict["Wout"]
        head_type = "Ridge Lineer"

    z = z - z.max()
    probs = np.exp(z)
    probs /= probs.sum()
    pred = int(np.argmax(probs))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Görselleştirme için gama düzeltmeli CMOS yoğunluğu ve Z1 kırınım alanı
    cmos_gamma = np.power(np.maximum(info["I_cam"], 0.0), 0.42)
    phase_norm = info["ito_phase"] / 5.0  # [0, ~5 rad] → [0, 1]

    return {
        "prediction": pred,
        "confidence": float(probs[pred]),
        "probs":      [round(float(x), 5) for x in probs],
        "head_type":  head_type,
        "drive_mode": twin.drive_mode,
        "n_ito":      twin.n_ito,
        "cam_n":      twin.cam_n,
        "grid":       twin.N,
        "compute_ms": round(elapsed_ms, 2),
        "maps": {
            "input28":  np.round(img, 3).tolist(),
            "diffract": downsample_2d(info["E_cell_amp"], map_size),
            "phase":    np.round(np.clip(phase_norm, 0.0, 1.0), 4).tolist(),
            "cmos":     downsample_2d(cmos_gamma, map_size),
        },
    }


def predict_photo(img_path, model_path):
    twin, d = load_twin_from_npz(model_path)
    img = load_photo(img_path)
    print(f"[TAHMIN] '{img_path}' optik zincirden geciriliyor "
          f"(LCD → kirinim → {twin.n_ito}×{twin.n_ito} {twin.drive_mode} ITO → CMOS)...")
    res = infer_array(img, twin, d)
    probs = np.array(res["probs"])
    top = np.argsort(probs)[::-1][:3]
    print(f"[TAHMIN] okuma kafasi: {res['head_type']} · sure: {res['compute_ms']:.1f} ms")
    for r, c in enumerate(top):
        bar = "█" * int(probs[c] * 40)
        print(f"  {r + 1}. sinif {c}  %{probs[c] * 100:5.1f}  {bar}")
    print(f"[SONUC] tahmin = {res['prediction']}")
    return res["prediction"]


# ─────────────────────────────────────────────────────────────────
#  MEKANİK DAYANIM VE ÇEVRESEL HASSASİYET TESTLERİ
# ─────────────────────────────────────────────────────────────────
def forward_perturbed(twin, img, W_volt, lcd_px=0, ito_px=0, dz1_mm=0.0, cam_px=0):
    """Tek eksenli yatay yanal kaymalar (lcd_px, ito_px, cam_px * 47μm) ve eksenel dz1_mm uygular.
    Yanal kaymalar kenar-kayıplıdır (shift_crop): ışık kenardan kaybolur, sarma artefaktı yok."""
    E = twin.encode_lcd(img)
    if lcd_px:
        E = shift_crop(E, 0, lcd_px)
    if dz1_mm:
        prop = AngularSpectrum(twin.N, PIX, LAMBDA, Z1 + dz1_mm * 1e-3)
        E = prop(E)
    else:
        E = twin.prop1(E)
    M = twin.ito_mask(W_volt)
    if ito_px:
        M = shift_crop(M, 0, ito_px)
    E = twin.prop2(E * M)
    I = np.abs(E) ** 2
    if cam_px:
        I = shift_crop(I, 0, cam_px)
    p = twin.N // twin.cam_n
    lim = p * twin.cam_n
    if I.ndim == 2:
        return I[:lim, :lim].reshape(twin.cam_n, p, twin.cam_n, p).mean(axis=(1, 3)).ravel()
    B = I.shape[0]
    return I[:, :lim, :lim].reshape(B, twin.cam_n, p, twin.cam_n, p).mean(axis=(2, 4)).reshape(B, -1)


def _resolve_model(model_or_tuple):
    if isinstance(model_or_tuple, tuple):
        return model_or_tuple
    return load_twin_from_npz(model_or_tuple)


def robustness_test(model_or_tuple, n_test=1000, seed=7):
    twin, d = _resolve_model(model_or_tuple)
    rng   = np.random.default_rng(seed)
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mnist_cache")
    X, y, _ = load_mnist(0, n_test, rng, cache)

    def head(F):
        f = (F - d["mu"]) / d["sd"]
        if "mlp_W1" in d:
            h = np.maximum(0.0, f @ d["mlp_W1"] + d["mlp_b1"])
            return np.argmax(h @ d["mlp_W2"] + d["mlp_b2"], axis=1)
        return np.argmax(np.hstack([f, np.ones((len(f), 1))]) @ d["Wout"], axis=1)

    def acc_under(**kw):
        F = forward_perturbed(twin, X, d["W_volt"], **kw)
        return float((head(F) == y).mean()) * 100.0

    um = PIX * 1e6
    print("═" * 68)
    print(f"  MEKANİK DAYANIM TESTİ · {n_test} MNIST test örneği (Seed={seed})")
    print(f"  (1 ızgara pikseli = {um:.0f}μm tek-eksenli yanal kayma)")
    print("═" * 68)

    base = acc_under()
    shift_px = [0, 1, 2, 4]
    lcd_map, ito_map, cam_map = {}, {}, {}
    for px in shift_px:
        key = str(int(round(px * um)))
        lcd_map[key] = round(base if px == 0 else acc_under(lcd_px=px), 2)
        ito_map[key] = round(base if px == 0 else acc_under(ito_px=px), 2)
        cam_map[key] = round(base if px == 0 else acc_under(cam_px=px), 2)

    dz_list = [0.0, 1.0, 3.0, 8.0]
    dz_map = {str(dz): round(base if dz == 0.0 else acc_under(dz1_mm=dz), 2) for dz in dz_list}
    comb = round(acc_under(lcd_px=1, ito_px=1, dz1_mm=1.0, cam_px=1), 2)

    print(f"  ✓ Temel (hizali)                 %{base:5.2f}")
    for key in ["47", "94", "188"]:
        print(f"  • LCD {key:>3s}μm: %{lcd_map[key]:5.2f}  |  LC {key:>3s}μm: %{ito_map[key]:5.2f}  |  CMOS {key:>3s}μm: %{cam_map[key]:5.2f}")
    for dz_k in ["1.0", "3.0", "8.0"]:
        print(f"  • Eksenel ΔZ1=+{dz_k}mm           %{dz_map[dz_k]:5.2f}")
    print(f"  • Kombine (hepsi 47μm + 1mm)     %{comb:5.2f}  (fark {comb - base:+5.2f} puan)")
    print("═" * 68)

    return {
        "n_test": n_test,
        "seed": seed,
        "grid": twin.N,
        "base_acc": round(base, 2),
        "lcd_shifts_um": lcd_map,
        "ito_shifts_um": ito_map,
        "cam_shifts_um": cam_map,
        "axial_dz1_mm": dz_map,
        "combined_47um_1mm": comb,
    }


def haller_scale(T_c_deg):
    Tc, beta, Tref = 59.0, 0.22, 25.0
    if T_c_deg >= Tc:
        return 0.0
    return ((Tc - T_c_deg) / (Tc - Tref)) ** beta


def env_test(model_or_tuple, n_test=1000, seed=7):
    twin, d = _resolve_model(model_or_tuple)
    rng   = np.random.default_rng(seed)
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mnist_cache")
    X, y, _ = load_mnist(0, n_test, rng, cache)

    def head(F):
        f = (F - d["mu"]) / d["sd"]
        if "mlp_W1" in d:
            h = np.maximum(0.0, f @ d["mlp_W1"] + d["mlp_b1"])
            return np.argmax(h @ d["mlp_W2"] + d["mlp_b2"], axis=1)
        return np.argmax(np.hstack([f, np.ones((len(f), 1))]) @ d["Wout"], axis=1)

    def feats(phi_scale=1.0):
        return twin.forward_batch(X, d["W_volt"], phi_scale=phi_scale)

    print("═" * 70)
    print(f"  ÇEVRESEL HASSASİYET TESTİ · {n_test} MNIST test örneği (Seed={seed})")
    print("═" * 70)

    F0 = feats()
    base = float((head(F0) == y).mean()) * 100.0
    sinyal = float(F0.mean())
    print(f"  Temel (25°C, karanlık kutu)          dogruluk %{base:5.2f}")

    print("  " + "─" * 64)
    print("  1) SICAKLIK  (Δn(T) · Haller · T_c=59°C · kalibrasyonsuz)")
    temp_res = [{"temp_c": 25, "scale": 1.0, "acc": round(base, 2)}]
    for T in [20, 30, 35, 45, 55]:
        sc = haller_scale(T)
        a = float((head(feats(sc)) == y).mean()) * 100.0
        dus = a - base
        temp_res.append({"temp_c": T, "scale": round(sc, 4), "acc": round(a, 2)})
        isaret = "✓" if abs(dus) < 2 else ("⚠" if abs(dus) < 10 else "✗")
        print(f"  {isaret} T={T:2d}°C  (Δn ölçeği {sc:.3f})          "
              f"dogruluk %{a:5.2f}  ({dus:+5.2f} puan)")
    temp_res.sort(key=lambda x: x["temp_c"])

    def noisy_dark_subtract(F_noisy, dc_val):
        # 16 bağımsız gürültülü karanlık kareden ortalama arka plan kestirimi (oracle çıkarma yok!)
        sigma_d = np.sqrt(max(dc_val, 1e-12) * sinyal) * 0.05
        dark_frames = dc_val + rng.normal(0.0, sigma_d, (16, F_noisy.shape[1]))
        dark_est = np.maximum(dark_frames.mean(axis=0, keepdims=True), 0.0)
        return F_noisy - dark_est

    print("  " + "─" * 64)
    print("  2) ORTAM IŞIĞI  (16-kare gürültülü karanlık-kare kestirimi)")
    leak_res = [{"leak_pct": 0, "raw_acc": round(base, 2), "dark_sub_acc": round(base, 2)}]
    for leak in [0.01, 0.05, 0.20, 0.50]:
        dc = leak * sinyal
        gurultu = rng.normal(0.0, np.sqrt(max(dc, 1e-12) * sinyal) * 0.05, F0.shape)
        F_ham = F0 + dc + gurultu
        a_ham = float((head(F_ham) == y).mean()) * 100.0
        F_duz = noisy_dark_subtract(F_ham, dc)
        a_duz = float((head(F_duz) == y).mean()) * 100.0
        leak_res.append({"leak_pct": int(round(leak * 100)),
                         "raw_acc": round(a_ham, 2),
                         "dark_sub_acc": round(a_duz, 2)})
        print(f"  ✗ sizinti %{leak * 100:4.0f}  ham: %{a_ham:5.2f} ({a_ham - base:+6.2f})   "
              f"karanlık-kare ile: %{a_duz:5.2f} ({a_duz - base:+5.2f})")

    print("  " + "─" * 64)
    print("  3) LAZER GÜÇ KAYMASI  (tüm yoğunluk × (1+ε))")
    drift_res = []
    for eps in [0.02, 0.05, 0.10, -0.10]:
        a = float((head(F0 * (1.0 + eps)) == y).mean()) * 100.0
        drift_res.append({"eps": eps, "acc": round(a, 2)})
        isaret = "✓" if abs(a - base) < 2 else ("⚠" if abs(a - base) < 10 else "✗")
        print(f"  {isaret} ε = {eps:+.2f}                            "
              f"dogruluk %{a:5.2f}  ({a - base:+5.2f} puan)")

    print("  " + "─" * 64)
    dc = 0.01 * sinyal
    Fk_noise = rng.normal(0.0, np.sqrt(max(dc, 1e-12) * sinyal) * 0.05, F0.shape)
    Fk_ham = feats(haller_scale(30)) * 1.02 + dc + Fk_noise
    a_ham_c = float((head(Fk_ham) == y).mean()) * 100.0
    a_duz_c = float((head(noisy_dark_subtract(Fk_ham, dc)) == y).mean()) * 100.0
    print("  ✦ KOMBİNE (30°C + %1 sızıntı + %2 drift)")
    print(f"    ham: %{a_ham_c:5.2f} ({a_ham_c - base:+6.2f})   "
          f"karanlık-kare ile: %{a_duz_c:5.2f} ({a_duz_c - base:+5.2f})")
    print("═" * 70)

    return {
        "n_test": n_test,
        "seed": seed,
        "base_acc": round(base, 2),
        "temps": temp_res,
        "stray_light": leak_res,
        "laser_drift": drift_res,
        "combined_30C_1pct_2pct": {
            "raw_acc": round(a_ham_c, 2),
            "dark_sub_acc": round(a_duz_c, 2),
        },
    }


# ─────────────────────────────────────────────────────────────────
#  v0.3 GERÇEKÇİ DONANIM KISITLARI VE ÇOKLU VERİ KÜMESİ PAKETİ
# ─────────────────────────────────────────────────────────────────
def quantize_array(arr, bits, vmin, vmax):
    """Sonlu bit derinlikli DAC / HDMI sürücü basamaklama modeli."""
    if bits is None or bits >= 32:
        return np.clip(arr, vmin, vmax)
    levels = float((1 << int(bits)) - 1)
    step = (vmax - vmin) / levels
    clipped = np.clip(arr, vmin, vmax)
    return vmin + step * np.round((clipped - vmin) / step)


def make_zernike_aberration(n_grid, pv_waves, seed=101):
    """Ucuz float-cam yüzey eğriliği ve kolimatör sapmasını Zernike polinomları
    (Z4 odak, Z5/Z6 astigmatizma, Z7/Z8 koma, Z11 küresel sapma), soda-kireç dalgalanması
    ve Gauss lazer zarfı ile modeller. seed rastgele yönelim ve mod katsayılarını belirler."""
    rng_z = np.random.default_rng(seed)
    y_lin = np.linspace(-1.0, 1.0, n_grid)
    XX, YY = np.meshgrid(y_lin, y_lin, indexing="xy")
    RR = np.sqrt(XX ** 2 + YY ** 2)
    TH = np.arctan2(YY, XX)

    a_astig = float(rng_z.uniform(0.0, 2.0 * np.pi))
    a_coma  = float(rng_z.uniform(0.0, 2.0 * np.pi))
    p_r1    = float(rng_z.uniform(0.0, 2.0 * np.pi))
    p_r2    = float(rng_z.uniform(0.0, 2.0 * np.pi))
    w_m     = rng_z.uniform(0.6, 1.4, 5) * np.array([0.35, 0.25, 0.16, 0.12, 0.12])
    s_m     = rng_z.choice([-1.0, 1.0], 5)

    z_defocus = 2.0 * (RR ** 2) - 1.0
    z_astig   = (RR ** 2) * np.cos(2.0 * TH + a_astig)
    z_coma    = (3.0 * (RR ** 3) - 2.0 * RR) * np.cos(TH + a_coma)
    z_sph     = 6.0 * (RR ** 4) - 6.0 * (RR ** 2) + 1.0
    z_ripple  = np.sin(3.5 * np.pi * XX + p_r1) * np.cos(3.0 * np.pi * YY + p_r2)

    raw_wfe = (s_m[0] * w_m[0] * z_defocus
               + s_m[1] * w_m[1] * z_astig
               + s_m[2] * w_m[2] * z_coma
               + s_m[3] * w_m[3] * z_sph
               + s_m[4] * w_m[4] * z_ripple)

    if pv_waves <= 0.0:
        phi_ab = np.zeros_like(raw_wfe)
    else:
        span = float(raw_wfe.max() - raw_wfe.min()) + 1e-12
        phi_ab = (raw_wfe - raw_wfe.min()) / span * (2.0 * np.pi * float(pv_waves))

    # Gauss demet zarfı lazerin fiziksel özelliğidir — sapma PV'sinden bağımsız
    # her koşulda uygulanır (pv=0'da yapay basamak oluşmaz).
    beam_env = np.exp(-0.15 * (RR ** 2))
    return beam_env * np.exp(1j * phi_ab)


def make_subpixel_black_matrix(n_grid, block_offset, block_count, sub_px, fill_factor):
    """Makro-piksel alt-açıklık (fill-factor) maskesi.
    fill_factor ∈ (0, 1]: her makro-hücre alanının şeffaf yüzdesi."""
    if fill_factor >= 0.999:
        return np.ones((n_grid, n_grid), dtype=float)
    lin_open = np.sqrt(float(fill_factor))
    w1d = np.zeros(sub_px, dtype=float)
    open_len = lin_open * sub_px
    full_px = int(np.floor(open_len))
    frac_px = open_len - full_px
    start = (sub_px - full_px) // 2
    w1d[start:start + full_px] = 1.0
    if full_px < sub_px and frac_px > 1e-6:
        if start + full_px < sub_px:
            w1d[start + full_px] = frac_px
    cell2d = np.outer(w1d, w1d)
    if cell2d.mean() > 1e-9:
        cell2d = np.clip(cell2d * (fill_factor / cell2d.mean()), 0.0, 1.0)
    tiled = np.tile(cell2d, (block_count, block_count))
    M = np.zeros((n_grid, n_grid), dtype=float)
    sz = block_count * sub_px
    M[block_offset:block_offset + sz, block_offset:block_offset + sz] = tiled
    return M


def _run_zernike_once(mnist_dir, seed=7, n_test=1000):
    """Tek bir tohum için Zernike (0→15λ PV) + 3·Z1 Fabry-Pérot (0.04) testini çalıştırır.
    Üç eşleşmiş koşul döner: kalibrasyonsuz, yalnızca kafa-kalibrasyon kontrolü, ve PAT."""
    twin_z = ZerreTwin(n_grid=128, n_ito=32, cam_n=8, drive_mode="active")
    prop_ghost = AngularSpectrum(128, PIX, LAMBDA, 3.0 * Z1)
    X_z, y_z, n_trz = load_mnist(2200, n_test, np.random.default_rng(seed), mnist_dir)
    X_trz, y_trz = X_z[:n_trz], y_z[:n_trz]
    X_tez, y_tez = X_z[n_trz:], y_z[n_trz:]

    W_init_z = np.random.default_rng(seed).uniform(1.4, 3.8, (32, 32))
    W_ideal_z, mu_id, sd_id, Wout_id, _, _, _ = pat_train(
        twin_z, X_trz[:1950], y_trz[:1950], X_trz[1950:], y_trz[1950:],
        W_init_z, 10, epochs=16, bs=256, lr_opt=0.10, lr_head=2.5e-2,
        physical_plant=None, use_mlp=False, rng=np.random.default_rng(seed), verbose=False
    )

    pv_list = [0.0, 1.0, 3.0, 6.0, 10.0, 15.0]
    zernike_res = []
    for pv in pv_list:
        ab_in = make_zernike_aberration(128, pv, seed=1000 + seed * 31)
        ab_wt = make_zernike_aberration(128, pv * 0.7, seed=2000 + seed * 37)
        ghost_amp = 0.04 if pv > 0.0 else 0.0
        noise_rng = np.random.default_rng(42 + seed)

        class AberratedPlant:
            def __init__(self):
                self.n_ito = 32
            def precompute_cells(self, X_arr, batch_size=256):
                chunks = []
                for k in range(0, len(X_arr), batch_size):
                    E0 = twin_z.encode_lcd(X_arr[k:k + batch_size]) * ab_in
                    E1 = twin_z.prop1(E0)
                    if ghost_amp > 0.0:
                        E1 = E1 + ghost_amp * prop_ghost(E0)
                    chunks.append((E1 * ab_wt).astype(np.complex64))
                return np.concatenate(chunks, axis=0)
            def forward_cached(self, E_cell_ab, W_p, noisy=True):
                M_z = twin_z.ito_mask(W_p).astype(np.complex64)
                I_z = np.abs(twin_z.prop2(E_cell_ab * M_z)) ** 2
                p = twin_z.N // twin_z.cam_n
                lim = p * twin_z.cam_n
                B = I_z.shape[0]
                feat = I_z[:, :lim, :lim].reshape(B, twin_z.cam_n, p, twin_z.cam_n, p).mean(axis=(2, 4)).reshape(B, -1)
                if noisy:
                    feat = np.maximum(feat + noise_rng.normal(0.0, 1e-6, feat.shape), 0.0)
                return feat.astype(float)

        ab_plant = AberratedPlant()
        E_tr_ab = ab_plant.precompute_cells(X_trz)
        E_te_ab = ab_plant.precompute_cells(X_tez)

        # 1) Kalibrasyonsuz ideal ağırlık + ideal kafa
        F_te_uncomp = apply_standardizer(ab_plant.forward_cached(E_te_ab, W_ideal_z, noisy=False), mu_id, sd_id)
        acc_uncomp = float((predict_ridge(F_te_uncomp, Wout_id) == y_tez).mean()) * 100.0

        if pv == 0.0:
            acc_head_only = acc_uncomp
            acc_pat_z = acc_uncomp
        else:
            # 2) Kontrol: Donmuş ideal optik ağırlık W_ideal_z + yalnızca kafa yeniden eğitimi (PAT ile eşleşmiş CE Adam)
            F_tr_ho = ab_plant.forward_cached(E_tr_ab[:1950], W_ideal_z, noisy=False)
            F_va_ho = ab_plant.forward_cached(E_tr_ab[1950:], W_ideal_z, noisy=False)
            mu_ho, sd_ho = fit_standardizer(F_tr_ho)
            Wout_ho = _fit_ce_linear_head(
                apply_standardizer(F_tr_ho, mu_ho, sd_ho), y_trz[:1950],
                apply_standardizer(F_va_ho, mu_ho, sd_ho), y_trz[1950:],
                10, epochs=16, bs=256, lr_head=2.5e-2, rng=np.random.default_rng(seed)
            )
            F_te_ho = apply_standardizer(ab_plant.forward_cached(E_te_ab, W_ideal_z, noisy=False), mu_ho, sd_ho)
            acc_head_only = float((predict_ridge(F_te_ho, Wout_ho) == y_tez).mean()) * 100.0

            # 3) Vekil-habersiz PAT (optik W + kafa birlikte güncellenir)
            W_pz, mu_pz, sd_pz, Wout_pz, _, _, _ = pat_train(
                twin_z, X_trz[:1950], y_trz[:1950], X_trz[1950:], y_trz[1950:],
                W_init_z, 10, epochs=16, bs=256, lr_opt=0.10, lr_head=2.5e-2,
                physical_plant=ab_plant, use_mlp=False, rng=np.random.default_rng(seed), verbose=False
            )
            F_te_pz = apply_standardizer(ab_plant.forward_cached(E_te_ab, W_pz, noisy=False), mu_pz, sd_pz)
            acc_pat_z = float((predict_ridge(F_te_pz, Wout_pz) == y_tez).mean()) * 100.0

        zernike_res.append({
            "pv_waves": pv,
            "uncompensated_acc": round(acc_uncomp, 2),
            "head_only_acc": round(acc_head_only, 2),
            "pat_compensated_acc": round(acc_pat_z, 2),
        })
    return zernike_res


def _run_fashion_once(fmnist_dir, seed=7, n_test=1000):
    """Tek bir tohum için Fashion-MNIST 8×8 ve 32×32 eşleşmiş kıyası çalıştırır.
    v0.5: tüm lineer satırlar PAT ile eşleşmiş CE-Adam kafa kullanır; rastgele
    kontrolde eğitim özellikleri gürültülü, değerlendirme özellikleri gürültüsüzdür
    (PAT ile aynı protokol); 32×32 bölümde N_train=6000 (5280 fit / 720 val)."""
    # 8×8 Düşük Boyutlu Dedektör Kıyaslaması
    X_fa, y_fa, n_fa = load_fashion_mnist(3000, n_test, np.random.default_rng(seed), fmnist_dir)
    n_val8 = 360
    n_fit8 = n_fa - n_val8
    y_fit8, y_val8 = y_fa[:n_fit8], y_fa[n_fit8:n_fa]

    F_fa_no = pool_area(X_fa, 8)
    mu_no, sd_no = fit_standardizer(F_fa_no[:n_fit8])
    Wo_fa_no = _fit_ce_linear_head(
        apply_standardizer(F_fa_no[:n_fit8], mu_no, sd_no), y_fit8,
        apply_standardizer(F_fa_no[n_fit8:n_fa], mu_no, sd_no), y_val8,
        10, epochs=18, bs=256, lr_head=2.5e-2, rng=np.random.default_rng(seed + 1))
    fmnist_no_opt_lin = float((predict_ridge(
        apply_standardizer(F_fa_no[n_fa:], mu_no, sd_no), Wo_fa_no) == y_fa[n_fa:]).mean()) * 100.0

    F_fa_no_s = apply_standardizer(F_fa_no, mu_no, sd_no)
    mlp_fa_no = MLPHead(64, 256, 10, np.random.default_rng(seed + 11))
    mlp_fa_no.train(F_fa_no_s[:n_fit8], y_fit8, F_fa_no_s[n_fit8:n_fa], y_val8,
                    epochs=40, verbose=False)
    fmnist_no_opt_mlp = float((mlp_fa_no.predict(F_fa_no_s[n_fa:]) == y_fa[n_fa:]).mean()) * 100.0

    twin_fa8 = ZerreTwin(n_grid=128, n_ito=32, cam_n=8, drive_mode="active")
    plant_fa8 = PhysicalPlantSimulator(twin_fa8, seed=seed)
    E_fa8 = plant_fa8.precompute_cells(X_fa, batch_size=256)
    W_r_fa = np.random.default_rng(seed).uniform(1.4, 3.8, (32, 32))
    # PAT paritesi: ölçekleyici gürültüsüz fit özelliklerinden; kafa gürültülü
    # eğitim + gürültüsüz val/test özellikleriyle eğitilir.
    F_fa_rnd_noisy = plant_fa8.forward_cached(E_fa8, W_r_fa, noisy=True)
    F_fa_rnd_eval  = plant_fa8.forward_cached(E_fa8, W_r_fa, noisy=False)
    mu_fr, sd_fr = fit_standardizer(F_fa_rnd_eval[:n_fit8])
    Wo_fa_rnd = _fit_ce_linear_head(
        apply_standardizer(F_fa_rnd_noisy[:n_fit8], mu_fr, sd_fr), y_fit8,
        apply_standardizer(F_fa_rnd_eval[n_fit8:n_fa], mu_fr, sd_fr), y_val8,
        10, epochs=18, bs=256, lr_head=2.5e-2, rng=np.random.default_rng(seed))
    fmnist_rnd8_lin = float((predict_ridge(
        apply_standardizer(F_fa_rnd_eval[n_fa:], mu_fr, sd_fr), Wo_fa_rnd) == y_fa[n_fa:]).mean()) * 100.0

    W_fa_pat8, mu_fp8, sd_fp8, Wo_fp8, _, _, fwd_fp8 = pat_train(
        twin_fa8, X_fa[:n_fit8], y_fa[:n_fit8], X_fa[n_fit8:n_fa], y_val8,
        W_r_fa, 10, epochs=18, bs=256, lr_opt=0.10, lr_head=2.5e-2,
        physical_plant=plant_fa8, use_mlp=False, rng=np.random.default_rng(seed), verbose=False
    )
    F_fa_p8 = apply_standardizer(fwd_fp8(E_fa8[n_fa:], W_fa_pat8, False), mu_fp8, sd_fp8)
    fmnist_pat8_lin = float((predict_ridge(F_fa_p8, Wo_fp8) == y_fa[n_fa:]).mean()) * 100.0

    F_fa_p8_all = apply_standardizer(fwd_fp8(E_fa8[:n_fa], W_fa_pat8, False), mu_fp8, sd_fp8)
    mlp_fa8 = MLPHead(64, 256, 10, np.random.default_rng(seed))
    mlp_fa8.train(F_fa_p8_all[:n_fit8], y_fit8, F_fa_p8_all[n_fit8:n_fa], y_val8,
                  epochs=40, verbose=False)
    fmnist_pat8_mlp = float((mlp_fa8.predict(F_fa_p8) == y_fa[n_fa:]).mean()) * 100.0

    # 32×32 Tam Çözünürlüklü Kıyaslama (6000 eğitim, 1000 test; 5280 fit / 720 val)
    X_ff, y_ff, n_ff = load_fashion_mnist(6000, n_test, np.random.default_rng(seed), fmnist_dir)
    n_val32 = int(round(0.12 * n_ff))
    n_fit32 = n_ff - n_val32

    F_raw32, _, _ = standardize_split(X_ff.reshape(len(X_ff), -1), n_ff)
    Wo_raw32, _a_raw = fit_ridge_val(F_raw32[:n_ff], y_ff[:n_ff], 10)
    fmnist_raw32_ridge = float((predict_ridge(F_raw32[n_ff:], Wo_raw32) == y_ff[n_ff:]).mean()) * 100.0
    mlp_raw32 = MLPHead(F_raw32.shape[1], 256, 10, np.random.default_rng(seed + 22))
    mlp_raw32.train(F_raw32[:n_fit32], y_ff[:n_fit32], F_raw32[n_fit32:n_ff], y_ff[n_fit32:n_ff],
                    epochs=45, verbose=False)
    fmnist_raw32_mlp = float((mlp_raw32.predict(F_raw32[n_ff:]) == y_ff[n_ff:]).mean()) * 100.0

    twin_ff = ZerreTwin(n_grid=128, n_ito=32, cam_n=32, drive_mode="active")
    F_ff_rnd, _, _ = standardize_split(twin_ff.forward_batch(X_ff, W_r_fa, batch_size=256), n_ff)
    mlp_ff_rnd = MLPHead(F_ff_rnd.shape[1], 256, 10, np.random.default_rng(seed + 33))
    mlp_ff_rnd.train(F_ff_rnd[:n_fit32], y_ff[:n_fit32], F_ff_rnd[n_fit32:n_ff], y_ff[n_fit32:n_ff],
                     epochs=45, verbose=False)
    fmnist_32_rnd_mlp = float((mlp_ff_rnd.predict(F_ff_rnd[n_ff:]) == y_ff[n_ff:]).mean()) * 100.0

    plant_ff = PhysicalPlantSimulator(twin_ff, seed=seed)
    W_ff_pat, mu_ffp, sd_ffp, _, mlp_ffp, _, fwd_ffp = pat_train(
        twin_ff, X_ff[:n_fit32], y_ff[:n_fit32], X_ff[n_fit32:n_ff], y_ff[n_fit32:n_ff],
        W_r_fa, 10, epochs=45, bs=256, lr_opt=0.08, lr_head=2.5e-3,
        physical_plant=plant_ff, use_mlp=True, rng=np.random.default_rng(seed), verbose=False
    )
    E_ff_te = plant_ff.precompute_cells(X_ff[n_ff:], batch_size=256)
    F_ff_te_phy = apply_standardizer(fwd_ffp(E_ff_te, W_ff_pat, False), mu_ffp, sd_ffp)
    fmnist_32_imperfect = float((mlp_ffp.predict(F_ff_te_phy) == y_ff[n_ff:]).mean()) * 100.0

    F_ff_clean = twin_ff.forward_batch(X_ff, W_ff_pat, batch_size=256)
    F_ff_cs, mu_ffc, sd_ffc = standardize_split(F_ff_clean, n_ff)
    Wo_ffc, _a_ffc = fit_ridge_val(F_ff_cs[:n_ff], y_ff[:n_ff], 10)
    fmnist_32_ridge = float((predict_ridge(F_ff_cs[n_ff:], Wo_ffc) == y_ff[n_ff:]).mean()) * 100.0
    mlp_ffc = MLPHead(F_ff_cs.shape[1], 256, 10, np.random.default_rng(seed))
    mlp_ffc.train(F_ff_cs[:n_fit32], y_ff[:n_fit32], F_ff_cs[n_fit32:n_ff], y_ff[n_fit32:n_ff],
                  epochs=45, verbose=False)
    fmnist_32_hybrid = float((mlp_ffc.predict(F_ff_cs[n_ff:]) == y_ff[n_ff:]).mean()) * 100.0

    return {
        "no_optics_8x8_linear": round(fmnist_no_opt_lin, 2),
        "no_optics_8x8_mlp": round(fmnist_no_opt_mlp, 2),
        "random_32x32_8x8_linear": round(fmnist_rnd8_lin, 2),
        "pat_32x32_8x8_linear": round(fmnist_pat8_lin, 2),
        "pat_32x32_8x8_mlp": round(fmnist_pat8_mlp, 2),
        "no_optics_raw_ridge": round(fmnist_raw32_ridge, 2),
        "no_optics_raw_mlp": round(fmnist_raw32_mlp, 2),
        "random_32x32_mlp": round(fmnist_32_rnd_mlp, 2),
        "pat_32x32_ridge": round(fmnist_32_ridge, 2),
        "pat_32x32_perturbed_mlp": round(fmnist_32_imperfect, 2),
        "pat_32x32_nominal_mlp": round(fmnist_32_hybrid, 2),
        "meta": {"n_train_8x8": int(n_fa), "n_fit8": int(n_fit8), "n_val8": int(n_val8),
                 "n_train_32x32": int(n_ff), "n_fit32": int(n_fit32), "n_val32": int(n_val32),
                 "head": "matched_ce_adam", "eval_noisy": False},
    }


def _run_mismatch_once(mnist_dir, seed=7, n_test=1000):
    """YAPISAL model-uyumsuzluğu testi (v0.5).

    PhysicalPlantSimulator(structural=True) vekilin bilmediği fiziği ekler:
    pertürbe LC LUT (±%10), CMOS gamma 0.90 ve çarpımsal benek — parametrik
    sapma değil yapısal farktır; PAT iddiasının anlamlı olabildiği tek rejim budur.
    Üç eşleşmiş koşul: kalibrasyonsuz ideal ağırlık, donmuş optikte yalnız-kafa
    CE yeniden eğitimi, vekil-habersiz PAT."""
    twin_s = ZerreTwin(n_grid=128, n_ito=32, cam_n=8, drive_mode="active")
    X_s, y_s, n_trs = load_mnist(2200, n_test, np.random.default_rng(seed), mnist_dir)
    X_trs, y_trs = X_s[:n_trs], y_s[:n_trs]
    X_tes, y_tes = X_s[n_trs:], y_s[n_trs:]

    W_init_s = np.random.default_rng(seed).uniform(1.4, 3.8, (32, 32))
    W_ideal_s, mu_id, sd_id, Wout_id, _, _, _ = pat_train(
        twin_s, X_trs[:1950], y_trs[:1950], X_trs[1950:], y_trs[1950:],
        W_init_s, 10, epochs=16, bs=256, lr_opt=0.10, lr_head=2.5e-2,
        physical_plant=None, use_mlp=False, rng=np.random.default_rng(seed), verbose=False
    )

    sm_plant = PhysicalPlantSimulator(twin_s, seed=seed, structural=True)
    E_tr_sm = sm_plant.precompute_cells(X_trs)
    E_te_sm = sm_plant.precompute_cells(X_tes)

    # 1) Kalibrasyonsuz ideal ağırlık + ideal kafa
    F_te_un = apply_standardizer(sm_plant.forward_cached(E_te_sm, W_ideal_s, noisy=False), mu_id, sd_id)
    acc_uncomp = float((predict_ridge(F_te_un, Wout_id) == y_tes).mean()) * 100.0

    # 2) Kontrol: donmuş ideal optik + yalnız kafa CE-Adam yeniden eğitimi
    F_tr_ho = sm_plant.forward_cached(E_tr_sm[:1950], W_ideal_s, noisy=False)
    F_va_ho = sm_plant.forward_cached(E_tr_sm[1950:], W_ideal_s, noisy=False)
    mu_ho, sd_ho = fit_standardizer(F_tr_ho)
    Wout_ho = _fit_ce_linear_head(
        apply_standardizer(F_tr_ho, mu_ho, sd_ho), y_trs[:1950],
        apply_standardizer(F_va_ho, mu_ho, sd_ho), y_trs[1950:],
        10, epochs=16, bs=256, lr_head=2.5e-2, rng=np.random.default_rng(seed)
    )
    F_te_ho = apply_standardizer(sm_plant.forward_cached(E_te_sm, W_ideal_s, noisy=False), mu_ho, sd_ho)
    acc_head_only = float((predict_ridge(F_te_ho, Wout_ho) == y_tes).mean()) * 100.0

    # 3) Vekil-habersiz PAT (optik W + kafa birlikte güncellenir)
    W_ps, mu_ps, sd_ps, Wout_ps, _, _, _ = pat_train(
        twin_s, X_trs[:1950], y_trs[:1950], X_trs[1950:], y_trs[1950:],
        W_init_s, 10, epochs=16, bs=256, lr_opt=0.10, lr_head=2.5e-2,
        physical_plant=sm_plant, use_mlp=False, rng=np.random.default_rng(seed), verbose=False
    )
    F_te_ps = apply_standardizer(sm_plant.forward_cached(E_te_sm, W_ps, noisy=False), mu_ps, sd_ps)
    acc_pat = float((predict_ridge(F_te_ps, Wout_ps) == y_tes).mean()) * 100.0

    return {
        "defects": "perturbed LC LUT ±10% + camera gamma 0.90 + speckle + parametric shifts",
        "uncompensated_acc": round(acc_uncomp, 2),
        "head_only_acc": round(acc_head_only, 2),
        "pat_acc": round(acc_pat, 2),
    }


def run_hardware_realism_suite(base_dir, seed=7):
    """4 fiziksel gerçekçilik & genelleme testini çalıştırır ve realism_results.json kaydeder."""
    rng = np.random.default_rng(seed)
    mnist_dir = os.path.join(base_dir, "mnist_cache")
    fmnist_dir = os.path.join(base_dir, "fashion_mnist_cache")
    model_path = os.path.join(base_dir, "zerre_model.npz")

    results = {"config": {"seed": seed, "n_test": 1000}}
    print("═" * 78, flush=True)
    print("  ZERRE v0.4 — FİZİKSEL GERÇEKÇİLİK VE ÇOKLU-GÖREV DOĞRULAMA PAKETİ", flush=True)
    print("═" * 78, flush=True)

    # ── 1) BİT KUANTİZASYONU (8-bit HDMI Giriş + b-bit Optik Ağırlık) ─────────
    t_s = time.time()
    twin_m, d_m = load_twin_from_npz(model_path)
    X_m, y_m, n_tr_m = load_mnist(2400, 1000, rng, mnist_dir)
    X_tr_m, y_tr_m = X_m[:n_tr_m], y_m[:n_tr_m]
    X_te_m, y_te_m = X_m[n_tr_m:], y_m[n_tr_m:]
    X_te_8bit = quantize_array(X_te_m, 8, 0.0, 1.0)
    X_tr_8bit = quantize_array(X_tr_m, 8, 0.0, 1.0)

    def predict_loaded(d_loaded, F_raw):
        f_std = (F_raw - d_loaded["mu"]) / d_loaded["sd"]
        if "mlp_W1" in d_loaded:
            h = np.maximum(0.0, f_std @ d_loaded["mlp_W1"] + d_loaded["mlp_b1"])
            return np.argmax(h @ d_loaded["mlp_W2"] + d_loaded["mlp_b2"], axis=1)
        return np.argmax(np.hstack([f_std, np.ones((len(f_std), 1))]) @ d_loaded["Wout"], axis=1)

    bit_list = [64, 12, 8, 6, 5, 4, 3, 2]
    quant_res = []
    print("\n[TEST 1] DAC / HDMI Bit Derinliği Kuantizasyonu (Giriş=8-bit HDMI, N_test=1000):", flush=True)
    for b in bit_list:
        Wq = quantize_array(d_m["W_volt"], None if b == 64 else b, 1.0, 5.0)
        F_te_q = twin_m.forward_batch(X_te_8bit if b < 64 else X_te_m, Wq, batch_size=256)
        acc_ptq = float((predict_loaded(d_m, F_te_q) == y_te_m).mean()) * 100.0
        lbl = "Float64" if b == 64 else f"{b}-bit ({(1 << b)} lvls)"
        quant_res.append({"bits": b, "label": lbl, "ptq_acc": round(acc_ptq, 2)})
        print(f"  • {lbl:20s} → PTQ Doğruluk: %{acc_ptq:5.2f}", flush=True)
    print(f"  [Süre: {time.time() - t_s:.1f}s]", flush=True)
    results["quantization"] = quant_res

    # ── 2) MAKRO-PİKSEL ALT-AÇIKLIK (FILL-FACTOR) KIRINIMI (N=256 İnce Izgara) ──
    t_s = time.time()
    print("\n[TEST 2] Makro-Piksel Açıklık Oranı (Fill-Factor) & Izgara Kırınımı (N=256, N_test=1000):", flush=True)
    twin_bm = ZerreTwin(n_grid=256, n_ito=32, cam_n=32, drive_mode="active")
    W_bm = d_m["W_volt"]
    X_bm_tr, y_bm_tr = X_tr_8bit[:2000], y_tr_m[:2000]
    X_bm_te, y_bm_te = X_te_8bit[:1000], y_te_m[:1000]
    F_tr_100 = twin_bm.forward_batch(X_bm_tr, W_bm, batch_size=128)
    mu_100, sd_100 = fit_standardizer(F_tr_100)
    F_tr_100_s = apply_standardizer(F_tr_100, mu_100, sd_100)
    mlp_100 = MLPHead(F_tr_100_s.shape[1], 256, 10, np.random.default_rng(seed))
    mlp_100.train(F_tr_100_s[:1750], y_bm_tr[:1750], F_tr_100_s[1750:], y_bm_tr[1750:],
                  epochs=35, verbose=False)

    fill_factors = [1.00, 0.75, 0.56, 0.36, 0.25]
    bm_res = []
    M_ideal = twin_bm.ito_mask(W_bm)
    for ff in fill_factors:
        bm_in = make_subpixel_black_matrix(256, twin_bm.o_in, 28, twin_bm.up, ff)
        bm_wt = make_subpixel_black_matrix(256, twin_bm.o_cell, 32, twin_bm.rep, ff)

        def fwd_bm(X_arr):
            out = []
            M_eff = M_ideal * bm_wt
            for i in range(0, len(X_arr), 128):
                E0 = twin_bm.encode_lcd(X_arr[i:i + 128]) * bm_in
                E1 = twin_bm.prop1(E0)
                E2 = twin_bm.prop2(E1 * M_eff)
                out.append(twin_bm.camera(E2))
            return np.vstack(out)

        F_tr_bm = F_tr_100 if ff >= 0.999 else fwd_bm(X_bm_tr)
        F_te_bm = fwd_bm(X_bm_te)
        # Yalnız eğitim kümesinden hesaplanan kazanç oranı (sıfır test sızıntısı!)
        gain_ratio = float(F_tr_100.mean() / (F_tr_bm.mean() + 1e-12))
        F_te_uncal = apply_standardizer(F_te_bm * gain_ratio, mu_100, sd_100)
        acc_uncal = float((mlp_100.predict(F_te_uncal) == y_bm_te).mean()) * 100.0

        if ff >= 0.999:
            acc_cal = acc_uncal
        else:
            mu_b, sd_b = fit_standardizer(F_tr_bm)
            F_tr_bs = apply_standardizer(F_tr_bm, mu_b, sd_b)
            mlp_b = MLPHead(F_tr_bs.shape[1], 256, 10, np.random.default_rng(seed))
            mlp_b.train(F_tr_bs[:1750], y_bm_tr[:1750], F_tr_bs[1750:], y_bm_tr[1750:],
                        epochs=35, verbose=False)
            acc_cal = float((mlp_b.predict(apply_standardizer(F_te_bm, mu_b, sd_b)) == y_bm_te).mean()) * 100.0

        bm_res.append({
            "fill_factor_pct": int(round(ff * 100)),
            "uncal_acc": round(acc_uncal, 2),
            "head_recalibrated_acc": round(acc_cal, 2),
        })
        print(f"  • Doluluk %{ff * 100:4.0f} → Kalibrasyonsuz: %{acc_uncal:5.2f}  |  "
              f"Kafa Kalibrasyonu: %{acc_cal:5.2f}", flush=True)
    print(f"  [Süre: {time.time() - t_s:.1f}s]", flush=True)
    results["black_matrix"] = bm_res

    # ── 3) UCUZ CAM ZERNIKE DALGA CEPHESİ BOZULMASI + 3·Z1 FABRY-PÉROT ────────
    t_s = time.time()
    print("\n[TEST 3] Ucuz Cam Zernike Sapması (0 → 15.0λ PV) + 3·Z1 Fresnel (0.04) Hayalet (8×8, N_test=1000):", flush=True)
    zernike_res = _run_zernike_once(mnist_dir, seed=seed, n_test=1000)
    for row in zernike_res:
        print(f"  • Zernike PV = {row['pv_waves']:4.1f}λ → Kalibrasyonsuz: %{row['uncompensated_acc']:5.2f}  |  "
              f"Kafa-Kontrol: %{row['head_only_acc']:5.2f}  |  PAT: %{row['pat_compensated_acc']:5.2f}", flush=True)
    print(f"  [Süre: {time.time() - t_s:.1f}s]", flush=True)
    results["zernike_aberration"] = zernike_res

    # ── 4) FASHION-MNIST EŞLEŞMİŞ KIYAS (N_test=1000) ─────────────────────────
    if os.path.exists(os.path.join(fmnist_dir, "train-images-idx3-ubyte.gz")):
        t_s = time.time()
        print("\n[TEST 4] Fashion-MNIST 10-Sınıf Eşleşmiş Kıyaslama (N_test=1000):", flush=True)
        fm = _run_fashion_once(fmnist_dir, seed=seed, n_test=1000)
        results["fashion_mnist"] = fm
        print(f"  • 8×8  → Optiksiz Lin: %{fm['no_optics_8x8_linear']:.2f} | Optiksiz MLP: %{fm['no_optics_8x8_mlp']:.2f} | "
              f"PAT Lin: %{fm['pat_32x32_8x8_linear']:.2f} | PAT+MLP: %{fm['pat_32x32_8x8_mlp']:.2f}", flush=True)
        print(f"  • 32×32 → Ham MLP: %{fm['no_optics_raw_mlp']:.2f} | Rastgele MLP: %{fm['random_32x32_mlp']:.2f} | "
              f"PAT Kusurlu: %{fm['pat_32x32_perturbed_mlp']:.2f} | PAT Nominal: %{fm['pat_32x32_nominal_mlp']:.2f}", flush=True)
        print(f"  [Süre: {time.time() - t_s:.1f}s]", flush=True)

    # ── 5) YAPISAL MODEL-UYUMSUZLUĞU (v0.5 — vekilin bilmediği fizik) ─────────
    t_s = time.time()
    print("\n[TEST 5] Yapısal Model-Uyumsuzluğu (pertürbe LC LUT + gamma + benek, N_test=1000):", flush=True)
    sm_res = _run_mismatch_once(mnist_dir, seed=seed, n_test=1000)
    results["structural_mismatch"] = sm_res
    print(f"  • Kalibrasyonsuz: %{sm_res['uncompensated_acc']:.2f}  |  Yalnız-Kafa: %{sm_res['head_only_acc']:.2f}  |  "
          f"PAT: %{sm_res['pat_acc']:.2f}", flush=True)
    print(f"  [Süre: {time.time() - t_s:.1f}s]", flush=True)

    out_json = os.path.join(base_dir, "makale", "scripts", "realism_results.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("─" * 78)
    print(f"  [KAYIT] Tüm v0.4 gerçekçilik sonuçları kaydedildi: {out_json}", flush=True)
    print("═" * 78, flush=True)
    return results


def _agg_stats(vals):
    arr = np.asarray(vals, dtype=float)
    sd = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    return {
        "mean": round(float(np.mean(arr)), 2),
        "std": round(sd, 2),
        "values": [round(float(v), 2) for v in arr],
    }


def run_paper_benchmark(base_dir, seeds=(7, 19, 42)):
    """Tüm makale tabloları ve figürleri için birleştirilmiş, sızıntısız ve çoklu-tohumlu
    kıyaslama paketini çalıştırır; sonuçları makale/scripts/paper_results.json içine yazar.
    v0.5: her bölüm tamamlandıkça paper_results_partial.json'a checkpoint atar;
    bitiminde eski paper_results.json yedeklenir (paper_results_v04_backup.json)."""
    import scipy
    t_total = time.time()
    seeds = list(seeds)
    mnist_dir = os.path.join(base_dir, "mnist_cache")
    fmnist_dir = os.path.join(base_dir, "fashion_mnist_cache")
    model_path = os.path.join(base_dir, "zerre_model.npz")
    partial_path = os.path.join(base_dir, "makale", "scripts", "paper_results_partial.json")
    final_path = os.path.join(base_dir, "makale", "scripts", "paper_results.json")

    out = {}
    def _ckpt():
        os.makedirs(os.path.dirname(partial_path), exist_ok=True)
        with open(partial_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"  [CKPT] {os.path.basename(partial_path)} güncellendi ({time.time() - t_total:.0f}s)", flush=True)

    print("═" * 82, flush=True)
    print(f"  ZERRE v0.5 UNIFIED PAPER BENCHMARK · Seeds={seeds}", flush=True)
    print("═" * 82, flush=True)

    # 1) Ortam + Alt-Pleshko + Gradyan Doğrulaması
    ap16 = passive_selection_ratio(16)
    ap32 = passive_selection_ratio(32)
    rng_gc = np.random.default_rng(123)
    X_gc, _ = make_shapes(4, rng_gc)
    Xb_gc = X_gc[:6]
    grad_errs = {}
    for gm in ["active", "passive"]:
        tw_g = ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode=gm)
        Ec_g = tw_g.field_at_cell(Xb_gc)
        Wg = rng_gc.uniform(1.3, 4.5, (8, 8)) if gm == "active" else rng_gc.uniform(-0.8, 0.8, (8, 8))
        tgt_g = rng_gc.normal(0.0, 1.0, (len(Xb_gc), 64))
        F0_g = tw_g.forward_cached(Ec_g, Wg)
        g_an = tw_g.backward_cached(Ec_g, Wg, F0_g - tgt_g).ravel()
        eps = 1e-6
        g_fd = np.zeros_like(Wg)
        for ii in range(8):
            for jj in range(8):
                Wp = Wg.copy(); Wp[ii, jj] += eps
                Wm = Wg.copy(); Wm[ii, jj] -= eps
                lp = 0.5 * float(np.sum((tw_g.forward_cached(Ec_g, Wp) - tgt_g) ** 2))
                lm = 0.5 * float(np.sum((tw_g.forward_cached(Ec_g, Wm) - tgt_g) ** 2))
                g_fd[ii, jj] = (lp - lm) / (2.0 * eps)
        g_fd = g_fd.ravel()
        grad_errs[gm] = float(np.linalg.norm(g_an - g_fd) / (np.linalg.norm(g_fd) + 1e-12))

    out["environment_info"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "os": platform.platform(),
        "processor": platform.processor() or "unknown",
        "seeds": seeds,
        "benchmark_version": "v0.5",
    }
    out["physics_checks"] = {
        "grad_check_eps": 1e-6,
        "grad_err_active": float(f"{grad_errs['active']:.4e}"),
        "grad_err_passive": float(f"{grad_errs['passive']:.4e}"),
        "alt_pleshko_n16_ratio": round(ap16, 6),
        "alt_pleshko_n32_ratio": round(ap32, 6),
        "phase_swing_active_rad": round(float(lc_phase(1.0) - lc_phase(5.0)), 3),
        "phase_swing_passive_n16_rad": round(float(lc_phase(1.0) - lc_phase(ap16)), 3),
        "phase_swing_passive_n32_rad": round(float(lc_phase(1.0) - lc_phase(ap32)), 3),
    }
    _ckpt()

    # 2) Tablo I — Çoklu Tohum 8×8 Sızıntısız Ablasyon (3000 train [2640/360], 1000 test)
    print("\n[1/6] Tablo I: 8×8 Sızıntısız MNIST Ablasyon (3 tohum, eşleşmiş CE kafa)...", flush=True)
    ab_runs = []
    for s in seeds:
        ab_runs.append(run_ablation(n_train=3000, n_test=1000, cam_n=8, grid=128, seed=s))
        gc.collect()

    ab_summary = []
    for idx in range(len(ab_runs[0]["rows"])):
        r0 = ab_runs[0]["rows"][idx]
        vals = [run["rows"][idx]["acc_pct"] for run in ab_runs]
        row_d = {
            "key": r0["key"],
            "label": r0["label"],
            "opt_w": r0["opt_w"],
            "dig_w": r0["dig_w"],
            **_agg_stats(vals),
        }
        rv = [run["rows"][idx]["acc_ridge_pct"] for run in ab_runs]
        if rv[0] is not None:
            row_d["acc_ridge"] = _agg_stats(rv)
        ab_summary.append(row_d)

    out["table1_ablation"] = {"config": ab_runs[0]["config"], "rows": ab_summary}
    _ckpt()

    # 3) Tablo II — Çoklu Tohum Tam Ölçek 32×32 Hibrit Kıyaslama (6000 train, 1000 test)
    print("\n[2/6] Tablo II: 32×32 Tam Ölçek MNIST Kıyaslama (3 tohum)...", flush=True)
    t2_keys = [
        ("raw_28x28_ridge", "Ham 28×28 (Optik Yok) + Ridge", 0, 7850),
        ("raw_28x28_mlp", "Ham 28×28 (Optik Yok) + MLP (256)", 0, 203530),
        ("opt_16_256f_ridge_2500", "16×16 Aktif (Rastgele) + 16×16 Ridge (N=2500)", 256, 2570),
        ("opt_16_1024f_ridge_2500", "16×16 Aktif (Rastgele) + 32×32 Ridge (N=2500)", 256, 10250),
        ("opt_32_1024f_ridge_6000", "32×32 Aktif (Rastgele) + 32×32 Ridge (N=6000)", 1024, 10250),
        ("opt_32_random_mlp_6000", "32×32 Aktif (Rastgele) + 32×32 MLP (N=6000)", 1024, 264970),
        ("opt_32_pat_perturbed_mlp_6000", "32×32 Aktif + PAT + MLP (Kusurlu Sistem)", 1024, 264970),
        ("opt_32_pat_nominal_mlp_6000", "32×32 Aktif + PAT + MLP (Nominal İkiz — Üst Sınır)", 1024, 264970),
    ]
    t2_per_seed = {k: [] for k, _, _, _ in t2_keys}
    t2_alphas = {}
    perturbed_seed7_tuple = None

    for s in seeds:
        rng_s = np.random.default_rng(s)
        X_m, y_m, n_tr_m = load_mnist(6000, 1000, rng_s, mnist_dir)
        X_tr_m, y_tr_m = X_m[:n_tr_m], y_m[:n_tr_m]
        X_te_m, y_te_m = X_m[n_tr_m:], y_m[n_tr_m:]
        n_val_m = 720
        n_fit_m = n_tr_m - n_val_m

        # 1-2) Ham dijital kontrol (Optik yok)
        X_flat_tr = X_tr_m.reshape(n_tr_m, -1)
        X_flat_te = X_te_m.reshape(len(X_te_m), -1)
        mu_r, sd_r = fit_standardizer(X_flat_tr)
        Xr_tr = apply_standardizer(X_flat_tr, mu_r, sd_r)
        Xr_te = apply_standardizer(X_flat_te, mu_r, sd_r)
        Wo_raw, a_raw = fit_ridge_val(Xr_tr, y_tr_m, 10)
        t2_per_seed["raw_28x28_ridge"].append(float((predict_ridge(Xr_te, Wo_raw) == y_te_m).mean()) * 100.0)
        t2_alphas.setdefault("raw_28x28_ridge", []).append(a_raw)

        mlp_raw = MLPHead(Xr_tr.shape[1], 256, 10, np.random.default_rng(s + 1))
        mlp_raw.train(Xr_tr[:n_fit_m], y_tr_m[:n_fit_m], Xr_tr[n_fit_m:], y_tr_m[n_fit_m:],
                      epochs=45, verbose=False)
        t2_per_seed["raw_28x28_mlp"].append(float((mlp_raw.predict(Xr_te) == y_te_m).mean()) * 100.0)

        # 3-4) N_train=2500 (16×16 optik + 16×16 vs 32×32 okuma aşırı uyum testi)
        W_r16 = rng_s.uniform(1.2, 3.2, (16, 16))
        tw_16_16 = ZerreTwin(128, n_ito=16, cam_n=16, drive_mode="active")
        F_16_tr = tw_16_16.forward_batch(X_tr_m[:2500], W_r16, batch_size=256)
        F_16_te = tw_16_16.forward_batch(X_te_m, W_r16, batch_size=256)
        mu_16, sd_16 = fit_standardizer(F_16_tr)
        W_16, a_16 = fit_ridge_val(apply_standardizer(F_16_tr, mu_16, sd_16), y_tr_m[:2500], 10)
        t2_per_seed["opt_16_256f_ridge_2500"].append(
            float((predict_ridge(apply_standardizer(F_16_te, mu_16, sd_16), W_16) == y_te_m).mean()) * 100.0
        )
        t2_alphas.setdefault("opt_16_256f_ridge_2500", []).append(a_16)

        tw_16_32 = ZerreTwin(128, n_ito=16, cam_n=32, drive_mode="active")
        F_1632_tr = tw_16_32.forward_batch(X_tr_m[:2500], W_r16, batch_size=256)
        F_1632_te = tw_16_32.forward_batch(X_te_m, W_r16, batch_size=256)
        mu_1632, sd_1632 = fit_standardizer(F_1632_tr)
        W_1632, a_1632 = fit_ridge_val(apply_standardizer(F_1632_tr, mu_1632, sd_1632), y_tr_m[:2500], 10)
        t2_per_seed["opt_16_1024f_ridge_2500"].append(
            float((predict_ridge(apply_standardizer(F_1632_te, mu_1632, sd_1632), W_1632) == y_te_m).mean()) * 100.0
        )
        t2_alphas.setdefault("opt_16_1024f_ridge_2500", []).append(a_1632)

        # 5-8) N_train=6000 (32×32 optik + 32×32 okuma)
        tw_32 = ZerreTwin(128, n_ito=32, cam_n=32, drive_mode="active")
        W_r32 = rng_s.uniform(1.2, 3.2, (32, 32))
        F_32r_tr = tw_32.forward_batch(X_tr_m, W_r32, batch_size=256)
        F_32r_te = tw_32.forward_batch(X_te_m, W_r32, batch_size=256)
        mu_32r, sd_32r = fit_standardizer(F_32r_tr)
        Fr_tr_s = apply_standardizer(F_32r_tr, mu_32r, sd_32r)
        Fr_te_s = apply_standardizer(F_32r_te, mu_32r, sd_32r)
        Wo_32r, a_32r = fit_ridge_val(Fr_tr_s, y_tr_m, 10)
        t2_per_seed["opt_32_1024f_ridge_6000"].append(float((predict_ridge(Fr_te_s, Wo_32r) == y_te_m).mean()) * 100.0)
        t2_alphas.setdefault("opt_32_1024f_ridge_6000", []).append(a_32r)

        mlp_32r = MLPHead(Fr_tr_s.shape[1], 256, 10, np.random.default_rng(s + 2))
        mlp_32r.train(Fr_tr_s[:n_fit_m], y_tr_m[:n_fit_m], Fr_tr_s[n_fit_m:], y_tr_m[n_fit_m:],
                      epochs=45, verbose=False)
        t2_per_seed["opt_32_random_mlp_6000"].append(float((mlp_32r.predict(Fr_te_s) == y_te_m).mean()) * 100.0)

        plant_32 = PhysicalPlantSimulator(tw_32, seed=s)
        W_pat_32, mu_p32, sd_p32, _, mlp_p32, _, fwd_p32 = pat_train(
            tw_32,
            X_tr_m[:n_fit_m], y_tr_m[:n_fit_m],
            X_tr_m[n_fit_m:], y_tr_m[n_fit_m:],
            W_r32, 10, epochs=45, bs=256,
            lr_opt=0.09, lr_head=2.5e-3,
            physical_plant=plant_32, use_mlp=True,
            rng=np.random.default_rng(s + 3), verbose=False
        )
        E_te_phy = plant_32.precompute_cells(X_te_m, batch_size=256)
        F_te_phy = apply_standardizer(fwd_p32(E_te_phy, W_pat_32, False), mu_p32, sd_p32)
        acc_phy = float((mlp_p32.predict(F_te_phy) == y_te_m).mean()) * 100.0
        t2_per_seed["opt_32_pat_perturbed_mlp_6000"].append(acc_phy)

        # Nominal (ideal) ikiz üzerinde kafa uyumu — üst sınır, donanım kalibrasyonu değil
        F_cl_tr = tw_32.forward_batch(X_tr_m, W_pat_32, batch_size=256)
        F_cl_te = tw_32.forward_batch(X_te_m, W_pat_32, batch_size=256)
        mu_c32, sd_c32 = fit_standardizer(F_cl_tr)
        Fc_tr_s = apply_standardizer(F_cl_tr, mu_c32, sd_c32)
        Fc_te_s = apply_standardizer(F_cl_te, mu_c32, sd_c32)
        Wo_c32, _a_c32 = fit_ridge_val(Fc_tr_s, y_tr_m, 10)
        mlp_c32 = MLPHead(Fc_tr_s.shape[1], 256, 10, np.random.default_rng(s + 4))
        mlp_c32.train(Fc_tr_s[:n_fit_m], y_tr_m[:n_fit_m], Fc_tr_s[n_fit_m:], y_tr_m[n_fit_m:],
                      epochs=45, verbose=False)
        acc_nom = float((mlp_c32.predict(Fc_te_s) == y_te_m).mean()) * 100.0
        t2_per_seed["opt_32_pat_nominal_mlp_6000"].append(acc_nom)

        print(f"  [Seed {s}] Ham MLP: %{t2_per_seed['raw_28x28_mlp'][-1]:.2f} | "
              f"Rastgele MLP: %{t2_per_seed['opt_32_random_mlp_6000'][-1]:.2f} | "
              f"PAT Kusurlu: %{acc_phy:.2f} | PAT Nominal: %{acc_nom:.2f}", flush=True)

        if s == seeds[0]:
            meta_npz = {
                "seed": s, "grid": 128, "n_ito": 32, "cam_n": 32,
                "drive_mode": "active", "n_train": n_tr_m, "n_test": 1000,
                "pat_perturbed_acc": round(acc_phy, 2),
                "pat_nominal_acc": round(acc_nom, 2),
                "version": "v0.5",
            }
            save_model(model_path, W_pat_32, mu_c32, sd_c32, Wo_c32, mlp_c32,
                       128, 32, 10, n_ito=32, drive_mode="active", metadata=meta_npz)
            d_phy = {
                "W_volt": W_pat_32, "mu": mu_p32, "sd": sd_p32,
                "mlp_W1": mlp_p32.W1, "mlp_b1": mlp_p32.b1,
                "mlp_W2": mlp_p32.W2, "mlp_b2": mlp_p32.b2,
                "grid": 128, "cam_n": 32, "n_cls": 10, "n_ito": 32, "drive_mode": "active",
            }
            perturbed_seed7_tuple = (tw_32, d_phy)

        del X_m, y_m, X_flat_tr, X_flat_te
        gc.collect()

    t2_summary = []
    for k, lbl, ow, dw in t2_keys:
        row_d = {"key": k, "label": lbl, "opt_w": ow, "dig_w": dw, **_agg_stats(t2_per_seed[k])}
        if k in t2_alphas:
            row_d["ridge_alpha"] = t2_alphas[k]
        t2_summary.append(row_d)

    out["table2_scaling"] = {
        "config": {"n_train": 6000, "n_fit": 5280, "n_val": 720, "n_test": 1000, "grid": 128,
                   "seeds": seeds, "pat_mlp_epochs": 45, "head_mlp_epochs": 45},
        "rows": t2_summary,
    }
    _ckpt()

    # 4) CPU Çıkarım Süresi (50 çalışma medyan/IQR)
    print("\n[3/6] CPU Simülasyon Süresi & Şekil 4 (Dayanım + Çevre, N_test=1000)...", flush=True)
    tw_lat, d_lat = load_twin_from_npz(model_path)
    demo_p = os.path.join(base_dir, "demo_rakam_8.png")
    demo_im = load_photo(demo_p) if os.path.exists(demo_p) else np.zeros((28, 28))
    for _ in range(3):
        infer_array(demo_im, tw_lat, d_lat)
    times_ms = [infer_array(demo_im, tw_lat, d_lat)["compute_ms"] for _ in range(50)]
    latency_info = {
        "n_runs": 50,
        "median_ms": round(float(np.median(times_ms)), 2),
        "mean_ms": round(float(np.mean(times_ms)), 2),
        "iqr_ms": round(float(np.percentile(times_ms, 75) - np.percentile(times_ms, 25)), 2),
        "min_ms": round(float(np.min(times_ms)), 2),
        "max_ms": round(float(np.max(times_ms)), 2),
    }

    rob_res = robustness_test(model_path, n_test=1000, seed=seeds[0])
    env_res = env_test(model_path, n_test=1000, seed=seeds[0])
    rob_phy_res = robustness_test(perturbed_seed7_tuple, n_test=1000, seed=seeds[0]) if perturbed_seed7_tuple else None

    # 5) Donanım Gerçekçiliği (Seed 0 Kuantizasyon & Makro-Piksel Fill-Factor, + 3-Tohum Zernike & Fashion-MNIST)
    print("\n[4/6] Kuantizasyon & Makro-Piksel Fill-Factor (N_test=1000)...", flush=True)
    realism_seed0 = run_hardware_realism_suite(base_dir, seed=seeds[0])
    gc.collect()

    print("\n[5/6] Zernike 0→15λ (3 tohum, Kafa-Kontrol vs PAT, N_test=1000)...", flush=True)
    z_runs = [realism_seed0["zernike_aberration"]]
    for s in seeds[1:]:
        z_runs.append(_run_zernike_once(mnist_dir, seed=s, n_test=1000))
        gc.collect()
    z_summary = []
    for idx in range(len(z_runs[0])):
        pv = z_runs[0][idx]["pv_waves"]
        z_summary.append({
            "pv_waves": pv,
            "uncompensated": _agg_stats([r[idx]["uncompensated_acc"] for r in z_runs]),
            "head_only": _agg_stats([r[idx]["head_only_acc"] for r in z_runs]),
            "pat_compensated": _agg_stats([r[idx]["pat_compensated_acc"] for r in z_runs]),
        })

    print("\n[6/6] Fashion-MNIST Eşleşmiş Kıyaslama (3 tohum, N_test=1000)...", flush=True)
    fm_runs = [realism_seed0["fashion_mnist"]]
    for s in seeds[1:]:
        fm_runs.append(_run_fashion_once(fmnist_dir, seed=s, n_test=1000))
        gc.collect()
    fm_keys = [k for k in fm_runs[0].keys() if k != "meta"]
    fm_summary = {k: _agg_stats([r[k] for r in fm_runs]) for k in fm_keys}
    fm_summary["meta"] = fm_runs[0]["meta"]

    sm_runs = [realism_seed0["structural_mismatch"]]
    for s in seeds[1:]:
        sm_runs.append(_run_mismatch_once(mnist_dir, seed=s, n_test=1000))
        gc.collect()
    sm_summary = {
        "defects": sm_runs[0]["defects"],
        "uncompensated": _agg_stats([r["uncompensated_acc"] for r in sm_runs]),
        "head_only": _agg_stats([r["head_only_acc"] for r in sm_runs]),
        "pat": _agg_stats([r["pat_acc"] for r in sm_runs]),
    }

    out["environment_info"]["total_runtime_s"] = round(time.time() - t_total, 1)
    out["latency_cpu"] = latency_info
    out["robustness"] = rob_res
    out["robustness_perturbed_head"] = rob_phy_res
    out["environment_tests"] = env_res
    out["quantization"] = realism_seed0["quantization"]
    out["black_matrix"] = realism_seed0["black_matrix"]
    out["zernike_multiseed"] = z_summary
    out["fashion_mnist_multiseed"] = fm_summary
    out["structural_mismatch"] = sm_summary

    if os.path.exists(final_path):
        bak = final_path.replace("paper_results.json", "paper_results_v04_backup.json")
        try:
            os.replace(final_path, bak)
            print(f"  [YEDEK] Eski sonuçlar: {os.path.basename(bak)}", flush=True)
        except OSError:
            pass
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    if os.path.exists(partial_path):
        os.remove(partial_path)
    print("═" * 82, flush=True)
    print(f"  [TAMAM] Tüm birleşik makale sonuçları kaydedildi: {final_path} ({out['environment_info']['total_runtime_s']}s)", flush=True)
    print("═" * 82, flush=True)
    return out


def _eval_linear_test(feat_raw, y_te, mu, sd, Wout):
    F_s = apply_standardizer(feat_raw, mu, sd)
    return float((predict_ridge(F_s, Wout) == y_te).mean()) * 100.0


def run_remedies_benchmark(base_dir, seeds=(7, 19, 42)):
    """v0.6 Teknik Çözümler Kıyaslama Paketi (3 Tohumlu):
      1) Uzamsal paketleme (2x2, 4x4 crosstalk + 2K/4K/8K 60Hz kapasite)
      2) Kara-kutu kalibre vekil PAT (yapısal uyumsuzluk telafisi + gradyan cos)
      3) Katlanmış çok-katmanlı (L=1,2,3) + diferansiyel (I_+ - I_-) okuma (8x8)
    Çıktı: makale/scripts/remedies_v06_results.json"""
    t_all = time.time()
    seeds = list(seeds)
    mnist_dir = os.path.join(base_dir, "mnist_cache")
    model_path = os.path.join(base_dir, "zerre_model.npz")
    out_path = os.path.join(base_dir, "makale", "scripts", "remedies_v06_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    out = {"seeds": seeds, "version": "v0.6"}
    def _save():
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    print("═" * 82, flush=True)
    print(f"  ZERRE v0.6 TEKNİK ÇÖZÜMLER KIYASLAMASI · Seeds={seeds}", flush=True)
    print("═" * 82, flush=True)

    # ── 1) Uzamsal Paketleme (Spatial Batching) ─────────────────────────────────
    print("\n[1/3] Uzamsal Paketleme (Spatial Batching) & 2K/4K/8K Kare Kapasitesi...", flush=True)
    twin_sb, d_sb = load_twin_from_npz(model_path)
    X_sb, y_sb, n_tr_sb = load_mnist(100, 1000, np.random.default_rng(seeds[0]), mnist_dir)
    X_te_sb, y_te_sb = X_sb[n_tr_sb:n_tr_sb + 64], y_sb[n_tr_sb:n_tr_sb + 64]
    W_sb = d_sb["W_volt"]

    def _pred_npz(F):
        fs = (F - d_sb["mu"]) / d_sb["sd"]
        if "mlp_W1" in d_sb:
            h = np.maximum(0.0, fs @ d_sb["mlp_W1"] + d_sb["mlp_b1"])
            return np.argmax(h @ d_sb["mlp_W2"] + d_sb["mlp_b2"], axis=1)
        return np.argmax(np.hstack([fs, np.ones((len(fs), 1))]) @ d_sb["Wout"], axis=1)

    F_single = twin_sb.forward_batch(X_te_sb, W_sb, batch_size=64)
    acc_single = float((_pred_npz(F_single) == y_te_sb).mean()) * 100.0
    sb_rows = []
    for gk in (2, 4):
        eng = SpatialBatchEngine(twin_sb, grid_k=gk)
        xt = eng.measure_crosstalk(X_te_sb[0], W_sb)
        t0 = time.time()
        F_blk = np.vstack([
            eng.forward_frame(X_te_sb[i:i + eng.n_tiles], W_sb)
            for i in range(0, len(X_te_sb), eng.n_tiles)
        ])
        dt_ms = (time.time() - t0) * 1000.0
        rel_diff = float(np.linalg.norm(F_blk - F_single) / (np.linalg.norm(F_single) + 1e-12))
        acc_b = float((_pred_npz(F_blk) == y_te_sb).mean()) * 100.0
        row = {
            "grid": f"{gk}x{gk}", "tiles_per_frame": eng.n_tiles, "N_big": eng.N_big,
            "crosstalk_ratio": float(f"{xt['crosstalk_ratio']:.3e}"),
            "crosstalk_db": xt["crosstalk_db"],
            "rel_feat_diff": float(f"{rel_diff:.3e}"),
            "acc_batched": round(acc_b, 2), "acc_single": round(acc_single, 2),
            "batch_64_imgs_ms": round(dt_ms, 1),
        }
        sb_rows.append(row)
        print(f"  {row['grid']} ({eng.n_tiles} karo/kare): crosstalk={row['crosstalk_ratio']:.2e} "
              f"({row['crosstalk_db']} dB) · acc={acc_b:.2f}% (tekil {acc_single:.2f}%)", flush=True)
    out["spatial_batching"] = {
        "n_test_sample": 64, "configs": sb_rows, "panel_throughput": panel_spatial_throughput(),
    }
    _save()

    # ── 2) Yapısal Model-Uyumsuzluğu: Kara-Kutu Kalibre Vekil PAT (3 Tohum) ─────
    print("\n[2/3] Yapısal Uyumsuzluk Altında Kara-Kutu Kalibre Vekil PAT (3 Tohum)...", flush=True)
    sm_runs = []
    for s in seeds:
        twin_s = ZerreTwin(n_grid=128, n_ito=32, cam_n=8, drive_mode="active")
        X_s, y_s, n_trs = load_mnist(2200, 1000, np.random.default_rng(s), mnist_dir)
        X_trs, y_trs = X_s[:n_trs], y_s[:n_trs]
        X_tes, y_tes = X_s[n_trs:], y_s[n_trs:]
        sm_plant = PhysicalPlantSimulator(twin_s, seed=s, structural=True)
        E_tr_sm = sm_plant.precompute_cells(X_trs)
        E_te_sm = sm_plant.precompute_cells(X_tes)

        W_init_s = np.random.default_rng(s).uniform(1.4, 3.8, (32, 32))
        W_ideal_s, mu_id, sd_id, Wout_id, _, _, _ = pat_train(
            twin_s, X_trs[:1950], y_trs[:1950], X_trs[1950:], y_trs[1950:],
            W_init_s, 10, epochs=16, bs=256, lr_opt=0.10, lr_head=2.5e-2,
            physical_plant=None, use_mlp=False, rng=np.random.default_rng(s), verbose=False,
        )
        acc_uncomp = _eval_linear_test(sm_plant.forward_cached(E_te_sm, W_ideal_s, False), y_tes, mu_id, sd_id, Wout_id)

        F_tr_ho = sm_plant.forward_cached(E_tr_sm[:1950], W_ideal_s, noisy=False)
        F_va_ho = sm_plant.forward_cached(E_tr_sm[1950:], W_ideal_s, noisy=False)
        mu_ho, sd_ho = fit_standardizer(F_tr_ho)
        Wout_ho = _fit_ce_linear_head(
            apply_standardizer(F_tr_ho, mu_ho, sd_ho), y_trs[:1950],
            apply_standardizer(F_va_ho, mu_ho, sd_ho), y_trs[1950:],
            10, epochs=16, bs=256, lr_head=2.5e-2, rng=np.random.default_rng(s),
        )
        acc_ho = _eval_linear_test(sm_plant.forward_cached(E_te_sm, W_ideal_s, False), y_tes, mu_ho, sd_ho, Wout_ho)

        W_bl, mu_bl, sd_bl, Wout_bl, _, _, _ = pat_train(
            twin_s, X_trs[:1950], y_trs[:1950], X_trs[1950:], y_trs[1950:],
            W_init_s, 10, epochs=24, bs=256, lr_opt=0.10, lr_head=2.5e-2,
            physical_plant=sm_plant, use_mlp=False, rng=np.random.default_rng(s),
            verbose=False, polish_head=True,
        )
        acc_bl = _eval_linear_test(sm_plant.forward_cached(E_te_sm, W_bl, False), y_tes, mu_bl, sd_bl, Wout_bl)

        cal_twin, cal_info = calibrate_surrogate_blackbox(twin_s, sm_plant, X_trs[:1950], seed=s)
        W_cal, mu_cal, sd_cal, Wout_cal, _, _, _ = pat_train(
            cal_twin, X_trs[:1950], y_trs[:1950], X_trs[1950:], y_trs[1950:],
            W_init_s, 10, epochs=24, bs=256, lr_opt=0.10, lr_head=2.5e-2,
            physical_plant=sm_plant, use_mlp=False, rng=np.random.default_rng(s),
            verbose=False, polish_head=True,
        )
        acc_cal = _eval_linear_test(sm_plant.forward_cached(E_te_sm, W_cal, False), y_tes, mu_cal, sd_cal, Wout_cal)

        # Gradyan kosinüs hizalaması (40 örnek ağırlıkta gerçek sonlu farklara karşı)
        Xb_g = X_trs[:8]
        Ep_g = sm_plant.precompute_cells(Xb_g)
        En_g = twin_s.prop1(twin_s.encode_lcd(Xb_g).astype(np.complex64))
        Ec_g = cal_twin.prop1(cal_twin.encode_lcd(Xb_g).astype(np.complex64))
        F_p0 = sm_plant.forward_cached(Ep_g, W_init_s, noisy=False)
        tgt_g = np.random.default_rng(s + 5).normal(0.0, 1.0, F_p0.shape)
        gf_g = F_p0 - tgt_g
        gb_full = twin_s.backward_cached(En_g, W_init_s, gf_g)
        gc_full = cal_twin.backward_cached(Ec_g, W_init_s, gf_g)
        gt_s, gb_s, gc_s = [], [], []
        eps_g = 1e-4
        for ii in range(0, 32, 4):
            for jj in range(0, 32, 6):
                Wp = W_init_s.copy(); Wp[ii, jj] += eps_g
                Wm = W_init_s.copy(); Wm[ii, jj] -= eps_g
                lp = 0.5 * float(np.sum((sm_plant.forward_cached(Ep_g, Wp, False) - tgt_g) ** 2))
                lm = 0.5 * float(np.sum((sm_plant.forward_cached(Ep_g, Wm, False) - tgt_g) ** 2))
                gt_s.append((lp - lm) / (2.0 * eps_g))
                gb_s.append(gb_full[ii, jj])
                gc_s.append(gc_full[ii, jj])
        gt_a, gb_a, gc_a = map(np.array, (gt_s, gb_s, gc_s))
        cos_bl = float(np.dot(gt_a, gb_a) / (np.linalg.norm(gt_a) * np.linalg.norm(gb_a) + 1e-12))
        cos_cal = float(np.dot(gt_a, gc_a) / (np.linalg.norm(gt_a) * np.linalg.norm(gc_a) + 1e-12))

        sm_runs.append({
            "seed": s, "uncompensated": round(acc_uncomp, 2), "head_only": round(acc_ho, 2),
            "blind_pat_polished": round(acc_bl, 2), "calibrated_pat_polished": round(acc_cal, 2),
            "cos_blind": round(cos_bl, 4), "cos_calibrated": round(cos_cal, 4),
            "calibration": cal_info,
        })
        print(f"  [Seed {s}] Head-only={acc_ho:.2f}% | Blind={acc_bl:.2f}% (cos={cos_bl:.4f}) | "
              f"Calibrated PAT={acc_cal:.2f}% (cos={cos_cal:.4f}, γ={cal_info['gamma_hat']}, "
              f"shift={cal_info['shifts']})", flush=True)

    out["calibrated_structural_mismatch"] = {
        "n_train": 2200, "n_test": 1000, "pat_epochs": 24, "polish_epochs": 16,
        "uncompensated": _agg_stats([r["uncompensated"] for r in sm_runs]),
        "head_only": _agg_stats([r["head_only"] for r in sm_runs]),
        "blind_pat_polished": _agg_stats([r["blind_pat_polished"] for r in sm_runs]),
        "calibrated_pat_polished": _agg_stats([r["calibrated_pat_polished"] for r in sm_runs]),
        "grad_cos_blind_mean": round(float(np.mean([r["cos_blind"] for r in sm_runs])), 4),
        "grad_cos_calibrated_mean": round(float(np.mean([r["cos_calibrated"] for r in sm_runs])), 4),
        "per_seed": sm_runs,
    }
    _save()

    # ── 3) Katlanmış Çok-Katmanlı + Diferansiyel Okuma (8×8, 3 Tohum) ──────────
    print("\n[3/3] Katlanmış Çok-Katmanlı (L=1,2,3) + Diferansiyel Okuma (8×8, 3 Tohum)...", flush=True)
    mp_cfgs = [
        ("l1_jones_pos", 1, "jones", False),
        ("l1_jones_diff", 1, "jones", True),
        ("l2_jones_diff", 2, "jones", True),
        ("l3_phase_diff", 3, "phase", True),
    ]
    mp_per_cfg = {k: [] for k, _, _, _ in mp_cfgs}
    for s in seeds:
        X_m, y_m, n_tr_m = load_mnist(3000, 1000, np.random.default_rng(s), mnist_dir)
        n_val_m = int(round(0.12 * n_tr_m))
        n_fit_m = n_tr_m - n_val_m
        X_fit, y_fit = X_m[:n_fit_m], y_m[:n_fit_m]
        X_val, y_val = X_m[n_fit_m:n_tr_m], y_m[n_fit_m:n_tr_m]
        X_te, y_te = X_m[n_tr_m:], y_m[n_tr_m:]
        r_s = np.random.default_rng(s)
        W_pool_init = [r_s.uniform(1.5, 4.0, (32, 32)) for _ in range(3)]
        seed_line = []
        for key, n_lay, mod_t, diff_flag in mp_cfgs:
            mp = FoldedMultiPassTwin(128, 32, 8, n_layers=n_lay, modulation=mod_t, differential=diff_flag)
            plant = FoldedMultiPassPlant(mp, seed=s)
            W_b, mu_b, sd_b, Wout_b, fwd_b = pat_train_multipass(
                mp, X_fit, y_fit, X_val, y_val, W_pool_init[:n_lay],
                n_cls=10, epochs=20, bs=256, lr_opt=0.10, lr_head=2.5e-2,
                physical_plant=plant, polish_head=True, val_every=2,
                rng=np.random.default_rng(s), verbose=False,
            )
            E_te_p = plant.precompute_cells(X_te)
            acc = _eval_linear_test(fwd_b(E_te_p, W_b, False), y_te, mu_b, sd_b, Wout_b)
            mp_per_cfg[key].append(acc)
            seed_line.append(f"{key}={acc:.2f}%")
        print(f"  [Seed {s}] " + " | ".join(seed_line), flush=True)
        out["multipass_differential"] = {
            "config": {"n_fit": n_fit_m, "n_val": n_val_m, "n_test": 1000, "cam_n": 8,
                       "dig_w": 650, "epochs": 20, "polish_epochs": 16},
            "rows": {k: _agg_stats(v) for k, v in mp_per_cfg.items() if v},
        }
        _save()

    out["total_runtime_s"] = round(time.time() - t_all, 1)
    _save()
    print("═" * 82, flush=True)
    print(f"  [TAMAM] v0.6 çözüm sonuçları kaydedildi: {out_path} ({out['total_runtime_s']}s)", flush=True)
    print("═" * 82, flush=True)
    return out


# ─────────────────────────────────────────────────────────────────
#  ANA AKIŞ
# ─────────────────────────────────────────────────────────────────
def main():
    global N_CLS, CAM_N

    ap = argparse.ArgumentParser(description="Zerre Model H dijital ikizi v0.4")
    ap.add_argument("--grid", type=int, default=256, help="simülasyon ızgarası (vars: 256)")
    ap.add_argument("--n-ito", type=int, default=16, help="ağırlık matrisi boyutu (16 veya 32)")
    ap.add_argument("--mode", choices=["active", "passive", "none"], default="active",
                    help="sürüş modu: active (TFT/bağımsız), passive (Alt-Pleshko RMS), none")
    ap.add_argument("--n", type=int, default=120, help="sentetik sınıf başına örnek (vars: 120)")
    ap.add_argument("--spsa", type=int, default=12, help="SPSA adım sayısı (0=atla)")
    ap.add_argument("--pat", action="store_true",
                    help="Physics-Aware Training (kusurlu fiziksel ileri + vekil adjoint geri)")
    ap.add_argument("--pat-epochs", type=int, default=25, help="PAT epok sayısı (vars: 25)")
    ap.add_argument("--mnist", action="store_true", help="gerçek MNIST kullan")
    ap.add_argument("--mnist-train", type=int, default=4000)
    ap.add_argument("--mnist-test", type=int, default=1000)
    ap.add_argument("--cam", type=int, default=CAM_N, help="kamera özellik ızgarası (vars: 16)")
    ap.add_argument("--hybrid", action="store_true", help="hibrit MLP okuma kafası")
    ap.add_argument("--predict", type=str, default=None, metavar="FOTO")
    ap.add_argument("--model", type=str, default=None)
    ap.add_argument("--robust", action="store_true", help="mekanik dayanım testi")
    ap.add_argument("--env", action="store_true", help="çevresel hassasiyet testi")
    ap.add_argument("--grad-check", action="store_true", help="analitik adjoint türev testi")
    ap.add_argument("--ablation", action="store_true", help="sızıntısız kontrollü ablasyon tablosu üret")
    ap.add_argument("--fashion", action="store_true", help="Fashion-MNIST veri kümesini kullan")
    ap.add_argument("--download-fashion", action="store_true", help="yalnız Fashion-MNIST önbelleğini indir ve çık")
    ap.add_argument("--hw-realism", action="store_true",
                    help="v0.4 donanım gerçekçilik paketi (kuantizasyon, doluluk, Zernike, Fashion-MNIST)")
    ap.add_argument("--paper-benchmark", action="store_true",
                    help="çoklu-tohum makale kıyaslama paketini çalıştırıp paper_results.json üret")
    ap.add_argument("--remedies-benchmark", action="store_true",
                    help="v0.6 teknik çözüm paketini (katlanmış çok-katman, kalibre vekil, uzamsal paketleme) çalıştır")
    ap.add_argument("--seeds", type=str, default="7,19,42",
                    help="--paper-benchmark için virgülle ayrılmış tohum listesi (vars: 7,19,42)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    model_path = args.model or os.path.join(base_dir, "zerre_model.npz")

    if args.download_fashion:
        fcache = os.path.join(base_dir, "fashion_mnist_cache")
        load_fashion_mnist(10, 10, np.random.default_rng(args.seed), fcache)
        print(f"[TAMAM] Fashion-MNIST önbelleği hazır: {fcache}")
        return

    if args.paper_benchmark:
        seed_list = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
        run_paper_benchmark(base_dir, seeds=seed_list)
        return

    if args.remedies_benchmark:
        seed_list = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
        run_remedies_benchmark(base_dir, seeds=seed_list)
        return

    if args.hw_realism:
        run_hardware_realism_suite(base_dir, seed=args.seed)
        return

    if args.grad_check:
        grad_check()
        return

    if args.ablation:
        run_ablation(
            n_train=args.mnist_train,
            n_test=args.mnist_test,
            cam_n=args.cam if args.cam != CAM_N else 8,
            grid=args.grid if args.grid != 256 else 128,
            seed=args.seed,
        )
        return

    if args.predict:
        predict_photo(args.predict, model_path)
        return

    if args.robust:
        robustness_test(model_path, n_test=args.mnist_test, seed=args.seed)
        return

    if args.env:
        env_test(model_path, n_test=args.mnist_test, seed=args.seed)
        return

    CAM_N = args.cam
    rng   = np.random.default_rng(args.seed)
    twin  = ZerreTwin(args.grid, n_ito=args.n_ito, cam_n=CAM_N, drive_mode=args.mode)

    print("═" * 68)
    print("  ZERRE — Model H Dijital İkizi v0.4")
    print(f"  Izgara {args.grid}² · LCD pikseli {PIX * 1e6:.0f}μm · Z1=Z2={Z1 * 100:.0f}cm")
    print(f"  Ağırlık {args.n_ito}×{args.n_ito} ({args.n_ito**2}) [{args.mode.upper()}] · "
          f"Kamera {CAM_N}×{CAM_N} ({CAM_N**2}) özellik")
    print("═" * 68)

    if args.fashion:
        N_CLS = 10
        cache = os.path.join(base_dir, "fashion_mnist_cache")
        X, y, n_tr = load_fashion_mnist(args.mnist_train, args.mnist_test, rng, cache)
        print(f"[VERI] Fashion-MNIST · egitim {n_tr} · test {len(y) - n_tr} (veri sizintisi: YOK)")
    elif args.mnist:
        N_CLS = 10
        cache = os.path.join(base_dir, "mnist_cache")
        X, y, n_tr = load_mnist(args.mnist_train, args.mnist_test, rng, cache)
        print(f"[VERI] MNIST · egitim {n_tr} · test {len(y) - n_tr} (veri sizintisi: YOK)")
    else:
        N_CLS = 5
        X, y = make_shapes(args.n, rng)
        n_tr = int(len(y) * 0.8)
        print(f"[VERI] sentetik {N_CLS} sinif · egitim {n_tr} · test {len(y) - n_tr}")

    # ── Aşama 1: Sabit rastgele optik + sızıntısız Ridge ─────────
    t0 = time.time()
    if args.mode == "passive":
        W_rand = rng.uniform(-1.0, 1.0, (args.n_ito, args.n_ito))
    else:
        W_rand = rng.uniform(1.2, 3.2, (args.n_ito, args.n_ito))

    F = twin.forward_batch(X, W_rand)
    F_std, mu, sd = standardize_split(F, n_tr)
    W_out = fit_ridge(F_std[:n_tr], y[:n_tr], N_CLS)
    acc1_tr = float((predict_ridge(F_std[:n_tr], W_out) == y[:n_tr]).mean())
    acc1_te = float((predict_ridge(F_std[n_tr:], W_out) == y[n_tr:]).mean())
    print(f"[ASAMA 1] rastgele optik + ridge → egitim %{acc1_tr * 100:.1f} · "
          f"TEST %{acc1_te * 100:.1f}   ({time.time() - t0:.1f}s)")

    best_W    = W_rand
    best_mu   = mu
    best_sd   = sd
    best_Wout = W_out
    best_mlp  = None
    acc_h     = None
    acc_pat   = None
    hist      = []

    # ── PAT (Physics-Aware Training) Modu ────────────────────────
    if args.pat:
        t0 = time.time()
        print(f"[PAT] Kusurlu fiziksel ileri gecis + vekil adjoint geri gecis basliyor "
              f"({args.pat_epochs} epok)...")
        plant = PhysicalPlantSimulator(twin, seed=args.seed)
        n_val = max(100, int(n_tr * 0.12))
        W_pat, mu_pat, sd_pat, Wout_pat, mlp_pat, hist, fwd_pat = pat_train(
            twin,
            X[:n_tr - n_val], y[:n_tr - n_val],
            X[n_tr - n_val:n_tr], y[n_tr - n_val:n_tr],
            W_rand, N_CLS,
            epochs=args.pat_epochs, bs=64,
            lr_opt=0.07, lr_head=(2e-3 if args.hybrid else 2e-2),
            physical_plant=plant, use_mlp=args.hybrid, rng=rng, verbose=True,
        )
        E_te_phy = plant.precompute_cells(X[n_tr:])
        F_te_phy = (fwd_pat(E_te_phy, W_pat, False) - mu_pat) / sd_pat
        if args.hybrid and mlp_pat is not None:
            acc_pat = float((mlp_pat.predict(F_te_phy) == y[n_tr:]).mean())
        else:
            acc_pat = float((predict_ridge(F_te_phy, Wout_pat) == y[n_tr:]).mean())
        print(f"[PAT] egitim tamamlandi → Fiziksel TEST %{acc_pat * 100:.1f}   ({time.time() - t0:.1f}s)")

        F_clean = twin.forward_batch(X[:n_tr], W_pat)
        mu_c, sd_c = fit_standardizer(F_clean)
        F_clean_std = apply_standardizer(F_clean, mu_c, sd_c)
        Wout_c = fit_ridge(F_clean_std, y[:n_tr], N_CLS)
        mlp_c = None
        if args.hybrid:
            n_val = max(100, int(n_tr * 0.1))
            mlp_c = MLPHead(F_clean_std.shape[1], 256, N_CLS, rng)
            mlp_c.train(F_clean_std[:n_tr - n_val], y[:n_tr - n_val],
                        F_clean_std[n_tr - n_val:n_tr], y[n_tr - n_val:n_tr], epochs=45, verbose=False)
            F_te_c = apply_standardizer(twin.forward_batch(X[n_tr:], W_pat), mu_c, sd_c)
            acc_h = float((mlp_c.predict(F_te_c) == y[n_tr:]).mean())
            print(f"[PAT+HIBRIT] temiz optik ikizde TEST %{acc_h * 100:.1f}")
        best_W, best_mu, best_sd, best_Wout, best_mlp = W_pat, mu_c, sd_c, Wout_c, mlp_c

    else:
        if args.hybrid:
            t0 = time.time()
            n_val = max(100, int(n_tr * 0.1))
            best_mlp = MLPHead(F_std.shape[1], 256, N_CLS, rng)
            print(f"[HIBRIT] MLP kafa egitiliyor · {F_std.shape[1]}→256→{N_CLS} "
                  f"({best_mlp.n_params():,} dijital parametre)")
            best_mlp.train(F_std[:n_tr - n_val], y[:n_tr - n_val],
                           F_std[n_tr - n_val:n_tr], y[n_tr - n_val:n_tr])
            acc_h = float((best_mlp.predict(F_std[n_tr:]) == y[n_tr:]).mean())
            print(f"[HIBRIT] optik on-uc + MLP kafa → TEST %{acc_h * 100:.1f}   ({time.time() - t0:.1f}s)")

        acc2_te, acc_bad = None, None
        if args.spsa > 0:
            t0 = time.time()
            W_bad = np.full((args.n_ito, args.n_ito), 0.9 if args.mode == "passive" else 4.3)
            Fb = twin.forward_batch(X, W_bad)
            Fb_std, _, _ = standardize_split(Fb, n_tr)
            Wob = fit_ridge(Fb_std[:n_tr], y[:n_tr], N_CLS)
            acc_bad = float((predict_ridge(Fb_std[n_tr:], Wob) == y[n_tr:]).mean())
            print(f"[ASAMA 2] kotu baslangic → TEST %{acc_bad * 100:.1f}")

            n_sub = min(200, n_tr)
            E_cells = twin.field_at_cell(X[:n_sub])
            print(f"[ASAMA 2] SPSA basliyor · {n_sub} ornek · {args.spsa} adim")
            W_spsa, hist = spsa_train(twin, E_cells, y[:n_sub], W_bad, args.spsa, rng, n_cls=N_CLS)

            F2 = twin.forward_batch(X, W_spsa)
            F2_std, mu2, sd2 = standardize_split(F2, n_tr)
            W_out2 = fit_ridge(F2_std[:n_tr], y[:n_tr], N_CLS)
            acc2_te = float((predict_ridge(F2_std[n_tr:], W_out2) == y[n_tr:]).mean())
            print(f"[ASAMA 2] SPSA sonrasi → TEST %{acc2_te * 100:.1f}   ({time.time() - t0:.1f}s)")
            if acc2_te >= acc1_te and best_mlp is None:
                best_W, best_mu, best_sd, best_Wout = W_spsa, mu2, sd2, W_out2

    # ── En iyi modeli diske kaydet (SPSA/PAT sonrası!) ───────────
    save_model(
        model_path, best_W, best_mu, best_sd, best_Wout, best_mlp,
        args.grid, CAM_N, N_CLS, n_ito=args.n_ito, drive_mode=args.mode,
        metadata={"seed": args.seed, "n_train": n_tr, "n_test": int(len(y) - n_tr), "version": "v0.4"},
    )

    # ── Görsel çıktı ─────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sample = X[n_tr]
        info = twin.inspect_forward(sample, best_W)

        fig, ax = plt.subplots(1, 5, figsize=(19, 4))
        fig.patch.set_facecolor("#04080c")
        panels = [
            (sample, "Giris goruntusu (mSLA LCD)", "gray"),
            (info["E_cell_amp"], "|E| hucre girisinde (Z1 sonrasi)", "viridis"),
            (info["ito_phase"], f"Faz haritasi Δφ(V) [{args.mode}]", "plasma"),
            (info["I_cam"] ** 0.4, "CMOS yogunluk |E|² (gamma 0.4)", "inferno"),
        ]
        for i, (im, title, cmap) in enumerate(panels):
            ax[i].imshow(im, cmap=cmap)
            ax[i].set_title(title, color="w", fontsize=9)
            ax[i].axis("off")
        if hist:
            ax[4].plot(hist, color="#39ff14", linewidth=1.8)
            ax[4].set_title("Egitim kaybi (PAT / SPSA)", color="w", fontsize=9)
            ax[4].tick_params(colors="w", labelsize=7)
            ax[4].set_facecolor("#0a141c")
        else:
            ax[4].axis("off")
        fig.suptitle("ZERRE Model H — Dijital Ikiz v0.4", color="#00f5ff", fontsize=12)
        fig.tight_layout()
        out = os.path.join(base_dir, "twin_output.png")
        fig.savefig(out, dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"[GORSEL] kaydedildi: {out}")
    except ImportError:
        print("[GORSEL] matplotlib yok — gorsel cikti atlandi")

    print("─" * 68)
    print(f"  Asama 1 (sabit rastgele optik + ridge) : TEST %{acc1_te * 100:.1f}")
    if acc_pat is not None:
        print(f"  PAT (kusurlu fizik + vekil geri gecis) : TEST %{acc_pat * 100:.1f}")
    if acc_h is not None:
        print(f"  HIBRIT (optik on-uc + MLP kafa)        : TEST %{acc_h * 100:.1f}")
    print("═" * 68)


if __name__ == "__main__":
    main()
