# -*- coding: utf-8 -*-
"""
ZERRE (Model H) Dual-Language IEEE Two-Column PDF Generator (TR & EN)
=====================================================================
Generates `makale/1_html_pdf/ZERRE_Akademik_Makale_TR.pdf` and
`makale/1_html_pdf/ZERRE_Academic_Paper_EN.pdf` directly via ReportLab
using the updated 3-seed figures in `makale/figures/`.

Usage:
  python makale/scripts/build_paper_pdf.py
"""

import os
import matplotlib
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def _register_fonts():
    """Cross-platform TTF font registration (Windows Times/Arial -> DejaVu -> built-ins)."""
    win_fonts = r"C:\Windows\Fonts"
    win_serif = {
        "regular": os.path.join(win_fonts, "times.ttf"),
        "bold": os.path.join(win_fonts, "timesbd.ttf"),
        "italic": os.path.join(win_fonts, "timesi.ttf"),
        "bi": os.path.join(win_fonts, "timesbi.ttf"),
        "sans": os.path.join(win_fonts, "arial.ttf"),
        "sans_b": os.path.join(win_fonts, "arialbd.ttf"),
    }
    if all(os.path.isfile(p) for p in win_serif.values()):
        pdfmetrics.registerFont(TTFont("ZSerif", win_serif["regular"]))
        pdfmetrics.registerFont(TTFont("ZSerif-B", win_serif["bold"]))
        pdfmetrics.registerFont(TTFont("ZSerif-I", win_serif["italic"]))
        pdfmetrics.registerFont(TTFont("ZSerif-BI", win_serif["bi"]))
        pdfmetrics.registerFontFamily(
            "ZSerif", normal="ZSerif", bold="ZSerif-B", italic="ZSerif-I", boldItalic="ZSerif-BI"
        )
        pdfmetrics.registerFont(TTFont("ZSans", win_serif["sans"]))
        pdfmetrics.registerFont(TTFont("ZSans-B", win_serif["sans_b"]))
        return "ZSerif", "ZSerif-B", "ZSerif-I", "ZSerif-BI", "ZSans", "ZSans-B"

    mpl_ttf = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    dv_paths = {
        "regular": os.path.join(mpl_ttf, "DejaVuSerif.ttf"),
        "bold": os.path.join(mpl_ttf, "DejaVuSerif-Bold.ttf"),
        "italic": os.path.join(mpl_ttf, "DejaVuSerif-Italic.ttf"),
        "bi": os.path.join(mpl_ttf, "DejaVuSerif-BoldItalic.ttf"),
        "sans": os.path.join(mpl_ttf, "DejaVuSans.ttf"),
        "sans_b": os.path.join(mpl_ttf, "DejaVuSans-Bold.ttf"),
    }
    if all(os.path.isfile(p) for p in dv_paths.values()):
        pdfmetrics.registerFont(TTFont("ZSerif", dv_paths["regular"]))
        pdfmetrics.registerFont(TTFont("ZSerif-B", dv_paths["bold"]))
        pdfmetrics.registerFont(TTFont("ZSerif-I", dv_paths["italic"]))
        pdfmetrics.registerFont(TTFont("ZSerif-BI", dv_paths["bi"]))
        pdfmetrics.registerFontFamily(
            "ZSerif", normal="ZSerif", bold="ZSerif-B", italic="ZSerif-I", boldItalic="ZSerif-BI"
        )
        pdfmetrics.registerFont(TTFont("ZSans", dv_paths["sans"]))
        pdfmetrics.registerFont(TTFont("ZSans-B", dv_paths["sans_b"]))
        return "ZSerif", "ZSerif-B", "ZSerif-I", "ZSerif-BI", "ZSans", "ZSans-B"

    return "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic", "Helvetica", "Helvetica-Bold"


def _make_styles(fonts):
    sr, sb, si, sbi, ssr, ssb = fonts
    return {
        "title": ParagraphStyle("title", fontName=sb, fontSize=14.2, leading=16.8, alignment=TA_CENTER, spaceAfter=1.6 * mm),
        "author": ParagraphStyle("author", fontName=sb, fontSize=9.8, leading=12.0, alignment=TA_CENTER, spaceAfter=0.5 * mm),
        "affil": ParagraphStyle("affil", fontName=si, fontSize=8.3, leading=10.5, alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=1.8 * mm),
        "abs": ParagraphStyle("abs", fontName=sr, fontSize=8.1, leading=10.0, alignment=TA_JUSTIFY),
        "kw": ParagraphStyle("kw", fontName=sr, fontSize=7.8, leading=9.6, alignment=TA_LEFT, spaceBefore=1.0 * mm),
        "h2": ParagraphStyle("h2", fontName=sb, fontSize=9.4, leading=11.2, alignment=TA_LEFT, spaceBefore=2.2 * mm, spaceAfter=1.0 * mm, keepWithNext=1),
        "h3": ParagraphStyle("h3", fontName=sbi, fontSize=8.7, leading=10.5, alignment=TA_LEFT, spaceBefore=1.8 * mm, spaceAfter=0.7 * mm, keepWithNext=1),
        "body": ParagraphStyle("body", fontName=sr, fontSize=8.45, leading=10.15, alignment=TA_JUSTIFY, firstLineIndent=3.0 * mm, spaceAfter=0.9 * mm),
        "body_noindent": ParagraphStyle("body_noindent", fontName=sr, fontSize=8.45, leading=10.15, alignment=TA_JUSTIFY, spaceAfter=0.9 * mm),
        "eq": ParagraphStyle("eq", fontName=si, fontSize=8.1, leading=9.8, alignment=TA_CENTER),
        "eq_num": ParagraphStyle("eq_num", fontName=sr, fontSize=8.1, leading=9.8, alignment=TA_RIGHT, textColor=colors.HexColor("#333333")),
        "cap": ParagraphStyle("cap", fontName=sr, fontSize=7.3, leading=8.9, alignment=TA_JUSTIFY, textColor=colors.HexColor("#222222"), spaceBefore=0.8 * mm),
        "tab_cap": ParagraphStyle("tab_cap", fontName=ssb, fontSize=7.3, leading=8.9, alignment=TA_CENTER, spaceBefore=1.3 * mm, spaceAfter=0.7 * mm, keepWithNext=1),
        "cell": ParagraphStyle("cell", fontName=ssr, fontSize=6.8, leading=8.2, alignment=TA_LEFT),
        "cell_r": ParagraphStyle("cell_r", fontName=ssr, fontSize=6.8, leading=8.2, alignment=TA_RIGHT),
        "cell_b": ParagraphStyle("cell_b", fontName=ssb, fontSize=6.8, leading=8.2, alignment=TA_LEFT),
        "cell_br": ParagraphStyle("cell_br", fontName=ssb, fontSize=6.8, leading=8.2, alignment=TA_RIGHT),
        "tab_note": ParagraphStyle("tab_note", fontName=si, fontSize=6.6, leading=7.8, alignment=TA_LEFT, textColor=colors.HexColor("#444444"), spaceBefore=0.5 * mm, spaceAfter=1.0 * mm),
        "ref": ParagraphStyle("ref", fontName=sr, fontSize=6.45, leading=7.65, alignment=TA_LEFT, leftIndent=3.8 * mm, firstLineIndent=-3.8 * mm, spaceAfter=0.55 * mm),
    }


def eq_block(math_html, eq_num_str, st, col_w):
    tbl = Table(
        [[Paragraph(math_html, st["eq"]), Paragraph(eq_num_str, st["eq_num"])]],
        colWidths=[col_w - 8 * mm, 8 * mm],
    )
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


def fig_block(img_path, caption_html, st, max_w_mm, max_img_h_mm=49.0):
    with PILImage.open(img_path) as im:
        iw, ih = im.size
    w_pt = max_w_mm * mm
    h_pt = w_pt * (ih / iw)
    if h_pt > max_img_h_mm * mm:
        h_pt = max_img_h_mm * mm
        w_pt = h_pt * (iw / ih)
    img = Image(img_path, width=w_pt, height=h_pt)
    img.hAlign = "CENTER"
    return KeepTogether([img, Paragraph(caption_html, st["cap"])])


