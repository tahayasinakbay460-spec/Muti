// Sohbet ekranının saat ve tarih biçimleri (saf fonksiyonlar; tarayıcısız test edilir: tests/chat-format.test.js).
// Saat cihazın kendi saat dilimine göre gösterilir; sunucu zamanı UTC gönderir (created_at).

// Bu kadar dakikadan uzun boşlukta mesajların arasına yeniden tarih çizgisi girer
const SEPARATOR_GAP_MS = 5 * 60 * 1000;

const pad = (n) => String(n).padStart(2, '0');
const sameDay = (a, b) => a.toDateString() === b.toDateString();

// "17:05"
export const clock = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`;

// Saniye → "1:07" (sesli mesaj ve arama süresi)
export const duration = (seconds) => `${Math.floor(seconds / 60)}:${pad(seconds % 60)}`;

// Tarih çizgisi: bugün "Bugün 17:22", dün "Dün 17:22", bu yıl "07.11 17:22", daha eski "07.11.2025 17:22"
export function separatorLabel(date, now = new Date()) {
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, now)) return `Bugün ${clock(date)}`;
  if (sameDay(date, yesterday)) return `Dün ${clock(date)}`;
  const day = `${pad(date.getDate())}.${pad(date.getMonth() + 1)}`;
  return `${date.getFullYear() === now.getFullYear() ? day : `${day}.${date.getFullYear()}`} ${clock(date)}`;
}

// İki mesaj arasına tarih çizgisi girmeli mi? İlk mesajın üstünde her zaman; sonra gün değişince
// ya da iki mesaj arasında uzun boşluk varsa (WhatsApp / Instagram gibi).
export function needsSeparator(previous, next) {
  if (!previous) return true;
  return !sameDay(previous, next) || next - previous > SEPARATOR_GAP_MS;
}
