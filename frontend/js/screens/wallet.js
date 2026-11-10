// Cüzdan: "Coin" sekmesi (bakiye, paketler, geçmiş) ve "Gelir" sekmesi (hediyelerden kazanılan elmaslar)
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCoins, toast } from '../ui.js';
import { flagEmoji } from '../countries.js';

const TX_ICONS = {
  gift_sent: 'gift', gift_received: 'gift', exchange: 'flame', lucky_win: 'flame', chest_reward: 'gift',
  vip_purchase: 'crown', vip_daily: 'crown', store_purchase: 'crown', dealer_topup: 'wallet',
};

// Resmi bayiler: kullanıcı bayiye mesaj atar, ödemeyi bayiyle yapar, bayi coin'i ID'sine gönderir
function dealerSection(dealers) {
  if (!dealers.length) return '';
  return `
    <section class="section">
      <div class="section-head"><h2>Bayiden coin al</h2></div>
      <p class="demo-note">Resmi bayilerimize yaz, ödemeyi onlarla yap; coin birkaç dakikada hesabına gelir.
        <b>Yalnızca bu listedeki bayilere ödeme yap.</b> Kendini bayi diye tanıtan başka hesaplar dolandırıcıdır.</p>
      ${dealers.map((d) => `
        <div class="member-row">
          ${avatarImg(d.user, 'avatar-md')}
          <span class="member-info">
            <b>${d.user.country ? `${flagEmoji(d.user.country)} ` : ''}${esc(d.user.display_name)} <span class="dealer-badge">Resmi bayi</span></b>
            <small>${esc(d.note || `ID ${d.user.id}`)}</small>
          </span>
          <button class="btn btn-sm btn-primary" data-dealer-chat="${d.user.id}">Yaz</button>
        </div>`).join('')}
    </section>`;
}

// Hediye paketi: coinin yanında süreli bir mağaza eşyası verir
function bundleCard(p) {
  const item = p.item;
  const itemPreview = item.kind === 'frame' ? `<i class="vip-frame ${esc(item.style)}"></i>` : `<i>${item.emoji}</i>`;
  return `
    <button class="bundle" data-package="${p.id}" ${p.is_bought ? 'disabled' : ''}>
      ${p.is_one_time ? `<span class="package-tag">${p.is_bought ? 'Alındı' : 'Tek seferlik'}</span>` : ''}
      <span class="bundle-item">${itemPreview}</span>
      <span class="bundle-body">
        <b>${esc(p.title)}</b>
        <small><span class="coin coin-sm"></span> ${formatCoins(p.coins + p.bonus)} coin + ${p.item_days} gün ${esc(item.name)}</small>
      </span>
      <span class="package-price">${esc(p.price_label)}</span>
    </button>`;
}

function transactionRows(transactions, unit = '') {
  if (!transactions.length) return '<p class="member-empty">Henüz hareket yok.</p>';
  return transactions.map((t) => `
    <div class="tx">
      <span class="tx-icon tx-${t.amount > 0 ? 'in' : 'out'}">${icon(TX_ICONS[t.type] || 'wallet', 18)}</span>
      <span class="tx-body"><b>${esc(t.label)}</b><small>${esc(t.time_label)}</small></span>
      <b class="tx-amount ${t.amount > 0 ? 'is-positive' : ''}">${t.amount > 0 ? '+' : ''}${formatCoins(t.amount)}${unit}</b>
    </div>`).join('');
}

