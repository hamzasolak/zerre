# ZERRE (Model H) — Scalar-Wave Digital Twin & Physics-Aware Training

**ZERRE (Model H)** is an open-source simulation framework and interactive 3D WebGL visualizer for studying an in-line (reference-free) diffractive optoelectronic encoder built around low-cost monochrome mSLA LCD panels, planar nematic liquid-crystal (LC) modulation, and analytical Wirtinger-adjoint Physics-Aware Training (PAT).

> **Scope Note:** All classification, ablation, tolerance, and hardware-realism results in this repository are obtained strictly from scalar-wave numerical simulations (Angular Spectrum Method) and synthetic perturbed-plant models; no physical optical bench prototype has been built or experimentally measured yet.

**Author:** Hamza Solak · Independent Researcher, Türkiye  
**ORCID:** [0009-0004-7541-9620](https://orcid.org/0009-0004-7541-9620) · **Contact:** `eng.hamzasolak@gmail.com`

---

## Repository Contents

| Path | Purpose |
| :--- | :--- |
| `zerre_twin.py` | Full scalar-wave ASM propagation, Alt–Pleshko passive-matrix model, exact Wirtinger complex-adjoint PAT trainer, leakage-free matched CE-Adam ablation, structural model-mismatch test, robustness/environment sweeps, and multi-seed `--paper-benchmark` suite (`v0.5`). |
| `zerre_pat_torch.py` | Optional PyTorch `nn.Module` (`ZerrePATLayer`) custom autograd bridge for forward/adjoint PAT workflows. |
| `start_server.py`, `index.html`, `js/`, `css/` | Local HTTP server + interactive Three.js 3D optical bench & live digital-twin inference UI (`http://localhost:5501`). |
| `tests/test_zerre_physics.py` | Standalone 8-test physics & sanity suite verifying adjoint gradients, Alt–Pleshko math, `sd_floor` invariance, `pool_area`, Zernike seed independence, `shift_crop` boundary loss, explicit `phi_scale`, and Zernike `pv=0` continuity. |
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

### 3. Reproduce All Multi-Seed Paper Benchmarks
Generates `makale/scripts/paper_results.json` and `makale/scripts/realism_results.json` (uses local cached MNIST & Fashion-MNIST datasets or downloads them on first run if absent):
```bash
python zerre_twin.py --paper-benchmark --seeds 7,19,42
```

### 4. Launch the Interactive 3D Web Visualizer
```bash
python start_server.py
```
On Windows, you can also run `ZERRE_Baslat.bat`.

---

## Türkçe Kısa Özet

**ZERRE (Model H)**, yüksek maliyetli laboratuvar LCOS uzamsal ışık modülatörleri yerine düşük maliyetli monokrom mSLA LCD panelleri kullanan, tek-yollu (referanssız) kırınımlı bir optoelektronik kodlayıcı mimarisinin **skaler dalga-optiği dijital ikizi** ve **Fizik-Farkındalıklı Eğitim (PAT)** simülasyon paketidir. Tüm sonuçlar sayısal dalga simülasyonu üzerinden elde edilmiştir; donanım prototipi kurulumu gelecek çalışma kapsamındadır.

Temel doğrulama ve yeniden üretim komutları yukarıdaki İngilizce bölümdekiyle aynıdır (`python tests/test_zerre_physics.py` ve `python zerre_twin.py --paper-benchmark`).

---

## Licensing & Third-Party Notices

* **Source Code:** Licensed under the [MIT License](LICENSE) (© 2026 Hamza Solak).
* **Manuscripts & Figures (`makale/`):** Licensed under **CC BY 4.0**.
* **Bundled Libraries:** `js/three.min.js` (Three.js r128, MIT) and `js/anime.min.js` (Anime.js, MIT).
* **External Datasets:** Benchmarks download/use standard MNIST (LeCun et al., 1998) and Fashion-MNIST (Xiao et al., 2017; MIT License) into local ignored caches (`mnist_cache/`, `fashion_mnist_cache/`).
