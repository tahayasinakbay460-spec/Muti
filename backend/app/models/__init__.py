"""
Bütün tablo sınıfları burada toplanır.

Yeni bir model dosyası eklersen buraya da import etmelisin; yoksa SQLAlchemy o
tablodan haberdar olmaz ve tabloyu oluşturmaz.
"""
from app.models.economy import CoinPackage, Gift, Transaction
from app.models.message import Conversation, Message
from app.models.room import ROOM_CATEGORIES, Room
from app.models.user import Follow, RefreshToken, User

__all__ = [
    "CoinPackage", "Conversation", "Follow", "Gift", "Message",
    "RefreshToken", "Room", "ROOM_CATEGORIES", "Transaction", "User",
]
