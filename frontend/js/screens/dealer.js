// Bayi paneli (#/dealer): yalnızca resmi coin bayileri görür.
// Bayi bizden toptan stok alır (panel yükler), burada kullanıcı ID + miktar girip coin gönderir.
// Kurallar sunucuda: günlük satış sınırı, misafire satış yok, askıdaki bayi satamaz.
import { api, newIdempotencyKey } from '../api.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet, timeAgo } from '../ui.js';

const ERRORS = {
  insufficient_balance: 'Stoğun yetersiz. Stok için müşteri hizmetlerine yaz.',
  dealer_daily_limit: null,   // sunucunun mesajı kalan miktarı söylüyor
  buyer_is_guest: 'Bu kişi misafir hesapla giriyor. Önce hesabını kaydetmesini iste.',
  cannot_sell_to_self: 'Kendine coin gönderemezsin.',
  not_found: 'Bu ID ile bir kullanıcı yok.',
};

function salesRows(sales) {
  if (!sales.length) return '<p class="member-empty">Henüz satış yok.</p>';
  return sales.map((s) => `
    <div class="member-row">
      ${s.user ? avatarImg(s.user, 'avatar-sm') : '<span class="avatar avatar-sm"></span>'}
      <span class="member-info"><b>${esc(s.user?.display_name || 'Silinmiş hesap')}</b><small>ID ${s.user?.id ?? '-'} · ${timeAgo(s.created_at)}</small></span>
      <b class="tx-amount">-${formatCoins(s.coins)}</b>
    </div>`).join('');
}

export async function renderDealer(root) {
  let panel;
  try {
    panel = await api.getMyDealerPanel();
  } catch (error) {
    root.innerHTML = `
      <header class="topbar"><a class="icon-btn icon-btn-plain" href="#/wallet" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Bayi paneli</h1><span></span></header>
      <p class="member-empty">${error.code === 'not_dealer' ? 'Bu sayfa yalnızca resmi coin bayilerine açık.' : esc(error.message)}</p>`;
    return;
  }

  function render() {
    const left = Math.max(0, panel.daily_limit - panel.sold_today);
    const percent = Math.min(100, Math.round((panel.sold_today * 100) / panel.daily_limit));
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/wallet" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Bayi paneli</h1>
        <span></span>
      </header>
      ${panel.status === 'suspended' ? '<p class="dealer-warning">Bayiliğin askıya alındı. Satış yapamazsın; müşteri hizmetleriyle görüş.</p>' : ''}
      <section class="balance-card">
        <small>Satılabilir stok</small>
        <div class="balance-amount"><span class="coin coin-lg"></span><b>${formatCoins(panel.stock)}</b></div>
        <p>Bugün ${formatCoins(panel.sold_today)} / ${formatCoins(panel.daily_limit)} coin sattın · kalan ${formatCoins(left)}</p>
        <div class="task-bar"><i style="width:${percent}%"></i></div>
      </section>

      <section class="section">
        <div class="section-head"><h2>Coin gönder</h2></div>
        <form class="dealer-form" id="sale-form">
          <label>Kullanıcı ID<input name="user_id" type="number" inputmode="numeric" min="1" required placeholder="Ör. 102938" /></label>
          <div class="dealer-buyer" id="buyer"></div>
          <label>Coin<input name="coins" type="number" inputmode="numeric" min="1" max="${Math.min(panel.stock, left)}" required placeholder="Ör. 1000" /></label>
          <button class="btn btn-primary btn-block" type="submit" ${panel.status === 'suspended' ? 'disabled' : ''}>Devam</button>
        </form>
        <p class="demo-note">Ödemeyi aldıktan sonra gönder. Gönderilen coin geri alınamaz.</p>
      </section>

      <section class="section">
        <div class="section-head"><h2>Son satışlar</h2></div>
        <div>${salesRows(panel.recent_sales)}</div>
      </section>`;

    const form = root.querySelector('#sale-form');
    const buyerEl = root.querySelector('#buyer');
    let buyer = null;
    // ID yazılınca kişinin adı ve fotoğrafı görünür: yanlış kişiye göndermeyi önler
    form.elements.user_id.addEventListener('change', async () => {
      buyer = null;
      const id = Number(form.elements.user_id.value);
      if (!id) return void (buyerEl.innerHTML = '');
      try {
        buyer = await api.getUser(id);
        buyerEl.innerHTML = `${avatarImg(buyer, 'avatar-sm')} <b>${esc(buyer.display_name)}</b> <small>@${esc(buyer.username)}</small>${buyer.is_guest ? ' <small class="is-danger">misafir hesap</small>' : ''}`;
      } catch {
        buyerEl.innerHTML = '<small class="is-danger">Bu ID ile kullanıcı yok.</small>';
      }
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!buyer || buyer.id !== Number(form.elements.user_id.value)) {
        form.elements.user_id.dispatchEvent(new Event('change'));
        return toast('Önce kullanıcı ID\'sini kontrol et.', 'error');
      }
      confirmSale(buyer, Number(form.elements.coins.value));
    });
  }

  // Onay penceresi: anahtar pencere açılınca bir kez üretilir. "Gönder"e iki kez basılsa ya da ağ
  // isteği tekrarlasa bile sunucu aynı anahtarı görür ve ikinci kez satmaz.
  function confirmSale(buyer, coins) {
    const key = newIdempotencyKey();
    const sheet = openSheet(`
      <div class="sheet-body">
        <h2>Coin gönderilsin mi?</h2>
        <div class="member-row">${avatarImg(buyer, 'avatar-md')}<span class="member-info"><b>${esc(buyer.display_name)}</b><small>ID ${buyer.id}</small></span></div>
        <p class="balance-amount"><span class="coin coin-lg"></span><b>${formatCoins(coins)}</b></p>
        <button class="btn btn-primary btn-block" data-confirm>Gönder</button>
        <button class="btn btn-soft btn-block" data-close>Vazgeç</button>
      </div>`);
    const button = sheet.el.querySelector('[data-confirm]');
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await api.sellCoins(buyer.id, coins, key);
        panel = { ...panel, stock: result.stock, sold_today: result.sold_today,
          recent_sales: [result.sale, ...panel.recent_sales.filter((s) => s.id !== result.sale.id)] };
        sheet.close();
        toast(`${buyer.display_name} hesabına ${formatCoins(coins)} coin gönderildi`, 'success');
        render();
      } catch (error) {
        toast(ERRORS[error.code] || error.message, 'error');
        button.disabled = false;
      }
    });
  }

  render();
}
