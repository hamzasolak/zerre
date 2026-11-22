# -*- coding: utf-8 -*-
"""
ZERRE (Model H) Academic Manuscript Figure Generator (300 DPI, Bilingual TR & EN)
=================================================================================
Reads 100% of numerical results dynamically from `makale/scripts/paper_results.json`
and executes live forward/adjoint diagnostics from `zerre_twin.py` and `zerre_model.npz`.
Generates Figures 1-5 into `makale/figures/` and synchronizes copies into
`makale/2_latex/figures/`.

Usage:
  python makale/scripts/generate_paper_figures.py --lang both
"""

import argparse
import json
import os
import shutil
import sys
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAKALE_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(MAKALE_DIR)
FIG_DIR = os.path.join(MAKALE_DIR, "figures")
LATEX_FIG_DIR = os.path.join(MAKALE_DIR, "2_latex", "figures")
RESULTS_JSON = os.path.join(SCRIPT_DIR, "paper_results.json")

os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(LATEX_FIG_DIR, exist_ok=True)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import zerre_twin as zt

# Okabe-Ito inspired publication palette
C_BLUE = "#0072B2"
C_VERM = "#D55E00"
C_GREEN = "#009E73"
C_AMBER = "#E69F00"
C_SKY = "#56B4E9"
C_PURP = "#CC79A7"
C_SLATE = "#4A5568"
C_DARK = "#1A202C"


def _setup_rc():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.titlesize": 9.3,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.5,
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.75,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 7.8,
        "ytick.labelsize": 7.8,
        "legend.fontsize": 7.4,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.08,
    })


