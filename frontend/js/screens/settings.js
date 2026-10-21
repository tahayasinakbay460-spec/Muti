// Ayarlar: şifre değiştirme, engellenen kişiler, çıkış, hesabı silme
import { api } from '../api.js';
import { APP_NAME } from '../config.js';
import { esc, icon, avatarImg, openSheet, toast } from '../ui.js';

export async function renderSettings(root) {
  const me = await api.getMe();

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/profile" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Ayarlar</h1>
      <span></span>
    </header>

    <section class="settings-card">
      ${avatarImg(me, 'avatar-md')}
      <span><b>${esc(me.display_name)}</b><small>@${esc(me.username)} • ID ${me.id}</small></span>
    </section>

    <h2 class="settings-title">Hesap ve güvenlik</h2>
    <div class="menu-list settings-list">
      ${me.is_guest
        ? `<p class="settings-note">Misafir hesaptasın. Çıkış yaparsan bu hesaba geri dönemezsin.</p>`
        : `<button data-setting="password">${icon('lock', 20)} Şifreyi değiştir</button>`}
      <button data-setting="blocked">${icon('users', 20)} Engellenen kişiler</button>
    </div>

    <h2 class="settings-title">Destek</h2>
    <div class="menu-list settings-list">
      <a href="legal.html#terms" target="_blank" rel="noopener">${icon('check', 20)} Kullanım koşulları</a>
      <a href="legal.html#privacy" target="_blank" rel="noopener">${icon('lock', 20)} Gizlilik ve KVKK aydınlatma metni</a>
    </div>

    <div class="menu-list settings-list">
      <button data-setting="logout">${icon('logout', 20)} Çıkış yap</button>
      <button data-setting="delete" class="is-danger">${icon('close', 20)} Hesabı sil</button>
    </div>
    <p class="settings-version">${esc(APP_NAME)} • Beta sürümü</p>`;

  root.addEventListener('click', async (event) => {
    const setting = event.target.closest('[data-setting]')?.dataset.setting;
    if (setting === 'password') openPasswordSheet();
    else if (setting === 'blocked') openBlockedSheet();
    else if (setting === 'delete') openDeleteSheet(me);
    else if (setting === 'logout') {
      await api.logout();
      location.hash = '#/auth';
    }
  });
}

function openPasswordSheet() {
  const sheet = openSheet(`
    <h2 class="sheet-title">Şifreyi değiştir</h2>
    <form id="password-form">
      <label class="field"><span>Mevcut şifre</span><input name="current" type="password" autocomplete="current-password" required maxlength="64" /></label>
      <label class="field"><span>Yeni şifre</span><input name="next" type="password" autocomplete="new-password" required minlength="6" maxlength="64" /></label>
      <p class="settings-note">Şifren değişince diğer cihazlardaki oturumların kapanır.</p>
      <button class="btn btn-primary btn-block" type="submit">Kaydet</button>
    </form>`);
  const form = sheet.el.querySelector('#password-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      await api.changePassword({ current_password: form.elements.current.value, new_password: form.elements.next.value });
      sheet.close();
      toast('Şifren değiştirildi', 'success');
    } catch (error) {
      toast(error.code === 'validation_error' ? 'Yeni şifre en az 6 karakter olmalı.' : error.message, 'error');
      submit.disabled = false;
    }
  });
}

async function openBlockedSheet() {
  const sheet = openSheet(`
    <h2 class="sheet-title">Engellenen kişiler</h2>
    <div class="member-list" id="blocked-list"><p class="member-empty">Yükleniyor...</p></div>`);
  const listEl = sheet.el.querySelector('#blocked-list');
  const users = await api.listBlocked();
  listEl.innerHTML = users.length
    ? users.map((u) => `
      <div class="member-row">
        ${avatarImg(u, 'avatar-md')}
        <span class="member-info"><b>${esc(u.display_name)}</b><small>@${esc(u.username)}</small></span>
        <button class="btn btn-sm btn-soft" data-unblock="${u.id}">Engeli kaldır</button>
      </div>`).join('')
    : '<p class="member-empty">Kimseyi engellemedin.</p>';
  listEl.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-unblock]');
    if (!button) return;
    button.disabled = true;
    try {
      await api.setBlocked(button.dataset.unblock, false);
      button.closest('.member-row').remove();
      toast('Engel kaldırıldı', 'success');
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  });
}

function openDeleteSheet(me) {
  const sheet = openSheet(`
    <h2 class="sheet-title">Hesabın silinsin mi?</h2>
    <p class="sheet-text">Profilin, fotoğrafların, takiplerin ve açtığın odalar kalıcı olarak kaldırılır. Kalan coin ve elmasların geri alınamaz. Bu işlem geri alınamaz.</p>
    <form id="delete-form">
      ${me.is_guest ? '' : '<label class="field"><span>Onay için şifren</span><input name="password" type="password" autocomplete="current-password" required maxlength="64" /></label>'}
      <div class="invite-actions">
        <button class="btn btn-soft" type="button" data-close>Vazgeç</button>
        <button class="btn btn-danger" type="submit">Hesabı sil</button>
      </div>
    </form>`);
  const form = sheet.el.querySelector('#delete-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await api.deleteAccount(form.elements.password?.value);
      sheet.close();
      toast('Hesabın silindi.');
      location.hash = '#/auth';
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}
