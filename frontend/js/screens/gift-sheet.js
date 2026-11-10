// Hediye paneli: odada ve özel sohbette aynı panel kullanılır.
// Panel yalnızca seçimi toplar; parayı harcayan isteği çağıran ekran yapar (`send`).
import { esc, avatarImg, formatCoins, toast, openSheet } from '../ui.js';

const QUANTITIES = [1, 5, 10, 99];

/**
 * receivers: alıcı seçilebilecek kişiler (sohbette tek kişi, seçim satırı gizlenir)
 * send({ receiverId, giftId, quantity }) → { coin_balance, lucky_win, lucky_multiplier, closeSheet? }
 */
export function openGiftSheet({ gifts, balance, receivers, preselectedReceiverId, send }) {
  let receiverId = preselectedReceiverId || receivers[0].id;
  let giftId = gifts[0].id;
  let quantity = 1;
  let isSending = false;

  const sheet = openSheet(`
    <div class="gift-sheet-head">
      <h2 class="sheet-title">Hediye Gönder</h2>
      <a class="coin-pill" href="#/wallet"><span class="coin"></span><b id="gift-balance">${formatCoins(balance)}</b><span class="coin-plus">+</span></a>
    </div>
    ${receivers.length > 1 ? `
      <div class="receiver-row" id="receivers">
        ${receivers.map((u) => `<button class="receiver ${u.id === receiverId ? 'is-active' : ''}" data-receiver="${u.id}">${avatarImg(u, 'avatar-md')}<small>${esc(u.display_name)}</small></button>`).join('')}
      </div>` : `<p class="gift-sheet-to">${avatarImg(receivers[0], 'avatar-xs')} <b>${esc(receivers[0].display_name)}</b> için</p>`}
    <div class="gift-grid" id="gift-grid">
      ${gifts.map((g) => `
        <button class="gift-item ${g.id === giftId ? 'is-active' : ''}" data-gift="${g.id}">
          ${g.is_lucky ? '<span class="lucky-tag">Şanslı</span>' : ''}<i>${g.emoji}</i><b>${esc(g.name)}</b><small><span class="coin coin-sm"></span>${formatCoins(g.price)}</small>
        </button>`).join('')}
    </div>
    <div class="gift-sheet-foot">
      <div class="quantity" id="quantities">
        ${QUANTITIES.map((q) => `<button class="${q === quantity ? 'is-active' : ''}" data-quantity="${q}">x${q}</button>`).join('')}
      </div>
      <button class="btn btn-primary" id="gift-send">Gönder</button>
    </div>`, { className: 'sheet-dark' });

  const select = (selector, attr, value) => sheet.el.querySelectorAll(selector).forEach((el) => el.classList.toggle('is-active', el.dataset[attr] === String(value)));

  sheet.el.addEventListener('click', async (event) => {
    const receiver = event.target.closest('[data-receiver]');
    const giftBtn = event.target.closest('[data-gift]');
    const quantityBtn = event.target.closest('[data-quantity]');
    if (receiver) { receiverId = Number(receiver.dataset.receiver); select('[data-receiver]', 'receiver', receiverId); }
    if (giftBtn) { giftId = Number(giftBtn.dataset.gift); select('[data-gift]', 'gift', giftId); }
    if (quantityBtn) { quantity = Number(quantityBtn.dataset.quantity); select('[data-quantity]', 'quantity', quantity); }

    if (event.target.closest('#gift-send') && !isSending) {
      isSending = true;
      try {
        const result = await send({ receiverId, giftId, quantity, gift: gifts.find((g) => g.id === giftId) });
        sheet.el.querySelector('#gift-balance').textContent = formatCoins(result.coin_balance);
        if (result.lucky_win) toast(`🍀 x${result.lucky_multiplier} yakaladın! +${formatCoins(result.lucky_win)} coin`, 'success');
        if (result.closeSheet) sheet.close();
      } catch (error) {
        toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.' : error.message, 'error');
      } finally {
        isSending = false;
      }
    }
  });
  return sheet;
}
