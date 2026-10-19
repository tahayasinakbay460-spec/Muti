"""
Cüzdan: bakiye değişiklikleri, coin satın alma, işlem geçmişi.

EN ÖNEMLİ KURAL: Bir kullanıcının bakiyesi YALNIZCA bu dosyadaki `change_balance`
fonksiyonu ile değişir. Başka hiçbir yerde `user.coin_balance = ...` yazılmaz.
Para ile ilgili bütün güvenlik önlemleri tek yerde durur; bir hata olursa bakılacak
yer bellidir.
"""
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.errors import InsufficientBalanceError, NotFoundError, UnavailableError
from app.core.timefmt import as_utc, time_ago_label
from app.models import CoinPackage, Transaction, User
from app.schemas.economy import (
    CoinPackageOut, ExchangeResult, IncomeSummary, PurchaseResult, Supporter, TransactionOut,
)
from app.services import user_service


async def change_balance(
    db: AsyncSession,
    *,
    user_id: int,
    currency: str,            # "coin" | "diamond"
    delta: int,               # artı: ekle, eksi: düş
    type: str,                # purchase | gift_sent | gift_received | reward | exchange
    label: str,
    idempotency_key: str | None = None,
    counterparty_id: int | None = None,
    gift_id: int | None = None,
    package_id: int | None = None,
    room_id: int | None = None,
    quantity: int | None = None,
) -> int:
    """
    Bakiyeyi değiştirir, deftere (transactions) kaydını yazar, yeni bakiyeyi döner.

    DİKKAT: Bu fonksiyon `commit` YAPMAZ. Çağıran taraf bütün adımlar başarılı olunca
    tek seferde commit eder. Örneğin hediyede "gönderenden düş" ve "alana ekle"
    adımlarının ya ikisi birden olur ya hiçbiri (transaction / ACID).

    NEDEN "ÖNCE OKU, SONRA YAZ" DEĞİL?
    Yanlış yöntem:   bakiye = oku()  →  yeterli mi?  →  yaz(bakiye - 100)
    Aynı anda iki istek gelirse ikisi de eski bakiyeyi okur, ikisi de "yeterli" der
    ve kullanıcı olmayan parayı harcar. Bunun yerine kontrolü ve düşmeyi veritabanına
    TEK komutla yaptırıyoruz:
        UPDATE users SET coin_balance = coin_balance - 100
        WHERE id = :id AND coin_balance >= 100
    Veritabanı bu komutu bölünmez şekilde çalıştırır. Bakiye yetmiyorsa hiçbir satır
    değişmez; biz de bunu "yetersiz bakiye" olarak anlarız.
    """
    column = User.coin_balance if currency == "coin" else User.diamond_balance

    statement = update(User).where(User.id == user_id).values({column: column + delta}).returning(column)
    if delta < 0:
        statement = statement.where(column >= -delta)
    # synchronize_session=False: bellekteki User nesnelerini güncellemeye uğraşma,
    # yeni bakiyeyi RETURNING ile zaten alıyoruz.
    result = await db.execute(statement.execution_options(synchronize_session=False))
    balance_after = result.scalar_one_or_none()

    if balance_after is None:
        if delta < 0:
            raise InsufficientBalanceError()
        raise NotFoundError("Kullanıcı bulunamadı.")

    db.add(Transaction(
        user_id=user_id, type=type, currency=currency, amount=delta, balance_after=balance_after,
        label=label, idempotency_key=idempotency_key, counterparty_id=counterparty_id,
        gift_id=gift_id, package_id=package_id, room_id=room_id, quantity=quantity,
    ))
    # flush: satırı şimdi veritabanına gönder (henüz kalıcı değil). Aynı idempotency
    # anahtarı daha önce kullanılmışsa hata tam burada çıkar.
    await db.flush()
    return balance_after