def _load_results():
    if not os.path.isfile(RESULTS_JSON):
        raise FileNotFoundError(
            f"Missing {RESULTS_JSON}. Run `python zerre_twin.py --paper-benchmark --seeds 7,19,42` first."
        )
    with open(RESULTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_fig(fig, filename):
    p_main = os.path.join(FIG_DIR, filename)
    p_latex = os.path.join(LATEX_FIG_DIR, filename)
    fig.savefig(p_main, dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    shutil.copy2(p_main, p_latex)
    print(f"  [OK] {filename}")


def _find_digit_eight(twin, model_dict):
    mnist_dir = os.path.join(ROOT_DIR, "mnist_cache")
    X, y, n_tr = zt.load_mnist(6000, 1000, np.random.default_rng(7), mnist_dir)
    X_te, y_te = X[n_tr:], y[n_tr:]
    for idx in np.where(y_te == 8)[0]:
        out = zt.infer_array(X_te[idx], twin, model_dict, map_size=int(model_dict["cam_n"]))
        if int(out["prediction"]) == 8 and float(out["confidence"]) >= 0.90:
            return X_te[idx], out
    # Fallback to first 8
    idx0 = int(np.where(y_te == 8)[0][0])
    return X_te[idx0], zt.infer_array(X_te[idx0], twin, model_dict, map_size=int(model_dict["cam_n"]))


def make_fig1(lang, pr):
    _setup_rc()
    model_path = os.path.join(ROOT_DIR, "zerre_model.npz")
    twin, model_dict = zt.load_twin_from_npz(model_path)
    img28, out = _find_digit_eight(twin, model_dict)
    vis = twin.inspect_forward(img28, model_dict["W_volt"])

    lat_med = pr["latency_cpu"]["median_ms"]
    pred = int(out["prediction"])
    conf = float(out["confidence"]) * 100.0
    n_grid = twin.N
    n_ito = twin.n_ito
    cam_n = twin.cam_n

    E_in_amp = np.squeeze(np.abs(twin.encode_lcd(img28[None, ...])))
    E1_amp = np.squeeze(vis["E_cell_amp"])
    phi_map = np.squeeze(vis["ito_phase"])
    I_cam = np.squeeze(vis["I_cam"])
    feat_map = np.squeeze(vis["feat"]).reshape(cam_n, cam_n)

    fig, axes = plt.subplots(1, 5, figsize=(13.6, 2.75))
    if lang == "tr":
        titles = [
            f"(a) Giriş Maskesi\n$A(x,y)$ ({n_grid}×{n_grid})",
            f"(b) Kırınım Genliği\n$|E_1(x,y)|$ ($Z_1=5$ cm)",
            f"(c) PAT Faz Haritası\n$\\Delta\\phi(V_{{ij}})$ ({n_ito}×{n_ito})",
            f"(d) CMOS Yoğunluğu\n$|E_2(x,y)|^2$ ($Z_2=5$ cm)",
            f"(e) {cam_n}×{cam_n} Özellikler\nSınıf {pred} (%{conf:.1f}), CPU {lat_med:.2f} ms",
        ]
        cbar_lbls = ["Genlik", "|E1|", "rad", "|E2|²", "Birim"]
    else:
        titles = [
            f"(a) Input Mask\n$A(x,y)$ ({n_grid}×{n_grid})",
            f"(b) Diffracted Field\n$|E_1(x,y)|$ ($Z_1=5$ cm)",
            f"(c) PAT Phase Map\n$\\Delta\\phi(V_{{ij}})$ ({n_ito}×{n_ito})",
            f"(d) CMOS Intensity\n$|E_2(x,y)|^2$ ($Z_2=5$ cm)",
            f"(e) {cam_n}×{cam_n} Pooled Map\nPred {pred} ({conf:.1f}%), CPU {lat_med:.2f} ms",
        ]
        cbar_lbls = ["Amp.", "|E1|", "rad", "|E2|²", "Norm."]

    imgs = [E_in_amp, E1_amp, phi_map, I_cam, feat_map]
    cmaps = ["gray", "inferno", "viridis", "magma", "cividis"]

    for ax, im_data, cmap, ttl, cbl in zip(axes, imgs, cmaps, titles, cbar_lbls):
        im = ax.imshow(im_data, cmap=cmap, interpolation="nearest")
        ax.set_title(ttl, pad=5, fontsize=8.3)
        ax.set_xticks([])
        ax.set_yticks([])
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.ax.tick_params(labelsize=6.8)
        cb.set_label(cbl, fontsize=7.0)

    fig.tight_layout(w_pad=0.9)
    _save_fig(fig, f"makale_fig1_dalga_{lang}.png")


def make_fig2(lang, pr):
    _setup_rc()
    pc = pr["physics_checks"]
    V = np.linspace(0.0, 5.2, 400)
    phi = zt.lc_phase(V)
    T = np.sin(phi / 2.0) ** 2

    V_off = 1.00
    r_n16 = pc["alt_pleshko_n16_ratio"]
    V_on_n16 = V_off * r_n16

    N_vals = np.arange(2, 33)
    ratios = np.array([zt.passive_selection_ratio(n) for n in N_vals])
    swings = np.array([float(zt.lc_phase(V_off) - zt.lc_phase(V_off * r)) for r in ratios])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.4, 3.9))

    # Panel (a): E7 Phase and Crossed-Polarizer Transmittance
    ax1.axvspan(1.05, 4.95, color=C_GREEN, alpha=0.11, zorder=0)
    ax1.axvspan(V_off, V_on_n16, color=C_VERM, alpha=0.22, zorder=1)
    l1, = ax1.plot(V, phi, color=C_BLUE, lw=2.2,
                   label="Phase retardation Δφ(V)" if lang == "en" else "Faz gecikmesi Δφ(V)")
    ax1.set_ylim(-0.1, 5.45)
    ax1.set_xlim(0.0, 5.2)
    ax1.set_xlabel("RMS Control Voltage $V_{\\mathrm{rms}}$ [V]" if lang == "en" else "Etkin Kontrol Gerilimi $V_{\\mathrm{rms}}$ [V]")
    ax1.set_ylabel("Retardation $\\Delta\\phi$ [rad]" if lang == "en" else "Faz Gecikmesi $\\Delta\\phi$ [rad]", color=C_BLUE)
    ax1.tick_params(axis="y", labelcolor=C_BLUE)
    ax1.grid(True, linestyle="--", alpha=0.28)

    ax1r = ax1.twinx()
    ax1r.spines["top"].set_visible(False)
    l2, = ax1r.plot(V, T, color=C_VERM, lw=1.8, ls="--",
                    label="$|t(V)|^2 = \\sin^2(\\Delta\\phi/2)$")
    ax1r.set_ylim(-0.04, 1.12)
    ax1r.set_ylabel("Crossed-Polarizer Intensity $|t|^2$" if lang == "en" else "Çapraz Polarizör Geçirgenliği $|t|^2$", color=C_VERM)
    ax1r.tick_params(axis="y", labelcolor=C_VERM)

    # Mark Δφ = π turnover peak
    idx_pi = int(np.argmin(np.abs(phi - np.pi)))
    v_pi = float(V[idx_pi])
    ax1r.scatter([v_pi], [1.0], color=C_VERM, s=28, zorder=5)
    ax1r.annotate(
        f"$\\Delta\\phi=\\pi$ peak\n({v_pi:.2f} V)" if lang == "en" else f"$\\Delta\\phi=\\pi$ tepe\n({v_pi:.2f} V)",
        xy=(v_pi, 1.0), xytext=(v_pi + 0.55, 0.90),
        fontsize=7.3, color=C_VERM,
        arrowprops=dict(arrowstyle="->", color=C_VERM, lw=0.8),
    )

    # Annotations for passive vs active windows
    ax1.annotate(
        f"Passive N=16\n[{V_off:.2f}–{V_on_n16:.3f} V]\nΔφ={pc['phase_swing_passive_n16_rad']:.2f} rad"
        if lang == "en" else
        f"Pasif N=16\n[{V_off:.2f}–{V_on_n16:.3f} V]\nΔφ={pc['phase_swing_passive_n16_rad']:.2f} rad",
        xy=(1.15, 4.55), xytext=(0.15, 2.55),
        fontsize=7.3, color="#902000",
        bbox=dict(boxstyle="round,pad=0.25", fc="#FFF5F0", ec=C_VERM, lw=0.7),
        arrowprops=dict(arrowstyle="->", color=C_VERM, lw=0.8),
    )
    phi_pat = float(zt.lc_phase(1.05) - zt.lc_phase(4.95))
    ax1.text(
        3.05, 1.80,
        f"Active TFT / Direct\n[1.05–4.95 V]: {phi_pat:.2f} rad\n([1.00–5.00 V]: {pc['phase_swing_active_rad']:.2f} rad)"
        if lang == "en" else
        f"Aktif TFT / Doğrudan\n[1,05–4,95 V]: {phi_pat:.2f} rad\n([1,00–5,00 V]: {pc['phase_swing_active_rad']:.2f} rad)",
        fontsize=7.2, color="#005A40",
        bbox=dict(boxstyle="round,pad=0.25", fc="#F0FFF8", ec=C_GREEN, lw=0.7),
    )
    ax1.set_title("(a) ECB Retardation & Non-Monotonic Jones Intensity" if lang == "en"
                  else "(a) ECB Faz Gecikmesi ve Jones Geçirgenliği")
    ax1.legend([l1, l2], [l1.get_label(), l2.get_label()], loc="upper right", framealpha=0.92)

    # Panel (b): Alt-Pleshko Decay vs N
    l3, = ax2.plot(N_vals, ratios, color=C_DARK, lw=2.0, marker="o", markersize=2.6,
                   label="Alt–Pleshko $V_{\\mathrm{on}}/V_{\\mathrm{off}}$" if lang == "en" else "Alt–Pleshko $V_{\\mathrm{on}}/V_{\\mathrm{off}}$")
    ax2.set_xlabel("Multiplexed Matrix Rows $N$" if lang == "en" else "Çoğullanan Matris Satır Sayısı $N$")
    ax2.set_ylabel("Max Selection Ratio $V_{\\mathrm{on,rms}}/V_{\\mathrm{off,rms}}$" if lang == "en" else "Azami Seçim Oranı $V_{\\mathrm{on,rms}}/V_{\\mathrm{off,rms}}$", color=C_DARK)
    ax2.grid(True, linestyle="--", alpha=0.28)
    ax2.set_xlim(2, 32)
    ax2.set_ylim(1.05, 2.55)

    ax2r = ax2.twinx()
    ax2r.spines["top"].set_visible(False)
    l4, = ax2r.plot(N_vals, swings, color=C_PURP, lw=2.0, ls="-.", marker="s", markersize=2.4,
                    label="Usable phase swing Δφ [rad]" if lang == "en" else "Kullanılabilir faz aralığı Δφ [rad]")
    ax2r.set_ylabel("Usable Phase Swing [rad]" if lang == "en" else "Kullanılabilir Faz Aralığı [rad]", color="#8B3A62")
    ax2r.tick_params(axis="y", labelcolor="#8B3A62")
    ax2r.set_ylim(0.0, 4.9)

    ax2.axvline(16, color=C_VERM, ls=":", lw=1.1)
    ax2.axvline(32, color=C_AMBER, ls=":", lw=1.1)
    ax2.annotate(
        f"N=16: {pc['alt_pleshko_n16_ratio']:.3f}\n({pc['phase_swing_passive_n16_rad']:.2f} rad)",
        xy=(16, pc["alt_pleshko_n16_ratio"]), xytext=(17.5, 1.72),
        fontsize=7.3, color="#902000",
        arrowprops=dict(arrowstyle="->", color=C_VERM, lw=0.8),
    )
    ax2.annotate(
        f"N=32: {pc['alt_pleshko_n32_ratio']:.3f}\n({pc['phase_swing_passive_n32_rad']:.2f} rad)",
        xy=(32, pc["alt_pleshko_n32_ratio"]), xytext=(22.0, 1.38),
        fontsize=7.3, color="#9A6000",
        arrowprops=dict(arrowstyle="->", color=C_AMBER, lw=0.8),
    )
    ax2.set_title("(b) Passive-Matrix Selection Ratio Collapse" if lang == "en"
                  else "(b) Pasif Matriste Alt–Pleshko Seçim Daralması")
    ax2.legend([l3, l4], [l3.get_label(), l4.get_label()], loc="upper right", framealpha=0.92)

    fig.tight_layout(w_pad=1.6)
    _save_fig(fig, f"makale_fig2_alt_pleshko_{lang}.png")


