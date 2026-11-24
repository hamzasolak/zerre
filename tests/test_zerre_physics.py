#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit and physics verification tests for the ZERRE Model H digital twin."""

import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import zerre_twin as zt


def test_adjoint_gradients():
    rng = np.random.default_rng(123)
    X, _ = zt.make_shapes(4, rng)
    Xb = X[:6]
    for mode in ("active", "passive"):
        twin = zt.ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode=mode)
        E_cells = twin.field_at_cell(Xb)
        W = rng.uniform(1.3, 4.5, (8, 8)) if mode == "active" else rng.uniform(-0.8, 0.8, (8, 8))
        target = rng.normal(0.0, 1.0, (len(Xb), 64))
        F0 = twin.forward_cached(E_cells, W)
        g_an = twin.backward_cached(E_cells, W, F0 - target).ravel()

        eps = 1e-6
        g_fd = np.zeros_like(W)
        for i in range(8):
            for j in range(8):
                Wp = W.copy(); Wp[i, j] += eps
                Wm = W.copy(); Wm[i, j] -= eps
                lp = 0.5 * float(np.sum((twin.forward_cached(E_cells, Wp) - target) ** 2))
                lm = 0.5 * float(np.sum((twin.forward_cached(E_cells, Wm) - target) ** 2))
                g_fd[i, j] = (lp - lm) / (2.0 * eps)
        rel_err = float(np.linalg.norm(g_an - g_fd.ravel()) / (np.linalg.norm(g_fd) + 1e-12))
        assert rel_err < 1e-5, f"{mode} adjoint gradient mismatch: {rel_err}"
        print(f"  [PASS] Adjoint gradient ({mode}): rel_L2_err = {rel_err:.3e}")


def test_alt_pleshko_limit():
    ratio16 = zt.passive_selection_ratio(16)
    expected = np.sqrt((4.0 + 1.0) / (4.0 - 1.0))
    assert abs(ratio16 - expected) < 1e-9
    swing_active = float(zt.lc_phase(1.0) - zt.lc_phase(5.0))
    swing_passive = float(zt.lc_phase(1.0) - zt.lc_phase(ratio16))
    assert abs(swing_active - 4.86) < 0.02
    assert abs(swing_passive - 0.92) < 0.03
    print(f"  [PASS] Alt-Pleshko N=16: ratio={ratio16:.6f}, active={swing_active:.2f} rad, passive={swing_passive:.2f} rad")


def test_single_sd_floor_and_infer():
    rng = np.random.default_rng(7)
    F = rng.uniform(0.0, 1.0, (20, 64))
    F[:, 0] = 0.0  # dark corner pixel with near-zero std
    mu, sd = zt.fit_standardizer(F)
    # Applying fit_standardizer vs apply_standardizer matches, unlike double sd_floor
    assert float(sd[0]) > 0.0
    z1 = zt.apply_standardizer(F, mu, sd)
    assert np.all(np.isfinite(z1))
    # Verify single sd_floor differs from mistakenly re-flooring stored sd
    assert float(zt.sd_floor(sd)[0]) > float(sd[0])
    print("  [PASS] Single sd_floor contract verified.")


def test_pool_area_and_zernike_seeds():
    imgs = np.zeros((3, 28, 28), dtype=float)
    imgs[:, 6:22, 6:22] = 1.0
    pooled = zt.pool_area(imgs, cam_n=8)
    assert pooled.shape == (3, 64)
    assert np.all((pooled >= 0.0) & (pooled <= 1.0))

    ab1 = zt.make_zernike_aberration(128, 5.0, seed=101)
    ab2 = zt.make_zernike_aberration(128, 5.0, seed=202)
    assert np.max(np.abs(ab1 - ab2)) > 0.2, "Zernike seeds failed to generate distinct wavefronts"
    print("  [PASS] pool_area shape/bounds and Zernike seed independence verified.")