def styled_table(rows_data, col_widths, highlight_rows=None):
    tbl = Table(rows_data, colWidths=col_widths)
    cmds = [
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in (highlight_rows or []):
        cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#eaf6ea")))
    tbl.setStyle(TableStyle(cmds))
    return tbl


def _make_doc(out_path, top_fig_h_mm=63.0):
    pw, ph = A4
    margin_x = 13.5 * mm
    margin_y = 13.5 * mm
    gap = 5.5 * mm
    full_w = pw - 2 * margin_x
    col_w = (full_w - gap) / 2.0
    usable_h = ph - 2 * margin_y

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.4)
        canvas.setFillColor(colors.HexColor("#666666"))
        if doc.page >= 2:
            canvas.drawString(margin_x, ph - 9.0 * mm, "ZERRE (Model H) — Technical Preprint (Wave-Optics Simulation Study)")
        canvas.drawCentredString(pw / 2.0, 7.5 * mm, f"{doc.page}")
        canvas.restoreState()

    head_h = 85.5 * mm
    body1_h = usable_h - head_h - 2.5 * mm
    f_head = Frame(margin_x, margin_y + body1_h + 2.5 * mm, full_w, head_h, id="F_HEAD", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f1_l = Frame(margin_x, margin_y, col_w, body1_h, id="F1_L", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f1_r = Frame(margin_x + col_w + gap, margin_y, col_w, body1_h, id="F1_R", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    top_h = top_fig_h_mm * mm
    bot_h = usable_h - top_h - 2.5 * mm
    ft_top = Frame(margin_x, margin_y + bot_h + 2.5 * mm, full_w, top_h, id="FT_TOP", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    ff_l = Frame(margin_x, margin_y, col_w, bot_h, id="FF_L", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    ff_r = Frame(margin_x + col_w + gap, margin_y, col_w, bot_h, id="FF_R", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    top_h_last = 56.0 * mm
    bot_h_last = usable_h - top_h_last - 2.5 * mm
    ft_top_last = Frame(margin_x, margin_y + bot_h_last + 2.5 * mm, full_w, top_h_last, id="FT_TOP_LAST", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    ff_l_last = Frame(margin_x, margin_y, col_w, bot_h_last, id="FF_L_LAST", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    ff_r_last = Frame(margin_x + col_w + gap, margin_y, col_w, bot_h_last, id="FF_R_LAST", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    c_l = Frame(margin_x, margin_y, col_w, usable_h, id="C_L", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    c_r = Frame(margin_x + col_w + gap, margin_y, col_w, usable_h, id="C_R", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc = BaseDocTemplate(out_path, pagesize=A4, pageTemplates=[
        PageTemplate(id="P_FIRST", frames=[f_head, f1_l, f1_r], onPage=on_page),
        PageTemplate(id="P_TOPFIG", frames=[ft_top, ff_l, ff_r], onPage=on_page),
        PageTemplate(id="P_TOPFIG_LAST", frames=[ft_top_last, ff_l_last, ff_r_last], onPage=on_page),
        PageTemplate(id="P_TWOCOL", frames=[c_l, c_r], onPage=on_page),
    ])
    return doc, full_w, col_w


def _refs_list(lang):
    tr_ve = "ve" if lang == "tr" else "and"
    vd = "vd." if lang == "tr" else "et al."
    ss = "ss." if lang == "tr" else "pp."
    cilt = "c." if lang == "tr" else "vol."
    baski = "4. baskı" if lang == "tr" else "4th ed."
    mak = "makale no." if lang == "tr" else "art. no."
    return [
        f'[1] M. Horowitz, "1.1 Computing\'s energy problem (and what we can do about it)," <i>IEEE Int. Solid-State Circuits Conf. (ISSCC)</i>, {ss} 10–14, 2014, doi: 10.1109/ISSCC.2014.6757323.',
        f'[2] V. Sze, Y.-H. Chen, T.-J. Yang, {tr_ve} J. S. Emer, "Efficient Processing of Deep Neural Networks: A Tutorial and Survey," <i>Proc. IEEE</i>, {cilt} 105, no. 12, {ss} 2295–2329, 2017, doi: 10.1109/JPROC.2017.2761740.',
        f'[3] G. Wetzstein {vd}, "Inference in artificial intelligence with deep optics and photonics," <i>Nature</i>, {cilt} 588, no. 7836, {ss} 39–47, 2020, doi: 10.1038/s41586-020-2973-6.',
        f'[4] D. Psaltis {tr_ve} N. H. Farhat, "Optical information processing based on an associative-memory model of neural nets with thresholding and feedback," <i>Opt. Lett.</i>, {cilt} 10, no. 2, {ss} 98–100, 1985, doi: 10.1364/OL.10.000098.',
        f'[5] X. Lin {vd}, "All-optical machine learning using diffractive deep neural networks," <i>Science</i>, {cilt} 361, no. 6406, {ss} 1004–1008, 2018, doi: 10.1126/science.aat8084.',
        f'[6] Y. Shen {vd}, "Deep learning with coherent nanophotonic circuits," <i>Nat. Photonics</i>, {cilt} 11, no. 7, {ss} 441–446, 2017, doi: 10.1038/nphoton.2017.93.',
        f'[7] T. Zhou {vd}, "Large-scale neuromorphic optoelectronic computing with a reconfigurable diffractive processing unit," <i>Nat. Photonics</i>, {cilt} 15, no. 5, {ss} 367–375, 2021, doi: 10.1038/s41566-021-00796-w.',
        f'[8] J. Feldmann {vd}, "Parallel convolutional processing using an integrated photonic tensor core," <i>Nature</i>, {cilt} 589, no. 7840, {ss} 52–58, 2021, doi: 10.1038/s41586-020-03070-1.',
        f'[9] X. Xu {vd}, "11 TOPS photonic convolutional accelerator for optical neural networks," <i>Nature</i>, {cilt} 589, no. 7840, {ss} 44–51, 2021, doi: 10.1038/s41586-020-03063-0.',
        f'[10] J. Chang, V. Sitzmann, X. Dun, W. Heidrich, {tr_ve} G. Wetzstein, "Hybrid optical-electronic convolutional neural networks with optimized diffractive optics for image classification," <i>Sci. Rep.</i>, {cilt} 8, {mak} 12324, 2018, doi: 10.1038/s41598-018-30619-y.',
        f'[11] F. T. S. Yu, T. Lu, X. Yang, {tr_ve} D. A. Gregory, "Optical neural network with pocket-sized liquid-crystal televisions," <i>Opt. Lett.</i>, {cilt} 15, no. 15, {ss} 863–865, 1990, doi: 10.1364/OL.15.000863.',
        f'[12] J. Spall, X. Guo, T. D. Barrett, {tr_ve} A. I. Lvovsky, "Fully reconfigurable coherent optical vector–matrix multiplication," <i>Opt. Lett.</i>, {cilt} 45, no. 20, {ss} 5752–5755, 2020, doi: 10.1364/OL.401675.',
        f'[13] S.-T. Wu {tr_ve} K.-C. Lim, "Absorption and scattering measurements of nematic liquid crystals," <i>Appl. Opt.</i>, {cilt} 26, no. 9, {ss} 1722–1727, 1987, doi: 10.1364/AO.26.001722.',
        f'[14] P. M. Alt {tr_ve} P. Pleshko, "Scanning limitations of liquid-crystal displays," <i>IEEE Trans. Electron Devices</i>, {cilt} 21, no. 2, {ss} 146–155, 1974, doi: 10.1109/T-ED.1974.17884.',
        f'[15] L. G. Wright {vd}, "Deep physical neural networks trained with backpropagation," <i>Nature</i>, {cilt} 601, no. 7894, {ss} 549–555, 2022, doi: 10.1038/s41586-021-04223-6.',
        f'[16] T. W. Hughes, M. Minkov, Y. Shi, {tr_ve} S. Fan, "Training of photonic neural networks through in situ backpropagation and gradient measurement," <i>Optica</i>, {cilt} 5, no. 7, {ss} 864–871, 2018, doi: 10.1364/OPTICA.5.000864.',
        f'[17] J. W. Goodman, <i>Introduction to Fourier Optics</i>, {baski}, New York, NY, USA: W. H. Freeman, 2017, ISBN 978-1-319-11916-4.',
        f'[18] K. Lu {tr_ve} B. E. A. Saleh, "Theory and design of the liquid crystal TV as an optical spatial phase modulator," <i>Opt. Eng.</i>, {cilt} 29, no. 3, {ss} 240–246, 1990, doi: 10.1117/12.55584.',
        f'[19] J. C. Spall, "Implementation of the simultaneous perturbation algorithm for stochastic optimization," <i>IEEE Trans. Aerosp. Electron. Syst.</i>, {cilt} 34, no. 3, {ss} 817–823, 1998, doi: 10.1109/7.705889.',
        f'[20] Y. LeCun, L. Bottou, Y. Bengio, {tr_ve} P. Haffner, "Gradient-based learning applied to document recognition," <i>Proc. IEEE</i>, {cilt} 86, no. 11, {ss} 2278–2324, 1998, doi: 10.1109/5.726791.',
        f'[21] I. Haller, "Thermodynamic and static properties of liquid crystals," <i>Prog. Solid State Chem.</i>, {cilt} 10, {ss} 103–118, 1975, doi: 10.1016/0079-6786(75)90008-4.',
        f'[22] J. Li, C.-H. Wen, S. Gauza, R. Lu, {tr_ve} S.-T. Wu, "Refractive indices of liquid crystals for display applications," <i>J. Display Technol.</i>, {cilt} 1, no. 1, {ss} 51–61, 2005, doi: 10.1109/JDT.2005.853357.',
        f'[23] H. Xiao, K. Rasul, {tr_ve} R. Vollgraf, "Fashion-MNIST: a Novel Image Dataset for Benchmarking Machine Learning Algorithms," <i>arXiv:1708.07747</i>, 2017, doi: 10.48550/arXiv.1708.07747.',
        f'[24] T. Xu {vd}, "Physical neural networks using sharpness-aware training," <i>Nat. Commun.</i>, {cilt} 17, {mak} 1766, 2026, doi: 10.1038/s41467-026-68470-9.',
    ]


def build_pdf(lang, out_path, base_dir, st):
    doc, full_w, col_w = _make_doc(out_path, top_fig_h_mm=63.0)
    story = []
    fig_dir = os.path.join(base_dir, "figures")

    if lang == "en":
        title_txt = "ZERRE (Model H): Wave-Optics Design, Physical Synthesis, and Physics-Aware Training of a Common-Path Optoelectronic Processor"
        affil_txt = "Independent Researcher, Türkiye &nbsp;|&nbsp; eng.hamzasolak@gmail.com &nbsp;|&nbsp; ORCID: 0009-0004-7541-9620"
        abs_txt = (
            "<i>Abstract:</i> Programmable optical neural processors typically rely on expensive spatial light modulators and vibration-sensitive "
            "dual-arm interferometers. This numerical design and wave-optics simulation study presents ZERRE (Model H), an open-source "
            "common-path optoelectronic architecture built around commodity monochrome masked stereolithography (mSLA) liquid-crystal displays. "
            "Based on measured nematic attenuation, volumetric reservoirs were rejected due to thermal Rayleigh–Gans scattering (15–40 dB/cm), "
            "and passive-matrix ITO addressing was shown via the Alt–Pleshko bound to compress usable E7 phase retardation from 4.86 rad "
            "(1.00–5.00 V) to 0.921 rad across 16 rows. An analytical Wirtinger-adjoint operator through scalar Angular Spectrum propagation "
            "and coupled Jones modulation (relative finite-difference error 5.52×10<sup>−7</sup>) enables Physics-Aware Training (PAT) under "
            "unmodeled hardware perturbations. Across three random seeds (<i>N</i><sub>test</sub> = 1000) in an 8×8 detector-bottlenecked regime "
            "with every readout head matched to an identical cross-entropy/Adam protocol, PAT lifts linear MNIST accuracy from 71.07% to 78.40% "
            "(+7.33 points over matched random optics) yet trails direct digital area pooling (87.00%) by 8.60 points. With a 32×32 readout grid "
            "and hybrid multilayer perceptron, the nominal-twin upper bound reaches 94.67% on MNIST and 84.43% on Fashion-MNIST (perturbed "
            "plant: 91.07%, 81.47%), matching raw-pixel (93.93%, 85.17%) and random-optics (94.20%, 84.70%) MLPs. Blind PAT reaches 77.30% under "
            "15-wavelength Zernike aberrations (+0.63 points over 76.67% head-only recalibration, within one combined SD) and retains 94.8% at "
            "4-bit quantization, but trails head-only recalibration (76.80% vs. 79.13%) under structural model mismatch (perturbed LC curve, "
            "camera gamma, speckle). Estimated component cost is $784–$959."
        )
        kw_txt = "<i>Index Terms:</i> Angular spectrum method, diffractive neural networks, liquid-crystal modulators, optoelectronic computing, physics-aware training, Wirtinger adjoint."
    else:
        title_txt = "ZERRE (Model H): Ortak-Yol Kırınımlı Optoelektronik İşlemcinin Dalga-Optiği Tasarımı, Fiziksel Sentezi ve Fizik-Farkındalıklı Eğitimi"
        affil_txt = "Bağımsız Araştırmacı, Türkiye &nbsp;|&nbsp; eng.hamzasolak@gmail.com &nbsp;|&nbsp; ORCID: 0009-0004-7541-9620"
        abs_txt = (
            "<i>Özet:</i> Programlanabilir optik sinir ağı işlemcileri çoğunlukla pahalı uzamsal ışık modülatörlerine ve titreşime duyarlı "
            "çift kollu interferometrelere dayanır. Bu sayısal tasarım ve dalga-optiği simülasyon çalışması, yaygın monokrom maskeli "
            "stereolitografi (mSLA) sıvı kristal ekranları temel alan açık kaynaklı ortak-yol optoelektronik ZERRE (Model H) mimarisini "
            "sunmaktadır. Ölçülmüş nematik zayıflama temelinde hacimsel rezervuarlar termal Rayleigh–Gans saçılması (15–40 dB/cm) nedeniyle "
            "elenmiş; pasif matrisli ITO sürüşünün ise Alt–Pleshko sınırı uyarınca 16 satırda kullanılabilir E7 faz aralığını 4,86 rad'dan "
            "(1,00–5,00 V) 0,921 rad'a daralttığı gösterilmiştir. Skaler Açısal Spektrum yayılımı ve kuple Jones modülasyonu için türetilen "
            "kapalı form Wirtinger eşlenik operatörü (sonlu farklarla bağıl hata 5,52×10<sup>−7</sup>), modellenmemiş donanım kusurlarına "
            "karşı Fizik-Farkındalıklı Eğitimi (PAT) mümkün kılar. Üç tohumda (<i>N</i><sub>test</sub> = 1000) tüm okuma kafalarının aynı "
            "çapraz-entropi/Adam protokolüyle eşlendiği kısıtlı 8×8 dedektör rejiminde PAT, lineer MNIST doğruluğunu eşleşmiş rastgele "
            "optiğe göre %71,07'den %78,40'a (+7,33 puan) çıkarırken doğrudan dijital alan havuzlamanın (%87,00) 8,60 puan gerisinde kalır. "
            "Tam 32×32 okuma ve hibrit çok katmanlı algılayıcıyla nominal-ikiz üst sınırı MNIST'te %94,67 ve Fashion-MNIST'te %84,43'e "
            "ulaşırken (kusurlu sistem: %91,07, %81,47), bu değerler ham piksel (%93,93, %85,17) ve rastgele optik (%94,20, %84,70) "
            "MLP'leriyle eşdeğerdir. 15 dalga boyu Zernike sapmasında kör PAT %77,30'a ulaşır (yalnız-kafa %76,67; +0,63 puan birleşik SS "
            "içinde) ve 4-bit basamaklamada %94,8'i korur; ancak pertürbe LC eğrisi, kamera gamması ve benek içeren yapısal uyumsuzlukta "
            "yalnız-kafa kalibrasyonunun gerisinde kalır (%76,80 ve %79,13). Tahmini bileşen bütçesi 784–959 USD'dir."
        )
        kw_txt = "<i>Anahtar Kelimeler:</i> Açısal spektrum yöntemi, kırınımlı sinir ağları, sıvı kristal modülatörler, optoelektronik hesaplama, fizik-farkındalıklı eğitim, Wirtinger eşlenik."

    story.append(Paragraph(title_txt, st["title"]))
    story.append(Paragraph("Hamza Solak", st["author"]))
    story.append(Paragraph(affil_txt, st["affil"]))

    abs_box = Table([[Paragraph(abs_txt, st["abs"])], [Paragraph(kw_txt, st["kw"])]], colWidths=[full_w])
    abs_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fa")),
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.HexColor("#777777")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.HexColor("#777777")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(abs_box)
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    # Section I + start of Section II fill both columns of Page 1 naturally!
    if lang == "en":
        story.append(Paragraph("I. INTRODUCTION", st["h2"]))
        story.append(Paragraph(
            "In modern CMOS and GPU accelerators, 60% to 90% of total inference energy is spent moving weights and activations "
            "across DRAM and interconnect hierarchies rather than performing multiply-accumulate arithmetic [1], [2]. Free-space and "
            "integrated optical computing architectures address this data-movement bottleneck in the analog domain: as an optical "
            "field propagates through structured diffractive or phase-modulating elements, spatial superposition executes dense "
            "linear transformations passively during its sub-nanosecond transit across a centimeter-scale cavity (~0.33 ns across a 10 cm optical path) [3]–[5].",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Static 3D-printed diffractive deep neural networks (D²NN) established passive inference at terahertz wavelengths [5], "
            "yet fixed dielectric plates cannot be reprogrammed after fabrication. Subsequent reconfigurable systems introduced "
            "nanophotonic Mach–Zehnder meshes [6], large-scale diffractive processing units [7], integrated photonic tensor cores [8], "
            "time-wavelength interleaving [9], and hybrid optical-electronic convolutional front-ends [10]. Parallel efforts dating back "
            "to pocket liquid-crystal televisions [11] and recent spatial-light vector-matrix multipliers [12] demonstrated that display "
            "hardware can serve as programmable optical weights.",
            st["body"]
        ))
        story.append(Paragraph(
            "Three engineering barriers still hinder accessible experimental adoption: laboratory liquid-crystal-on-silicon (LCOS) "
            "spatial light modulators cost $8,000–$40,000 per plane; dual-arm interferometers experience destructive fade under "
            "nanometer path shifts (λ/4 ≈ 133 nm at 532 nm) [6]; and weights trained on idealized numerical models lose accuracy when "
            "deployed onto misaligned optical hardware, an effect worsened when designers overlook RMS voltage clamping in passive-matrix liquid-crystal cells.",
            st["body"]
        ))
        story.append(Paragraph(
            "This article presents a numerical design and wave-optics simulation study of <b>ZERRE (Model H)</b>, an open-source "
            "common-path optoelectronic processor architecture and digital twin; no physical benchtop prototype has been constructed or "
            "optically measured at this stage. Starting from volumetric bulk scattering bounds in nematic liquid crystals [13], eight "
            "candidate topologies (Models A–H) are winnowed down to a planar 7 μm thin-cell stack built from commodity monochrome mSLA 2K displays "
            "($40–$60 each). Applying the Alt–Pleshko multiplexing theorem [14] shows that 16×16 passive-matrix scanning (1/5 voltage "
            "bias) restricts the RMS selection ratio to 1.290994 and shrinks usable E7 phase retardation by 5.28× (4.86 rad to "
            "0.921 rad), motivating an active-matrix TFT-LCD or direct AC-PWM weight plane. Finally, deriving exact analytical "
            "Wirtinger-adjoint gradients through Angular Spectrum propagation enables Physics-Aware Training (PAT) [15], [16] on a "
            "perturbed physical plant simulator, audited across three random seeds on MNIST and Fashion-MNIST alongside mechanical, "
            "thermal, stray-light, bit-quantization, sub-aperture fill-factor, and Zernike aberration stress tests.",
            st["body"]
        ))
        story.append(Paragraph("II. ARCHITECTURAL SYNTHESIS & PHYSICAL CONSTRAINTS", st["h2"]))
        story.append(Paragraph("A. Bulk Nematic Scattering: Spherical Reservoir vs. Thin Planar Cell", st["h3"]))
        story.append(Paragraph(
            "Among eight evaluated conceptual topologies (Models A–H), four volumetric nematic-reservoir designs (32-electrode Fibonacci "
            "sphere Model A, hemispherical hybrid bowl Model C, photodiode-addressed sphere Model F, and spherical ITO matrix Model G) "
            "investigated filling centimeter-scale borosilicate vessels (Ø100 mm) with Merck E7 to induce three-dimensional optical mixing. "
            "In nematic mesophases, however, thermal fluctuations of the molecular director generate Rayleigh–Gans scattering roughly two orders of magnitude "
            "stronger than intrinsic absorption, producing attenuation coefficients of α<sub>scat</sub> ≈ 15–40 dB/cm across the visible "
            "spectrum [13]. Across an <i>L</i> = 10 cm optical path inside a spherical cell, ballistic attenuation reaches 150–400 dB, "
            "extinguishing wavefront coherence into diffuse photon transport and rendering the director field unstable under mechanical sloshing.",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "By contrast, confining E7 inside a planar gap of <i>d</i> ≤ 7 μm reduces bulk scattering loss to 0.003–0.03 dB while capillary "
            "forces immobilize the fluid layer. At λ = 532 nm, a 7 μm layer of pure E7 (Δ<i>n</i> = 0.225) imparts an unbiased phase "
            "retardation of 18.60 rad (≈ 5.92π), spanning multiple interference orders. A monotonic, single-order working window of",
            st["body"]
        ))
        story.append(eq_block("Δφ<sub>max</sub> = (2π / λ) · Δn<sub>eff</sub> · d ≈ 4.97 rad  (≈ 1.58π)", "(1)", st, col_w))
        story.append(Paragraph(
            "is realized either with fluorinated nematic mixtures native to mSLA TFT panels (Δ<i>n</i><sub>eff</sub> ≈ 0.060 at <i>d</i> = 7 μm), "
            "a thinner <i>d</i> = 1.87 μm pure E7 gap, or a 7 μm E7 cell biased above 2.2 V RMS. Among the remaining planar thin-cell "
            "candidates, a passive 16×16 ITO plate (Model B) hits the multiplexing limit in Section II-C, a single 7-layer stack (Model D) "
            "defines the 7 μm cell cross-section, and a 3-layer cascaded stack (Model E) compounds loss and alignment cost, leaving the "
            "single-weight-plane common-path stack (Model H) as the minimal realizable synthesis. Any future thick-cell test is gated by a 1 cm cuvette check.",
            st["body_noindent"]
        ))
    else:
        story.append(Paragraph("I. GİRİŞ", st["h2"]))
        story.append(Paragraph(
            "Modern CMOS ve GPU hızlandırıcılarında toplam çıkarım enerjisinin %60 ila %90'ı, aritmetik işlemlerden çok ağırlıkların "
            "ve aktivasyonların bellek hiyerarşisi ile ara bağlantılar boyunca taşınmasında harcanmaktadır [1], [2]. Serbest uzay ve "
            "entegre optik hesaplama mimarileri bu veri taşıma darboğazını analog düzeyde ele alır: yapılandırılmış kırınımlı veya "
            "faz modülasyonlu bir ortamdan geçen ışık alanı, 10 cm uzunluğundaki bir optik yoldan ~0,33 ns sürede geçerken uzamsal "
            "süperpozisyon yoluyla yoğun doğrusal dönüşümleri pasif biçimde icra eder [3]–[5].",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "3B baskılı kırınımlı derin sinir ağları (D²NN) terahertz bandında pasif sınıflandırma ortaya koymuş [5], ancak sabit "
            "dielektrik plakaların görev değişimine uyarlanamaması nedeniyle araştırmalar yeniden yapılandırılabilir sistemlere yönelmiştir. "
            "Takip eden çalışmalarda nanofotonik Mach–Zehnder ağları [6], büyük ölçekli kırınımlı işleme birimleri [7], entegre fotonik "
            "tensör çekirdekleri [8], zaman-dalga boyu çoğullaması [9] ve hibrit optik-elektronik evrişimli ön uçlar [10] geliştirilmiştir. "
            "Cep tipi sıvı kristal televizyonlarla başlayan [11] ve güncel uzamsal matris çarpıcılarla [12] sürdürülen paralel "
            "çalışmalar da ticari ekranların programlanabilir optik ağırlık olarak kullanılabileceğini göstermiştir.",
            st["body"]
        ))
        story.append(Paragraph(
            "Buna karşın deneysel erişilebilirliği kısıtlayan üç mühendislik engeli sürmektedir: laboratuvar tipi LCOS modülatörler "
            "düzlem başına 8.000–40.000 USD maliyet gerektirmekte; çift kollu interferometreler nanometre ölçeğindeki yol kaymalarında "
            "(λ/4 ≈ 133 nm) sönümlenmeye uğramakta [6]; ideal sayısal modellerde eğitilen ağırlıklar ise fiziksel hiza hataları ve "
            "pasif matrisli sıvı kristal hücrelerdeki etkin (RMS) voltaj kenetlenmesi nedeniyle doğruluk kaybetmektedir.",
            st["body"]
        ))
        story.append(Paragraph(
            "Bu makale, <b>ZERRE (Model H)</b> ortak-yol optoelektronik işlemci mimarisi ile açık kaynaklı dalga-optiği sayısal ikizinin "
            "tasarımını ve simülasyon analizini sunmaktadır; bu aşamada henüz fiziksel bir masaüstü prototip kurulmamış ve optik ölçüm "
            "alınmamıştır. Nematik sıvı kristallerdeki hacimsel saçılma sınırlarından [13] yola çıkılarak sekiz aday topoloji (Model A–H) taranmış "
            "ve birimi 40–60 USD olan monokrom mSLA 2K ekranlara dayalı düzlemsel 7 μm ince hücre mimarisi seçilmiştir. Alt–Pleshko "
            "teoremi [14] uygulanarak 16×16 pasif matris taramasının (1/5 gerilim öngerilimi) RMS seçim oranını 1,290994'e kısıtladığı "
            "ve kullanılabilir E7 faz aralığını 5,28× daraltarak 4,86 rad'dan 0,921 rad'a düşürdüğü gösterilmiştir. Son olarak, Açısal "
            "Spektrum yayılımı üzerinden kapalı form Wirtinger eşlenik gradyanı türetilerek kusurlu fiziksel sistem simülatörü üzerinde "
            "Fizik-Farkındalıklı Eğitim (PAT) [15], [16] uygulanmış; üç rastgele tohumda MNIST ve Fashion-MNIST başarımı mekanik, "
            "termal, ortam ışığı, bit kuantizasyonu, alt-açıklık doluluğu ve Zernike sapma testleriyle birlikte sayısal olarak değerlendirilmiştir.",
            st["body"]
        ))
        story.append(Paragraph("II. MİMARİ SENTEZ VE FİZİKSEL KISITLAR", st["h2"]))
        story.append(Paragraph("A. Hacimsel Nematik Saçılma Sınırı: Küreye Karşı İnce Hücre", st["h3"]))
        story.append(Paragraph(
            "Değerlendirilen sekiz kavramsal topolojiden (Model A–H) dört hacimsel nematik rezervuar tasarımı (32 elektrotlu Fibonacci küresi "
            "Model A, yarı-küre hibrit kase Model C, fotodiyot adreslemeli küre Model F ve küresel ITO matrisi Model G), santimetre ölçekli "
            "borosilikat kapları (Ø100 mm) Merck E7 ile doldurmayı incelemiştir. Ancak nematik fazda termal direktör dalgalanmaları, görünür dalga "
            "boylarında içsel soğurmadan yaklaşık iki mertebe daha güçlü Rayleigh–Gans saçılması üreterek α<sub>scat</sub> ≈ 15–40 dB/cm zayıflama "
            "oluşturur [13]. <i>L</i> = 10 cm optik yol boyunca balistik iletim kaybı 150–400 dB düzeyine ulaşır; koherent dalga cephesi "
            "foton difüzyonuna dönüşür ve mekanik sarsıntı altında sıvı çalkalanması direktör alanını bozar.",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Buna karşılık E7 katmanını <i>d</i> ≤ 7 μm düzlemsel bir boşluğa hapsetmek saçılma kaybını 0,003–0,03 dB aralığına indirir "
            "ve kılcal kuvvetler sıvıyı sabitler. λ = 532 nm için 7 μm saf E7 (Δ<i>n</i> = 0,225) 18,60 rad (≈ 5,92π) çok-mertebeli faz "
            "gecikmesi üretirken, tek-mertebeli çalışma penceresi",
            st["body"]
        ))
        story.append(eq_block("Δφ<sub>maks</sub> = (2π / λ) · Δn<sub>eff</sub> · d ≈ 4,97 rad  (≈ 1,58π)", "(1)", st, col_w))
        story.append(Paragraph(
            "ya ticari mSLA TFT panellerdeki florlu nematik karışımlarla (Δ<i>n</i><sub>eff</sub> ≈ 0,060, <i>d</i> = 7 μm), ya <i>d</i> = 1,87 μm "
            "ince E7 hücreyle, ya da 7 μm E7'nin <i>V</i> ≥ 2,2 V RMS öngerilim penceresinde sağlanır. Kalan düzlemsel adaylardan pasif 16×16 ITO "
            "plaka (Model B) Bölüm II-C çoğullama sınırına takılır; tek 7 katmanlı yığın (Model D) 7 μm hücre kesitini tanımlar ve 3 katmanlı yığın "
            "(Model E) kayıp ile hizalamayı katlar; böylece tek düzlemli ortak-yol mimari (Model H) temel sentez olarak seçilir. Kalın hücre testi "
            "1 cm cam küvet kontrolüyle sınırlandırılmıştır.",
            st["body_noindent"]
        ))

    # Page 2: Fig 1 banner + II.B + II.C + start of III.A
    story.append(NextPageTemplate("P_TOPFIG"))
    story.append(PageBreak())
    fig1_cap = (
        "<b>Fig. 1.</b> Scalar wave-optics forward propagation of a handwritten MNIST digit ('8') through the simulated ZERRE Model H "
        "pipeline (<i>N</i> = 128², Δ<i>x</i> = 47 μm): <b>(a)</b> input amplitude mask <i>A</i>(<i>x,y</i>); <b>(b)</b> diffracted amplitude "
        "|<i>E</i><sub>1</sub>| after <i>Z</i><sub>1</sub> = 5 cm ASM propagation; <b>(c)</b> PAT-trained 32×32 active LC phase map Δφ(<i>V<sub>ij</sub></i>) [rad]; "
        "<b>(d)</b> CMOS intensity |<i>E</i><sub>2</sub>|² after <i>Z</i><sub>2</sub> = 5 cm; <b>(e)</b> 32×32 pooled map (Class 8 at 94.7%, 1.04 ms median CPU sim)."
        if lang == "en" else
        "<b>Şekil 1.</b> ZERRE Model H dalga-optiği hattında el yazısı bir MNIST rakamının ('8') skaler ileri yayılımı "
        "(<i>N</i> = 128², Δ<i>x</i> = 47 μm): <b>(a)</b> giriş genlik maskesi <i>A</i>(<i>x,y</i>); <b>(b)</b> <i>Z</i><sub>1</sub> = 5 cm ASM sonrası "
        "|<i>E</i><sub>1</sub>| genliği; <b>(c)</b> PAT ile eğitilmiş 32×32 aktif LC faz haritası Δφ(<i>V<sub>ij</sub></i>) [rad]; <b>(d)</b> <i>Z</i><sub>2</sub> = 5 cm "
        "sonrası CMOS yoğunluğu |<i>E</i><sub>2</sub>|²; <b>(e)</b> 32×32 havuzlanmış harita (%94,7 ile Sınıf 8, ortanca 1,04 ms CPU sim)."
    )
    story.append(fig_block(os.path.join(fig_dir, f"makale_fig1_dalga_{lang}.png"), fig1_cap, st, 180, max_img_h_mm=43.0))
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    if lang == "en":
        story.append(Paragraph("B. Input Encoding via Commodity mSLA Monochrome LCDs", st["h3"]))
        story.append(Paragraph(
            "Mass-produced monochrome LCD panels built for masked stereolithography (mSLA) 3D printers offer a practical alternative "
            "to research LCOS modulators. Typical units offer 1440×2560 pixels on a 5.5-inch panel (~47 μm pitch, with 1620×2560 resolution "
            "on ~6.1-inch displays), omit absorptive RGB color filters, ship without a backlight as bare transmissive valves, and interface "
            "with standard HDMI-to-MIPI driver boards at 60 Hz (8-bit grayscale) for $40–$60. Although thin-film transistor (TFT) bus lines "
            "restrict clear aperture transmittance to roughly 4%–8%, a 100 mW 532 nm DPSS laser paired with millisecond camera exposure "
            "compensates for this loss, while the 16.7 ms frame refresh outpaces the ~50 ms viscoelastic relaxation time of E7.",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. The Alt–Pleshko RMS Bottleneck in Passive Matrices", st["h3"]))
        story.append(Paragraph(
            "Addressing an <i>N</i>×<i>N</i> ITO grid using 2<i>N</i> row-and-column channels via time multiplexing (for instance, a 1/5 voltage "
            "bias scheme for <i>N</i> = 16) appears economical at first glance. Because the electro-optic dielectric torque in a nematic LC "
            "scales quadratically with electric field (~<i>E</i>²) and integrates over a ~50 ms response time, each cell reacts to the "
            "root-mean-square voltage over the entire scan period rather than instantaneous row pulses:",
            st["body_noindent"]
        ))
        story.append(eq_block("V<sub>rms</sub>(i,j) = [ (1/N)(V<sub>sel</sub> + U<sub>ij</sub>V<sub>data</sub>)² + (1/N)∑<sub>r≠i</sub>(U<sub>rj</sub>V<sub>data</sub>)² ]<sup>1/2</sup>", "(2)", st, col_w))
        story.append(Paragraph(
            "where −1 ≤ <i>U<sub>rj</sub></i> ≤ +1 denotes normalized column weights. Under optimal drive ratio <i>V</i><sub>sel</sub>/<i>V</i><sub>data</sub> = √<i>N</i> "
            "(= 4 for <i>N</i> = 16), the Alt–Pleshko theorem [14] bounds the maximum RMS selection ratio to",
            st["body_noindent"]
        ))
        story.append(eq_block("V<sub>on,rms</sub> / V<sub>off,rms</sub> ≤ [ (√N + 1) / (√N − 1) ]<sup>1/2</sup>", "(3)", st, col_w))
        story.append(Paragraph(
            "For <i>N</i> = 16 multiplexed rows, this ceiling equals √(5/3) ≈ 1.290994 (dropping to 1.195606 at <i>N</i> = 32). Holding unselected "
            "elements near the 1.00 V Freedericksz threshold caps selected pixels at 1.291 V RMS, reducing usable E7 phase modulation from "
            "4.86 rad down to 0.921 rad (5.28× loss, Fig. 2a) while introducing vertical column crosstalk via Eq. (2). Model H therefore "
            "replaces passive scanning in the weight plane with either direct AC-coupled PWM channels or a second active-matrix TFT mSLA panel.",
            st["body_noindent"]
        ))
        story.append(Paragraph("III. WAVE-OPTICS MODEL & PHYSICS-AWARE TRAINING", st["h2"]))
        story.append(Paragraph("A. Angular Spectrum Propagation and Coupled Jones Modulation", st["h3"]))
        story.append(Paragraph(
            "Linearly polarized (0°) 532 nm light modulated in amplitude by the input mSLA panel forms <i>E</i><sub>0</sub>(<i>x,y</i>) = <i>A</i>(<i>x,y</i>) "
            "and propagates across free space <i>Z</i><sub>1</sub> = 5 cm via the non-paraxial scalar Angular Spectrum Method (ASM) [17]:",
            st["body_noindent"]
        ))
        story.append(eq_block("E<sub>1</sub> = P<sub>Z1</sub>{E<sub>0</sub>} = F<sup>−1</sup>{ F{E<sub>0</sub>} · H(f<sub>x</sub>, f<sub>y</sub>; Z<sub>1</sub>) }", "(4)", st, col_w))
        story.append(eq_block("H(f<sub>x</sub>, f<sub>y</sub>; z) = exp[ i(2π/λ)z √(1 − λ²f<sub>x</sub>² − λ²f<sub>y</sub>²) ]  (f<sub>x</sub>²+f<sub>y</sub>² < λ<sup>−2</sup>)", "(5)", st, col_w))
        story.append(Paragraph(
            "where evanescent modes are truncated. At the weight plane, our analytical model treats each pixel as a parallel-aligned "
            "electrically controlled birefringence (ECB) retarder oriented at 45° between crossed polarizers (0°/90°), yielding scalar Jones transmittance",
            st["body_noindent"]
        ))
        story.append(eq_block("t(V<sub>ij</sub>) = sin(Δφ(V<sub>ij</sub>)/2) · exp(i Δφ(V<sub>ij</sub>)/2)", "(6)", st, col_w))
        story.append(Paragraph(
            "followed by <i>E</i><sub>2</sub> = <i>P</i><sub><i>Z</i>2</sub>{<i>E</i><sub>1</sub> · <i>M</i>(<b>V</b>)} and square-law intensity "
            "<i>I</i><sub>CMOS</sub> = |<i>E</i><sub>2</sub>|² block-averaged into <b>f</b> in ℝ<sup><i>K</i>²</sup> (Fig. 1). Δφ(<i>V</i>) follows a "
            "piecewise-linear electro-optic curve decreasing from 4.97 rad (1.00 V) to 0.11 rad (5.00 V; 4.86 rad full span, 4.64 rad inside PAT bounds "
            "[1.05, 4.95] V), whereas |<i>t</i>(<i>V</i>)|² peaks at Δφ = π. Equation (6) acts as a closed-form surrogate for TN mSLA displays [18], "
            "requiring empirical calibration in hardware. With Δ<i>x</i> = 47 μm, <i>N</i><sub>crit</sub> = λ<i>Z</i><sub>1</sub>/Δ<i>x</i>² ≈ 12.0 px "
            "(>10× margin at <i>N</i> = 128) and walk-off 0.283 mm sits inside zero-pad guard bands of 1.69 mm (input) and 0.75 mm (weight) at <i>N</i> = 128 "
            "(2.73 and 1.50 mm at <i>N</i> = 256). PAT FFT paths use <code>complex64</code>; non-PAT sweeps and evaluation paths use <code>complex128</code>.",
            st["body_noindent"]
        ))
    else:
        story.append(Paragraph("B. Giriş Kodlama: Ticari mSLA Monokrom LCD Paneller", st["h3"]))
        story.append(Paragraph(
            "Maskeli stereolitografi (mSLA) 3B yazıcılar için seri üretilen monokrom LCD paneller, araştırma sınıfı LCOS modülatörlere "
            "erişilebilir bir seçenek oluşturur. Yaygın 5,5 inç paneller 1440×2560 piksel (~47 μm adım; ~6,1 inç modellerde 1620×2560) "
            "sunar, RGB renk filtresi ve arka aydınlatma içermeden çıplak transmisif vana olarak gelir ve standart HDMI–MIPI sürücü kartıyla "
            "60 Hz 8-bit gri tonda 40–60 USD karşılığında temin edilir. TFT veri yolları net açıklık geçirgenliğini %4–%8 düzeyine düşürse de "
            "100 mW 532 nm DPSS lazer ve milisaniye CMOS pozlaması bunu telafi eder; 16,7 ms çerçeve yenilemesi E7'nin ~50 ms gevşemesinden hızlıdır.",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. Pasif Matris Sürüşte Alt–Pleshko RMS Kısıtı", st["h3"]))
        story.append(Paragraph(
            "<i>N</i>×<i>N</i> elektrotlu bir örgüyü 2<i>N</i> satır/sütun kanalıyla zaman çoğullamalı (örneğin <i>N</i> = 16 için 1/5 gerilim öngerilimi) "
            "sürmek ilk bakışta ekonomik görünür. Ancak nematik sıvı kristallerdeki dielektrik tork elektrik alanın karesiyle (~<i>E</i>²) "
            "orantılı olduğundan ve ~50 ms pencere üzerinden ortalandığından, her hücre tüm tarama periyodu boyunca oluşan etkin (RMS) gerilime yanıt verir:",
            st["body_noindent"]
        ))
        story.append(eq_block("V<sub>rms</sub>(i,j) = [ (1/N)(V<sub>sel</sub> + U<sub>ij</sub>V<sub>data</sub>)² + (1/N)∑<sub>r≠i</sub>(U<sub>rj</sub>V<sub>data</sub>)² ]<sup>1/2</sup>", "(2)", st, col_w))
        story.append(Paragraph(
            "burada −1 ≤ <i>U<sub>rj</sub></i> ≤ +1 normalize sütun ağırlıklarıdır. Optimum <i>V</i><sub>sel</sub>/<i>V</i><sub>data</sub> = √<i>N</i> "
            "(<i>N</i> = 16 için 4) oranında Alt–Pleshko teoremi [14] ulaşılabilir en yüksek seçim oranını",
            st["body_noindent"]
        ))
        story.append(eq_block("V<sub>on,rms</sub> / V<sub>off,rms</sub> ≤ [ (√N + 1) / (√N − 1) ]<sup>1/2</sup>", "(3)", st, col_w))
        story.append(Paragraph(
            "ile sınırlar. <i>N</i> = 16 satır için bu sınır √(5/3) ≈ 1,290994'tür (<i>N</i> = 32 için 1,195606). Seçilmemiş pikseller 1,00 V "
            "Freedericksz eşiğinde tutulduğunda seçili piksel en fazla 1,291 V RMS alabilir; böylece faz aralığı 4,86 rad'dan 0,921 rad'a "
            "(5,28× daralma, Şekil 2a) inerken Denklem (2) sütun çapraz etkileşimi üretir. Bu nedenle Model H, ağırlık düzleminde doğrudan "
            "AC-PWM veya ikinci bir aktif-matris TFT mSLA panelini benimser.",
            st["body_noindent"]
        ))
        story.append(Paragraph("III. DALGA-OPTİĞİ MODELİ VE PAT EĞİTİMİ", st["h2"]))
        story.append(Paragraph("A. Açısal Spektrum Yayılımı ve Kuple Jones Modülasyonu", st["h3"]))
        story.append(Paragraph(
            "Giriş mSLA panelinde modüle edilen doğrusal polarize (0°) 532 nm düzlem dalga <i>E</i><sub>0</sub> = <i>A</i>(<i>x,y</i>), <i>Z</i><sub>1</sub> = 5 cm "
            "boyunca paraksiyel olmayan skaler Açısal Spektrum Yöntemi (ASM) ile yayılır [17]:",
            st["body_noindent"]
        ))
        story.append(eq_block("E<sub>1</sub> = P<sub>Z1</sub>{E<sub>0</sub>} = F<sup>−1</sup>{ F{E<sub>0</sub>} · H(f<sub>x</sub>, f<sub>y</sub>; Z<sub>1</sub>) }", "(4)", st, col_w))
        story.append(eq_block("H(f<sub>x</sub>, f<sub>y</sub>; z) = exp[ i(2π/λ)z √(1 − λ²f<sub>x</sub>² − λ²f<sub>y</sub>²) ]  (f<sub>x</sub>²+f<sub>y</sub>² < λ<sup>−2</sup>)", "(5)", st, col_w))
        story.append(Paragraph(
            "Ağırlık düzleminde çapraz polarizörler (0°/90°) arasında 45° yönlendirilmiş paralel ECB hücresi skaler Jones geçişi üretir:",
            st["body_noindent"]
        ))
        story.append(eq_block("t(V<sub>ij</sub>) = sin(Δφ(V<sub>ij</sub>)/2) · exp(i Δφ(V<sub>ij</sub>)/2)", "(6)", st, col_w))
        story.append(Paragraph(
            "ardından <i>E</i><sub>2</sub> = <i>P</i><sub><i>Z</i>2</sub>{<i>E</i><sub>1</sub> · <i>M</i>(<b>V</b>)} ve <i>I</i><sub>CMOS</sub> = |<i>E</i><sub>2</sub>|² "
            "ortalanmış <i>K</i>×<i>K</i> bloklarda <b>f</b>, ℝ<sup><i>K</i>²</sup> uzayında havuzlanır (Şekil 1). Parçalı-doğrusal eğride Δφ(<i>V</i>) "
            "4,97 rad'dan (1,00 V) 0,11 rad'a (5,00 V; toplam 4,86 rad, [1,05, 4,95] V PAT sınırında 4,64 rad) inerken |<i>t</i>|² = sin²(Δφ/2) "
            "Δφ = π noktasında tepe yapar. Denklem (6), ticari TN mSLA paneller için analitik vekildir [18] ve kurulumda kalibrasyon ister. Δ<i>x</i> = 47 μm "
            "için <i>N</i><sub>crit</sub> ≈ 12,0 piksel (>10× marj) ve 0,283 mm yayılma, 1,69 ve 0,75 mm koruma bantlarının (<i>N</i> = 256'da 2,73 ve 1,50 mm) "
            "içindedir. PAT FFT yolları <code>complex64</code>, PAT-dışı tarama ve değerlendirme yolları ise <code>complex128</code> duyarlık kullanır.",
            st["body_noindent"]
        ))

    # Page 3: Fig 2 banner + III.B + III.C + Table I + start of IV.A
    story.append(NextPageTemplate("P_TOPFIG"))
    story.append(PageBreak())
    fig2_cap = (
        "<b>Fig. 2.</b> Passive-matrix multiplexing limit: <b>(a)</b> ECB retardation Δφ(<i>V</i><sub>rms</sub>) (blue) and non-monotonic crossed-polarizer "
        "intensity |<i>t</i>(<i>V</i>)|² = sin²(Δφ/2) peaking at Δφ = π near 1.84 V (dashed vermilion); red shading shows [1.00 V, 1.291 V] (0.921 rad) "
        "vs. 4.64 rad active PAT window over [1.05, 4.95] V (4.86 rad over [1.00, 5.00] V, green). <b>(b)</b> Alt–Pleshko ratio vs. row count <i>N</i>."
        if lang == "en" else
        "<b>Şekil 2.</b> Pasif matris çoğullama sınırı: <b>(a)</b> ECB faz gecikmesi Δφ(<i>V</i><sub>rms</sub>) (mavi) ve 1,84 V'ta Δφ = π "
        "tepesi yapan |<i>t</i>(<i>V</i>)|² = sin²(Δφ/2) eğrisi (kesikli turuncu); kırmızı alan 0,921 rad pasif bandı, yeşil alan [1,05, 4,95] V'ta "
        "4,64 rad aktif PAT bandını ([1,00, 5,00] V'ta 4,86 rad) gösterir. <b>(b)</b> Satır sayısı <i>N</i> ile Alt–Pleshko seçme oranı düşüşü."
    )
    story.append(fig_block(os.path.join(fig_dir, f"makale_fig2_alt_pleshko_{lang}.png"), fig2_cap, st, 176, max_img_h_mm=46.5))
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    if lang == "en":
        story.append(Paragraph("B. Analytical Wirtinger Adjoint Backpropagation", st["h3"]))
        story.append(Paragraph(
            "To differentiate loss <i>L</i> with respect to control voltages <b>V</b>, the complex Wirtinger error field at the sensor plane (<i>I</i> = |<i>E</i><sub>2</sub>|²) is:",
            st["body_noindent"]
        ))
        story.append(eq_block("G<sub>cam</sub> = 2(∂L/∂I) · E<sub>2</sub>", "(7)", st, col_w))
        story.append(Paragraph(
            "Under real inner product (<i>u, v</i>) = Re ∑ <i>u</i><sup>*</sup><i>v</i>, the exact Hermitian adjoint of ASM is backward propagation by −<i>Z</i><sub>2</sub>:",
            st["body_noindent"]
        ))
        story.append(eq_block("G<sub>mask</sub> = P<sub>Z2</sub><sup>†</sup>{G<sub>cam</sub>} = F<sup>−1</sup>{ F{G<sub>cam</sub>} · H<sup>*</sup>(f<sub>x</sub>, f<sub>y</sub>; Z<sub>2</sub>) }", "(8)", st, col_w))
        story.append(Paragraph(
            "Integrating <i>G<sub>t,ij</sub></i> = ∑<sub>(u,v) in Ω<sub>ij</sub></sub> <i>E</i><sub>1</sub><sup>*</sup><i>G</i><sub>mask</sub> over macro-pixel "
            "Ω<sub><i>ij</i></sub> and applying <i>dt</i>/<i>d</i>φ = (1/2)<i>e<sup>iφ</sup></i> gives the exact voltage gradient in one FFT pair:",
            st["body_noindent"]
        ))
        story.append(eq_block("∂L / ∂V<sub>ij</sub> = Re{ G<sub>t,ij</sub><sup>*</sup> · (1/2)exp(iΔφ(V<sub>ij</sub>)) } · (dΔφ/dV)|<sub>Vij</sub>", "(9)", st, col_w))
        story.append(Paragraph(
            "Against central finite differences (ε = 10<sup>−6</sup>), Eq. (9) achieves 5.52×10<sup>−7</sup> relative <i>L</i><sub>2</sub> error "
            "(active) and 7.46×10<sup>−7</sup> (passive Alt–Pleshko chain rule, Fig. 3b).",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. Physics-Aware Training and Dark-Frame Stabilization", st["h3"]))
        story.append(Paragraph(
            "Our PAT loop [15] takes forward activations from a perturbed physical plant simulator and backpropagates through Eqs. (7)–(9) of the "
            "nominal surrogate twin (retaining SPSA [19] fallback). To prevent near-zero-variance peripheral pixels from blowing up under ambient light, "
            "16-frame noisy dark subtraction is paired with a strictly training-only standard-deviation floor:",
            st["body_noindent"]
        ))
        story.append(eq_block("f̃ = ( (f<sub>on</sub> − f<sub>dark</sub>) − μ<sub>tr</sub> ) / max(σ<sub>tr</sub>, 0.05·mean(σ<sub>tr</sub>))", "(10)", st, col_w))
        t1_rows = [
            [Paragraph("<b>Parameter</b>", st["cell_b"]), Paragraph("<b>Value / Specification</b>", st["cell_b"])],
            [Paragraph("Wavelength λ / Pitch Δ<i>x</i>", st["cell"]), Paragraph("532 nm / 47 μm", st["cell"])],
            [Paragraph("Spacings <i>Z</i><sub>1</sub>, <i>Z</i><sub>2</sub>", st["cell"]), Paragraph("50 mm, 50 mm (10 cm path, 0.33 ns)", st["cell"])],
            [Paragraph("Grids <i>N</i> / Walk-off", st["cell"]), Paragraph("128² (6.02 mm), 256² (12.03 mm) / 0.283 mm", st["cell"])],
            [Paragraph("Guard bands (<i>N</i>=128)", st["cell"]), Paragraph("1.69 mm (input), 0.75 mm (weight)", st["cell"])],
            [Paragraph("Drive bounds", st["cell"]), Paragraph("[1.05, 4.95] V (4.64 rad) / [−1, +1] (0.921 rad)", st["cell"])],
            [Paragraph("Optimizer", st["cell"]), Paragraph("Adam (lr<sub>opt</sub>=0.07–0.10; lr<sub>head</sub>=2.5e-2 / 2.5e-3)", st["cell"])],
            [Paragraph("Reg. / Schedule", st["cell"]), Paragraph("1e-4 L2; 16–22 ep. (PAT), 40–45 ep. (MLP); early stop", st["cell"])],
            [Paragraph("Perturbed faults", st["cell"]), Paragraph("47 μm LCD/CMOS, +1.2/−0.8 mm Z, 29 °C, 2% drift", st["cell"])],
            [Paragraph("Seeds / Test count", st["cell"]), Paragraph("{7, 19, 42} / <i>N</i><sub>test</sub>=1000 per split", st["cell"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLE I — SIMULATION SETUP & HYPERPARAMETERS", st["tab_cap"]),
            styled_table(t1_rows, [col_w * 0.36, col_w * 0.64]),
            Spacer(1, 1.2 * mm),
        ]))
        story.append(Paragraph("IV. NUMERICAL RESULTS AND ANALYSIS", st["h2"]))
        story.append(Paragraph("A. Controlled 8×8 Detector Ablation on MNIST", st["h3"]))
        story.append(Paragraph(
            "All runs executed in Python 3.11.9 / NumPy 2.2.3 on CPU (Intel64 Family 6 Model 170) using <code>complex64</code> PAT propagation and "
            "<code>complex128</code> evaluation (Table I). Across 3 MNIST [20] seeds (<i>N</i><sub>fit</sub>=2640, <i>N</i><sub>val</sub>=360, <i>N</i><sub>test</sub>=1000) "
            "on an 8×8 grid, the plant injected 47 μm lateral shifts, +1.2/−0.8 mm axial offsets, 29 °C Haller drift [21], [22], 2% laser drift, and noise (Table II, Fig. 3a).",
            st["body_noindent"]
        ))
    else:
        story.append(Paragraph("B. Wirtinger Kalkülüsü ile Analitik Eşlenik Geri Yayılım", st["h3"]))
        story.append(Paragraph(
            "Skaler kayıp <i>L</i>'nin <b>V</b> gerilimlerine göre türevini almak için sensör düzlemindeki karmaşık Wirtinger hata alanı (<i>I</i> = |<i>E</i><sub>2</sub>|²):",
            st["body_noindent"]
        ))
        story.append(eq_block("G<sub>cam</sub> = 2(∂L/∂I) · E<sub>2</sub>", "(7)", st, col_w))
        story.append(Paragraph(
            "Gerçel iç çarpım (<i>u, v</i>) = Re ∑ <i>u</i><sup>*</sup><i>v</i> altında ASM operatörünün Hermitik eşleniği −<i>Z</i><sub>2</sub> yönünde geri yayılımdır:",
            st["body_noindent"]
        ))
        story.append(eq_block("G<sub>mask</sub> = P<sub>Z2</sub><sup>†</sup>{G<sub>cam</sub>} = F<sup>−1</sup>{ F{G<sub>cam</sub>} · H<sup>*</sup>(f<sub>x</sub>, f<sub>y</sub>; Z<sub>2</sub>) }", "(8)", st, col_w))
        story.append(Paragraph(
            "Elektrot makro-pikseli Ω<sub><i>ij</i></sub> üzerinde <i>G<sub>t,ij</sub></i> = ∑ <i>E</i><sub>1</sub><sup>*</sup><i>G</i><sub>mask</sub> toplanıp "
            "<i>dt</i>/<i>d</i>φ = (1/2)<i>e<sup>iφ</sup></i> konduğunda tek FFT çiftiyle tam voltaj gradyanı elde edilir:",
            st["body_noindent"]
        ))
        story.append(eq_block("∂L / ∂V<sub>ij</sub> = Re{ G<sub>t,ij</sub><sup>*</sup> · (1/2)exp(iΔφ(V<sub>ij</sub>)) } · (dΔφ/dV)|<sub>Vij</sub>", "(9)", st, col_w))
        story.append(Paragraph(
            "Merkezi sonlu farklara (ε = 10<sup>−6</sup>) karşı (9) aktif modda 5,52×10<sup>−7</sup>, pasif modda 7,46×10<sup>−7</sup> bağıl <i>L</i><sub>2</sub> hatası verir (Şekil 3b).",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. Fizik-Farkındalıklı Eğitim ve Karanlık-Kare Stabilizasyonu", st["h3"]))
        story.append(Paragraph(
            "PAT döngüsü [15] ileri geçişi kusurlu fiziksel simülatörden alırken geri yayılımı nominal ikizin (7)–(9) denklemleriyle (SPSA [19] yedekli) "
            "yürütür. Ortam ışığı altında sıfıra yakın varyanslı piksellerin şişmesini önlemek için 16 kareli karanlık arka plan çıkarma ve yalnızca eğitim tabanlı taban uygulanır:",
            st["body_noindent"]
        ))
        story.append(eq_block("f̃ = ( (f<sub>açık</sub> − f<sub>karanlık</sub>) − μ<sub>tr</sub> ) / max(σ<sub>tr</sub>, 0,05·mean(σ<sub>tr</sub>))", "(10)", st, col_w))
        t1_rows = [
            [Paragraph("<b>Parametre</b>", st["cell_b"]), Paragraph("<b>Değer / Şartname</b>", st["cell_b"])],
            [Paragraph("Dalga boyu λ / Adım Δ<i>x</i>", st["cell"]), Paragraph("532 nm / 47 μm", st["cell"])],
            [Paragraph("Mesafeler <i>Z</i><sub>1</sub>, <i>Z</i><sub>2</sub>", st["cell"]), Paragraph("50 mm, 50 mm (10 cm yol, 0,33 ns)", st["cell"])],
            [Paragraph("Izgaralar <i>N</i> / Yayılma", st["cell"]), Paragraph("128² (6,02 mm), 256² (12,03 mm) / 0,283 mm", st["cell"])],
            [Paragraph("Koruma bantları (<i>N</i>=128)", st["cell"]), Paragraph("1,69 mm (giriş), 0,75 mm (ağırlık)", st["cell"])],
            [Paragraph("Sürüş sınırları", st["cell"]), Paragraph("[1,05, 4,95] V (4,64 rad) / [−1, +1] (0,921 rad)", st["cell"])],
            [Paragraph("Eniyileyici", st["cell"]), Paragraph("Adam (lr<sub>opt</sub>=0,07–0,10; lr<sub>head</sub>=2,5e-2 / 2,5e-3)", st["cell"])],
            [Paragraph("Düzenlileme / Takvim", st["cell"]), Paragraph("1e-4 L2; 16–22 ep. (PAT), 40–45 ep. (MLP); erken durdurma", st["cell"])],
            [Paragraph("Kusurlu sistem hataları", st["cell"]), Paragraph("47 μm LCD/CMOS, +1,2/−0,8 mm Z, 29 °C, %2 drift", st["cell"])],
            [Paragraph("Tohumlar / Test örneği", st["cell"]), Paragraph("{7, 19, 42} / bölme başına <i>N</i><sub>test</sub>=1000", st["cell"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLO I — SİMÜLASYON DÜZENEĞİ VE HİPERPARAMETRELER", st["tab_cap"]),
            styled_table(t1_rows, [col_w * 0.36, col_w * 0.64]),
            Spacer(1, 1.2 * mm),
        ]))
        story.append(Paragraph("IV. SAYISAL BULGULAR VE ANALİZ", st["h2"]))
        story.append(Paragraph("A. Kontrollü 8×8 Dedektör MNIST Ablasyonu", st["h3"]))
        story.append(Paragraph(
            "Deneyler Python 3.11.9 / NumPy 2.2.3 ortamında CPU'da (Intel64 Family 6 Model 170) PAT yollarında <code>complex64</code>, değerlendirmede "
            "<code>complex128</code> ile çalıştırıldı (Tablo I). MNIST [20] 3 tohumda (<i>N</i><sub>fit</sub>=2640, <i>N</i><sub>val</sub>=360, "
            "<i>N</i><sub>test</sub>=1000) 47 μm kayma, +1,2/−0,8 mm hata, 29 °C Haller drifti [21], [22], %2 lazer drifti ve gürültü uygulandı (Tablo II, Şekil 3a).",
            st["body_noindent"]
        ))

    # Page 4: Fig 3 banner + Table II + IV.B + Table III + start of IV.C
    story.append(NextPageTemplate("P_TOPFIG"))
    story.append(PageBreak())
    fig3_cap = (
        "<b>Fig. 3.</b> <b>(a)</b> 3-seed MNIST test accuracy (mean ± 1 SD, <i>N</i><sub>test</sub> = 1000) across 11 matched configurations "
        "(8×8 detector, perturbed plant): PAT 32×32 linear (+7.33 pts over random) vs. digital area pooling (87.00%). "
        "<b>(b)</b> Analytical Wirtinger adjoint vs. central finite differences (ε = 10<sup>−6</sup>)."
        if lang == "en" else
        "<b>Şekil 3.</b> <b>(a)</b> Kusurlu sistemde 8×8 dedektörde 11 eşleşmiş yapılandırmada 3 tohumlu MNIST doğruluğu "
        "(ort. ± 1 SS, <i>N</i><sub>test</sub> = 1000). <b>(b)</b> Analitik Wirtinger eşlenik gradyanının merkezi sonlu farklarla (ε = 10<sup>−6</sup>) doğrulaması."
    )
    story.append(fig_block(os.path.join(fig_dir, f"makale_fig3_ablasyon_pat_{lang}.png"), fig3_cap, st, 178, max_img_h_mm=49.0))
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    if lang == "en":
        t2_rows = [
            [Paragraph("<b>#</b>", st["cell_b"]), Paragraph("<b>Architecture</b>", st["cell_b"]), Paragraph("<b>Opt.W</b>", st["cell_br"]), Paragraph("<b>Dig.W</b>", st["cell_br"]), Paragraph("<b>Test (%)</b>", st["cell_br"])],
            [Paragraph("1", st["cell"]), Paragraph("Digital Area (8×8) + Lin.", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("87.00±1.47", st["cell_r"])],
            [Paragraph("2", st["cell"]), Paragraph("Digital PCA (64) + Lin.", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650ᵃ", st["cell_r"]), Paragraph("87.73±1.23", st["cell_r"])],
            [Paragraph("3", st["cell"]), Paragraph("Free-Space (No LC)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("75.53±1.63", st["cell_r"])],
            [Paragraph("4", st["cell"]), Paragraph("Passive 16×16 Rand.", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("70.93±1.39", st["cell_r"])],
            [Paragraph("5", st["cell"]), Paragraph("Active 16×16 Rand.", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("70.47±2.51", st["cell_r"])],
            [Paragraph("6", st["cell"]), Paragraph("Active 32×32 Rand.", st["cell"]), Paragraph("1,024", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("71.07±1.55", st["cell_r"])],
            [Paragraph("7", st["cell"]), Paragraph("Passive 16×16 PAT", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("72.43±2.93", st["cell_r"])],
            [Paragraph("8", st["cell"]), Paragraph("Active 16×16 PAT", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("74.10±2.08", st["cell_r"])],
            [Paragraph("<b>9</b>", st["cell_b"]), Paragraph("<b>Active 32×32 PAT Lin.</b>", st["cell_b"]), Paragraph("<b>1,024</b>", st["cell_br"]), Paragraph("<b>650</b>", st["cell_br"]), Paragraph("<b>78.40±2.31</b>", st["cell_br"])],
            [Paragraph("10", st["cell"]), Paragraph("Digital Area + MLP", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("19,210", st["cell_r"]), Paragraph("91.60±1.25", st["cell_r"])],
            [Paragraph("<b>11</b>", st["cell_b"]), Paragraph("<b>Active 32×32 PAT MLP</b>", st["cell_b"]), Paragraph("<b>1,024</b>", st["cell_br"]), Paragraph("<b>19,210</b>", st["cell_br"]), Paragraph("<b>86.13±0.74</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLE II — CONTROLLED MNIST ABLATION (8×8, 3 SEEDS)", st["tab_cap"]),
            styled_table(t2_rows, [col_w*0.07, col_w*0.43, col_w*0.14, col_w*0.15, col_w*0.21], highlight_rows=[9, 11]),
            Paragraph("ᵃExcludes 784×64 training-only PCA basis matrix.", st["tab_note"]),
        ]))
        story.append(Paragraph(
            "PAT raises 32×32 linear accuracy by +7.33 points over matched random optics (71.07% → 78.40%), whereas passive (72.43±2.93%) and active (74.10±2.08%) "
            "16×16 PAT are statistically equivalent within 1 SD on rank-bottlenecked 8×8 readout. Single-layer positive intensity optics trails digital 8×8 area pooling "
            "(87.00%), unconstrained PCA-64 linear ceiling (87.73±1.23%), and digital area MLP (91.60% vs. 86.13%).",
            st["body"]
        ))
        story.append(Paragraph("B. Full-Scale 32×32 Hybrid Classification on MNIST and Fashion-MNIST", st["h3"]))
        t3_rows = [
            [Paragraph("<b>Configuration</b>", st["cell_b"]), Paragraph("<b>Opt.W</b>", st["cell_br"]), Paragraph("<b>Dig.W</b>", st["cell_br"]), Paragraph("<b>MNIST</b>", st["cell_br"]), Paragraph("<b>F-MNIST</b>", st["cell_br"])],
            [Paragraph("Raw 28×28 Ridge (6k)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("7,850", st["cell_r"]), Paragraph("85.43±1.36", st["cell_r"]), Paragraph("80.57±0.95", st["cell_r"])],
            [Paragraph("Opt 16×16 256f Ridge", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("2,570", st["cell_r"]), Paragraph("81.90±1.08", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 16×16 1024f Ridge", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("10,250", st["cell_r"]), Paragraph("84.13±1.22", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 32×32 Rand. 1024f Ridge", st["cell"]), Paragraph("1,024", st["cell_r"]), Paragraph("10,250", st["cell_r"]), Paragraph("85.97±2.05", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 32×32 PAT 1024f Ridge", st["cell"]), Paragraph("1,024", st["cell_r"]), Paragraph("10,250", st["cell_r"]), Paragraph("—", st["cell_r"]), Paragraph("79.80±1.93", st["cell_r"])],
            [Paragraph("Raw 28×28 MLP (6k)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("203.5K", st["cell_r"]), Paragraph("93.93±0.99", st["cell_r"]), Paragraph("85.17±0.15", st["cell_r"])],
            [Paragraph("32×32 Rand + MLP", st["cell"]), Paragraph("1,024", st["cell_r"]), Paragraph("265.0K", st["cell_r"]), Paragraph("94.20±0.95", st["cell_r"]), Paragraph("84.70±0.85", st["cell_r"])],
            [Paragraph("32×32 PAT Pert. MLP", st["cell"]), Paragraph("1,024", st["cell_r"]), Paragraph("265.0K", st["cell_r"]), Paragraph("91.07±1.90", st["cell_r"]), Paragraph("81.47±1.27", st["cell_r"])],
            [Paragraph("<b>32×32 PAT Nom. MLP</b>", st["cell_b"]), Paragraph("<b>1,024</b>", st["cell_br"]), Paragraph("<b>265.0K</b>", st["cell_br"]), Paragraph("<b>94.67±0.55</b>", st["cell_br"]), Paragraph("<b>84.43±0.51</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLE III — FULL-SCALE 32×32 HYBRID & DIGITAL BASELINES", st["tab_cap"]),
            styled_table(t3_rows, [col_w*0.36, col_w*0.13, col_w*0.15, col_w*0.18, col_w*0.18], highlight_rows=[9]),
            Spacer(1, 0.9 * mm),
        ]))
        story.append(Paragraph(
            "Across MNIST [20] and Fashion-MNIST [23] (Table III), random 32×32 optical Ridge is statistically equivalent to raw MNIST pixels (85.97% vs. 85.43%) while "
            "PAT Ridge trails raw pixels at the margin on Fashion-MNIST (79.80±1.93% vs. 80.57±0.95%). Attaching the 265K-parameter MLP lets digital capacity dominate "
            "within ~0.5 points across nominal PAT (94.67% / 84.43%), random optics (94.20% / 84.70%), and raw pixels (93.93% / 85.17%). Under 8×8 Fashion-MNIST (Fig. 5c), "
            "PAT linear beats matched random optics by +4.76 points (71.63% vs. 66.87%; 77.50% MLP vs. 77.93% linear / 81.43% MLP digital pooling).",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. Mechanical Alignment, Thermal Drift, and Ambient Light Resilience", st["h3"]))
        story.append(Paragraph(
            "Without an external reference arm, axial intensity tolerance scales with Talbot length <i>z<sub>T</sub></i> = 2Δ<i>x</i>²/λ ≈ 8.3 mm. "
            "On 1,000 test digits (seed 7, base 94.7%, Fig. 4a), LC weight shifts up to 188 μm drop accuracy by only 0.2 points (94.5%), whereas "
            "input LCD and CMOS shifts fall past 47 μm (93.7% → 68.3%/68.7% at 188 μm). Axial shifts 0 ≤ Δ<i>Z</i><sub>1</sub> ≤ 8 mm hold 94.3%–94.7%, "
            "while combined 47 μm + 1 mm yields 88.4% (nominal head) and 88.9% (perturbed-trained head from 89.0%).",
            st["body_noindent"]
        ))
    else:
        t2_rows = [
            [Paragraph("<b>#</b>", st["cell_b"]), Paragraph("<b>Mimari</b>", st["cell_b"]), Paragraph("<b>Opt.W</b>", st["cell_br"]), Paragraph("<b>Dij.W</b>", st["cell_br"]), Paragraph("<b>Test (%)</b>", st["cell_br"])],
            [Paragraph("1", st["cell"]), Paragraph("Dijital Alan (8×8) + Lin.", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("87,00±1,47", st["cell_r"])],
            [Paragraph("2", st["cell"]), Paragraph("Dijital PCA (64) + Lin.", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650ᵃ", st["cell_r"]), Paragraph("87,73±1,23", st["cell_r"])],
            [Paragraph("3", st["cell"]), Paragraph("Serbest Uzay (LC Yok)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("75,53±1,63", st["cell_r"])],
            [Paragraph("4", st["cell"]), Paragraph("Pasif 16×16 Rast.", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("70,93±1,39", st["cell_r"])],
            [Paragraph("5", st["cell"]), Paragraph("Aktif 16×16 Rast.", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("70,47±2,51", st["cell_r"])],
            [Paragraph("6", st["cell"]), Paragraph("Aktif 32×32 Rast.", st["cell"]), Paragraph("1.024", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("71,07±1,55", st["cell_r"])],
            [Paragraph("7", st["cell"]), Paragraph("Pasif 16×16 PAT", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("72,43±2,93", st["cell_r"])],
            [Paragraph("8", st["cell"]), Paragraph("Aktif 16×16 PAT", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("650", st["cell_r"]), Paragraph("74,10±2,08", st["cell_r"])],
            [Paragraph("<b>9</b>", st["cell_b"]), Paragraph("<b>Aktif 32×32 PAT Lin.</b>", st["cell_b"]), Paragraph("<b>1.024</b>", st["cell_br"]), Paragraph("<b>650</b>", st["cell_br"]), Paragraph("<b>78,40±2,31</b>", st["cell_br"])],
            [Paragraph("10", st["cell"]), Paragraph("Dijital Alan + MLP", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("19.210", st["cell_r"]), Paragraph("91,60±1,25", st["cell_r"])],
            [Paragraph("<b>11</b>", st["cell_b"]), Paragraph("<b>Aktif 32×32 PAT MLP</b>", st["cell_b"]), Paragraph("<b>1.024</b>", st["cell_br"]), Paragraph("<b>19.210</b>", st["cell_br"]), Paragraph("<b>86,13±0,74</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLO II — KONTROLLÜ MNIST ABLASYONU (8×8, 3 TOHUM)", st["tab_cap"]),
            styled_table(t2_rows, [col_w*0.07, col_w*0.43, col_w*0.14, col_w*0.15, col_w*0.21], highlight_rows=[9, 11]),
            Paragraph("ᵃEğitim kümesinden kurulan 784×64 PCA matrisi hariç.", st["tab_note"]),
        ]))
        story.append(Paragraph(
            "PAT, 32×32 lineer doğruluğu eşleşmiş rastgele optiğe göre +7,33 puan (%71,07 → %78,40) artırırken pasif (%72,43±2,93) ve aktif (%74,10±2,08) "
            "16×16 PAT, 8×8 sıra darboğazında 1 SS içinde istatistiksel olarak eşdeğerdir. Tek katmanlı optik, 8×8 dijital alan havuzlama (%87,00), "
            "dijital PCA-64 tavanı (%87,73±1,23) ve dijital MLP (%91,60 vs %86,13) gerisinde kalır.",
            st["body"]
        ))
        story.append(Paragraph("B. MNIST ve Fashion-MNIST Üzerinde Tam 32×32 Hibrit Sınıflandırma", st["h3"]))
        t3_rows = [
            [Paragraph("<b>Yapılandırma</b>", st["cell_b"]), Paragraph("<b>Opt.W</b>", st["cell_br"]), Paragraph("<b>Dij.W</b>", st["cell_br"]), Paragraph("<b>MNIST</b>", st["cell_br"]), Paragraph("<b>F-MNIST</b>", st["cell_br"])],
            [Paragraph("Ham 28×28 Ridge (6k)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("7.850", st["cell_r"]), Paragraph("85,43±1,36", st["cell_r"]), Paragraph("80,57±0,95", st["cell_r"])],
            [Paragraph("Opt 16×16 256öz Ridge", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("2.570", st["cell_r"]), Paragraph("81,90±1,08", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 16×16 1024öz Ridge", st["cell"]), Paragraph("256", st["cell_r"]), Paragraph("10.250", st["cell_r"]), Paragraph("84,13±1,22", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 32×32 Rast. 1024öz Ridge", st["cell"]), Paragraph("1.024", st["cell_r"]), Paragraph("10.250", st["cell_r"]), Paragraph("85,97±2,05", st["cell_r"]), Paragraph("—", st["cell_r"])],
            [Paragraph("Opt 32×32 PAT 1024öz Ridge", st["cell"]), Paragraph("1.024", st["cell_r"]), Paragraph("10.250", st["cell_r"]), Paragraph("—", st["cell_r"]), Paragraph("79,80±1,93", st["cell_r"])],
            [Paragraph("Ham 28×28 MLP (6k)", st["cell"]), Paragraph("0", st["cell_r"]), Paragraph("203.5K", st["cell_r"]), Paragraph("93,93±0,99", st["cell_r"]), Paragraph("85,17±0,15", st["cell_r"])],
            [Paragraph("32×32 Rast + MLP", st["cell"]), Paragraph("1.024", st["cell_r"]), Paragraph("265.0K", st["cell_r"]), Paragraph("94,20±0,95", st["cell_r"]), Paragraph("84,70±0,85", st["cell_r"])],
            [Paragraph("32×32 PAT Kusurlu MLP", st["cell"]), Paragraph("1.024", st["cell_r"]), Paragraph("265.0K", st["cell_r"]), Paragraph("91,07±1,90", st["cell_r"]), Paragraph("81,47±1,27", st["cell_r"])],
            [Paragraph("<b>32×32 PAT Nominal MLP</b>", st["cell_b"]), Paragraph("<b>1.024</b>", st["cell_br"]), Paragraph("<b>265.0K</b>", st["cell_br"]), Paragraph("<b>94,67±0,55</b>", st["cell_br"]), Paragraph("<b>84,43±0,51</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLO III — TAM ÖLÇEKLİ 32×32 HİBRİT VE DİJİTAL KIYAS", st["tab_cap"]),
            styled_table(t3_rows, [col_w*0.36, col_w*0.13, col_w*0.15, col_w*0.18, col_w*0.18], highlight_rows=[9]),
            Spacer(1, 0.9 * mm),
        ]))
        story.append(Paragraph(
            "MNIST [20] ve Fashion-MNIST [23] genelinde (Tablo III) sabit rastgele 32×32 optik Ridge MNIST'te ham Ridge ile 1 SS içinde eşdeğerdir (%85,97 vs %85,43), "
            "PAT Ridge Fashion-MNIST'te ham piksellerin sınırda gerisindedir (%79,80±1,93 vs %80,57±0,95). 265K MLP eklendiğinde elektronik kapasite baskın çıkarak "
            "nominal PAT (%94,67/%84,43), rastgele optik (%94,20/%84,70) ve ham piksel (%93,93/%85,17) ~0,5 puan içine toplanır. 8×8 Fashion-MNIST'te ise (Şekil 5c) "
            "PAT lineer eşleşmiş rastgele optiği +4,76 puan geçer (%71,63 vs %66,87; MLP %77,50 vs %77,93 lineer / %81,43 MLP dijital havuzlama).",
            st["body_noindent"]
        ))
        story.append(Paragraph("C. Mekanik Hizalama, Sıcaklık Kayması ve Ortam Işığı Dayanımı", st["h3"]))
        story.append(Paragraph(
            "Harici referans kolsuz ortak-yol optik düzlemde eksenel tolerans Talbot uzunluğu <i>z<sub>T</sub></i> = 2Δ<i>x</i>²/λ ≈ 8,3 mm ile ölçeklenir. "
            "1.000 test örneğinde (tohum 7, baz %94,7, Şekil 4a), 188 μm LC ağırlık kayması yalnızca 0,2 puan kayıp yaratırken (%94,5), giriş LCD ve CMOS "
            "kaymaları 47 μm (%93,7) sonrası %68,3/%68,7'ye iner. 0 ≤ Δ<i>Z</i><sub>1</sub> ≤ 8 mm eksenel sapmalar %94,3–%94,7 aralığında kalır; "
            "kombine 47 μm + 1 mm nominal kafada %88,4, pertürbe kafada ise %88,9 (baz %89,0; −0,1 puan) verir.",
            st["body_noindent"]
        ))

    # Page 5: Fig 4 banner + IV.C (Haller+stray) + IV.D + Table IV + start of Section V
    story.append(NextPageTemplate("P_TOPFIG"))
    story.append(PageBreak())
    fig4_cap = (
        "<b>Fig. 4.</b> Mechanical and environmental tests (<i>N</i><sub>test</sub> = 1000, seed 7): <b>(a)</b> lateral shifts of LC weight cell "
        "(94.7% → 94.5% at 188 μm), input LCD (→ 68.3%), CMOS (→ 68.7%), and combined 47 μm + 1 mm (88.4% nom.; 88.9% pert. from 89.0% base). "
        "<b>(b)</b> Stray ambient light raw vs. 16-frame dark subtraction + training floor and 30 °C+1%+2% recovery (64.4% → 95.0%). "
        "<b>(c)</b> Uncalibrated Haller thermal sweep (20–55 °C, <i>T<sub>c</sub></i> = 59 °C)."
        if lang == "en" else
        "<b>Şekil 4.</b> Mekanik ve çevresel testler (<i>N</i><sub>test</sub> = 1000, tohum 7): <b>(a)</b> LC ağırlık (%94,7 → %94,5, 188 μm), "
        "giriş LCD (→ %68,3), CMOS (→ %68,7) kaymaları ve kombine 47 μm + 1 mm (%88,4 nom.; %88,9 kusurlu, baz %89,0). "
        "<b>(b)</b> Ortam ışığı ham çöküşe karşı 16 kareli karanlık çıkarma ve 30 °C+%1+%2 iyileşmesi (%64,4 → %95,0). "
        "<b>(c)</b> Kalibrasyonsuz E7 Haller sıcaklık taraması (20–55 °C, <i>T<sub>c</sub></i> = 59 °C)."
    )
    story.append(fig_block(os.path.join(fig_dir, f"makale_fig4_dayanim_{lang}.png"), fig4_cap, st, 178, max_img_h_mm=43.0))
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    if lang == "en":
        story.append(Paragraph("Under Haller thermal scaling [21], [22]:", st["body_noindent"]))
        story.append(eq_block("Δn(T) / Δn(25 °C) = [ (T<sub>c</sub> − T) / (T<sub>c</sub> − 25) ]<sup>β</sup>,   T<sub>c</sub> = 59 °C,  β = 0.22", "(11)", st, col_w))
        story.append(Paragraph(
            "uncalibrated accuracy holds 94.4%–94.7% over 20–45 °C and 92.3% at 55 °C (Fig. 4c). Raw stray light drops to 64.1% (1%) and 9.8% (5%), "
            "whereas 16-frame dark subtraction + Eq. (10) holds 94.4% (1%), 93.7% (5%), 88.2% (20%), and 78.2% (50%), recovering combined "
            "30 °C + 1% leak + 2% drift from 64.4% to 95.0%. ±10% laser power stays in 94.2%–94.9%.",
            st["body_noindent"]
        ))
        story.append(Paragraph("D. Bit Quantization, Aperture Proxy, and Wavefront Aberrations", st["h3"]))
        story.append(Paragraph(
            "8-bit HDMI input + <i>b</i>-bit weight quantization (seed 7, Fig. 5a) holds 94.6%–94.9% down to 4 bits and slips to 92.7% at 2 bits. "
            "On the <i>N</i> = 256 sub-aperture proxy at 25% fill, uncalibrated and head-recalibrated both score 91.3% (from 92.3%). Across Zernike "
            "aberrations (0–15λ PV) + 3<i>Z</i><sub>1</sub> 0.04 ghost under matched CE Adam heads (Fig. 5b), head-only recalibration recovers 1λ–10λ "
            "losses (78.63%–77.53% vs. PAT 78.50%–76.70%), and at 15λ uncompensated 65.27 ± 7.67% rises to 76.67 ± 1.15% (head) and 77.30 ± 1.82% "
            "(PAT, +0.63 pts within one combined SD). Under structural mismatch (±10% perturbed LC curve, camera gamma 0.90, speckle), "
            "uncompensated 71.30 ± 1.08% improves to 79.13 ± 2.39% with head recalibration vs. 76.80 ± 1.65% for PAT.",
            st["body_noindent"]
        ))
        bom_rows = [
            [Paragraph("<b>Subsystem</b>", st["cell_b"]), Paragraph("<b>Selected Hardware</b>", st["cell_b"]), Paragraph("<b>USD</b>", st["cell_br"])],
            [Paragraph("Optical Input", st["cell"]), Paragraph("532nm DPSS (100mW) + Expander + mSLA LCD", st["cell"]), Paragraph("150", st["cell_r"])],
            [Paragraph("Active Weights", st["cell"]), Paragraph("2nd mSLA TFT-LCD (or ITO + AC-PWM)", st["cell"]), Paragraph("90–230", st["cell_r"])],
            [Paragraph("Readout & Host", st["cell"]), Paragraph("RPi Cam 3 (IMX708, 12MP) + M12 + RPi 5", st["cell"]), Paragraph("125", st["cell_r"])],
            [Paragraph("Optomechanics", st["cell"]), Paragraph("Optical Rail, Mounts, Dark Box, Filter", st["cell"]), Paragraph("262", st["cell_r"])],
            [Paragraph("Subtotal", st["cell"]), Paragraph("Core optical and electronic parts", st["cell"]), Paragraph("627–767", st["cell_r"])],
            [Paragraph("<b>Total (+25%)</b>", st["cell_b"]), Paragraph("<b>Prototype w/ contingency</b>", st["cell_b"]), Paragraph("<b>784–959</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLE IV — ESTIMATED PROTOTYPE BILL OF MATERIALS", st["tab_cap"]),
            styled_table(bom_rows, [col_w*0.28, col_w*0.54, col_w*0.18], highlight_rows=[6]),
            Spacer(1, 1.2 * mm),
        ]))
        story.append(Paragraph("V. DISCUSSION, LIMITATIONS, & HARDWARE ROADMAP", st["h2"]))
        story.append(Paragraph(
            "Direct prototype components in Table IV total $627–$767 ($784–$959 with 25% contingency). Three timescales must be kept distinct: "
            "coherent wave transit across 10 cm takes ~0.33 ns; physical throughput is gated by 60 Hz LCD/camera frame intervals (~16.7 ms) during "
            "inference and ~50 ms nematic settling during weight updates; and our uncompiled NumPy CPU ASM simulator runs in 1.04 ms median per digit "
            "(<i>N</i> = 128², Intel64 Family 6 Model 170 CPU, Python 3.11.9 / NumPy 2.2.3, mean 1.27 ms, IQR 0.63 ms, range 0.84–2.23 ms over 50 runs).",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Benchtop realization requires three practical precautions: RPi Cam 3 (IMX708, 6.45 × 3.63 mm) needs a ~1.6× demagnifying M12 relay onto its "
            "3.63 mm minor axis; the 100 mW 532 nm Class 3B DPSS laser demands OD 4+ eyewear, a matte enclosure, and an IR-cut filter against 808/1064 nm "
            "pump leakage; and unipolar PCA9685 PWM boards require AC polarity-inversion buffering before bare ITO electrodes to prevent DC electrolysis.",
            st["body"]
        ))
    else:
        story.append(Paragraph("Haller bağıntısıyla [21], [22] modellenen termal kaymada:", st["body_noindent"]))
        story.append(eq_block("Δn(T) / Δn(25 °C) = [ (T<sub>c</sub> − T) / (T<sub>c</sub> − 25) ]<sup>β</sup>,   T<sub>c</sub> = 59 °C,  β = 0,22", "(11)", st, col_w))
        story.append(Paragraph(
            "kalibrasyonsuz doğruluk 20–45 °C'de %94,4–%94,7 ve 55 °C'de %92,3 kalır (Şekil 4c). Ham sızıntıda %64,1 (%1) ve %9,8 (%5) olan doğruluk, "
            "16 kareli karanlık çıkarma + Denklem (10) ile %94,4 (%1), %93,7 (%5), %88,2 (%20) ve %78,2 (%50) düzeyinde korunur; kombine 30 °C + %1 + %2 "
            "testini %64,4'ten %95,0'a çıkarır. ±10% lazer gücü %94,2–%94,9 aralığındadır.",
            st["body_noindent"]
        ))
        story.append(Paragraph("D. Bit Kuantizasyonu, Alt-Açıklık Vekili ve Dalga Cephesi Sapması", st["h3"]))
        story.append(Paragraph(
            "8-bit HDMI giriş + <i>b</i>-bit basamaklamada (tohum 7, Şekil 5a) doğruluk 4-bit'e dek %94,6–%94,9 ve 2-bit'te %92,7 kalır. "
            "<i>N</i> = 256 alt-açıklık vekilinde %25 dolulukta kalibrasyonsuz ve kafa kalibrasyonu %91,3 verir (baz %92,3). Zernike sapması (0–15λ PV) "
            "+ 3<i>Z</i><sub>1</sub> 0,04 hayalette eşit CE Adam kafalarıyla (Şekil 5b) 1λ–10λ'da yalnız kafa (%78,63–%77,53) habersiz PAT'ye (%78,50–%76,70) "
            "denktir; 15λ'da kalibrasyonsuz %65,27 ± 7,67, kafa kalibrasyonu %76,67 ± 1,15 ve PAT %77,30 ± 1,82 elde eder (+0,63 puan birleşik SS içinde). "
            "Yapısal uyumsuzlukta (±%10 pertürbe LC eğrisi, 0,90 kamera gamması, benek) kalibrasyonsuz %71,30 ± 1,08, yalnız-kafa %79,13 ± 2,39 ve PAT "
            "%76,80 ± 1,65 verir; yani yalnız-kafa kalibrasyonu bu rejimde PAT'yi geçer.",
            st["body_noindent"]
        ))
        bom_rows = [
            [Paragraph("<b>Alt Sistem</b>", st["cell_b"]), Paragraph("<b>Seçilen Donanım</b>", st["cell_b"]), Paragraph("<b>USD</b>", st["cell_br"])],
            [Paragraph("Optik Giriş", st["cell"]), Paragraph("532nm DPSS (100mW) + Genişletici + mSLA LCD", st["cell"]), Paragraph("150", st["cell_r"])],
            [Paragraph("Aktif Ağırlıklar", st["cell"]), Paragraph("2. mSLA TFT-LCD (veya ITO + AC-PWM)", st["cell"]), Paragraph("90–230", st["cell_r"])],
            [Paragraph("Okuma ve Kontrol", st["cell"]), Paragraph("RPi Cam 3 (IMX708, 12MP) + M12 + RPi 5", st["cell"]), Paragraph("125", st["cell_r"])],
            [Paragraph("Optomekanik", st["cell"]), Paragraph("Optik Ray, Tutucular, Kutu, 532nm Filtre", st["cell"]), Paragraph("262", st["cell_r"])],
            [Paragraph("Ara Toplam", st["cell"]), Paragraph("Temel optik ve elektronik parçalar", st["cell"]), Paragraph("627–767", st["cell_r"])],
            [Paragraph("<b>Toplam (+%25)</b>", st["cell_b"]), Paragraph("<b>Yedek paylı masaüstü prototip</b>", st["cell_b"]), Paragraph("<b>784–959</b>", st["cell_br"])],
        ]
        story.append(KeepTogether([
            Paragraph("TABLO IV — TAHMİNİ PROTOTİP MALZEME BÜTÇESİ", st["tab_cap"]),
            styled_table(bom_rows, [col_w*0.28, col_w*0.54, col_w*0.18], highlight_rows=[6]),
            Spacer(1, 1.2 * mm),
        ]))
        story.append(Paragraph("V. TARTIŞMA, SINIRLILIKLAR VE DONANIM YOL HARİTASI", st["h2"]))
        story.append(Paragraph(
            "Tablo IV'teki modüler optik ray kurulumu doğrudan parçada 627–767 USD (%25 yedekle 784–959 USD) tutmaktadır. Üç zaman ölçeği ayrılmalıdır: "
            "10 cm optik geçiş ~0,33 ns sürer; fiziksel donanım akışını çıkarımda 60 Hz LCD/kamera (~16,7 ms) ve ağırlık değişiminde ~50 ms nematik "
            "gevşeme belirler; derlenmemiş CPU NumPy ASM simülasyonu ise <i>N</i> = 128²'de 1,04 ms ortanca sürede (Intel64 Family 6 Model 170 CPU, Python 3.11.9 / NumPy 2.2.3, ort. 1,27 ms, IQR 0,63 ms, 50 koşum) çalışır.",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Masaüstü kurulumda üç mühendislik koşulu gerekir: RPi Cam 3 (IMX708, 6,45 × 3,63 mm) için 3,63 mm kısa eksene ~1,6× küçültücü M12 röle "
            "optiği; Sınıf 3B 100 mW 532 nm lazer için OD 4+ gözlük, mat kasa ve 808/1064 nm IR kesici filtre; tek kutuplu PCA9685 kartlarında ise ITO "
            "elektrolizini önleyen AC polarite-evirici sürücü devre kullanılmalıdır.",
            st["body"]
        ))

    # Page 6: Fig 5 banner + Limitations + Conclusion + Back Matter + All 24 References!
    story.append(NextPageTemplate("P_TOPFIG_LAST"))
    story.append(PageBreak())
    fig5_cap = (
        "<b>Fig. 5.</b> <b>(a)</b> Weight bit quantization (4-bit 94.8%, 2-bit 92.7%) and <i>N</i> = 256 sub-aperture fill-factor inset (uncalibrated vs. "
        "head recalibrated). <b>(b)</b> 3-seed Zernike wavefront aberrations (0–15λ PV + 3<i>Z</i><sub>1</sub> ghost): uncompensated, CE head-only control, "
        "and blind-surrogate PAT. <b>(c)</b> 3-seed 10-class Fashion-MNIST across 8×8 and 32×32 regimes."
        if lang == "en" else
        "<b>Şekil 5.</b> <b>(a)</b> Ağırlık bit basamaklaması (4-bit %94,8, 2-bit %92,7) ve <i>N</i> = 256 alt-açıklık doluluğu iç grafiği (kalibrasyonsuz ve kafa kalibre). "
        "<b>(b)</b> 3 tohumlu Zernike dalga cephesi sapmaları (0–15λ PV + 3<i>Z</i><sub>1</sub> hayalet): kalibrasyonsuz, CE yalnız-kafa ve habersiz vekil PAT. "
        "<b>(c)</b> 8×8 ve 32×32 rejimlerinde 3 tohumlu Fashion-MNIST."
    )
    story.append(fig_block(os.path.join(fig_dir, f"makale_fig5_gercekcilik_{lang}.png"), fig5_cap, st, 180, max_img_h_mm=38.5))
    story.append(NextPageTemplate("P_TWOCOL"))
    story.append(FrameBreak())

    if lang == "en":
        story.append(Paragraph("A. Limitations", st["h3"]))
        story.append(Paragraph(
            "Eight limitations qualify these findings. First, all accuracies and fault tolerances are simulated; physical fabrication and detector measurements "
            "remain future work. Second, on 8×8 detectors PAT beats matched random optics (+7.33 pts) yet trails digital area pooling (78.40% vs. 87.00%), while a "
            "265K MLP at 32×32 masks optical differences within ~0.5 pts. Third, Eq. (6) uses an ECB proxy whereas TN panels rotate polarization [18]. Fourth, "
            "monochromatic models omit laser speckle, finite coherence, and higher-order ghosts.",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Fifth, <i>N</i> = 256 sub-aperture fill serves as a scaled proxy rather than native 47 μm resolution. Sixth, the default plant probes parametric shifts "
            "within the ASM class, so we added the structural-mismatch test in Sec. IV (where PAT trails head-only recalibration). Seventh, hardware PAT requires ~16.7 ms/sample "
            "(60 Hz), showing feasibility rather than fast online training. Finally, 3-seed fixed splits apply, and cell-specific weights do not transfer across alignments "
            "without robustness methods like Sharpness-Aware Training [24].",
            st["body"]
        ))
        story.append(Paragraph("VI. CONCLUSION", st["h2"]))
        story.append(Paragraph(
            "Grounded in nematic scattering (15–40 dB/cm) and Alt–Pleshko RMS bounds (5.28× loss on 16 passive rows), ZERRE (Model H) pairs commodity mSLA "
            "LCDs with Wirtinger-adjoint PAT within an estimated $784–$959 BOM, lifting 8×8 linear MNIST by +7.33 points over matched random optics (78.40%) "
            "yet remaining 8.60 pts below digital area pooling (87.00%) and reaching a 94.67% MNIST / 84.43% Fashion-MNIST nominal-twin upper bound at 32×32 hybrid "
            "readout while defining concrete benchtop validation steps as a design-feasibility study.",
            st["body_noindent"]
        ))
        story.append(Paragraph("DATA AND CODE AVAILABILITY", st["h2"]))
        story.append(Paragraph(
            "Simulation scripts (<code>zerre_twin.py</code>, <code>zerre_pat_torch.py</code>), interactive WebGL/ASM tool (<code>start_server.py</code>), "
            "physics tests (<code>tests/test_zerre_physics.py</code>), 3-seed JSON outputs (<code>makale/scripts/paper_results.json</code>), and build scripts are "
            "released under the <b>MIT License</b> (code) and <b>CC BY 4.0</b> (paper/figures) at "
            "https://github.com/hamzasolak/zerre (release tag v0.5.0; ORCID: 0009-0004-7541-9620).",
            st["body_noindent"]
        ))
        story.append(Paragraph("FUNDING & CONFLICTS OF INTEREST", st["h2"]))
        story.append(Paragraph("This work received no external funding. The author declares no conflicts of interest.", st["body_noindent"]))
        story.append(Paragraph("ACKNOWLEDGMENTS", st["h2"]))
        story.append(Paragraph(
            "Generative AI assistance (Gemini and Claude) was used for prose editing, LaTeX formatting, and code-audit verification across Sections I–VI; "
            "the author conceived the design, wrote and verified the wave-optics simulation code, ran all benchmarks, and assumes full responsibility for all claims.",
            st["body_noindent"]
        ))
        story.append(Paragraph("REFERENCES", st["h2"]))
    else:
        story.append(Paragraph("A. Sınırlılıklar", st["h3"]))
        story.append(Paragraph(
            "Sekiz sınırlılık bulguları çerçeveler. İlk olarak tüm veriler simülasyon kaynaklıdır; fiziksel kurulum ve sensör gürültüsü ölçümleri "
            "sonraki aşamadır. İkincisi, 8×8 dedektörde PAT eşleşmiş rastgele optiği +7,33 puan geçse de dijital alan havuzlamanın (%87,00) gerisindedir "
            "ve 32×32'de 265K MLP optik farkları ~0,5 puana sıkıştırır. Üçüncüsü, (6) ECB vekili kullanırken TN paneller polarizasyon çevirir [18]. "
            "Dördüncüsü, skaler modeller lazer benek gürültüsünü ve çoklu yansımaları ihmal eder.",
            st["body_noindent"]
        ))
        story.append(Paragraph(
            "Beşincisi, <i>N</i> = 256 alt-açıklık testi ölçeklenmiş bir vekildir. Altıncısı, varsayılan sistem ASM içinde parametrik pertürbasyonu sınadığından "
            "Bölüm IV'e yapısal uyumsuzluk testi eklenmiştir (PAT yalnız-kafanın gerisinde kalır). Yedincisi, donanımda PAT 60 Hz'de ~16,7 ms/örnek sürdüğünden "
            "hızlı çevrimiçi eğitim değil fizibilite gösterir. Son olarak 3 tohumlu sabit bölmeler kullanılmış olup ağırlıklar Keskinlik-Farkındalıklı Eğitim [24] olmadan aktarılamaz.",
            st["body"]
        ))
        story.append(Paragraph("VI. SONUÇ", st["h2"]))
        story.append(Paragraph(
            "Nematik saçılma (15–40 dB/cm) ve Alt–Pleshko RMS kısıtları (16 satırda 5,28× kayıp) temelinde sentezlenen ZERRE (Model H), 784–959 USD "
            "bütçe dahilinde Wirtinger-eşlenik PAT ile 8×8 lineer MNIST doğruluğunu eşleşmiş rastgele optiğe göre +7,33 puan artırırken (%78,40) "
            "dijital alan havuzlamanın 8,60 puan gerisinde kalmakta; 32×32 hibrit okumada nominal-ikiz üst sınırı %94,67 MNIST ve %84,43 "
            "Fashion-MNIST'e ulaşarak çalışmayı deneysel doğrulama adımlarını netleştiren bir fizibilite değerlendirmesi olarak konumlandırmaktadır.",
            st["body_noindent"]
        ))
        story.append(Paragraph("VERİ VE KOD ERİŞİLEBİLİRLİĞİ", st["h2"]))
        story.append(Paragraph(
            "Simülasyon kodları (<code>zerre_twin.py</code>, <code>zerre_pat_torch.py</code>), etkileşimli WebGL/ASM aracı (<code>start_server.py</code>), "
            "fizik testleri (<code>tests/test_zerre_physics.py</code>), 3 tohumlu JSON sonuçları (<code>makale/scripts/paper_results.json</code>) ve derleme betikleri "
            "<b>MIT Lisansı</b> (kod) ve <b>CC BY 4.0</b> (makale/şekiller) ile https://github.com/hamzasolak/zerre adresinde "
            "(sürüm etiketi v0.5.0; ORCID: 0009-0004-7541-9620) sunulur.",
            st["body_noindent"]
        ))
        story.append(Paragraph("FİNANSMAN VE ÇIKAR ÇATIŞMASI", st["h2"]))
        story.append(Paragraph("Bu çalışma dış fon almadan bağımsız yürütülmüştür; yazar çıkar çatışması olmadığını beyan eder.", st["body_noindent"]))
        story.append(Paragraph("TEŞEKKÜR", st["h2"]))
        story.append(Paragraph(
            "Makalenin I–VI. Bölümlerinde üslup düzenleme, LaTeX biçimlendirme ve kod-doğrulama denetimi için üretken yapay zekâ (Gemini ve Claude) "
            "kullanılmıştır; tasarım, kod, deneyler ve tüm bilimsel iddialar tamamen yazarın sorumluluğundadır.",
            st["body_noindent"]
        ))
        story.append(Paragraph("KAYNAKLAR", st["h2"]))

    for r in _refs_list(lang):
        story.append(Paragraph(r, st["ref"]))

    doc.build(story)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    out_dir = os.path.join(base_dir, "1_html_pdf")
    os.makedirs(out_dir, exist_ok=True)

    fonts = _register_fonts()
    st = _make_styles(fonts)

    tr_pdf = os.path.join(out_dir, "ZERRE_Akademik_Makale_TR.pdf")
    en_pdf = os.path.join(out_dir, "ZERRE_Academic_Paper_EN.pdf")

    build_pdf("tr", tr_pdf, base_dir, st)
    print(f"[OK] Built {tr_pdf}")
    build_pdf("en", en_pdf, base_dir, st)
    print(f"[OK] Built {en_pdf}")


if __name__ == "__main__":
    main()
