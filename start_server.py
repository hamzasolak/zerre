#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start_server.py — Zerre Dashboard + Canlı Dijital İkiz API Sunucusu
════════════════════════════════════════════════════════════════════
Statik 3B WebGL arayüzünü (port 5501) sunar ve aynı zamanda gerçek
dalga-optiği dijital ikizini (zerre_twin.py) canlı REST API üzerinden
web panosuna bağlar:

  GET  /api/status          → Yüklü optik modelin fiziksel parametreleri
  GET  /api/sample?digit=3  → Gerçek MNIST test kümesinden 28×28 örnek rakam
  POST /api/predict         → 28×28 LCD girişini ASM + ITO Jones + CMOS |E|²
                              zincirinden geçirip olasılık ve alan haritalarını döner

Kullanım:
  python start_server.py            # sunucuyu başlatır ve tarayıcıyı açar
  python start_server.py --no-open  # tarayıcı açmadan başlatır (test/sunucu modu)
════════════════════════════════════════════════════════════════════
"""

import http.server
import socketserver
import webbrowser
import threading
import urllib.parse
import json
import gzip
import struct
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

import mimetypes
import numpy as np

from zerre_twin import load_twin_from_npz, infer_array, ZerreTwin, fit_standardizer, fit_ridge

PORT      = 5501
HOST      = "127.0.0.1"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css",               ".css")
mimetypes.add_type("text/html",              ".html")


# ─── Canlı Optik Çıkarım Motoru (Bellekte Tek Seferlik Yüklenir) ───
class LiveOpticalEngine:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.model_path = os.path.join(base_dir, "zerre_model.npz")
        self.lock = threading.Lock()
        self.twin = None
        self.model_dict = None
        self.mnist_images = None
        self.mnist_labels = None
        self.is_trained_model = False
        self._last_mtime = None
        self.rng = np.random.default_rng()
        self._load_model()
        self._load_mnist_samples()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.twin, self.model_dict = load_twin_from_npz(self.model_path)
            self._last_mtime = os.path.getmtime(self.model_path)
            self.is_trained_model = True
            print(f"  [İKİZ] Model yüklendi: {os.path.basename(self.model_path)} "
                  f"({self.twin.n_ito}×{self.twin.n_ito} {self.twin.drive_mode}, "
                  f"izgara {self.twin.N}², kamera {self.twin.cam_n}×{self.twin.cam_n})")
        else:
            # Yedek: model dosyası yoksa hızlı varsayılan oluştur
            print("  [İKİZ] Uyarı: zerre_model.npz bulunamadı, eğitimsiz yedek demo hazırlanıyor...")
            self.twin = ZerreTwin(128, n_ito=16, cam_n=16, drive_mode="active")
            W = np.random.default_rng(7).uniform(1.2, 3.2, (16, 16))
            dummy_F = self.twin.forward_batch(np.random.default_rng(7).random((30, 28, 28)), W)
            mu, sd = fit_standardizer(dummy_F)
            Wout = fit_ridge((dummy_F - mu) / sd, np.arange(30) % 10, 10)
            self._last_mtime = None
            self.is_trained_model = False
            self.model_dict = {
                "W_volt": W, "mu": mu, "sd": sd, "Wout": Wout,
                "grid": 128, "cam_n": 16, "n_cls": 10, "n_ito": 16, "drive_mode": "active"
            }

    def _load_mnist_samples(self):
        img_p = os.path.join(self.base_dir, "mnist_cache", "t10k-images-idx3-ubyte.gz")
        lbl_p = os.path.join(self.base_dir, "mnist_cache", "t10k-labels-idx1-ubyte.gz")
        if os.path.exists(img_p) and os.path.exists(lbl_p):
            try:
                with gzip.open(img_p, "rb") as f:
                    _, n, r, c = struct.unpack(">IIII", f.read(16))
                    self.mnist_images = np.frombuffer(f.read(), np.uint8).reshape(n, r, c) / 255.0
                with gzip.open(lbl_p, "rb") as f:
                    _, n = struct.unpack(">II", f.read(8))
                    self.mnist_labels = np.frombuffer(f.read(), np.uint8).astype(int)
                print(f"  [İKİZ] MNIST test örnek havuzu hazır ({len(self.mnist_labels)} görüntü).")
            except Exception as exc:
                print(f"  [İKİZ] MNIST önbellek okuma uyarısı: {exc}")

    def reload_if_updated(self):
        if os.path.exists(self.model_path):
            mtime = os.path.getmtime(self.model_path)
            if self._last_mtime != mtime:
                self._load_model()

    def status(self):
        with self.lock:
            self.reload_if_updated()
            has_mlp = "mlp_W1" in self.model_dict
            return {
                "ready": True,
                "is_trained_model": self.is_trained_model,
                "grid": self.twin.N,
                "n_ito": self.twin.n_ito,
                "cam_n": self.twin.cam_n,
                "drive_mode": self.twin.drive_mode,
                "head_type": "Hibrit MLP" if has_mlp else "Ridge Lineer",
                "n_classes": int(self.model_dict["n_cls"]),
                "has_mnist_pool": self.mnist_images is not None,
            }

    def get_sample(self, digit=None):
        if self.mnist_images is not None:
            if digit is not None and 0 <= digit <= 9:
                idxs = np.where(self.mnist_labels == digit)[0]
            else:
                idxs = np.arange(len(self.mnist_labels))
            chosen = int(self.rng.choice(idxs))
            return {
                "pixels": np.round(self.mnist_images[chosen], 3).tolist(),
                "label": int(self.mnist_labels[chosen]),
                "source": f"MNIST test #{chosen}",
            }
        # Yedek: sentetik rakam benzeri şekil
        d = int(digit) if digit is not None else 0
        img = np.zeros((28, 28))
        img[5:23, 12:16] = 1.0
        return {"pixels": img.tolist(), "label": d, "source": "sentetik"}

    @staticmethod
    def text_to_lcd28(text):
        """UTF-8 metin baytlarını 28×28 mSLA LCD ikili/gri genlik desenine kodlar."""
        raw = text.encode("utf-8")
        bits = []
        for b in raw:
            for k in range(7, -1, -1):
                bits.append((b >> k) & 1)
        if not bits:
            bits = [0]
        arr = np.resize(np.array(bits, dtype=float), (24, 24))
        pad = np.zeros((28, 28), dtype=float)
        pad[2:26, 2:26] = arr
        return pad

    def predict(self, payload):
        with self.lock:
            self.reload_if_updated()
            if "pixels" in payload and payload["pixels"] is not None:
                img28 = np.asarray(payload["pixels"], dtype=float)
                if img28.shape != (28, 28):
                    raise ValueError(f"28x28 matris bekleniyordu, gelen: {img28.shape}")
                mode_in = "lcd_draw"
            elif "text" in payload:
                img28 = self.text_to_lcd28(str(payload["text"]))
                mode_in = "text_slm"
            else:
                raise ValueError("Geçersiz istek: 'pixels' veya 'text' alanı gerekli.")

            res = infer_array(img28, self.twin, self.model_dict, map_size=64)
            res["input_mode"] = mode_in
            return res


ENGINE = None


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ZerreHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        code = args[1] if len(args) > 1 else "???"
        color = "\033[92m" if str(code).startswith("2") else \
                "\033[93m" if str(code).startswith("3") else \
                "\033[91m"
        reset = "\033[0m"
        print(f" {color}[{code}]{reset}  {args[0]}  —  {self.address_string()}")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(ENGINE.status())
            return
        if parsed.path == "/api/sample":
            qs = urllib.parse.parse_qs(parsed.query)
            digit = None
            if "digit" in qs and qs["digit"][0].lstrip("-").isdigit():
                d = int(qs["digit"][0])
                if 0 <= d <= 9:
                    digit = d
            self._send_json(ENGINE.get_sample(digit))
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/predict":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 2 * 1024 * 1024:
                    self._send_json({"error": "İstek gövdesi çok büyük (maks 2 MB)"}, status=413)
                    return
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw) if raw else {}
                result = ENGINE.predict(payload)
                self._send_json(result, status=200)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json({"error": "Bilinmeyen uç nokta"}, status=404)


def main():
    global ENGINE
    no_open = "--no-open" in sys.argv
    url = f"http://localhost:{PORT}/index.html"

    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((HOST, PORT)) == 0:
            print(f"\n⚠  Port {PORT} zaten kullanımda.")
            if not no_open:
                print(f"   Tarayıcıda açılıyor: {url}\n")
                webbrowser.open(url)
            return

    print("\n" + "═" * 58)
    print("  ZERRE — Optofluidik AI İşlemci + Canlı Dijital İkiz")
    print("═" * 58)
    ENGINE = LiveOpticalEngine(DIRECTORY)

    with ThreadingHTTPServer((HOST, PORT), ZerreHandler) as httpd:
        print(f"  Sunucu : \033[92m{url}\033[0m")
        print(f"  API    : http://localhost:{PORT}/api/predict")
        print(f"  Dizin  : {DIRECTORY}")
        print("  Durdurmak için  Ctrl+C  tuşlayın.")
        print("═" * 58 + "\n")

        if not no_open:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\033[93m  Sunucu durduruldu.\033[0m\n")
            httpd.shutdown()


if __name__ == "__main__":
    main()