def test_shift_crop_edge_loss():
    """Kenar-kayıplı kaydırma: ışık sarmalanmaz, boşalan bölge sıfırlanır."""
    a = np.zeros((4, 8, 8))
    a[:, :, 3] = 1.0
    shifted = zt.shift_crop(a, 0, 2)
    assert np.allclose(shifted[:, :, 5], 1.0)
    assert np.allclose(shifted[:, :, :2], 0.0)
    assert float(shifted.sum()) == float(a.sum())
    off = zt.shift_crop(a, 0, -3)
    assert np.allclose(off[:, :, 0], 1.0)
    assert float(off[:, :, -3:].sum()) == 0.0
    edge = np.zeros((4, 8, 8))
    edge[:, :, -1] = 1.0
    wrapped = np.roll(edge, 1, axis=-1)
    cropped = zt.shift_crop(edge, 0, 1)
    assert float(wrapped[:, :, 0].sum()) == 32.0, "np.roll should wrap edge energy"
    assert float(cropped[:, :, 0].sum()) == 0.0, "shift_crop must drop edge energy, not wrap it"
    assert float(cropped.sum()) == 0.0
    print("  [PASS] shift_crop edge-loss (no wrap-around) verified.")


def test_phi_scale_explicit():
    """Faz ölçeği artık açık parametre: global durum yok, çağrılar bağımsız."""
    v = 2.5
    base = zt.lc_phase(v)
    hot = zt.lc_phase(v, phi_scale=1.2)
    assert abs(float(hot) - 1.2 * float(base)) < 1e-12
    assert abs(float(zt.lc_phase(v)) - float(base)) < 1e-12, "phi_scale leaked between calls"
    g0 = zt.lc_phase_grad(v)
    g1 = zt.lc_phase_grad(v, phi_scale=1.2)
    assert abs(float(g1) - 1.2 * float(g0)) < 1e-12
    twin = zt.ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode="active")
    rng = np.random.default_rng(3)
    Xb = rng.uniform(0.0, 1.0, (2, 28, 28))
    W = rng.uniform(1.3, 4.5, (8, 8))
    F_nom = twin.forward_batch(Xb, W)
    F_hot = twin.forward_batch(Xb, W, phi_scale=1.15)
    F_nom2 = twin.forward_batch(Xb, W)
    assert np.allclose(F_nom, F_nom2), "forward_batch phi_scale state leaked"
    assert not np.allclose(F_nom, F_hot), "phi_scale had no effect"
    tab = zt.PHI_TAB * 0.9
    F_tab = twin.forward_batch(Xb, W, phi_tab=tab)
    assert not np.allclose(F_nom, F_tab), "phi_tab had no effect"
    print("  [PASS] Explicit phi_scale/phi_tab (no global state) verified.")


def test_zernike_zero_pv_continuity():
    """pv=0 ile pv>0 arasında demet zarfı basamağı kalmamalı."""
    ab0 = zt.make_zernike_aberration(128, 0.0, seed=42)
    ab_eps = zt.make_zernike_aberration(128, 0.01, seed=42)
    env0 = np.abs(ab0)
    assert np.all(env0 < 1.0), "beam envelope missing at pv=0"
    assert np.allclose(env0, np.abs(ab_eps), atol=0.05), "envelope step between pv=0 and small pv"
    print("  [PASS] Zernike beam-envelope continuity at pv=0 verified.")


def test_server_status_lock():
    import start_server
    eng = start_server.LiveOpticalEngine(ROOT)
    st = eng.status()
    assert "is_trained_model" in st
    assert st["grid"] > 0
    print(f"  [PASS] start_server LiveOpticalEngine status lock verified (trained={st['is_trained_model']}).")


