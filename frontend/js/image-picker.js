// Fotoğraf seçme ve yüklemeye hazırlama.
// Telefonun fotoğraf seçicisini açar, seçilen fotoğrafı tarayıcıda küçültüp JPEG'e çevirir.
// Neden küçültüyoruz? (1) Telefon fotoğrafı 3-8 MB; küçültünce ~200 KB olur, hızlı yüklenir.
// (2) Canvas'a çizip yeniden kaydedince fotoğrafın içindeki EXIF bilgisi (çekildiği yerin konumu,
// telefon modeli) silinir. Profil fotoğrafından ev adresi bulunmasın.

const MAX_SIDE = 1280;
const QUALITY = 0.85;

// Kullanıcıya dosya seçtirir. Vazgeçerse null döner.
export function pickImageFile() {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/jpeg,image/png,image/webp';
    input.addEventListener('change', () => resolve(input.files?.[0] || null), { once: true });
    // Pencere kapatılınca "change" gelmez; odak geri dönünce boş say
    window.addEventListener('focus', () => setTimeout(() => resolve(input.files?.[0] || null), 400), { once: true });
    input.click();
  });
}

// Dosyayı en uzun kenarı MAX_SIDE olacak şekilde küçültür ve JPEG Blob olarak döner.
export async function shrinkImage(file, maxSide = MAX_SIDE) {
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

// Seç + küçült. Vazgeçilirse null.
export async function pickAndShrink(maxSide) {
  const file = await pickImageFile();
  return file ? shrinkImage(file, maxSide) : null;
}
