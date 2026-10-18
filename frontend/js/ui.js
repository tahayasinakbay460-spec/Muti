// Ekranların ortak kullandığı küçük arayüz yardımcıları.
import { DEFAULT_AVATAR_URL } from './config.js';

// Kullanıcıdan gelen metni HTML'e basmadan önce kaçışla (XSS önlemi)
export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
  ));
}

const ICON_PATHS = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chat: '<path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1z"/><path d="M8.5 11h.01M12 11h.01M15.5 11h.01"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5 6.5-5s6.5 1.5 6.5 5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 15.3c2 .6 3.5 2 3.5 4.7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  bell: '<path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v8h14v-8M12 8v12M12 8S10.5 3 8 3a2.5 2.5 0 0 0 0 5zM12 8s1.500-5 4-5a2.5 2.5 0 0 1 0 5z"/>',
  gamepad: '<path d="M7 7h10a5 5 0 0 1 5 5v2a4 4 0 0 1-7.2 2.4L14 15h-4l-.8 1.400A4 4 0 0 1 2 14v-2a5 5 0 0 1 5-5z"/><path d="M7 10v4M5 12h4M16 11h.01M18.500 13h.01"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  'mic-off': '<path d="M9 9v2a3 3 0 0 0 5 2.200M15 9.500V6a3 3 0 0 0-5.700-1.300M5 11a7 7 0 0 0 11.500 5.400M19 11a7 7 0 0 1-.400 2.300M12 18v3M3 3l18 18"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  'chevron-left': '<path d="m15 5-7 7 7 7"/>',
  'chevron-right': '<path d="m9 5 7 7-7 7"/>',
  'chevron-down': '<path d="m5 9 7 7 7-7"/>',
  more: '<circle cx="12" cy="5" r="1.300"/><circle cx="12" cy="12" r="1.300"/><circle cx="12" cy="19" r="1.300"/>',
  share: '<path d="M14 5l7 6-7 6v-4c-5 0-8 1.500-11 6 1-7 4-10 11-10z"/>',
  smile: '<circle cx="12" cy="12" r="9"/><path d="M8.500 14.500a4.500 4.500 0 0 0 7 0M9 10h.01M15 10h.01"/>',
  send: '<path d="M21 3 3 10.500l7 2.500 2.500 7z"/><path d="m10 13 5-5"/>',
  crown: '<path d="m3 8 4.500 4L12 5l4.500 7L21 8l-2 11H5z"/>',
  check: '<path d="m5 12.500 4.500 4.500L19 7.500"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.500 6.500 4 4"/>',
  logout: '<path d="M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h5M16 8l4 4-4 4M20 12H9"/>',
  heart: '<path d="M12 20s-8-5-8-11a4.500 4.500 0 0 1 8-2.800A4.500 4.500 0 0 1 20 9c0 6-8 11-8 11z"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  flame: '<path d="M12 3c1 4 5 5.500 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z"/>',
  wallet: '<path d="M4 6h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h11"/><path d="M16 13h2"/>',
  dice: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8.500 8.500h.01M15.500 8.500h.01M12 12h.01M8.500 15.500h.01M15.500 15.500h.01"/>',
  verified: '<path d="m12 2 2.400 2.200 3.200-.400.800 3.100 2.800 1.600-1.300 3 1.300 3-2.800 1.600-.800 3.100-3.200-.400L12 21l-2.400-2.200-3.200.400-.800-3.100-2.800-1.600 1.300-3-1.300-3 2.800-1.600.800-3.100 3.200.400z" fill="currentColor" stroke="none"/><path d="m8.500 12 2.500 2.500 4.500-5" stroke="#fff"/>',
};

export function icon(name, size = 22) {
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.800" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON_PATHS[name] || ''}</svg>`;
}

// 1200 -> 1.2K
export function formatCount(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace('.0', '')}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace('.0', '')}K`;
  return String(n);
}

// 12450 -> 12.450
export function formatCoins(n) {
  return Number(n).toLocaleString('tr-TR');
}

export function avatarImg(user, className = '') {
  return `<img class="avatar ${className}" src="${esc(user.avatar_url || DEFAULT_AVATAR_URL)}" alt="${esc(user.display_name)}" loading="lazy" />`;
}

// "26 • Ankara" — yaşını/şehrini girmemiş kullanıcıda boş kalan parça atlanır
export function joinParts(parts, separator = ' • ') {
  return parts.filter(Boolean).join(separator);
}

export function vipBadge(level) {
  if (!level) return '';
  return `<span class="badge badge-vip">${icon('crown', 12)} VIP ${level}</span>`;
}

export function levelBadge(level) {
  return `<span class="badge badge-level">Lv.${level}</span>`;
}

export function toast(message, type = 'info') {
  const root = document.getElementById('toast-root');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.classList.add('is-leaving'), 2200);
  setTimeout(() => el.remove(), 2600);
}

// Alttan açılan panel (bottom sheet). close() fonksiyonu ile kapatılır.
export function openSheet(innerHtml, { className = '' } = {}) {
  const root = document.getElementById('overlay-root');
  const backdrop = document.createElement('div');
  backdrop.className = 'sheet-backdrop';
  backdrop.innerHTML = `<div class="sheet ${className}" role="dialog" aria-modal="true"><div class="sheet-handle"></div>${innerHtml}</div>`;
  root.appendChild(backdrop);
  requestAnimationFrame(() => backdrop.classList.add('is-open'));

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    backdrop.classList.remove('is-open');
    setTimeout(() => backdrop.remove(), 250);
  };
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop || event.target.closest('[data-close]')) close();
  });
  return { el: backdrop.querySelector('.sheet'), close };
}

export function closeAllSheets() {
  document.getElementById('overlay-root').innerHTML = '';
}
