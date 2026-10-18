// Cüzdan: bakiye, coin paketleri ve işlem geçmişi
import { api } from '../api.js';
import { esc, icon, formatCoins, toast } from '../ui.js';

export async function renderWallet(root) {
  const [me, packages] = await Promise.all([api.getMe(), api.listCoinPackages()]);

  root.innerHTML = `
    <header class="topbar"><h1 class="page-title">Cüzdan</h1></header>

    <section class="balance-card">
      <small>Coin bakiyen</small>
      <div class="balance-amount"><span class="coin coin-lg"></span><b id="balance">${formatCoins(me.coin_balance)}</b></div>
      <p>Coin ile hediye gönderebilir, özel çerçeve ve giriş efektleri alabilirsin.</p>
    </section>

    <section class="section">
      <div class="section-head"><h2>Coin Paketleri</h2></div>
      <div class="package-grid">
        ${packages.map((p) => `
          <button class="package ${p.is_popular || p.is_best_value ? 'is-featured' : ''}" data-package="${p.id}">
            ${p.is_popular ? '<span class="package-tag">Popüler</span>' : ''}
            ${p.is_best_value ? '<span class="package-tag">En Avantajlı</span>' : ''}
            <span class="coin coin-lg"></span>
            <b>${formatCoins(p.coins)}</b>
            <small>${p.bonus ? `+${formatCoins(p.bonus)} bonus` : '&nbsp;'}</small>
            <span class="package-price">${esc(p.price_label)}</span>
          </button>`).join('')}
      </div>
      <p class="demo-note">Demo sürümü: gerçek ödeme alınmaz, coinler test amaçlı eklenir.</p>
    </section>

    <section class="section">
      <div class="section-head"><h2>İşlem Geçmişi</h2></div>
      <div class="tx-list" id="transactions"></div>
    </section>`;

  const balanceEl = root.querySelector('#balance');
  const txEl = root.querySelector('#transactions');

  async function loadTransactions() {
    const transactions = await api.listTransactions();
    txEl.innerHTML = transactions.map((t) => `
      <div class="tx">
        <span class="tx-icon tx-${t.amount > 0 ? 'in' : 'out'}">${icon(t.type === 'gift_sent' ? 'gift' : 'wallet', 18)}</span>
        <span class="tx-body"><b>${esc(t.label)}</b><small>${esc(t.time_label)}</small></span>
        <b class="tx-amount ${t.amount > 0 ? 'is-positive' : ''}">${t.amount > 0 ? '+' : ''}${formatCoins(t.amount)}</b>
      </div>`).join('');
  }
  await loadTransactions();

  root.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-package]');
    if (!button || button.disabled) return;
    button.disabled = true;
    button.classList.add('is-loading');
    try {
      const result = await api.purchaseCoins(Number(button.dataset.package));
      balanceEl.textContent = formatCoins(result.coin_balance);
      balanceEl.classList.remove('pop');
      void balanceEl.offsetWidth;
      balanceEl.classList.add('pop');
      toast(`+${formatCoins(result.added)} coin eklendi`, 'success');
      await loadTransactions();
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('is-loading');
    }
  });
}
