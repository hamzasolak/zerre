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
    print("ALL TESTS PASSED.")
