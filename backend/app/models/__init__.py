"""
Bütün tablo sınıfları burada toplanır.

Yeni bir model dosyası eklersen buraya da import etmelisin; yoksa SQLAlchemy o
tablodan haberdar olmaz ve tabloyu oluşturmaz.
"""
from app.models.agency import Agency, AgencyMember
from app.models.economy import CoinPackage, Gift, Transaction
from app.models.engagement import EVENT_METRICS, DailyCheckIn, Event, TaskClaim, TaskCounter
from app.models.family import FAMILY_ROLES, Couple, Family, FamilyMember, FamilyMessage
from app.models.message import Conversation, Message
from app.models.room import ROOM_CATEGORIES, ROOM_MEMBER_ROLES, Room, RoomFollow, RoomMember
from app.models.social import REPORT_REASONS, REPORT_TARGET_TYPES, Notification, Report, UserBlock
from app.models.store import STORE_DURATIONS, STORE_ITEM_KINDS, StoreItem, UserItem
from app.models.user import Follow, RefreshToken, User

__all__ = [
    "Agency", "AgencyMember",
    "Couple", "DailyCheckIn", "Event", "EVENT_METRICS", "FAMILY_ROLES", "Family", "FamilyMember", "FamilyMessage",
    "TaskClaim", "TaskCounter",
    "CoinPackage", "Conversation", "Follow", "Gift", "Message", "Notification",
    "RefreshToken", "Report", "REPORT_REASONS", "REPORT_TARGET_TYPES", "Room", "RoomFollow", "RoomMember",
    "ROOM_CATEGORIES", "ROOM_MEMBER_ROLES", "STORE_DURATIONS", "STORE_ITEM_KINDS", "StoreItem", "Transaction",
    "User", "UserBlock", "UserItem",
]