def make_fig3(lang, pr):
    _setup_rc()
    rows = pr["table1_ablation"]["rows"]
    pc = pr["physics_checks"]

    name_map_en = {
        "digital_area_linear": "Digital Area Pool (No Opt.) + Lin.",
        "digital_pca_linear": "Digital PCA (64-dim) + Lin.",
        "free_space_linear": "Free-Space Diffr. (No LC) + Lin.",
        "passive_16_random_linear": "Passive 16×16 Random + Lin.",
        "active_16_random_linear": "Active 16×16 Random + Lin.",
        "active_32_random_linear": "Active 32×32 Random + Lin.",
        "passive_16_pat_linear": "Passive 16×16 PAT + Lin.",
        "active_16_pat_linear": "Active 16×16 PAT + Lin.",
        "active_32_pat_linear": "Active 32×32 PAT + Lin.",
        "digital_area_mlp": "Digital Area Pool + 19K MLP",
        "active_32_pat_mlp": "Active 32×32 PAT + 19K MLP",
    }
    name_map_tr = {
        "digital_area_linear": "Dijital Alan Havuzlama + Lineer",
        "digital_pca_linear": "Dijital PCA (64) + Lineer",
        "free_space_linear": "Serbest Uzay (LC Yok) + Lineer",
        "passive_16_random_linear": "Pasif 16×16 Rastgele + Lineer",
        "active_16_random_linear": "Aktif 16×16 Rastgele + Lineer",
        "active_32_random_linear": "Aktif 32×32 Rastgele + Lineer",
        "passive_16_pat_linear": "Pasif 16×16 PAT + Lineer",
        "active_16_pat_linear": "Aktif 16×16 PAT + Lineer",
        "active_32_pat_linear": "Aktif 32×32 PAT + Lineer",
        "digital_area_mlp": "Dijital Alan + 19K MLP",
        "active_32_pat_mlp": "Aktif 32×32 PAT + 19K MLP",
    }
    nmap = name_map_en if lang == "en" else name_map_tr

    labels = [nmap.get(r["key"], r["label"]) for r in rows]
    means = [r["mean"] for r in rows]
    stds = [r["std"] for r in rows]

    colors_bar = []
    for r in rows:
        k = r["key"]
        if k.startswith("digital_"):
            colors_bar.append(C_BLUE)
        elif "random" in k or "free_space" in k:
            colors_bar.append(C_VERM)
        elif "mlp" in k:
            colors_bar.append("#006D4E")
        else:
            colors_bar.append(C_GREEN)

    # Live finite-difference gradient check scatter (same seed/setup as zt.grad_check)
    rng = np.random.default_rng(123)
    X_s, _ = zt.make_shapes(4, rng)
    Xb = X_s[:6]
    twin_g = zt.ZerreTwin(n_grid=64, n_ito=8, cam_n=8, drive_mode="active")
    E_cells = twin_g.field_at_cell(Xb)
    W_g = rng.uniform(1.3, 4.5, (8, 8))
    target = rng.normal(0.0, 1.0, (len(Xb), 64))
    F0 = twin_g.forward_cached(E_cells, W_g)
    g_analytic = twin_g.backward_cached(E_cells, W_g, F0 - target).ravel()
    eps = 1e-6
    g_num = np.zeros_like(g_analytic)
    W_flat = W_g.ravel().copy()
    for p_idx in range(len(W_flat)):
        Wp = W_flat.copy(); Wp[p_idx] += eps
        Wm = W_flat.copy(); Wm[p_idx] -= eps
        lp = 0.5 * float(np.sum((twin_g.forward_cached(E_cells, Wp.reshape(8, 8)) - target) ** 2))
        lm = 0.5 * float(np.sum((twin_g.forward_cached(E_cells, Wm.reshape(8, 8)) - target) ** 2))
        g_num[p_idx] = (lp - lm) / (2.0 * eps)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.4), gridspec_kw={"width_ratios": [1.45, 1.0]})

    y_pos = np.arange(len(rows))[::-1]
    ax1.barh(y_pos, means, xerr=stds, color=colors_bar, alpha=0.88,
             error_kw=dict(ecolor=C_DARK, lw=1.0, capsize=2.8), height=0.68)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(labels, fontsize=7.6)
    ax1.set_xlim(55.0, 99.5)
    ax1.set_xlabel("3-Seed Test Accuracy Mean ± SD [%] (8×8 Detector, N_test=1000)" if lang == "en"
                   else "3-Tohum Test Doğruluğu Ort. ± SS [%] (8×8 Dedektör, N_test=1000)")
    ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

    for yp, m, s in zip(y_pos, means, stds):
        ax1.text(m + s + 0.55, yp, f"{m:.2f} ± {s:.2f}%", va="center", fontsize=7.2, color=C_DARK)

    legend_handles = [
        Patch(facecolor=C_BLUE, alpha=0.88, label="Digital Baseline" if lang == "en" else "Dijital Baz"),
        Patch(facecolor=C_VERM, alpha=0.88, label="Untrained / Free-Space Optics" if lang == "en" else "Eğitimsiz / Serbest Uzay"),
        Patch(facecolor=C_GREEN, alpha=0.88, label="PAT Optical + Linear" if lang == "en" else "PAT Optik + Lineer"),
        Patch(facecolor="#006D4E", alpha=0.88, label="PAT Optical + 19K MLP" if lang == "en" else "PAT Optik + 19K MLP"),
    ]
    ax1.legend(handles=legend_handles, loc="center right", bbox_to_anchor=(0.99, 0.56),
               framealpha=0.95, fontsize=7.0)
    ax1.set_title("(a) Controlled 8×8 Detector Ablation (Seeds 7, 19, 42)" if lang == "en"
                  else "(a) Kontrollü 8×8 Dedektör Ablasyonu (Tohum 7, 19, 42)")

    # Panel (b): Gradient scatter
    lim_lo = float(min(g_analytic.min(), g_num.min())) * 1.12
    lim_hi = float(max(g_analytic.max(), g_num.max())) * 1.12
    ax2.plot([lim_lo, lim_hi], [lim_lo, lim_hi], color=C_DARK, lw=1.2, ls="--",
             label="$y = x$ identity" if lang == "en" else "$y = x$ özdeşlik")
    ax2.scatter(g_num, g_analytic, color=C_BLUE, s=22, alpha=0.85, edgecolors="white", linewidths=0.4,
                label="64 electrode gradients" if lang == "en" else "64 elektrot gradyanı")
    ax2.set_xlim(lim_lo, lim_hi)
    ax2.set_ylim(lim_lo, lim_hi)
    ax2.set_xlabel("Central Finite Difference ($\\varepsilon = 10^{-6}$)" if lang == "en"
                   else "Merkezi Sonlu Fark ($\\varepsilon = 10^{-6}$)")
    ax2.set_ylabel("Analytical Wirtinger Adjoint $\\partial\\mathcal{L}/\\partial V$" if lang == "en"
                   else "Analitik Wirtinger Eşlenik $\\partial\\mathcal{L}/\\partial V$")
    ax2.grid(True, linestyle="--", alpha=0.28)
    ax2.text(
        0.05, 0.80,
        f"Active rel. $L_2$: {pc['grad_err_active']:.2e}\nPassive rel. $L_2$: {pc['grad_err_passive']:.2e}",
        transform=ax2.transAxes, fontsize=7.6,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F7FAFC", ec=C_BLUE, lw=0.8),
    )
    ax2.legend(loc="lower right", framealpha=0.92)
    ax2.set_title("(b) Analytical Wirtinger Adjoint Verification" if lang == "en"
                  else "(b) Analitik Wirtinger Adjoint Doğrulaması")

    fig.tight_layout(w_pad=1.5)
    _save_fig(fig, f"makale_fig3_ablasyon_pat_{lang}.png")


