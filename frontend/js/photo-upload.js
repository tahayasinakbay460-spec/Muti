// Fotoğraf yükleme: profil fotoğrafı, kapak, anı, oda kapağı ve sohbette fotoğraf aynı akışı kullanır.
//   1. Kullanıcı yükleme alanına dokunur.
//   2. İlk seferde "Fotoğraflarına erişim" izni sorulur (neden istediğimiz yazar). Telefonda buradan
//      galeri ya da kamera seçilir. İzin verildiyse bilgisayarda bir dahaki sefere doğrudan dosya penceresi açılır.
//   3. Seçilen fotoğraf küçültülür (konum bilgisi silinir, bkz. image-picker.js), sunucuya yüklenir.
//   4. Sunucunun verdiği adres döner; ekran onu profile / anıya bağlar.
// Neden önce kendi panelimiz? Telefonun kendi izin penceresi tek sefer ve açıklamasız çıkar; "Reddet"e
// basan kişiye bir daha soramayız. Önce ne için istediğimizi anlatmak (soft ask) izin oranını artırır.
// Web'de galeri için ayrı izin yok (kişi dosyayı kendi seçer); kamerayı telefon kendisi sorar.
// MOBİL UYGULAMADA: bu panelin "İzin ver" tuşu gerçek izin isteğini (iOS Fotoğraflar / Android medya) tetikler.
import { api } from './api.js';
import { pickImageFile, shrinkImage } from './image-picker.js';
import { esc, openSheet, toast } from './ui.js';

const CONSENT_KEY = 'muti_photo_access';

// Tür başına: küçültme boyutu, kamera yönü ve metinler
const KINDS = {
  avatar: { maxSide: 640, camera: 'user', title: 'Profil fotoğrafı', hint: 'Yüzünün net göründüğü bir fotoğraf seç' },
  cover: { maxSide: 1280, camera: 'environment', title: 'Kapak fotoğrafı', hint: 'Yatay bir fotoğraf en iyi görünür' },
  moment: { maxSide: 1280, camera: 'environment', title: 'Fotoğraf ekle', hint: 'Anını bir fotoğrafla anlat' },
  room_cover: { maxSide: 1280, camera: 'environment', title: 'Oda kapağı', hint: 'Oda listesinde bu görünür' },
  // Sohbette alan yok (yalnızca 📷 tuşu): fotoğraf seçilip doğrudan mesaj olarak gönderilir
  chat: { maxSide: 1280, camera: 'environment', title: 'Fotoğraf gönder', hint: '' },
};

const CAMERA_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.2l1.3-2h6l1.3 2h1.200A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.500h-11A2.5 2.5 0 0 1 4 16.500z"/><circle cx="12" cy="12.5" r="3.5"/></svg>`;
const GALLERY_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="9.5" r="1.8"/><path d="m21 16-5-5-9 9"/></svg>`;
const SHIELD_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 5 6v5c0 4.5 3 8.2 7 10 4-1.8 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/></svg>`;

const hasConsent = () => { try { return localStorage.getItem(CONSENT_KEY) === 'granted'; } catch { return false; } };
const saveConsent = () => { try { localStorage.setItem(CONSENT_KEY, 'granted'); } catch { /* gizli sekme: her sefer sorulur */ } };
const isPhone = () => matchMedia('(pointer: coarse)').matches;

// Yükleme alanının HTML'i. `url` doluysa fotoğraf görünür, üstünde "Değiştir" yazar.
//   shape: 'avatar' (yuvarlak), 'cover' (geniş), 'tile' (anı için büyük kare alan)
export function photoUploadField({ kind, url = null, shape = 'tile' }) {
  const { title, hint } = KINDS[kind];
  return `
    <button type="button" class="photo-upload photo-upload-${shape} ${url ? 'has-photo' : ''}" data-photo-upload="${kind}" aria-label="${esc(title)}">
      <span class="photo-upload-media">${url ? `<img src="${esc(url)}" alt="" />` : ''}</span>
      <span class="photo-upload-cta">
        <span class="photo-upload-icon">${CAMERA_ICON}</span>
        ${shape === 'avatar' ? '' : `<b>${url ? 'Değiştir' : esc(title)}</b><small>${esc(hint)}</small>`}
      </span>
      <span class="photo-upload-busy"><i></i><small>Yükleniyor</small></span>
    </button>`;
}

