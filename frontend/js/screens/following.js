// Takip ettiğim odalar (ana sayfadaki "Takip" sekmesi)
import { api } from '../api.js';
import { icon } from '../ui.js';
import { roomRow } from './components.js';

export async function renderFollowing(root) {
  const rooms = await api.listFollowedRooms();

  root.innerHTML = `
    <header class="topbar topbar-solid">
      <a class="icon-btn" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title page-title-center">Takip Ettiğim Odalar</h1>
      <span class="icon-btn-spacer"></span>
    </header>
    ${rooms.length
      ? `<div class="room-list following-list">${rooms.map(roomRow).join('')}</div>`
      : `<div class="empty">
          <p>Henüz bir oda takip etmiyorsun.<br />Bir odaya girip <b>Takip Et</b>'e dokunduğunda burada görünür.</p>
          <a class="btn btn-primary" href="#/explore">Odaları keşfet</a>
        </div>`}`;
}