async def find_by_idempotency_key(db: AsyncSession, user_id: int, key: str | None) -> Transaction | None:
    """
    Bu kullanıcı bu anahtarla daha önce işlem yapmış mı?

    İDEMPOTENCY NEDİR? Mobilde bağlantı koptuğunda uygulama aynı isteği tekrar gönderir.
    İstek aslında ilk seferde işlendiyse kullanıcıdan ikinci kez para düşmemeli.
    İstemci her "satın al / hediye gönder" dokunuşu için benzersiz bir anahtar üretir
    ve `Idempotency-Key` başlığında yollar. Aynı anahtar tekrar gelirse işlemi
    yeniden yapmaz, ilk sonucun aynısını döneriz.
    """
    if not key:
        return None
    return await db.scalar(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.idempotency_key == key)
    )


async def get_coin_balance(db: AsyncSession, user_id: int) -> int:
    return await db.scalar(select(User.coin_balance).where(User.id == user_id)) or 0


# ── Coin paketleri ve satın alma ──────────────────────────────────────────────

async def list_packages(db: AsyncSession) -> list[CoinPackageOut]:
    packages = await db.scalars(select(CoinPackage).where(CoinPackage.is_active).order_by(CoinPackage.coins))
    return [CoinPackageOut.model_validate(package) for package in packages]


async def purchase(db: AsyncSession, user_id: int, package_id: int, idempotency_key: str | None) -> PurchaseResult:
    """
    Coin paketi satın alır.

    DEMO KISAYOLU: Gerçek ödeme YOK, coin doğrudan eklenir. Canlıda akış şöyle olacak:
    mobil uygulama App Store / Google Play'den satın alır → makbuzu buraya yollar →
    biz makbuzu mağazanın sunucusunda doğrularız → ancak ondan sonra coin ekleriz.
    Bu yüzden demo modu kapalıyken bu fonksiyon çalışmayı reddeder.
    """
    if not settings.demo_mode:
        raise UnavailableError("Satın alma şu an kullanılamıyor.", code="purchases_unavailable")

    async def replay(previous: Transaction) -> PurchaseResult:
        return PurchaseResult(coin_balance=await get_coin_balance(db, user_id), added=previous.amount)

    previous = await find_by_idempotency_key(db, user_id, idempotency_key)
    if previous:
        return await replay(previous)

    package = await db.get(CoinPackage, package_id)
    if package is None or not package.is_active:
        raise NotFoundError("Coin paketi bulunamadı.")
    total = package.coins + package.bonus

    try:
        balance = await change_balance(
            db, user_id=user_id, currency="coin", delta=total, type="purchase",
            label=f"Coin satın alma ({package.price_label})",
            package_id=package.id, idempotency_key=idempotency_key,
        )
        await db.commit()
    except IntegrityError:
        # Aynı anahtarla iki istek tam aynı anda geldi ve diğeri bizden önce yazdı.
        # Bizimkini geri alıp onun sonucunu dönüyoruz.
        await db.rollback()
        previous = await find_by_idempotency_key(db, user_id, idempotency_key)
        if previous is None:
            raise
        return await replay(previous)

    return PurchaseResult(coin_balance=balance, added=total)


# ── Yayıncı geliri (elmas) ────────────────────────────────────────────────────

async def _balances(db: AsyncSession, user_id: int) -> tuple[int, int]:
    row = (await db.execute(select(User.coin_balance, User.diamond_balance).where(User.id == user_id))).one()
    return row.coin_balance, row.diamond_balance