// Alanın görünümünü yeni fotoğrafa göre tazeler (yükleme bitince ya da fotoğraf kaldırılınca)
export function setFieldPhoto(field, url) {
  const media = field.querySelector('.photo-upload-media');
  media.innerHTML = url ? `<img src="${esc(url)}" alt="" />` : '';
  field.classList.toggle('has-photo', Boolean(url));
  const label = field.querySelector('.photo-upload-cta b');
  if (label) label.textContent = url ? 'Değiştir' : KINDS[field.dataset.photoUpload].title;
}

// İzin / kaynak paneli. Seçilen dosyayla (vazgeçilirse null ile) biter.
function askForPhoto(kind) {
  const { camera } = KINDS[kind];
  const firstTime = !hasConsent();
  return new Promise((resolve) => {
    let picked = null;
    const sheet = openSheet(`
      <div class="photo-access">
        <span class="photo-access-badge">${firstTime ? SHIELD_ICON : GALLERY_ICON}</span>
        <h2>${firstTime ? 'Fotoğraflarına erişim' : 'Fotoğraf seç'}</h2>
        <p>${firstTime
          ? 'Profil fotoğrafı, kapak, anı ve sohbette fotoğraf paylaşmak için fotoğraflarına erişmemiz gerekiyor. Yalnızca senin seçtiğin fotoğraf yüklenir; çekildiği yer bilgisi silinir.'
          : 'Galeriden bir fotoğraf seç ya da hemen çek.'}</p>
        <div class="photo-access-actions">
          <button type="button" class="btn btn-primary btn-block photo-access-main" data-source="gallery">${GALLERY_ICON}${firstTime ? 'İzin ver ve galeriyi aç' : 'Galeriden seç'}</button>
          ${isPhone() ? `<button type="button" class="btn btn-ghost btn-block" data-source="camera">${CAMERA_ICON}Kamerayla çek</button>` : ''}
          <button type="button" class="photo-access-later" data-close>${firstTime ? 'Şimdi değil' : 'Vazgeç'}</button>
        </div>
      </div>`, { className: 'sheet-photo-access', onClose: () => resolve(picked) });
    sheet.el.addEventListener('click', (event) => {
      const button = event.target.closest('[data-source]');
      if (!button) return;
      saveConsent();
      // Dosya penceresi bu dokunuşun içinde açılmalı (bkz. image-picker.js), o yüzden await yok
      picked = pickImageFile(button.dataset.source === 'camera' ? camera : null);
      sheet.close();
    });
  });
}

// İzin → galeri/kamera → küçült. Küçültülmüş fotoğrafı (Blob) döner; vazgeçilirse null.
// Tıklama olayının içinde ve öncesinde `await` olmadan çağrılmalı (dosya penceresi kuralı).
// Hata olursa (açılamayan dosya, çok büyük) fırlatır; çağıran gösterir.
export async function choosePhoto(kind) {
  // İzin verilmiş ve bilgisayardaysa (kamera seçeneği yok) panel göstermeden pencereyi aç
  const file = await (hasConsent() && !isPhone() ? pickImageFile() : askForPhoto(kind));
  return file ? shrinkImage(file, KINDS[kind].maxSide) : null;
}

// Alan tıklanınca çağrılır. Yüklenen fotoğrafın adresini döner; vazgeçilirse null.
export async function uploadPhoto(field, kind = field.dataset.photoUpload) {
  if (field.classList.contains('is-busy')) return null;
  let blob;
  try {
    blob = await choosePhoto(kind);
  } catch (error) {
    toast(error.message, 'error');
    return null;
  }
  if (!blob) return null;
  field.classList.add('is-busy');
  try {
    const { url } = await api.uploadImage(blob, kind);
    setFieldPhoto(field, url);
    return url;
  } catch (error) {
    toast(error.message, 'error');
    return null;
  } finally {
    field.classList.remove('is-busy');
  }
}
