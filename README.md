# ZERRE (Model H) — Scalar-Wave Digital Twin & Physics-Aware Training

[![Optica Open Preprint](https://img.shields.io/badge/Optica%20Open-10.1364%2Fopticaopen.35085502-6A1B9A)](https://doi.org/10.1364/opticaopen.35085502)
[![Release](https://img.shields.io/badge/Release-v0.5.0-blue)](https://github.com/hamzasolak/zerre/releases/tag/v0.5.0)
[![License: MIT](https://img.shields.io/badge/Code%20License-MIT-green.svg)](LICENSE)
[![Paper: CC BY 4.0](https://img.shields.io/badge/Paper%20License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

**ZERRE (Model H)** is an open-source simulation framework and interactive 3D WebGL visualizer for studying an in-line (reference-free) diffractive optoelectronic encoder built around low-cost monochrome mSLA LCD panels, planar nematic liquid-crystal (LC) modulation, and analytical Wirtinger-adjoint Physics-Aware Training (PAT).

> **Scope Note:** All classification, ablation, tolerance, and hardware-realism results in this repository are obtained strictly from scalar-wave numerical simulations (Angular Spectrum Method) and synthetic perturbed-plant models; no physical optical bench prototype has been built or experimentally measured yet.

**Author:** Hamza Solak · Independent Researcher, Türkiye  
**ORCID:** [0009-0004-7541-9620](https://orcid.org/0009-0004-7541-9620) · **Contact:** `eng.hamzasolak@gmail.com`  
**Preprint (Optica Open, V1 — 24 Nov 2026):** [doi:10.1364/opticaopen.35085502](https://doi.org/10.1364/opticaopen.35085502) · Preprint ID: `137810` · CC BY 4.0

---

## Repository Contents

| Path | Purpose |
| :--- | :--- |
| `zerre_twin.py` | Full scalar-wave ASM propagation, Alt–Pleshko passive-matrix model, exact Wirtinger complex-adjoint PAT trainer, leakage-free matched CE-Adam ablation, structural model-mismatch test, folded multi-pass + differential readout, black-box surrogate calibration, spatial batching, robustness/environment sweeps, and multi-seed `--paper-benchmark` / `--remedies-benchmark` suites (`v0.5` + `v0.6`). |
| `zerre_pat_torch.py` | Optional PyTorch `nn.Module` (`ZerrePATLayer`, `FoldedMultiPassSurrogateTorch`) custom autograd bridge for forward/adjoint PAT workflows. |
| `start_server.py`, `index.html`, `js/`, `css/` | Local HTTP server + interactive Three.js 3D optical bench & live digital-twin inference UI (`http://localhost:5501`). |
| `tests/test_zerre_physics.py` | Standalone 13-test physics & sanity suite verifying adjoint gradients (single-pass, multi-pass, calibrated surrogate), Alt–Pleshko math, `sd_floor` invariance, `pool_area`, Zernike seed independence, `shift_crop` boundary loss, explicit `phi_scale`, Zernike `pv=0` continuity, black-box calibration recovery, spatial-batch crosstalk, and pure-phase energy preservation. |
| `HYBRID_ROADMAP.md` | Future GPU + ZERRE hybrid architecture research notes (label-free phase front-end, `4f` FNO accelerator, calibrated benchtop twin, optical reservoir). |
| `makale/` | Manuscript sources (LaTeX/BibTeX, HTML, PDF build scripts, Markdown, 300 DPI figures, and JSON benchmark artifacts). |

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Physics & Code Verification Tests
```bash
python tests/test_zerre_physics.py
python zerre_twin.py --grad-check
```

### 3. Reproduce Multi-Seed Benchmarks
Generates `makale/scripts/paper_results.json` (`v0.5.0` paper suite) or `makale/scripts/remedies_v06_results.json` (`v0.6` technical remedies suite):
```bash
python zerre_twin.py --paper-benchmark --seeds 7,19,42
python zerre_twin.py --remedies-benchmark --seeds 7,19,42
```

### 4. Launch the Interactive 3D Web Visualizer
```bash
python start_server.py
```
On Windows, you can also run `ZERRE_Baslat.bat`.

---

## Citation

The published Optica Open `V1` preprint corresponds to the immutable release tag [`v0.5.0`](https://github.com/hamzasolak/zerre/releases/tag/v0.5.0). The `main` branch additionally includes verified post-`v0.5.0` (`v0.6`) technical remedies recorded in `makale/scripts/remedies_v06_results.json` (folded 3-pass pure-phase differential readout `83.20 ± 0.90%`, 85-query black-box surrogate calibration `81.57 ± 0.90%`, and `-64.5 dB` crosstalk spatial batching).

```bibtex
@article{solak2026zerre,
  author  = {Solak, Hamza},
  title   = {{ZERRE (Model H)}: Wave-Optics Design, Physical Synthesis, and Physics-Aware Training of a Common-Path Optoelectronic Processor},
  journal = {Optica Open},
  year    = {2026},
  month   = nov,
  doi     = {10.1364/opticaopen.35085502},
  url     = {https://doi.org/10.1364/opticaopen.35085502},
  note    = {Preprint ID: 137810, Version 1}
}
```

---

## Türkçe Kısa Özet

**ZERRE (Model H)**, yüksek maliyetli laboratuvar LCOS uzamsal ışık modülatörleri yerine düşük maliyetli monokrom mSLA LCD panelleri kullanan, tek-yollu (referanssız) kırınımlı bir optoelektronik kodlayıcı mimarisinin **skaler dalga-optiği dijital ikizi** ve **Fizik-Farkındalıklı Eğitim (PAT)** simülasyon paketidir. Tüm sonuçlar sayısal dalga simülasyonu üzerinden elde edilmiştir; donanım prototipi kurulumu gelecek çalışma kapsamındadır.

Yayınlanan İngilizce ön baskıya Optica Open üzerinden kalıcı DOI bağlantısı ile erişilebilir: [doi:10.1364/opticaopen.35085502](https://doi.org/10.1364/opticaopen.35085502).

Temel doğrulama ve yeniden üretim komutları yukarıdaki İngilizce bölümdekiyle aynıdır (`python tests/test_zerre_physics.py` ve `python zerre_twin.py --paper-benchmark`).

---

## Licensing & Third-Party Notices

* **Source Code:** Licensed under the [MIT License](LICENSE) (© 2026 Hamza Solak).
* **Manuscripts & Figures (`makale/`):** Licensed under **CC BY 4.0**.
* **Bundled Libraries:** `js/three.min.js` (Three.js r128, MIT) and `js/anime.min.js` (Anime.js, MIT).
* **External Datasets:** Benchmarks download/use standard MNIST (LeCun et al., 1998) and Fashion-MNIST (Xiao et al., 2017; MIT License) into local ignored caches (`mnist_cache/`, `fashion_mnist_cache/`).
