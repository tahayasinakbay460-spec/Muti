// "Profili Düzenle" paneli: profil fotoğrafı, kapak, görünen ad, hakkımda, yaş, şehir
import { api } from '../api.js';
import { COUNTRY_CODES, countryName, flagEmoji } from '../countries.js';
import { photoUploadField, uploadPhoto } from '../photo-upload.js';
import { esc, openSheet, toast } from '../ui.js';

// Kaydedilince onSaved(güncel kullanıcı) çağrılır; ekran kendini yeniden çizer.
// Avatar ve kapak yalnızca kişinin kendi yüklediği fotoğraf olabilir (hazır görsel listesi yok).
export async function openEditProfileSheet(user, onSaved) {
  let avatarUrl = user.avatar_url;
  let coverUrl = user.cover_url;

  const sheet = openSheet(`
    <h2 class="sheet-title">Profili Düzenle</h2>
    <form id="edit-profile-form">
      <div class="profile-photos">
        ${photoUploadField({ kind: 'cover', url: coverUrl, shape: 'cover' })}
        ${photoUploadField({ kind: 'avatar', url: avatarUrl, shape: 'avatar' })}
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
      <label class="field">
        <span>Ülke</span>
        <select name="country">
          <option value="">Seçilmedi</option>
          ${[...new Set([...(user.country ? [user.country] : []), ...COUNTRY_CODES])]
            .map((code) => ({ code, name: countryName(code) }))
            .sort((a, b) => a.name.localeCompare(b.name, 'tr'))
            .map(({ code, name }) => `<option value="${code}" ${code === user.country ? 'selected' : ''}>${flagEmoji(code)} ${esc(name)}</option>`).join('')}
        </select>
      </label>
      <button class="btn btn-primary btn-block" type="submit">Kaydet</button>
    </form>`);

  // Fotoğraf alanına dokununca: izin → seç → küçült → yükle. Adres "Kaydet"e basınca profile yazılır.
  sheet.el.querySelectorAll('[data-photo-upload]').forEach((field) => {
    field.addEventListener('click', async () => {
      const url = await uploadPhoto(field);
      if (!url) return;
      if (field.dataset.photoUpload === 'avatar') avatarUrl = url;
      else coverUrl = url;
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
      country: data.get('country') || null,
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
