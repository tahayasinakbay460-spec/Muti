// "Oda Aç" paneli
import { api } from '../api.js';
import { ROOM_CATEGORIES } from '../config.js';
import { openSheet, toast } from '../ui.js';

export function openCreateRoomSheet() {
  const categories = ROOM_CATEGORIES.filter((c) => c.id !== 'for_you');
  let category = categories[0].id;

  const sheet = openSheet(`
    <h2 class="sheet-title">Oda Aç</h2>
    <form id="create-room-form">
      <label class="field">
        <span>Oda adı</span>
        <input name="title" maxlength="30" placeholder="Örn. Gece Muhabbeti" required />
      </label>
      <div class="field">
        <span>Kategori</span>
        <div class="chips chips-wrap">
          ${categories.map((c, i) => `<button type="button" class="chip ${i === 0 ? 'is-active' : ''}" data-chip="${c.id}">${c.label}</button>`).join('')}
        </div>
      </div>
      <button class="btn btn-primary btn-block" type="submit">Odayı Başlat</button>
    </form>`);

  sheet.el.querySelector('.chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-chip]');
    if (!chip) return;
    category = chip.dataset.chip;
    sheet.el.querySelectorAll('.chip').forEach((c) => c.classList.toggle('is-active', c === chip));
  });

  sheet.el.querySelector('#create-room-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const title = new FormData(event.target).get('title');
    try {
      const room = await api.createRoom({ title, category });
      sheet.close();
      location.hash = `#/room/${room.id}`;
    } catch (error) {
      toast(error.message, 'error');
    }
  });

  setTimeout(() => sheet.el.querySelector('input').focus(), 300);
}
