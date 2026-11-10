// Sohbet saat/tarih biçimleri ve ülke yardımcıları
import assert from 'node:assert/strict';
import test from 'node:test';

import { duration, needsSeparator, separatorLabel } from '../js/chat-format.js';
import { flagEmoji } from '../js/countries.js';

const now = new Date(2026, 10, 10, 15, 0);   // 10 Kasım 2026 15:00 (yerel saat)

test('tarih çizgisi bugün, dün, bu yıl ve eski yıl için', () => {
  assert.equal(separatorLabel(new Date(2026, 10, 10, 9, 5), now), 'Bugün 09:05');
  assert.equal(separatorLabel(new Date(2026, 10, 9, 23, 59), now), 'Dün 23:59');
  assert.equal(separatorLabel(new Date(2026, 10, 7, 17, 22), now), '07.11 17:22');
  assert.equal(separatorLabel(new Date(2025, 0, 2, 8, 0), now), '02.01.2025 08:00');
});

test('tarih çizgisi ilk mesajda, gün değişince ve uzun boşlukta girer', () => {
  const at = new Date(2026, 10, 10, 12, 0);
  assert.equal(needsSeparator(null, at), true);
  assert.equal(needsSeparator(at, new Date(2026, 10, 10, 12, 4)), false);
  assert.equal(needsSeparator(at, new Date(2026, 10, 10, 12, 6)), true);
  assert.equal(needsSeparator(new Date(2026, 10, 9, 23, 58), new Date(2026, 10, 10, 0, 1)), true);
});

test('süre ve bayrak', () => {
  assert.equal(duration(67), '1:07');
  assert.equal(duration(5), '0:05');
  assert.equal(flagEmoji('TR'), '🇹🇷');
  assert.equal(flagEmoji('bad'), '🌐');
});