async def exchange_diamonds(db: AsyncSession, user_id: int, diamonds: int, idempotency_key: str | None) -> ExchangeResult:
    """
    Hediyelerden kazanılan elmasları coine çevirir: elmas düşer, coin eklenir; ikisi
    tek transaction'da (ya ikisi birden olur ya hiçbiri). Oran: settings.diamond_to_coin_rate.
    """
    coins = diamonds * settings.diamond_to_coin_rate

    async def replay() -> ExchangeResult:
        coin_balance, diamond_balance = await _balances(db, user_id)
        return ExchangeResult(coin_balance=coin_balance, diamond_balance=diamond_balance, coins_added=coins)

    if await find_by_idempotency_key(db, user_id, idempotency_key):
        return await replay()
    try:
        # İdempotency anahtarı yalnızca ilk satıra yazılır: aynı kullanıcıda bir anahtar tek satırda olabilir.
        diamond_balance = await change_balance(
            db, user_id=user_id, currency="diamond", delta=-diamonds, type="exchange",
            label=f"Elmas → coin ({diamonds} elmas)", idempotency_key=idempotency_key,
        )
        coin_balance = await change_balance(
            db, user_id=user_id, currency="coin", delta=coins, type="exchange",
            label=f"Elmas çevirme (+{coins} coin)",
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if await find_by_idempotency_key(db, user_id, idempotency_key) is None:
            raise
        return await replay()
    except Exception:
        await db.rollback()
        raise
    return ExchangeResult(coin_balance=coin_balance, diamond_balance=diamond_balance, coins_added=coins)


async def income_summary(db: AsyncSession, user_id: int) -> IncomeSummary:
    """
    Hediyelerden kazanılan elmasların özeti ve en çok destek olanlar.
    DEMO KISAYOLU: her istekte hareket defterinden toplanıyor; canlıda günlük özet tablosu
    ya da Redis sayaçları kullanılır.
    """
    received = (Transaction.user_id == user_id) & (Transaction.type == "gift_received")

    async def total_since(start) -> int:
        statement = select(func.coalesce(func.sum(Transaction.amount), 0)).where(received)
        if start is not None:
            statement = statement.where(Transaction.created_at >= start)
        return await db.scalar(statement)

    now = utcnow()
    # "Bugün" kullanıcının saatine göre (DEMO: sabit Türkiye saati, bkz. config).
    offset = timedelta(hours=settings.display_utc_offset_hours)
    local_midnight = (now + offset).replace(hour=0, minute=0, second=0, microsecond=0) - offset

    supporters_total = func.sum(Transaction.amount).label("total")
    rows = (await db.execute(
        select(Transaction.counterparty_id, supporters_total)
        .where(received, Transaction.counterparty_id.is_not(None))
        .group_by(Transaction.counterparty_id).order_by(supporters_total.desc()).limit(5)
    )).all()
    users = await user_service.load_users_out(db, {row.counterparty_id for row in rows}, user_id)

    _, diamond_balance = await _balances(db, user_id)
    return IncomeSummary(
        diamond_balance=diamond_balance,
        today_diamonds=await total_since(local_midnight),
        week_diamonds=await total_since(now - timedelta(days=7)),
        total_diamonds=await total_since(None),
        diamond_to_coin_rate=settings.diamond_to_coin_rate,
        withdrawals_enabled=settings.withdrawals_enabled,
        top_supporters=[
            Supporter(user=users[row.counterparty_id], diamonds=row.total)
            for row in rows if row.counterparty_id in users
        ],
    )


# ── İşlem geçmişi ─────────────────────────────────────────────────────────────

async def list_transactions(
    db: AsyncSession, user_id: int, currency: str = "coin", limit: int = 50, before_id: int | None = None,
) -> list[TransactionOut]:
    """
    Kullanıcının son hareketleri, yeniden eskiye.

    Sayfalama `before_id` ile yapılır: "id'si şundan küçük olanları getir".
    ("5. sayfayı getir" yöntemi tablo büyüdükçe yavaşlar; bu yöntem hep hızlıdır.)
    """
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.currency == currency)
        .order_by(Transaction.id.desc())
        .limit(limit)
    )
    if before_id is not None:
        statement = statement.where(Transaction.id < before_id)

    return [
        TransactionOut(
            id=tx.id, type=tx.type, currency=tx.currency, label=tx.label, amount=tx.amount,
            created_at=as_utc(tx.created_at), time_label=time_ago_label(tx.created_at),
        )
        for tx in await db.scalars(statement)
    ]
