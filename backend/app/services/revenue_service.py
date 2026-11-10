"""
Yayıncı geliri: bir hediyenin (ya da ücretli arama dakikasının) coin değeri kime ne kadar gider?

KURAL (oranlar .env, bkz. core/config.py):
  - Bağımsız yayıncı (ajansı yok):  hediyenin %50'si elmas olarak yayıncıya, %50 uygulamaya.
  - Ajans yayıncısı:                hediyenin %60'ı yayıncıya + ajansın oranı (ör. %10) ajansa,
                                    kalan (%30) uygulamaya.
  Yani ajansa katılmak yayıncıya da kazandırır; ajansın komisyonu yayıncının payından KESİLMEZ,
  uygulamanın payından çıkar. Ajans bu yüzden yayıncı bulmaya ve büyütmeye teşvik edilir.

NEDEN UYGULAMAYA HEP PAY KALMALI? Ajans kendi hesaplarından kendi yayıncısına hediye gönderirse
100 coin harcar, yayıncı + ajans en fazla 60 + 15 = 75 alır: sahte hediye döngüsü zarar ettirir.
Ayarlar bu kuralı bozarsa uygulama hiç açılmaz (config.py `_payouts_leave_platform_share`).

Şanslı hediyede gönderen coin geri kazanabildiği için alıcının payı sabit ve düşüktür (%10), ajans
payı yoktur.

Ajansın payı hediye anında `agency_earnings` tablosuna yazılır (bakiye değişmez); ay sonunda
panelden toplu ödenir (agency_service.settle_month).
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Agency, AgencyEarning, AgencyMember
from app.schemas.economy import RevenueRates

IncomeSource = Literal["gift", "lucky_gift", "call"]


@dataclass(frozen=True)
class IncomeSplit:
    host_diamonds: int
    host_percent: int
    agency_id: int | None = None
    agency_percent: int = 0
    agency_diamonds: int = 0


def effective_commission(agency: Agency) -> int:
    """Ajansın oranı, üst sınırı aşamaz (sınır sonradan düşürülürse eski ajanslar da uyar)."""
    return max(0, min(agency.commission_percent, settings.agency_commission_max_percent))


async def active_agency_of(db: AsyncSession, host_id: int) -> Agency | None:
    """Kişi şu an bir ajansın aktif yayıncısı mı? (davet/başvuru sayılmaz)"""
    return await db.scalar(
        select(Agency).join(AgencyMember, AgencyMember.agency_id == Agency.id)
        .where(AgencyMember.user_id == host_id, AgencyMember.status == "active")
    )


def _host_percent(source: IncomeSource, in_agency: bool) -> int:
    if source == "lucky_gift":
        return settings.lucky_gift_receiver_share_percent
    if source == "call":
        return settings.call_agency_host_share_percent if in_agency else settings.call_receiver_share_percent
    return settings.agency_host_share_percent if in_agency else settings.gift_receiver_share_percent


async def split_income(db: AsyncSession, host_id: int, coins: int, source: IncomeSource) -> IncomeSplit:
    """
    `coins` değerindeki bir gelirin paylaşımı. `//` tamsayı bölmesidir: küsurat uygulamada kalır,
    float kullanılmaz (para hesabında 0,1 + 0,2 ≠ 0,3 sorunları olmasın).
    """
    agency = await active_agency_of(db, host_id)
    host_percent = _host_percent(source, agency is not None)
    host_diamonds = coins * host_percent // 100
    if agency is None or source == "lucky_gift":
        return IncomeSplit(host_diamonds=host_diamonds, host_percent=host_percent)
    agency_percent = effective_commission(agency)
    return IncomeSplit(
        host_diamonds=host_diamonds, host_percent=host_percent, agency_id=agency.id,
        agency_percent=agency_percent, agency_diamonds=coins * agency_percent // 100,
    )


def record_agency_share(db: AsyncSession, split: IncomeSplit, host_id: int, coins: int, source: IncomeSource) -> None:
    """
    Ajansın payını kayda geçirir. commit YAPMAZ: hediyeyle aynı transaction'da kalıcı olur
    (hediye geri alınırsa ajans payı da yazılmamış olur).
    """
    if split.agency_id is None or split.agency_diamonds <= 0:
        return
    db.add(AgencyEarning(
        agency_id=split.agency_id, host_id=host_id, source="call" if source == "call" else "gift", coins=coins,
        host_diamonds=split.host_diamonds, commission_percent=split.agency_percent,
        commission_diamonds=split.agency_diamonds,
    ))


def rates() -> RevenueRates:
    """Uygulamada ve panelde gösterilen oranlar (yayıncı "ajansa katılırsam ne kazanırım?" görsün)."""
    return RevenueRates(
        independent_host_percent=settings.gift_receiver_share_percent,
        agency_host_percent=settings.agency_host_share_percent,
        agency_commission_max_percent=settings.agency_commission_max_percent,
        lucky_gift_host_percent=settings.lucky_gift_receiver_share_percent,
        call_host_percent=settings.call_receiver_share_percent,
        call_agency_host_percent=settings.call_agency_host_share_percent,
        call_voice_price_per_minute=settings.call_voice_price_per_minute,
        call_video_price_per_minute=settings.call_video_price_per_minute,
        diamond_to_coin_rate=settings.diamond_to_coin_rate,
        coin_price_per_1000_kurus=settings.coin_price_per_1000_kurus,
        dealer_discount_percent=settings.dealer_discount_percent,
        withdrawals_enabled=settings.withdrawals_enabled,
    )