export async function renderWallet(root, { query }) {
  const [me, allPackages] = await Promise.all([api.getMe(), api.listCoinPackages()]);
  const bundles = allPackages.filter((p) => p.item);
  const packages = allPackages.filter((p) => !p.item);
  let tab = query.tab === 'income' ? 'income' : 'coins';

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/profile" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Cüzdan</h1>
      <span></span>
    </header>
    <div class="segmented wallet-tabs">
      <button data-wallet-tab="coins">🪙 Coin</button>
      <button data-wallet-tab="income">💎 Gelir</button>
    </div>
    <div id="wallet-panel"></div>`;

  const panel = root.querySelector('#wallet-panel');

  // ─── COIN ──────────────────────────────────────────────────────────────────
  async function renderCoins() {
    // Bayi listesi ve (bayiysem) kendi panelim; biri gelmezse cüzdan yine açılır
    const [dealers, myDealer] = await Promise.all([
      api.listDealers().catch(() => []),
      api.getMyDealerPanel().catch(() => null),
    ]);
    panel.innerHTML = `
      <section class="balance-card">
        <small>Coin bakiyen</small>
        <div class="balance-amount"><span class="coin coin-lg"></span><b id="balance">${formatCoins(me.coin_balance)}</b></div>
        <p>Coin ile hediye gönderebilir, özel çerçeve ve giriş efektleri alabilirsin.</p>
        <div class="balance-links">
          <a class="btn btn-sm btn-glass" href="#/store">${icon('crown', 14)} Mağaza</a>
          <a class="btn btn-sm btn-glass" href="#/vip">👑 VIP</a>
        </div>
      </section>

      ${myDealer ? `
      <a class="dealer-entry" href="#/dealer">
        <span>🪙</span>
        <span><b>Bayi paneli</b><small>Stok: ${formatCoins(myDealer.stock)} coin${myDealer.status === 'suspended' ? ' · Askıda' : ''}</small></span>
        ${icon('chevron-right', 18)}
      </a>` : ''}

      ${dealerSection(dealers)}

      ${bundles.length ? `
      <section class="section">
        <div class="section-head"><h2>Hediye Paketleri</h2></div>
        <div class="bundle-list">${bundles.map(bundleCard).join('')}</div>
      </section>` : ''}

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
    panel.querySelector('#transactions').innerHTML = transactionRows(await api.listTransactions('coin'));
  }

  // ─── GELİR (yayıncı) ───────────────────────────────────────────────────────
  async function renderIncome() {
    const [income, history, rates] = await Promise.all([
      api.getIncome(), api.listTransactions('diamond'), api.getRevenueRates().catch(() => null),
    ]);
    panel.innerHTML = `
      <section class="balance-card balance-card-diamond">
        <small>Elmas bakiyen</small>
        <div class="balance-amount"><span class="diamond-lg">💎</span><b id="diamond-balance">${formatCoins(income.diamond_balance)}</b></div>
        <p>Sana gönderilen her hediyenin değerinin <b>%${income.share_percent}</b>'i elmas olarak hesabına geçer${income.agency_name ? ` (${esc(income.agency_name)} ajansı)` : ''}.</p>
      </section>
      ${income.agency_name ? '' : `<p class="demo-note" id="agency-hint"></p>`}

      <div class="income-stats">
        <div><b>${formatCoins(income.today_diamonds)}</b><small>Bugün</small></div>
        <div><b>${formatCoins(income.week_diamonds)}</b><small>Son 7 gün</small></div>
        <div><b>${formatCoins(income.total_diamonds)}</b><small>Toplam</small></div>
      </div>

      <section class="section">
        <div class="section-head"><h2>Elmasları coine çevir</h2></div>
        <form class="exchange-form" id="exchange-form">
          <input name="diamonds" type="number" inputmode="numeric" min="1" max="${income.diamond_balance}" placeholder="Elmas miktarı" required />
          <button class="btn btn-sm btn-soft" type="button" data-exchange-all>Tümü</button>
          <button class="btn btn-primary" type="submit">Çevir</button>
        </form>
        <p class="demo-note">1 elmas = ${income.diamond_to_coin_rate} coin.
          ${income.withdrawals_enabled ? '' : 'Gerçek paraya çekim henüz açık değil.'}</p>
      </section>

      <section class="section">
        <div class="section-head"><h2>En çok destek olanlar</h2></div>
        ${income.top_supporters.length
          ? income.top_supporters.map((s, i) => `
            <a class="member-row" href="#/profile/${s.user.id}">
              <span class="supporter-rank">${i + 1}</span>
              ${avatarImg(s.user, 'avatar-md')}
              <span class="member-info"><b>${esc(s.user.display_name)}</b><small>💎 ${formatCoins(s.diamonds)}</small></span>
            </a>`).join('')
          : '<p class="member-empty">Henüz hediye almadın. Bir odada koltuğa otur, sohbete katıl!</p>'}
      </section>

      <section class="section">
        <div class="section-head"><h2>Elmas Geçmişi</h2></div>
        <div class="tx-list">${transactionRows(history, ' 💎')}</div>
      </section>`;

    const hint = panel.querySelector('#agency-hint');
    if (hint && rates) {
      hint.innerHTML = `💡 Bir ajansa katılan yayıncılar hediyenin <b>%${rates.agency_host_percent}</b>'ini alır (şu an %${rates.independent_host_percent}). <a href="#/rooms?tab=mine">Ajanslara bak</a>`;
    }
    const form = panel.querySelector('#exchange-form');
    panel.querySelector('[data-exchange-all]').addEventListener('click', () => {
      form.elements.diamonds.value = income.diamond_balance;
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const result = await api.exchangeDiamonds(Number(form.elements.diamonds.value));
        me.coin_balance = result.coin_balance;
        toast(`+${formatCoins(result.coins_added)} coin eklendi`, 'success');
        await renderIncome();
      } catch (error) {
        toast(error.code === 'insufficient_balance' ? 'Elmas bakiyen yetersiz.' : error.message, 'error');
        submit.disabled = false;
      }
    });
  }

  async function showTab(next) {
    tab = next;
    root.querySelectorAll('[data-wallet-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.walletTab === tab));
    panel.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    await (tab === 'coins' ? renderCoins() : renderIncome());
  }
  await showTab(tab);

  root.addEventListener('click', async (event) => {
    const tabButton = event.target.closest('[data-wallet-tab]');
    if (tabButton && tabButton.dataset.walletTab !== tab) return showTab(tabButton.dataset.walletTab);

    const dealerChat = event.target.closest('[data-dealer-chat]');
    if (dealerChat) {
      dealerChat.disabled = true;
      try {
        location.hash = `#/chat/${await api.openConversationWith(Number(dealerChat.dataset.dealerChat))}`;
      } catch (error) {
        toast(error.message, 'error');
        dealerChat.disabled = false;
      }
      return;
    }

    const button = event.target.closest('[data-package]');
    if (!button || button.disabled) return;
    button.disabled = true;
    button.classList.add('is-loading');
    try {
      const result = await api.purchaseCoins(Number(button.dataset.package));
      me.coin_balance = result.coin_balance;
      const balanceEl = panel.querySelector('#balance');
      balanceEl.textContent = formatCoins(result.coin_balance);
      balanceEl.classList.remove('pop');
      void balanceEl.offsetWidth;
      balanceEl.classList.add('pop');
      toast(result.item ? `+${formatCoins(result.added)} coin ve ${result.item.name} eklendi` : `+${formatCoins(result.added)} coin eklendi`, 'success');
      if (result.item) {
        const pack = allPackages.find((p) => p.id === Number(button.dataset.package));
        if (pack?.is_one_time) {
          pack.is_bought = true;
          button.outerHTML = bundleCard(pack);
        }
      }
      panel.querySelector('#transactions').innerHTML = transactionRows(await api.listTransactions('coin'));
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('is-loading');
    }
  });
}
