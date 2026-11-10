"""
Geliştirme için web sunucusu: `python -m http.server` ile aynı, tek farkı her dosyaya
"Cache-Control: no-cache" başlığı eklemesi.

NEDEN? Build adımı olmadığı için JS dosyalarının adı hiç değişmez. Başlık olmazsa telefonun
tarayıcısı bir dosyanın ESKİ halini saklayıp yenisiyle karıştırır (ör. eski app.js yeni sayfayı
tanımaz ve ana sayfaya atar). "no-cache" = her seferinde sunucuya "değişti mi?" diye sor; değişmediyse
sunucu kısa bir "304" der, dosya yeniden inmez. Canlıda bu işi backend yapıyor (bkz. main.py FRONTEND_DIR).

Çalıştırma: python dev_server.py   (adres: http://127.0.0.1:5500)
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 5500


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    handler = partial(NoCacheHandler, directory=str(Path(__file__).resolve().parent))
    print(f"Frontend: http://127.0.0.1:{PORT}  (önbellek kapalı)")
    ThreadingHTTPServer(("0.0.0.0", PORT), handler).serve_forever()
