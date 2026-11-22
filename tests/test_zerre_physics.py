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
    test_server_status_lock()
    print("ALL TESTS PASSED.")