def test_multipass_differential_adjoint_gradients():
    """FoldedMultiPassTwin (L=2 Jones, L=3 Phase) + diferansiyel okuma analitik gradyan testi."""
    rng = np.random.default_rng(77)
    X, _ = zt.make_shapes(3, rng)
    Xb = X[:4]
    eps = 1e-6
    for n_lay, mod_t in [(2, "jones"), (3, "phase")]:
        mp = zt.FoldedMultiPassTwin(n_grid=64, n_ito=8, cam_n=8, n_layers=n_lay, modulation=mod_t, differential=True)
        W_list = [rng.uniform(1.4, 4.4, (8, 8)) for _ in range(n_lay)]
        Ec = mp.field_at_cell(Xb, dtype=np.complex128)
        target = rng.normal(0.0, 1.0, (len(Xb), 64))
        F0, E_bef, M_lst = mp.forward_cached(Ec, W_list, return_cache=True)
        g_an = mp.backward_cached(E_bef, M_lst, W_list, F0 - target)
        # Her katman için sonlu fark kontrolü
        for l_idx in range(n_lay):
            g_fd = np.zeros((8, 8))
            for i in range(0, 8, 2):
                for j in range(0, 8, 2):
                    Wp = W_list[l_idx].copy(); Wp[i, j] += eps
                    Wm = W_list[l_idx].copy(); Wm[i, j] -= eps
                    lp = 0.5 * float(np.sum((mp.forward_cached(Ec, W_list[:l_idx] + [Wp] + W_list[l_idx + 1:]) - target) ** 2))
                    lm = 0.5 * float(np.sum((mp.forward_cached(Ec, W_list[:l_idx] + [Wm] + W_list[l_idx + 1:]) - target) ** 2))
                    g_fd[i, j] = (lp - lm) / (2.0 * eps)
            an_sub = g_an[l_idx][::2, ::2].ravel()
            fd_sub = g_fd[::2, ::2].ravel()
            rel = float(np.linalg.norm(an_sub - fd_sub) / (np.linalg.norm(fd_sub) + 1e-12))
            assert rel < 1e-5, f"MultiPass L={n_lay} mod={mod_t} layer {l_idx} grad err={rel}"
        print(f"  [PASS] FoldedMultiPass L={n_lay} ({mod_t}, differential) all-layer adjoint err < 1e-5.")


def test_calibrated_surrogate_adjoint_gradients():
    """CalibratedSurrogateTwin (gamma, kayma, kazanç, LUT) analitik adjoint doğrulaması."""
    rng = np.random.default_rng(88)
    X, _ = zt.make_shapes(3, rng)
    Xb = X[:4]
    tw = zt.ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode="active")
    phi_p = zt.PHI_TAB * np.array([0.92, 0.94, 1.06, 0.90, 1.08, 0.95])
    cal = zt.CalibratedSurrogateTwin(tw, phi_p, gamma_hat=0.88,
                                     gain_map=rng.uniform(0.7, 1.3, 64), shifts=(1, 0, 0, 1))
    Ec = cal.field_at_cell(Xb)
    W = rng.uniform(1.4, 4.4, (8, 8))
    target = rng.normal(0.0, 1.0, (len(Xb), 64))
    F0 = cal.forward_cached(Ec, W)
    g_an = cal.backward_cached(Ec, W, F0 - target)
    eps = 1e-6
    g_fd = np.zeros((8, 8))
    for i in range(8):
        for j in range(8):
            Wp = W.copy(); Wp[i, j] += eps
            Wm = W.copy(); Wm[i, j] -= eps
            lp = 0.5 * float(np.sum((cal.forward_cached(Ec, Wp) - target) ** 2))
            lm = 0.5 * float(np.sum((cal.forward_cached(Ec, Wm) - target) ** 2))
            g_fd[i, j] = (lp - lm) / (2.0 * eps)
    rel = float(np.linalg.norm(g_an - g_fd) / (np.linalg.norm(g_fd) + 1e-12))
    assert rel < 1e-5, f"CalibratedSurrogateTwin grad err={rel}"
    print(f"  [PASS] CalibratedSurrogateTwin adjoint gradient: rel_L2_err = {rel:.3e}")