def make_fig4(lang, pr):
    _setup_rc()
    rob = pr["robustness"]
    rob_pert = pr["robustness_perturbed_head"]
    env = pr["environment_tests"]

    shifts = sorted([int(k) for k in rob["lcd_shifts_um"].keys()])
    acc_lcd = [rob["lcd_shifts_um"][str(k)] for k in shifts]
    acc_ito = [rob["ito_shifts_um"][str(k)] for k in shifts]
    acc_cam = [rob["cam_shifts_um"][str(k)] for k in shifts]
    comb_nom = rob["combined_47um_1mm"]
    comb_pert = rob_pert["combined_47um_1mm"]

    sl = env["stray_light"]
    leaks = [d["leak_pct"] for d in sl]
    raw_sl = [d["raw_acc"] for d in sl]
    dark_sl = [d["dark_sub_acc"] for d in sl]

    temps = env["temps"]
    temp_c = [d["temp_c"] for d in temps]
    temp_acc = [d["acc"] for d in temps]
    comb_env = env["combined_30C_1pct_2pct"]

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.0, 4.1), gridspec_kw={"width_ratios": [1.12, 1.15, 0.92]})

    # Panel (a): Lateral misalignment + combined callout
    ax1.plot(shifts, acc_ito, marker="s", lw=2.1, color=C_GREEN,
             label="LC Weight Cell shift" if lang == "en" else "LC Ağırlık Hücresi kayması")
    ax1.plot(shifts, acc_lcd, marker="o", lw=2.0, color=C_VERM,
             label="Input LCD shift" if lang == "en" else "Giriş LCD kayması")
    ax1.plot(shifts, acc_cam, marker="^", lw=1.9, ls="--", color=C_BLUE,
             label="CMOS Sensor shift" if lang == "en" else "CMOS Sensör kayması")
    ax1.axhline(comb_nom, color=C_PURP, ls=":", lw=1.3,
                label=f"Comb. 47µm+1mm (nom. head): {comb_nom:.1f}%" if lang == "en"
                else f"Komb. 47µm+1mm (nom. kafa): %{comb_nom:.1f}")
    ax1.axhline(comb_pert, color=C_AMBER, ls="-.", lw=1.2,
                label=f"Comb. 47µm+1mm (pert. head): {comb_pert:.1f}%" if lang == "en"
                else f"Komb. 47µm+1mm (kusurlu kafa): %{comb_pert:.1f}")
    ax1.set_xticks(shifts)
    ax1.set_xlabel("Single-Axis Lateral Shift [µm] ($N_{\\mathrm{test}}=1000$)" if lang == "en"
                   else "Tek Eksenli Yanal Kayma [µm] ($N_{\\mathrm{test}}=1000$)")
    ax1.set_ylabel("MNIST Test Accuracy [%]" if lang == "en" else "MNIST Test Doğruluğu [%]")
    ax1.set_ylim(63.0, 98.5)
    ax1.grid(True, linestyle="--", alpha=0.28)
    ax1.legend(loc="lower left", framealpha=0.93, fontsize=6.9)
    ax1.set_title("(a) Lateral & Combined Misalignment" if lang == "en"
                  else "(a) Yanal ve Kombine Hizasızlık")

    # Panel (b): Stray light raw vs 16-frame dark subtraction (no sd_floor legend clutter)
    x_sl = np.arange(len(leaks))
    w = 0.35
    b1 = ax2.bar(x_sl - w / 2, raw_sl, width=w, color=C_VERM, alpha=0.86,
                 label="Raw uncalibrated" if lang == "en" else "Ham kalibrasyonsuz")
    b2 = ax2.bar(x_sl + w / 2, dark_sl, width=w, color=C_GREEN, alpha=0.88,
                 label="16-frame dark sub." if lang == "en" else "16-kare karanlık çıkarma")
    ax2.set_xticks(x_sl)
    ax2.set_xticklabels([f"{p}%" for p in leaks])
    ax2.set_xlabel("Stray Ambient Light [% of mean signal]" if lang == "en"
                   else "Ortam Işığı Sızıntısı [ort. sinyalin %'si]")
    ax2.set_ylabel("MNIST Test Accuracy [%]" if lang == "en" else "MNIST Test Doğruluğu [%]")
    ax2.set_ylim(0.0, 114.0)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.28)

    for bar in b2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.4, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=6.8, color="#005A40", fontweight="bold")
    for bar in b1:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.4, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=6.7, color="#8A2000")

    ax2.text(
        0.96, 0.36,
        f"30°C + 1% + 2%:\nRaw {comb_env['raw_acc']:.1f}% → {comb_env['dark_sub_acc']:.1f}%"
        if lang == "en" else
        f"30°C + %1 + %2:\nHam %{comb_env['raw_acc']:.1f} → %{comb_env['dark_sub_acc']:.1f}",
        transform=ax2.transAxes, ha="right", fontsize=7.0,
        bbox=dict(boxstyle="round,pad=0.25", fc="#F0FFF8", ec=C_GREEN, lw=0.7),
    )
    ax2.legend(loc="upper center", ncol=2, framealpha=0.95, fontsize=6.9)
    ax2.set_title("(b) Stray Ambient Light Recovery" if lang == "en"
                  else "(b) Ortam Işığı Sızıntısı Kurtarma")

    # Panel (c): Dedicated Haller Thermal Sweep (20-55 C)
    ax3.plot(temp_c, temp_acc, marker="o", ms=4.8, lw=2.1, color=C_BLUE,
             label="Uncalibrated E7" if lang == "en" else "Kalibrasyonsuz E7")
    ax3.axvspan(20, 35, color=C_GREEN, alpha=0.10,
                label="Room band (20–35°C)" if lang == "en" else "Oda bandı (20–35°C)")
    for tc, ta in zip(temp_c, temp_acc):
        if tc in (20, 35, 45, 55):
            ax3.text(tc, ta + 0.18, f"{ta:.1f}%", ha="center", fontsize=6.8, color=C_DARK)
    ax3.set_xticks(temp_c)
    ax3.set_xlabel("Temperature $T$ [°C] ($T_c=59$°C)" if lang == "en"
                   else "Sıcaklık $T$ [°C] ($T_c=59$°C)")
    ax3.set_ylabel("MNIST Test Accuracy [%]" if lang == "en" else "MNIST Test Doğruluğu [%]")
    ax3.set_ylim(90.5, 96.4)
    ax3.grid(True, linestyle="--", alpha=0.28)
    ax3.legend(loc="lower left", framealpha=0.93, fontsize=6.9)
    ax3.set_title("(c) Uncalibrated Haller Thermal Sweep" if lang == "en"
                  else "(c) Kalibrasyonsuz Haller Sıcaklık Testi")

    fig.tight_layout(w_pad=1.4)
    _save_fig(fig, f"makale_fig4_dayanim_{lang}.png")


