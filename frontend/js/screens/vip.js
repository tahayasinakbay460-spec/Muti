// VIP üyelik: durum, günlük ödül ve üç kademe (Gümüş, Altın, Elmas)
import { api } from '../api.js';
import { esc, icon, formatCoins, toast, openSheet } from '../ui.js';

const TIER_CLASSES = { 1: 'vip-silver', 2: 'vip-gold', 3: 'vip-diamond' };
const daysLeft = (iso) => Math.max(1, Math.ceil((new Date(iso) - Date.now()) / 86400000));

function statusCard(status) {
  if (!status.level) {
    return `
      <section class="vip-status">
        <span class="vip-status-icon">👑</span>
        <div><b>Henüz VIP değilsin</b><small>Üye ol: özel rozet, çerçeve, giriş efekti ve her gün coin.</small></div>
      </section>`;
  }
  const tier = status.tiers.find((t) => t.level === status.level);
  return `
    <section class="vip-status ${TIER_CLASSES[status.level]}">
      <span class="vip-status-icon">👑</span>
      <div>
        <b>VIP ${status.level} · ${esc(tier.name)}</b>
        <small>${status.expires_at ? `${daysLeft(status.expires_at)} gün kaldı` : 'Süresiz üyelik'}</small>
      </div>
      <button class="btn btn-sm ${status.daily_reward_available ? 'btn-primary' : 'btn-soft'}" data-action="daily" ${status.daily_reward_available ? '' : 'disabled'}>
        ${status.daily_reward_available ? `+${formatCoins(tier.daily_coins)} al` : 'Yarın tekrar'}
      </button>
    </section>`;
}

function tierButton(tier, status) {
  if (status.level > tier.level) return '<button class="btn btn-soft btn-block" disabled>Daha yüksek üyeliğin var</button>';
  if (status.level === tier.level && !status.expires_at) return '<button class="btn btn-soft btn-block" disabled>Süresiz üyesin</button>';
  const label = status.level === tier.level ? '30 gün uzat' : status.level ? 'Yükselt' : 'Üye ol';
  return `<button class="btn btn-primary btn-block" data-tier="${tier.level}">${label} · <span class="coin coin-sm"></span> ${formatCoins(tier.price_30d)}</button>`;
}

function tierCard(tier, status) {
  return `
    <article class="vip-tier ${TIER_CLASSES[tier.level]} ${status.level === tier.level ? 'is-current' : ''}">
      <header>
        <b>VIP ${tier.level}</b><span>${esc(tier.name)}</span>
        ${status.level === tier.level ? '<small>Üyeliğin</small>' : ''}
      </header>
      <div class="vip-items">
        ${tier.items.map((item) => `<span title="${esc(item.name)}">${item.kind === 'frame' ? `<i class="vip-frame ${esc(item.style)}"></i>` : item.emoji}</span>`).join('')}
      </div>
      <ul>${tier.perks.map((perk) => `<li>${icon('check', 14)} ${esc(perk)}</li>`).join('')}</ul>
      ${tierButton(tier, status)}
    </article>`;
}

export async function renderVip(root) {
  let [status, me] = await Promise.all([api.getVip(), api.getMe()]);

  function render() {
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/store" aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">VIP</h1>
        <a class="coin-pill topbar-actions" href="#/wallet"><span class="coin"></span><b>${formatCoins(me.coin_balance)}</b><span class="coin-plus">+</span></a>
      </header>
      ${statusCard(status)}
      <div class="vip-tiers">${status.tiers.map((tier) => tierCard(tier, status)).join('')}</div>
      <p class="demo-note">Demo sürümü: üyelik coinle alınır. Mobil uygulamada mağaza aboneliği olacak.</p>`;
  }
  render();

  function confirmPurchase(tier) {
    const sheet = openSheet(`
      <h2 class="sheet-title">VIP ${tier.level} · ${esc(tier.name)}</h2>
      <p class="store-detail-note">30 günlük üyelik için <b>${formatCoins(tier.price_30d)} coin</b> harcanacak.
        ${status.level && status.level < tier.level ? 'Yükseltme hemen başlar, 30 gün yeniden sayılır.' : ''}</p>
      <div class="store-buy">
        <button class="btn btn-soft" data-close>Vazgeç</button>
        <button class="btn btn-primary" data-confirm>Onayla</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.querySelector('[data-confirm]').addEventListener('click', async (event) => {
      event.currentTarget.disabled = true;
      try {
        const result = await api.purchaseVip(tier.level);
        status = result.status;
        me.coin_balance = result.coin_balance;
        sheet.close();
        render();
        toast(`👑 VIP ${tier.level} oldun! Eşyaların takıldı.`, 'success');
      } catch (error) {
        sheet.close();
        toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.' : error.message, 'error');
      }
    });
  }

  root.addEventListener('click', async (event) => {
    const tierBtn = event.target.closest('[data-tier]');
    if (tierBtn) return confirmPurchase(status.tiers.find((t) => t.level === Number(tierBtn.dataset.tier)));

    const daily = event.target.closest('[data-action="daily"]');
    if (!daily) return;
    daily.disabled = true;
    try {
      const result = await api.claimVipDailyReward();
      me.coin_balance = result.coin_balance;
      status = await api.getVip();
      render();
      toast(`+${formatCoins(result.coins)} coin günlük VIP ödülü`, 'success');
    } catch (error) {
      toast(error.message, 'error');
      daily.disabled = false;
    }
  });
}
