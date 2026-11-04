"""
DEMO KISAYOLU — sabit içerik.

Bu dosyadaki veriler henüz veritabanında tablo olarak yok; frontend'in ekranları
dolu görünsün diye buradan sabit olarak dönüyor. İlgili özellik gerçekten yazıldığında
(görsel yükleme) buradaki listeler
silinip yerlerine tablo + servis gelecek.

Görsel yolları frontend'in kendi `assets/` klasörünü gösterir.
"""

# Profil düzenlemede seçilebilecek hazır görseller.
# DEMO KISAYOLU: Görsel yükleme (upload) yokken kullanıcı yalnızca bu listeden seçebilir.
# Sunucu gelen adresi bu listeyle karşılaştırır; böylece profile dışarıdan rastgele
# bir adres (ör. kötü amaçlı bir site) yazılamaz.
AVATAR_CHOICES = [f"assets/avatars/{gender}{number}.jpg" for gender in ("w", "m") for number in range(1, 11)]
COVER_CHOICES = [
    f"assets/covers/{name}.jpg"
    for name in ("sky", "coast", "city", "night", "beach", "cafe", "canal", "canyon",
                 "coffee", "guitar", "lighthouse", "mountain", "music", "terrace", "profile")
]

# Anı paylaşırken seçilebilecek hazır görseller (aynı güvenlik kuralı: yalnızca bu liste).
MOMENT_IMAGE_CHOICES = [url for url in COVER_CHOICES if not url.endswith("/profile.jpg")]