def make_fig5(lang, pr):
    _setup_rc()
    quant = pr["quantization"]
    bm = pr["black_matrix"]
    zern = pr["zernike_multiseed"]
    fm = pr["fashion_mnist_multiseed"]

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.4, 4.6))

    # Panel (a): Bit quantization + sub-aperture fill-factor inset
    q_labels = ["FP64" if d["bits"] == 64 else f"{d['bits']}b" for d in quant]
    q_accs = [d["ptq_acc"] for d in quant]
    xq = np.arange(len(q_labels))
    ax1.plot(xq, q_accs, marker="o", lw=2.2, color=C_BLUE,
             label="8-bit HDMI + b-bit Weight" if lang == "en" else "8-bit HDMI + b-bit Ağırlık")
    ax1.fill_between(xq, 91.5, q_accs, color=C_BLUE, alpha=0.09)
    ax1.set_xticks(xq)
    ax1.set_xticklabels(q_labels, fontsize=7.4)
    ax1.set_xlabel("Weight DAC/PWM Precision" if lang == "en" else "Ağırlık DAC/PWM Bit Derinliği")
    ax1.set_ylabel("MNIST Test Accuracy [%] (seed=7)" if lang == "en" else "MNIST Test Doğruluğu [%] (tohum=7)")
    ax1.set_ylim(91.5, 96.4)
    ax1.grid(True, linestyle="--", alpha=0.28)
    for xi, acc in zip(xq, q_accs):
        if q_labels[xi] in ("FP64", "4b", "3b"):
            ax1.text(xi, acc + 0.16, f"{acc:.1f}%", ha="center", fontsize=6.9, color=C_DARK)
        elif q_labels[xi] == "2b":
            ax1.text(xi - 0.12, acc - 0.32, f"{acc:.1f}%", ha="center", fontsize=6.9, color=C_DARK)

    # Inset: Macro-pixel Sub-Aperture Fill-Factor
    ax_in = ax1.inset_axes([0.10, 0.13, 0.56, 0.42])
    ff = [d["fill_factor_pct"] for d in bm]
    u_ff = [d["uncal_acc"] for d in bm]
    r_ff = [d["head_recalibrated_acc"] for d in bm]
    ax_in.plot(ff, u_ff, marker="o", ms=3.0, lw=1.4, color=C_VERM,
               label="Uncalibrated" if lang == "en" else "Kalibrasyonsuz")
    ax_in.plot(ff, r_ff, marker="s", ms=3.0, lw=1.5, color=C_GREEN,
               label="Head Recalibrated" if lang == "en" else "Kafa Kalibre")
    ax_in.invert_xaxis()
    ax_in.set_title("Sub-Aperture Fill-Factor (N=256)" if lang == "en" else "Alt-Açıklık Doluluk (N=256)", fontsize=6.7, pad=2)
    ax_in.set_xlabel("Fill Factor [%]" if lang == "en" else "Doluluk [%]", fontsize=6.3, labelpad=1)
    ax_in.set_ylim(89.2, 94.0)
    ax_in.tick_params(labelsize=6.1)
    ax_in.grid(True, linestyle=":", alpha=0.35)
    ax_in.legend(loc="lower left", fontsize=5.8, framealpha=0.9)
    ax1.set_title("(a) Weight Quantization & Aperture Proxy" if lang == "en"
                  else "(a) Kuantizasyon ve Alt-Açıklık Proxy")

    # Panel (b): Zernike wavefront distortion (3 matched curves + +-1 SD bands)
    pvs = np.array([d["pv_waves"] for d in zern])
    u_m = np.array([d["uncompensated"]["mean"] for d in zern])
    u_s = np.array([d["uncompensated"]["std"] for d in zern])
    h_m = np.array([d["head_only"]["mean"] for d in zern])
    h_s = np.array([d["head_only"]["std"] for d in zern])
    p_m = np.array([d["pat_compensated"]["mean"] for d in zern])
    p_s = np.array([d["pat_compensated"]["std"] for d in zern])

    ax2.plot(pvs, p_m, marker="D", ms=4.5, lw=2.2, color=C_GREEN,
             label="Blind-Surrogate PAT" if lang == "en" else "Habersiz Vekil PAT")
    ax2.fill_between(pvs, p_m - p_s, p_m + p_s, color=C_GREEN, alpha=0.14)

    ax2.plot(pvs, h_m, marker="s", ms=4.2, lw=1.9, ls="--", color=C_BLUE,
             label="Head-Only Control (CE)" if lang == "en" else "Yalnız Kafa Kontrol (CE)")
    ax2.fill_between(pvs, h_m - h_s, h_m + h_s, color=C_BLUE, alpha=0.12)

    ax2.plot(pvs, u_m, marker="o", ms=4.2, lw=2.0, color=C_VERM,
             label="Uncompensated" if lang == "en" else "Kalibrasyonsuz")
    ax2.fill_between(pvs, u_m - u_s, u_m + u_s, color=C_VERM, alpha=0.12)

    ax2.set_xlabel("Zernike Aberration $\\alpha_{\\mathrm{PV}}$ [$\\lambda$] + $3Z_1$ Ghost" if lang == "en"
                   else "Zernike Sapması $\\alpha_{\\mathrm{PV}}$ [$\\lambda$] + $3Z_1$ Hayalet")
    ax2.set_ylabel("3-Seed Test Accuracy Mean ± SD [%]" if lang == "en"
                   else "3-Tohum Test Doğruluğu Ort. ± SS [%]")
    ax2.set_xticks(pvs)
    ax2.set_ylim(55.0, 84.5)
    ax2.grid(True, linestyle="--", alpha=0.28)
    gain_vs_uncomp = p_m[-1] - u_m[-1]
    gain_vs_head = p_m[-1] - h_m[-1]
    ax2.annotate(
        f"15λ PAT: {p_m[-1]:.2f}%\n(+{gain_vs_uncomp:.2f} vs uncomp,\n +{gain_vs_head:.2f} vs head)"
        if lang == "en" else
        f"15λ PAT: %{p_m[-1]:.2f}\n(+{gain_vs_uncomp:.2f} kalibr.,\n +{gain_vs_head:.2f} kafa)",
        xy=(15.0, p_m[-1]), xytext=(6.2, 60.5),
        fontsize=7.0, color="#005A40",
        bbox=dict(boxstyle="round,pad=0.25", fc="#F0FFF8", ec=C_GREEN, lw=0.7),
        arrowprops=dict(arrowstyle="->", color=C_GREEN, lw=0.9),
    )
    ax2.legend(loc="lower left", framealpha=0.92, fontsize=7.0)
    ax2.set_title("(b) Wavefront Aberration Compensation (3 Seeds)" if lang == "en"
                  else "(b) Dalga Cephesi Sapması Telafisi (3 Tohum)")

    # Panel (c): Fashion-MNIST 10-class generalization (3 seeds, NO privacy box)
    fm_items = [
        ("8×8 No-Opt Lin.", "no_optics_8x8_linear", C_BLUE),
        ("8×8 Rand. Lin.", "random_32x32_8x8_linear", C_VERM),
        ("8×8 PAT Lin.", "pat_32x32_8x8_linear", C_GREEN),
        ("8×8 PAT MLP", "pat_32x32_8x8_mlp", "#006D4E"),
        ("8×8 No-Opt MLP", "no_optics_8x8_mlp", C_SKY),
        ("32×32 Raw Ridge", "no_optics_raw_ridge", C_SLATE),
        ("32×32 PAT Ridge", "pat_32x32_ridge", C_GREEN),
        ("32×32 Pert. MLP", "pat_32x32_perturbed_mlp", C_AMBER),
        ("32×32 Rand. MLP", "random_32x32_mlp", C_VERM),
        ("32×32 PAT Nom.", "pat_32x32_nominal_mlp", "#006D4E"),
        ("32×32 Raw MLP", "no_optics_raw_mlp", C_BLUE),
    ]
    if lang == "tr":
        fm_items = [
            ("8×8 Optiksiz Lin.", "no_optics_8x8_linear", C_BLUE),
            ("8×8 Rast. Lin.", "random_32x32_8x8_linear", C_VERM),
            ("8×8 PAT Lin.", "pat_32x32_8x8_linear", C_GREEN),
            ("8×8 PAT MLP", "pat_32x32_8x8_mlp", "#006D4E"),
            ("8×8 Optiksiz MLP", "no_optics_8x8_mlp", C_SKY),
            ("32×32 Ham Ridge", "no_optics_raw_ridge", C_SLATE),
            ("32×32 PAT Ridge", "pat_32x32_ridge", C_GREEN),
            ("32×32 Kusur MLP", "pat_32x32_perturbed_mlp", C_AMBER),
            ("32×32 Rast. MLP", "random_32x32_mlp", C_VERM),
            ("32×32 PAT Nom.", "pat_32x32_nominal_mlp", "#006D4E"),
            ("32×32 Ham MLP", "no_optics_raw_mlp", C_BLUE),
        ]

    f_lbls = [it[0] for it in fm_items]
    f_means = [fm[it[1]]["mean"] for it in fm_items]
    f_stds = [fm[it[1]]["std"] for it in fm_items]
    f_cols = [it[2] for it in fm_items]

    yf = np.arange(len(fm_items))[::-1]
    ax3.barh(yf, f_means, xerr=f_stds, color=f_cols, alpha=0.88,
             error_kw=dict(ecolor=C_DARK, lw=0.9, capsize=2.3), height=0.68)
    ax3.axhline(5.5, color="#888888", ls="--", lw=0.9)
    ax3.set_yticks(yf)
    ax3.set_yticklabels(f_lbls, fontsize=7.1)
    ax3.set_xlim(55.0, 93.5)
    ax3.set_xlabel("3-Seed Test Accuracy Mean ± SD [%]" if lang == "en"
                   else "3-Tohum Test Doğruluğu Ort. ± SS [%]")
    ax3.grid(True, axis="x", linestyle="--", alpha=0.28)
    for yp, m, s in zip(yf, f_means, f_stds):
        ax3.text(m + s + 0.45, yp, f"{m:.1f}±{s:.1f}%", va="center", fontsize=6.7, color=C_DARK)
    ax3.set_title("(c) Fashion-MNIST 10-Class Generalization" if lang == "en"
                  else "(c) Fashion-MNIST 10-Sınıf Genellemesi")

    fig.tight_layout(w_pad=1.5)
    _save_fig(fig, f"makale_fig5_gercekcilik_{lang}.png")


def main():
    parser = argparse.ArgumentParser(description="Generate ZERRE publication figures from paper_results.json.")
    parser.add_argument("--lang", choices=["tr", "en", "both"], default="both")
    args = parser.parse_args()

    pr = _load_results()
    langs = ["tr", "en"] if args.lang == "both" else [args.lang]
    for lang in langs:
        print(f"=== Generating figures ({lang.upper()}) ===")
        make_fig1(lang, pr)
        make_fig2(lang, pr)
        make_fig3(lang, pr)
        make_fig4(lang, pr)
        make_fig5(lang, pr)


if __name__ == "__main__":
    main()
