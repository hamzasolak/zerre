# ZERRE (Model H) — Akademik Makale Paketi / Academic Manuscript Archive

Bu klasör, **ZERRE (Model H) Ortak-Yol Kırınımlı Optoelektronik Hibrit Sinir Ağı İşlemcisi** tasarım ve dalga-optiği simülasyon çalışmasının Türkçe ve İngilizce yayın sürümlerini üç farklı formatta düzenli şekilde barındırır.

> **Yayınlanan Ön Baskı (Optica Open Preprint):** [doi:10.1364/opticaopen.35085502](https://doi.org/10.1364/opticaopen.35085502) · Preprint ID: `137810` · Sürüm: `V1` (24 Kasım 2026) · Lisans: **CC BY 4.0** · Birebir eşleşen kod sürümü: [`v0.5.0`](https://github.com/hamzasolak/zerre/releases/tag/v0.5.0)

---

## Klasör Yapısı / Directory Structure

```text
makale/
├── 1_html_pdf/                     # Çift sütun akademik HTML ve baskıya hazır PDF sürümleri
│   ├── makale_tr.html
│   ├── ZERRE_Akademik_Makale_TR.pdf
│   ├── paper_en.html
│   └── ZERRE_Academic_Paper_EN.pdf
├── 2_latex/                        # IEEEtran LaTeX kaynakları, BibTeX ve Overleaf ZIP paketi
│   ├── zerre_makale_tr.tex
│   ├── zerre_paper_en.tex
│   ├── references.bib              # 24 doğrulanmış akademik kaynak
│   ├── figures/                    # Overleaf bağımsız derleme için 10 adet 300 DPI PNG kopyası
│   └── ZERRE_Overleaf_LaTeX_Paketi.zip
├── 3_markdown/                     # GitHub / KaTeX / Pandoc uyumlu Akademik Markdown sürümleri
│   ├── ZERRE_Akademik_Makale_TR.md
│   └── ZERRE_Academic_Paper_EN.md
├── figures/                        # 300 DPI yayın kalitesinde üretilmiş TR & EN şekiller (10 adet)
│   ├── makale_fig1_dalga_{tr,en}.png
│   ├── makale_fig2_alt_pleshko_{tr,en}.png
│   ├── makale_fig3_ablasyon_pat_{tr,en}.png
│   ├── makale_fig4_dayanim_{tr,en}.png
│   └── makale_fig5_gercekcilik_{tr,en}.png
└── scripts/                        # Çok-tohum kıyaslama çıktıları, şekil ve PDF üretim betikleri
    ├── paper_results.json          # 3 tohumlu ([7, 19, 42], N_test=1000) doğrulama sonuçları
    ├── realism_results.json
    ├── remedies_v06_results.json   # v0.6 teknik çözümler çok-tohumlu doğrulama çıktıları
    ├── generate_paper_figures.py
    └── build_paper_pdf.py
```

---

## Yeniden Üretim Komutları / Build Commands

Proje kök dizininden (`zerre/`) aşağıdaki komutlarla tüm deney çıktıları, şekiller ve PDF dosyaları yeniden üretilebilir:

```powershell
# 0. İsteğe bağlı: 3 tohumlu ([7, 19, 42]) tüm makale deneylerini ve paper_results.json dosyasını baştan üret:
python zerre_twin.py --paper-benchmark --seeds 7,19,42

# 1. 300 DPI şekilleri (TR & EN) paper_results.json ve fizik motorundan canlı üret (makale/2_latex/figures/ otomatik güncellenir):
python makale/scripts/generate_paper_figures.py --lang both

# 2. Çift sütun akademik PDF'leri (TR & EN) derle:
python makale/scripts/build_paper_pdf.py
```

### Overleaf Kullanımı (`2_latex/`)
1. `2_latex/ZERRE_Overleaf_LaTeX_Paketi.zip` dosyasını Overleaf'te **New Project → Upload Project** ile yükleyin.
2. Sol üstteki **Menu → Main document** ayarından `zerre_makale_tr.tex` (Türkçe, pdfLaTeX) veya `zerre_paper_en.tex` (İngilizce, pdfLaTeX) dosyasını seçip **Recompile** butonuna tıklayın.
