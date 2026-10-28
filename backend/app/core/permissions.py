"""
Yönetim paneli rolleri ve yetkileri.

Panelde çalışan her kişinin (personel, "staff") bir rolü vardır. Rol doğrudan kontrol
edilmez; rolün verdiği YETKİ kontrol edilir: "moderator mü?" değil, "users.ban yetkisi var mı?".
Böylece yeni bir rol eklemek ya da bir role yetki eklemek yalnızca bu dosyayı değiştirmek demektir;
router'lardaki kontroller aynı kalır.

Yetki her istekte veritabanındaki güncel rolden hesaplanır (token'a yazılmaz): bir kişinin
rolü alınınca bir sonraki isteği reddedilir.
"""
from typing import Literal

StaffRole = Literal["admin", "moderator", "finance"]
STAFF_ROLES: tuple[str, ...] = ("admin", "moderator", "finance")

# Yetkiler ve ne işe yaradıkları
PERMISSIONS: dict[str, str] = {
    "dashboard.view": "Genel bakış sayıları",
    "finance.view": "Finans grafikleri ve bütün para hareketleri",
    "users.view": "Kullanıcı arama ve kullanıcı detayı",
    "users.ban": "Kullanıcı banlama / banı kaldırma",
    "users.balance": "Bakiye düzeltme",
    "users.vip": "Ücretsiz VIP verme",
    "reports.manage": "Şikâyetleri karara bağlama",
    "rooms.manage": "Odaları görme ve kapatma",
    "messages.read": "Özel mesaj ve oda sohbeti okuma",
    "catalog.manage": "Hediye ve coin paketi fiyatları",
    "agencies.manage": "Ajans kurma",
    "broadcast.send": "Bütün kullanıcılara duyuru",
    "staff.manage": "Personel rolü verme / alma",
    "staff.audit": "Personel işlem kaydını görme",
}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # Her şey
    "admin": frozenset(PERMISSIONS),
    # Topluluk güvenliği: şikâyet, ban, oda kapatma. Paraya dokunamaz.
    "moderator": frozenset({
        "dashboard.view", "users.view", "users.ban", "reports.manage", "rooms.manage", "messages.read",
    }),
    # Para tarafı: gelir raporları, para hareketleri, bakiye düzeltme. Kimseyi banlayamaz.
    "finance": frozenset({"dashboard.view", "finance.view", "users.view", "users.balance"}),
}

ROLE_LABELS: dict[str, str] = {"admin": "Yönetici", "moderator": "Moderatör", "finance": "Finans"}


def permissions_of(role: str | None) -> frozenset[str]:
    return ROLE_PERMISSIONS.get(role or "", frozenset())
