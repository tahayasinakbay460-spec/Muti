"""
Seviye sistemi.

Kullanıcı hediye gönderdikçe harcadığı her coin için 1 deneyim puanı (XP) kazanır.
Seviye XP'den hesaplanır; her seviye bir öncekinden daha fazla XP ister:

    Lv.n'ye ulaşmak için gereken toplam XP = 100 × (n - 1)²
    Lv.2 → 100   Lv.3 → 400   Lv.5 → 1.600   Lv.10 → 8.100   Lv.50 → 240.100

Kural tek yerde (bu dosyada) durur; eşikler değişirse yalnızca burası değişir.
"""
import math

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

XP_PER_LEVEL_STEP = 100
MAX_LEVEL = 99


def level_for(experience: int) -> int:
    return min(MAX_LEVEL, math.isqrt(max(0, experience) // XP_PER_LEVEL_STEP) + 1)


def experience_for(level: int) -> int:
    """Bu seviyeye ulaşmak için gereken toplam XP."""
    return XP_PER_LEVEL_STEP * (level - 1) ** 2


async def add_experience(db: AsyncSession, user_id: int, amount: int) -> tuple[int, int] | None:
    """
    Kullanıcıya XP ekler ve gerekiyorsa seviyesini yükseltir. Commit ETMEZ: hediye ile
    aynı transaction içinde çalışır. Seviye atladıysa (eski seviye, yeni seviye) döner.

    Seviye yalnızca yükselir: demo verisindeki elle verilmiş seviyeler düşmez.
    """
    if amount <= 0:
        return None
    result = await db.execute(
        update(User).where(User.id == user_id)
        .values(experience=User.experience + amount)
        .returning(User.experience, User.level)
        .execution_options(synchronize_session=False)
    )
    experience, old_level = result.one()
    new_level = level_for(experience)
    if new_level <= old_level:
        return None
    await db.execute(
        update(User).where(User.id == user_id).values(level=new_level).execution_options(synchronize_session=False)
    )
    return old_level, new_level
