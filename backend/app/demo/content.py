"""
DEMO KISAYOLU — sabit içerik.

Bu dosyadaki veriler henüz veritabanında tablo olarak yok; frontend'in ekranları
dolu görünsün diye buradan sabit olarak dönüyor. İlgili özellik gerçekten yazıldığında
(duvar gönderileri, çerçeve mağazası, başarımlar, banner yönetimi) buradaki listeler
silinip yerlerine tablo + servis gelecek.

Görsel yolları frontend'in kendi `assets/` klasörünü gösterir.
"""

BANNERS = [
    {"id": 1, "title": "Gerçek insanlarla\ngerçek sohbetler", "cta": "MUTI'de buluş",
     "image_url": "assets/covers/banner1.jpg", "target": "#/explore"},
    {"id": 2, "title": "Oda içinde oyna,\nsohbeti bölme", "cta": "Oyun odalarını gör",
     "image_url": "assets/covers/banner2.jpg", "target": "#/explore?category=game"},
    {"id": 3, "title": "İlk alımına özel\n%50 bonus coin", "cta": "Coin al",
     "image_url": "assets/covers/banner3.jpg", "target": "#/wallet"},
]

PROFILE_EXTRAS = {
    "wall_posts": [
        {"id": 1, "time_label": "2 gün önce", "text": "Harika bir geceydi, güzel insanlar 🔥",
         "image_urls": ["assets/covers/terrace.jpg", "assets/covers/night.jpg", "assets/covers/music.jpg"],
         "like_count": 128, "comment_count": 24},
        {"id": 2, "time_label": "1 hafta önce", "text": "Yeni avatar çerçevemi aldım 🎮",
         "image_urls": ["assets/covers/city.jpg"], "like_count": 86, "comment_count": 11},
    ],
    "avatar_frames": [
        {"id": 1, "name": "Klasik", "style": "frame-classic", "is_owned": True},
        {"id": 2, "name": "Neon", "style": "frame-neon", "is_owned": True},
        {"id": 3, "name": "Altın", "style": "frame-gold", "is_owned": True},
        {"id": 4, "name": "Buz", "style": "frame-ice", "is_owned": False},
        {"id": 5, "name": "Alev", "style": "frame-fire", "is_owned": False},
        {"id": 6, "name": "Orman", "style": "frame-forest", "is_owned": False},
        {"id": 7, "name": "Galaksi", "style": "frame-galaxy", "is_owned": False},
        {"id": 8, "name": "Kraliyet", "style": "frame-royal", "is_owned": False},
    ],
    "achievements": [
        {"id": 1, "name": "Zar Ustası", "emoji": "🎲", "detail": "Seviye 5"},
        {"id": 2, "name": "Çark Şampiyonu", "emoji": "🎡", "detail": "Seviye 3"},
        {"id": 3, "name": "Sohbet Yıldızı", "emoji": "⭐", "detail": "Seviye 4"},
        {"id": 4, "name": "Turnuva", "emoji": "🏆", "detail": "İlk 100"},
    ],
    "recent_rewards": [
        {"id": 1, "name": "Altın Kupa", "emoji": "🏆", "date_label": "15.09.2026"},
        {"id": 2, "name": "Özel Çerçeve", "emoji": "💠", "date_label": "01.09.2026"},
        {"id": 3, "name": "365 Gün Rozeti", "emoji": "🎖️", "date_label": "28.08.2026"},
        {"id": 4, "name": "1000 Coin", "emoji": "🪙", "date_label": "20.08.2026"},
    ],
}
