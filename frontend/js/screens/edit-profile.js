// "Profili Düzenle" paneli: avatar, kapak, görünen ad, hakkımda, yaş, şehir
import { api } from '../api.js';
import { esc, openSheet, toast } from '../ui.js';

// Kaydedilince onSaved(güncel kullanıcı) çağrılır; ekran kendini yeniden çizer.
export async function openEditProfileSheet(user, onSaved) {
  const options = await api.getMediaOptions();
  let avatarUrl = user.avatar_url;
  let coverUrl = user.cover_url;

  const sheet = openSheet(`
    <h2 class="sheet-title">Profili Düzenle</h2>
    <form id="edit-profile-form">
      <div class="field">
        <span>Avatar</span>
        <div class="picker-row" data-picker="avatar">
          ${options.avatars.map((url) => `
            <button type="button" class="picker-avatar ${url === avatarUrl ? 'is-active' : ''}" data-url="${esc(url)}">
              <img src="${esc(url)}" alt="" loading="lazy" />
            </button>`).join('')}
        </div>
      </div>
      <div class="field">
        <span>Kapak</span>
        <div class="picker-row" data-picker="cover">
          ${options.covers.map((url) => `
            <button type="button" class="picker-cover ${url === coverUrl ? 'is-active' : ''}" data-url="${esc(url)}">
              <img src="${esc(url)}" alt="" loading="lazy" />
            </button>`).join('')}
        </div>
      </div>
      <label class="field">
        <span>Görünen ad</span>
        <input name="display_name" maxlength="40" value="${esc(user.display_name)}" required />
      </label>
      <label class="field">
        <span>Hakkımda</span>
        <textarea name="bio" maxlength="300" rows="3" placeholder="Kendinden biraz bahset...">${esc(user.bio)}</textarea>
      </label>
      <div class="field-row">
        <label class="field">
          <span>Yaş</span>
          <input name="age" type="number" inputmode="numeric" min="13" max="99" value="${user.age ?? ''}" />
        </label>
        <label class="field">
          <span>Şehir</span>
          <input name="city" maxlength="60" value="${esc(user.city || '')}" placeholder="Örn. İzmir" />
        </label>
      </div>
      <button class="btn btn-primary btn-block" type="submit">Kaydet</button>
    </form>`);

  // Avatar/kapak seçimi: tıklanan görsel seçili olur. Açılışta seçili olan ortaya kaydırılır.
  sheet.el.querySelectorAll('[data-picker]').forEach((row) => {
    const active = row.querySelector('.is-active');
    if (active) row.scrollLeft = active.offsetLeft - (row.clientWidth - active.clientWidth) / 2;
    row.addEventListener('click', (event) => {
      const item = event.target.closest('[data-url]');
      if (!item) return;
      row.querySelectorAll('[data-url]').forEach((el) => el.classList.toggle('is-active', el === item));
      if (row.dataset.picker === 'avatar') avatarUrl = item.dataset.url;
      else coverUrl = item.dataset.url;
    });
  });

  const form = sheet.el.querySelector('#edit-profile-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const age = data.get('age').trim();
    const next = {
      display_name: data.get('display_name').trim(),
      bio: data.get('bio').trim(),
      age: age ? Number(age) : null,
      city: data.get('city').trim() || null,
      avatar_url: avatarUrl,
      cover_url: coverUrl,
    };
    // Yalnızca değişen alanları gönder (PATCH)
    const changes = Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== (user[key] ?? null)));
    if (!Object.keys(changes).length) {
      sheet.close();
      return;
    }

    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const updated = await api.updateProfile(changes);
      sheet.close();
      toast('Profilin güncellendi', 'success');
      onSaved(updated);
    } catch (error) {
      toast(error.message, 'error');
      submit.disabled = false;
    }
  });
}
