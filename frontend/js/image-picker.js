// Fotoğraf seçme ve yüklemeye hazırlama.
// Telefonun fotoğraf seçicisini açar, seçilen fotoğrafı tarayıcıda küçültüp JPEG'e çevirir.
// Neden küçültüyoruz? (1) Telefon fotoğrafı 3-8 MB; küçültünce ~200 KB olur, hızlı yüklenir.
// (2) Canvas'a çizip yeniden kaydedince fotoğrafın içindeki EXIF bilgisi (çekildiği yerin konumu,
// telefon modeli) silinir. Profil fotoğrafından ev adresi bulunmasın.

const MAX_SIDE = 1280;
const QUALITY = 0.85;
// Telefondan seçilen ham dosya için üst sınır. Küçültmeden önce bakılır: çok büyük dosya tarayıcıyı kilitler.
const MAX_INPUT_BYTES = 25 * 1024 * 1024;

// Kullanıcıya dosya seçtirir. Vazgeçerse null döner.
// `capture` = 'user' (ön kamera) ya da 'environment' (arka kamera): telefonda galeri yerine kamera açılır,
// kamera iznini telefonun kendisi sorar. Bilgisayarda yok sayılır, normal dosya penceresi açılır.
// DİKKAT: tarayıcı dosya penceresini yalnızca bir dokunuşun içinde açar. Bu fonksiyon tıklama
// olayının içinde, öncesinde hiç `await` olmadan çağrılmalı; yoksa pencere sessizce açılmaz.
export function pickImageFile(capture = null) {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/jpeg,image/png,image/webp';
    if (capture) input.setAttribute('capture', capture);
    input.addEventListener('change', () => resolve(input.files?.[0] || null), { once: true });
    // Pencere kapatılınca "change" gelmez; odak geri dönünce boş say
    window.addEventListener('focus', () => setTimeout(() => resolve(input.files?.[0] || null), 400), { once: true });
    input.click();
  });
}

// Dosyayı en uzun kenarı MAX_SIDE olacak şekilde küçültür ve JPEG Blob olarak döner.
export async function shrinkImage(file, maxSide = MAX_SIDE) {
  // Türü boş gelebilir (bazı telefonlar); o zaman açmayı deneriz, açılamazsa aşağıda hata verilir.
  if (file.type && !file.type.startsWith('image/')) throw new Error('Yalnızca fotoğraf seçebilirsin.');
  if (file.size > MAX_INPUT_BYTES) throw new Error('Bu fotoğraf çok büyük (en fazla 25 MB).');
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) throw new Error('Bu dosya açılamadı. Başka bir fotoğraf seç.');
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY));
  if (!blob) throw new Error('Fotoğraf hazırlanamadı.');
  return blob;
}
