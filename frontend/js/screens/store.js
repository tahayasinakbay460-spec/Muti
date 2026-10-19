// Mağaza: avatar çerçevesi, odaya giriş efekti ve sohbet balonu satın alma ve takma
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet } from '../ui.js';

const TABS = [
  { id: 'frame', label: 'Çerçeve' },
  { id: 'entry_effect', label: 'Giriş Efekti' },
  { id: 'chat_bubble', label: 'Sohbet Balonu' },
];

const daysLeft = (iso) => Math.max(1, Math.ceil((new Date(iso) - Date.now()) / 86400000));

// Eşyanın nasıl görüneceği: çerçeve avatarın etrafında, efekt şerit olarak, balon örnek mesajla
function preview(item, me, size = '') {
  if (item.kind === 'frame') return `<span class="frame-preview ${size} ${esc(item.style)}">${avatarImg(me)}</span>`;
  if (item.kind === 'entry_effect') return `<span class="store-entry ${size} ${esc(item.style)}"><i>${item.emoji}</i></span>`;
  return `<span class="store-bubble ${size}"><span class="chat-bubble ${esc(item.style)}">Selam! 👋</span></span>`;
}

function itemCard(item, me) {
  let status = `<small class="store-price"><span class="coin coin-sm"></span>${formatCoins(item.price_7d)} / 7 gün</small>`;
  if (item.is_equipped) status = '<small class="store-on">Kullanılıyor</small>';
  else if (item.is_owned) status = `<small>${daysLeft(item.owned_until)} gün kaldı</small>`;
  return `
    <button class="store-item ${item.is_equipped ? 'is-active' : ''}" data-item="${item.id}">
      ${item.vip_level_required ? `<span class="store-vip">VIP ${item.vip_level_required}+</span>` : ''}
      ${preview(item, me)}
      <b>${esc(item.name)}</b>
      ${status}
    </button>`;
}

export async function renderStore(root, { query }) {
  let me = await api.getMe();
  let tab = TABS.some((t) => t.id === query.tab) ? query.tab : 'frame';
  let items = [];

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/profile" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Mağaza</h1>
      <a class="coin-pill topbar-actions" href="#/wallet"><span class="coin"></span><b id="store-balance">${formatCoins(me.coin_balance)}</b><span class="coin-plus">+</span></a>
    </header>
    <a class="vip-promo" href="#/vip">
      <span>👑</span>
      <span><b>${me.vip_level ? `VIP ${me.vip_level} üyesisin` : 'VIP ol, öne çık'}</b><small>Özel çerçeve, giriş efekti ve her gün coin</small></span>
      ${icon('chevron-right', 18)}
    </a>
    <div class="segmented segmented-3 store-tabs">
      ${TABS.map((t) => `<button data-tab="${t.id}">${t.label}</button>`).join('')}
    </div>
    <div class="store-grid" id="store-grid"></div>
    <p class="demo-note">Eşyalar süreli satılır. Süre dolunca eşya otomatik olarak çıkar.</p>`;

  const gridEl = root.querySelector('#store-grid');
  const setBalance = (balance) => {
    me.coin_balance = balance;
    root.querySelector('#store-balance').textContent = formatCoins(balance);
  };

  async function load() {
    root.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === tab));
    gridEl.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    items = await api.listStoreItems(tab);
    gridEl.innerHTML = items.map((item) => itemCard(item, me)).join('');
  }

  function openItemSheet(item) {
    const needsVip = item.vip_level_required > (me.vip_level || 0);
    const sheet = openSheet(`
      <div class="store-detail">
        ${preview(item, me, 'is-large')}
        <h2 class="sheet-title">${esc(item.name)}</h2>
        <p class="store-detail-note">${item.is_owned ? `Sende · ${daysLeft(item.owned_until)} gün kaldı` : 'Satın alınca hemen takılır.'}</p>
      </div>
      ${item.is_owned ? `<button class="btn btn-soft btn-block" data-equip="${item.is_equipped ? 'off' : 'on'}">${item.is_equipped ? 'Çıkar' : 'Kullan'}</button>` : ''}
      ${needsVip
        ? `<a class="btn btn-primary btn-block" href="#/vip">VIP ${item.vip_level_required} ve üstüne özel · VIP ol</a>`
        : `<div class="store-buy">
            <button class="btn btn-soft" data-days="7"><span>${item.is_owned ? '+7 gün' : '7 gün'}</span><b><span class="coin coin-sm"></span>${formatCoins(item.price_7d)}</b></button>
            <button class="btn btn-primary" data-days="30"><span>${item.is_owned ? '+30 gün' : '30 gün'}</span><b><span class="coin coin-sm"></span>${formatCoins(item.price_30d)}</b></button>
          </div>`}`, { className: 'sheet-dark' });

    sheet.el.addEventListener('click', async (event) => {
      const buy = event.target.closest('[data-days]');
      const equip = event.target.closest('[data-equip]');
      if (!buy && !equip) return;
      const button = buy || equip;
      button.disabled = true;
      try {
        if (buy) {
          const result = await api.purchaseStoreItem(item.id, Number(buy.dataset.days));
          setBalance(result.coin_balance);
          toast(`${item.name} alındı ve takıldı`, 'success');
        } else {
          await api.equipStoreItem(item.id, equip.dataset.equip === 'on');
          toast(equip.dataset.equip === 'on' ? `${item.name} takıldı` : `${item.name} çıkarıldı`, 'success');
        }
        sheet.close();
        me = await api.getMe();
        await load();
      } catch (error) {
        toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.' : error.message, 'error');
        button.disabled = false;
      }
    });
  }

  root.addEventListener('click', (event) => {
    const tabButton = event.target.closest('[data-tab]');
    if (tabButton && tabButton.dataset.tab !== tab) {
      tab = tabButton.dataset.tab;
      load();
      return;
    }
    const card = event.target.closest('[data-item]');
    if (card) openItemSheet(items.find((i) => i.id === Number(card.dataset.item)));
  });

  await load();
}
