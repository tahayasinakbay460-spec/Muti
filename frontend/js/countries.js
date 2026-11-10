// Ülke yardımcıları: bayrak, Türkçe ad, tarayıcıdan tahmin. Ülke backend'de ISO iki harfli kod ("TR").

// Profilde seçilebilecek ülkeler. Liste kısa tutuldu: kullanıcılarımızın çoğunun geldiği bölge.
export const COUNTRY_CODES = [
  'TR', 'AZ', 'DE', 'NL', 'BE', 'FR', 'AT', 'CH', 'GB', 'SE', 'DK', 'NO', 'IT', 'ES', 'US', 'CA',
  'RU', 'UA', 'GE', 'KZ', 'UZ', 'TM', 'KG', 'IR', 'IQ', 'SY', 'LB', 'JO', 'SA', 'AE', 'KW', 'QA',
  'BH', 'OM', 'EG', 'LY', 'TN', 'DZ', 'MA', 'CY', 'GR', 'BG', 'RO', 'BA', 'MK', 'AL', 'XK',
];

let displayNames = null;
try {
  displayNames = new Intl.DisplayNames(['tr'], { type: 'region' });
} catch {
  // Çok eski tarayıcı: ad yerine kod gösterilir
}

// "TR" → 🇹🇷. Bayrak emojisi iki "bölge harfi" karakterinden oluşur.
// Not: Windows'taki tarayıcılar bayrak emojisi çizmez, harfleri gösterir; bu yüzden yanında ad da yazılır.
export function flagEmoji(code) {
  if (!/^[A-Z]{2}$/.test(code || '')) return '🌐';
  return String.fromCodePoint(...[...code].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

export function countryName(code) {
  try {
    return displayNames?.of(code) || code;
  } catch {
    return code;
  }
}

// Kayıtta varsayılan ülke: tarayıcı dilinin bölgesi ("tr-TR" → "TR"). Bölge yoksa dilden tahmin.
const LANGUAGE_COUNTRY = { tr: 'TR', az: 'AZ', de: 'DE', ar: 'SA', ru: 'RU', fa: 'IR', nl: 'NL', fr: 'FR', en: 'GB' };
export function guessCountry() {
  for (const tag of navigator.languages || [navigator.language || '']) {
    const [language, region] = tag.split('-');
    if (region && /^[A-Za-z]{2}$/.test(region)) return region.toUpperCase();
    if (LANGUAGE_COUNTRY[language?.toLowerCase()]) return LANGUAGE_COUNTRY[language.toLowerCase()];
  }
  return null;
}
