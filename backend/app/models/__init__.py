"""
Bütün tablo sınıfları burada toplanır.

Yeni bir model dosyası eklersen buraya da import etmelisin; yoksa SQLAlchemy o
tablodan haberdar olmaz ve tabloyu oluşturmaz.
"""
from app.models.agency import Agency, AgencyEarning, AgencyMember, AgencySettlement
from app.models.call import CALL_KINDS, CALL_STATUSES, Call
from app.models.dealer import DEALER_STATUSES, CoinDealer, DealerStockOrder
from app.models.economy import CoinPackage, Gift, Transaction
from app.models.engagement import EVENT_METRICS, DailyCheckIn, Event, TaskClaim, TaskCounter
from app.models.host import HOST_APPLICATION_STATUSES, HostApplication
from app.models.media import MEDIA_KINDS, MediaUpload
from app.models.family import FAMILY_ROLES, Couple, Family, FamilyMember, FamilyMessage
from app.models.message import MESSAGE_KINDS, Conversation, Message, RoomMessage
from app.models.moment import Moment, MomentComment, MomentLike, ProfileVisit
from app.models.room import ROOM_CATEGORIES, ROOM_KINDS, ROOM_MEMBER_ROLES, Room, RoomFollow, RoomMember, RoomVisit
from app.models.social import INBOX_SECTIONS, REPORT_REASONS, REPORT_TARGET_TYPES, InboxSeen, Notification, Report, UserBlock
from app.models.staff import StaffAction
from app.models.store import STORE_DURATIONS, STORE_ITEM_KINDS, StoreItem, UserItem
from app.models.user import Follow, RefreshToken, User

__all__ = [
    "Agency", "AgencyEarning", "AgencyMember", "AgencySettlement", "HostApplication", "HOST_APPLICATION_STATUSES",
    "MediaUpload", "MEDIA_KINDS", "RoomMessage", "Call", "CALL_KINDS", "CALL_STATUSES", "MESSAGE_KINDS",
    "Couple", "DailyCheckIn", "Event", "EVENT_METRICS", "FAMILY_ROLES", "Family", "FamilyMember", "FamilyMessage",
    "TaskClaim", "TaskCounter",
    "CoinDealer", "DealerStockOrder", "DEALER_STATUSES",
    "CoinPackage", "Conversation", "Follow", "Gift", "Message", "Moment", "MomentComment", "MomentLike", "Notification", "ProfileVisit",
    "RefreshToken", "Report", "REPORT_REASONS", "REPORT_TARGET_TYPES", "Room", "RoomFollow", "RoomMember", "RoomVisit",
    "ROOM_CATEGORIES", "ROOM_KINDS", "ROOM_MEMBER_ROLES", "StaffAction", "STORE_DURATIONS", "STORE_ITEM_KINDS", "StoreItem", "Transaction",
    "User", "UserBlock", "UserItem", "InboxSeen", "INBOX_SECTIONS",
]
