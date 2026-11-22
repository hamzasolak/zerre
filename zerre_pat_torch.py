#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zerre_pat_torch.py — Physics-Aware Training (PAT) PyTorch + Donanım Köprüsü
════════════════════════════════════════════════════════════════════════════
Wright et al., Nature 601, 549–555 (2022) mimarisinin Zerre Model H için
birebir uygulanması:

  • İLERİ GEÇİŞ (Forward)  : Gerçek fiziksel donanım (HDMI mSLA LCD + DAC + RPi Cam3)
                             veya herhangi bir kara-kutu fiziksel simülatör fonksiyonu
  • GERİ GEÇİŞ  (Backward) : PyTorch kompleks FFT autograd vekil ikizi (Surrogate Twin)

PyTorch yüklü olduğunda GPU/CPU autograd grafiği olarak çalışır; PyTorch yüklü
olmadığında otomatik olarak zerre_twin.py içindeki analitik Wirtinger adjoint
NumPy PAT motoruna yönlendirir.
════════════════════════════════════════════════════════════════════════════
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


if TORCH_AVAILABLE:
    import numpy as np
    from zerre_twin import LAMBDA, PIX, Z1, Z2, V_TAB, PHI_TAB

    class DifferentiableSurrogateTwin(nn.Module):
        """Model H optik zincirinin tam türevlenebilir PyTorch vekil modeli."""

        def __init__(self, n_grid=256, n_ito=16, cam_n=16, drive_mode="active"):
            super().__init__()
            self.N = n_grid
            self.n_ito = n_ito
            self.cam_n = cam_n
            self.drive_mode = drive_mode

            self.register_buffer("H1", self._make_transfer(n_grid, PIX, LAMBDA, Z1))
            self.register_buffer("H2", self._make_transfer(n_grid, PIX, LAMBDA, Z2))
            self.register_buffer("v_tab", torch.tensor(V_TAB, dtype=torch.float32))
            self.register_buffer("phi_tab", torch.tensor(PHI_TAB, dtype=torch.float32))

            cell_px = int(n_grid * 0.75)
            self.rep = max(1, cell_px // n_ito)
            self.side = self.rep * n_ito
            self.o_cell = (n_grid - self.side) // 2

            self.up = max(1, int(n_grid * 0.55) // 28)
            self.gsz = self.up * 28
            self.o_in = (n_grid - self.gsz) // 2

        @staticmethod
        def _make_transfer(n_grid, pix, wavelength, z):
            k = 2.0 * np.pi / wavelength
            fx = np.fft.fftfreq(n_grid, d=pix)
            FX, FY = np.meshgrid(fx, fx, indexing="xy")
            arg = 1.0 - (wavelength * FX) ** 2 - (wavelength * FY) ** 2
            kz = k * np.sqrt(np.maximum(arg, 0.0))
            H = np.exp(1j * kz * z) * (arg > 0.0)
            return torch.tensor(H, dtype=torch.complex64)

        def lc_phase_torch(self, V, phi_scale=1.0, phi_tab=None):
            """NumPy lc_phase ile aynı API: phi_scale sıcaklık/Δn ölçeği,
            phi_tab opsiyonel pertürbe faz tablosu (yapısal uyumsuzluk)."""
            tab = self.phi_tab if phi_tab is None else phi_tab
            Vc = torch.clamp(V, 0.0, 5.0)
            idx = torch.clamp(torch.searchsorted(self.v_tab, Vc, right=True) - 1,
                              0, len(self.v_tab) - 2)
            v0 = self.v_tab[idx]
            v1 = self.v_tab[idx + 1]
            p0 = tab[idx]
            p1 = tab[idx + 1]
            t = (Vc - v0) / (v1 - v0 + 1e-12)
            return (p0 + t * (p1 - p0)) * float(phi_scale)

        def effective_voltage(self, W_param):
            if self.drive_mode != "passive":
                return torch.clamp(W_param, 0.0, 5.0)
            U = torch.clamp(W_param, -1.0, 1.0)
            n = float(U.shape[0])
            ratio = float(np.sqrt(n))
            norm_off = (ratio ** 2 - 2.0 * ratio + n) / n
            v_data = 1.0 / float(np.sqrt(norm_off))
            v_sel = ratio * v_data
            col_sq = torch.sum((U * v_data) ** 2, dim=0, keepdim=True)
            other = col_sq - (U * v_data) ** 2
            return torch.sqrt(torch.clamp(((v_sel + U * v_data) ** 2 + other) / n, min=1e-12))

        def forward(self, img28_batch, W_param):
            B = img28_batch.shape[0]
            device = img28_batch.device
            A = torch.zeros((B, self.N, self.N), dtype=torch.complex64, device=device)
            big = img28_batch.repeat_interleave(self.up, dim=1).repeat_interleave(self.up, dim=2)
            A[:, self.o_in:self.o_in + self.gsz, self.o_in:self.o_in + self.gsz] = big.to(torch.complex64)

            E1 = torch.fft.ifft2(torch.fft.fft2(A) * self.H1)

            V_eff = self.effective_voltage(W_param)
            phi = self.lc_phase_torch(V_eff)
            t_px = torch.sin(phi / 2.0) * torch.exp(1j * (phi / 2.0))
            tile = t_px.repeat_interleave(self.rep, dim=0).repeat_interleave(self.rep, dim=1)
            M = torch.zeros((self.N, self.N), dtype=torch.complex64, device=device)
            M[self.o_cell:self.o_cell + self.side, self.o_cell:self.o_cell + self.side] = tile

            E2 = torch.fft.ifft2(torch.fft.fft2(E1 * M) * self.H2)
            I = torch.abs(E2) ** 2
            p = self.N // self.cam_n
            lim = p * self.cam_n
            feat = I[:, :lim, :lim].reshape(B, self.cam_n, p, self.cam_n, p).mean(dim=(2, 4))
            return feat.reshape(B, -1)

    class _PATFunction(torch.autograd.Function):
        """Wright et al. (2022) PAT özel türev düğümü:
        İleri geçişte gerçek fiziksel ölçümü döndürür, geri geçişte vekil
        modelin autograd grafiği üzerinden dL/dW_param hesaplar."""

        @staticmethod
        def forward(ctx, img_batch, W_param, surrogate_module, hardware_forward_fn):
            ctx.surrogate = surrogate_module
            ctx.save_for_backward(img_batch, W_param)
            with torch.no_grad():
                y_phys = hardware_forward_fn(img_batch, W_param)
            return y_phys

        @staticmethod
        def backward(ctx, grad_output):
            img_batch, W_param = ctx.saved_tensors
            with torch.enable_grad():
                W_req = W_param.detach().requires_grad_(True)
                y_sur = ctx.surrogate(img_batch, W_req)
                (grad_W,) = torch.autograd.grad(
                    outputs=y_sur, inputs=W_req, grad_outputs=grad_output
                )
            return None, grad_W, None, None

    class ZerrePATLayer(nn.Module):
        """Fiziksel optik katmanı PyTorch nn.Module içine saran PAT katmanı."""

        def __init__(self, hardware_forward_fn, n_grid=256, n_ito=16, cam_n=16, drive_mode="active"):
            super().__init__()
            self.surrogate = DifferentiableSurrogateTwin(n_grid, n_ito, cam_n, drive_mode)
            self.hardware_forward_fn = hardware_forward_fn
            init = torch.empty((n_ito, n_ito)).uniform_(
                -0.8 if drive_mode == "passive" else 1.3,
                 0.8 if drive_mode == "passive" else 3.2
            )
            self.W_param = nn.Parameter(init)

        def forward(self, img_batch):
            return _PATFunction.apply(img_batch, self.W_param, self.surrogate, self.hardware_forward_fn)


def main():
    if TORCH_AVAILABLE:
        print("[PAT-PyTorch] PyTorch bulundu! DifferentiableSurrogateTwin ve ZerrePATLayer aktif.")
        hw_twin = DifferentiableSurrogateTwin(n_grid=128, n_ito=16, cam_n=16, drive_mode="active")

        def perturbed_hw_forward(img_batch, w_tensor):
            shifted = torch.roll(img_batch, shifts=(1, 0), dims=(-2, -1))
            return hw_twin(shifted, w_tensor) * 1.02

        layer = ZerrePATLayer(
            hardware_forward_fn=perturbed_hw_forward,
            n_grid=128, n_ito=16, cam_n=16
        )
        x = torch.rand(4, 28, 28)
        out = layer(x)
        out.sum().backward()
        print(f"[PAT-PyTorch] İleri çıktı boyutu: {tuple(out.shape)} · "
              f"Gradyan normu: {layer.W_param.grad.norm().item():.6f}")
    else:
        print("[PAT-Bilgi] Bu ortamda 'torch' paketi kurulu değil.")
        print("            Sıfır bağımlılıklı tam analitik Wirtinger Adjoint PAT motoru")
        print("            zerre_twin.py içinde aktif! Hemen doğrulama çalıştırılıyor:\n")
        from zerre_twin import grad_check
        grad_check()


if __name__ == "__main__":
    main()