def test_blackbox_calibration_recovery():
    """Kara-kutu kalibrasyonun kayma, gamma ve gerçek plant gradyan hizalamasını kurtarması."""
    rng = np.random.default_rng(7)
    X, _ = zt.make_shapes(8, rng)
    tw = zt.ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode="active")
    plant = zt.PhysicalPlantSimulator(tw, seed=7, structural=True)
    cal_tw, info = zt.calibrate_surrogate_blackbox(tw, plant, X[:32], seed=7, n_cal_imgs=24, maxiter=100)
    assert abs(info["gamma_hat"] - 0.90) < 0.06, f"gamma recovery failed: {info['gamma_hat']}"
    assert info["shifts"] == [1, 0, 0, 1], f"shift recovery failed: {info['shifts']}"

    W_t = rng.uniform(1.5, 4.0, (8, 8))
    Xb = X[:4]
    Ep = plant.precompute_cells(Xb)
    Ec = cal_tw.prop1(cal_tw.encode_lcd(Xb).astype(np.complex64))
    F0 = plant.forward_cached(Ep, W_t, noisy=False)
    tgt = rng.normal(0.0, 1.0, F0.shape)
    gc = cal_tw.backward_cached(Ec, W_t, F0 - tgt)
    g_true, g_est = [], []
    eps = 1e-4
    for i in range(0, 8, 2):
        for j in range(0, 8, 2):
            Wp = W_t.copy(); Wp[i, j] += eps
            Wm = W_t.copy(); Wm[i, j] -= eps
            lp = 0.5 * float(np.sum((plant.forward_cached(Ep, Wp, noisy=False) - tgt) ** 2))
            lm = 0.5 * float(np.sum((plant.forward_cached(Ep, Wm, noisy=False) - tgt) ** 2))
            g_true.append((lp - lm) / (2.0 * eps))
            g_est.append(gc[i, j])
    gt, ge = np.array(g_true), np.array(g_est)
    cos = float(np.dot(gt, ge) / (np.linalg.norm(gt) * np.linalg.norm(ge) + 1e-12))
    assert cos > 0.99, f"Calibrated surrogate grad alignment too low: {cos}"
    print(f"  [PASS] Black-box calibration: shift={info['shifts']}, gamma={info['gamma_hat']:.3f}, grad_cos={cos:.4f}")


def test_spatial_batching_crosstalk():
    """2x2 uzamsal paketleme çapraz etkileşim (<1e-5) ve tekil ikiz paritesi testi."""
    rng = np.random.default_rng(11)
    X, _ = zt.make_shapes(2, rng)
    tw = zt.ZerreTwin(n_grid=128, n_ito=32, cam_n=32, drive_mode="active")
    W = rng.uniform(1.3, 4.5, (32, 32))
    eng = zt.SpatialBatchEngine(tw, grid_k=2)
    xt = eng.measure_crosstalk(X[0], W)
    assert xt["crosstalk_ratio"] < 1e-5, f"Crosstalk too high: {xt}"
    F_s = tw.forward_batch(X[:4], W, batch_size=4)
    F_b = eng.forward_frame(X[:4], W)
    rel = float(np.linalg.norm(F_b - F_s) / (np.linalg.norm(F_s) + 1e-12))
    assert rel < 1e-3, f"Spatial batch feature drift too high: {rel}"
    print(f"  [PASS] SpatialBatchEngine 2x2: crosstalk={xt['crosstalk_ratio']:.2e}, rel_diff={rel:.2e}")


def test_multipass_phase_energy_preservation():
    """L=3 saf-faz modülasyonun 3 katlı çapraz polarizör Jones kaybını gidermesi."""
    rng = np.random.default_rng(19)
    X, _ = zt.make_shapes(2, rng)
    Xb = X[:3]
    W_lst = [rng.uniform(1.3, 4.5, (8, 8)) for _ in range(3)]
    mp_j = zt.FoldedMultiPassTwin(n_grid=64, n_ito=8, cam_n=8, n_layers=3, modulation="jones", differential=False)
    mp_p = zt.FoldedMultiPassTwin(n_grid=64, n_ito=8, cam_n=8, n_layers=3, modulation="phase", differential=False)
    Ej = mp_j.forward_batch(Xb, W_lst).mean()
    Ep = mp_p.forward_batch(Xb, W_lst).mean()
    ratio = Ep / (Ej + 1e-12)
    assert ratio > 5.0, f"Pure-phase energy ratio expected >5x, got {ratio:.2f}x"
    print(f"  [PASS] Multi-pass L=3 phase vs Jones mean intensity gain: {ratio:.1f}x")


if __name__ == "__main__":
    print("Running ZERRE Model H physics & sanity tests...")
    test_adjoint_gradients()
    test_alt_pleshko_limit()
    test_single_sd_floor_and_infer()
    test_pool_area_and_zernike_seeds()
    test_shift_crop_edge_loss()
    test_phi_scale_explicit()
    test_zernike_zero_pv_continuity()
    test_server_status_lock()
    test_multipass_differential_adjoint_gradients()
    test_calibrated_surrogate_adjoint_gradients()
    test_blackbox_calibration_recovery()
    test_spatial_batching_crosstalk()
    test_multipass_phase_energy_preservation()
    print("ALL TESTS PASSED.")
