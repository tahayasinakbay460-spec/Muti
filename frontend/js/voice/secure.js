// Tarayıcılar mikrofonu ve kamerayı YALNIZCA güvenli adreste açar: https:// ya da bilgisayarın kendisi
// (localhost / 127.0.0.1). Telefondan http://192.168.x.x:5500 ile açılan sayfada `navigator.mediaDevices`
// hiç yoktur; ses/görüntü kütüphaneleri de çalışmaz. Bu durumda belirsiz "bağlantı kurulamadı" yerine
// gerçek sebebi söylüyoruz.
export const INSECURE_MEDIA_TEXT = 'Mikrofon ve kamera yalnızca https ile açılan sayfada çalışır. '
  + 'Telefondan http://… adresiyle açtın; canlı sitede (https) dene.';

export function mediaBlockedReason() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) return INSECURE_MEDIA_TEXT;
  if (!window.RTCPeerConnection) return 'Bu tarayıcı sesli/görüntülü görüşmeyi desteklemiyor.';
  return null;
}

export function requireMedia() {
  const reason = mediaBlockedReason();
  if (reason) throw Object.assign(new Error(reason), { code: 'insecure_context' });
}
