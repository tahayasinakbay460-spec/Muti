// Tüm veri erişimi bu dosyadan geçer. Ekranlar yalnızca `api` nesnesini kullanır;
// her metot backend'deki bir `/api/v1/...` ucuna karşılık gelir.
import { API_BASE_URL, STORAGE_KEYS } from './config.js';

function storeTokens({ access_token, refresh_token }) {
  localStorage.setItem(STORAGE_KEYS.accessToken, access_token);
  if (refresh_token) localStorage.setItem(STORAGE_KEYS.refreshToken, refresh_token);
}

function clearTokens() {
  localStorage.removeItem(STORAGE_KEYS.accessToken);
  localStorage.removeItem(STORAGE_KEYS.refreshToken);
}

// Yönetim paneli oturumu (bkz. backend core/security.py "Panel oturumu"). Uygulamanın
// oturumundan ayrı ve kısa: sekmeye özel sessionStorage'da durur, sekme kapanınca silinir.
// Sunucu her panel cevabında süresi uzatılmış yenisini X-Staff-Token başlığıyla gönderir.
const staffStorage = {
  get: () => { try { return sessionStorage.getItem(STORAGE_KEYS.staffToken); } catch { return null; } },
  set: (token) => {
    try { sessionStorage.setItem(STORAGE_KEYS.staffToken, token); } catch { /* bu sekmede saklanamadı */ }
    // Panel, hareketsizlik sayacını buna göre sıfırlar (bkz. admin/main.js restartIdleTimer)
    window.dispatchEvent(new Event('staff-session-renewed'));
  },
  clear: () => { try { sessionStorage.removeItem(STORAGE_KEYS.staffToken); } catch { /* yok */ } },
};

// Panel "şifreni yeniden gir" dediğinde ne yapılacağını panel sayfası söyler (setStaffAuthHandler).
let staffAuthHandler = null;
export function setStaffAuthHandler(handler) { staffAuthHandler = handler; }

// İstek başarısız olunca fırlatılır. `code` sunucunun verdiği hata kodu (ör. insufficient_balance);
// ekranlar mesaj yerine bu koda bakarak karar verir. (Mock katmanı silinirken yanlışlıkla kaldırılmıştı.)
class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

// `rawBody`: gövde JSON değil, olduğu gibi gider (ses dosyası); türü headers'taki Content-Type.
// `asBlob`: cevap JSON değil dosyadır (sesli mesajı çalmak için).
async function send(path, { method = 'GET', body, headers = {}, rawBody, asBlob = false } = {}) {
  const token = localStorage.getItem(STORAGE_KEYS.accessToken);
  const isAdmin = path.startsWith('/admin/');
  const staffToken = isAdmin ? staffStorage.get() : null;
  let response;
  try {
    response = await fetch(API_BASE_URL + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(staffToken ? { 'X-Staff-Token': staffToken } : {}),
        ...headers,
      },
      body: rawBody ?? (body ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError('network_error', 'Sunucuya ulaşılamıyor. Backend çalışıyor mu?');
  }
  const renewedStaffToken = isAdmin && response.headers.get('X-Staff-Token');
  if (renewedStaffToken) staffStorage.set(renewedStaffToken);
  if (asBlob && response.ok) return response.blob();
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new ApiError(data.code || 'request_failed', data.detail || 'İstek başarısız oldu.');
    error.status = response.status;
    throw error;
  }
  return data;
}

// Aynı anda birçok istek 401 alabilir; hepsi tek bir yenileme isteğini bekler.
// (Refresh token tek kullanımlıktır: iki kez gönderilirse backend tüm oturumları kapatır.)
let refreshPromise = null;

// Access token'ın süresi dolunca refresh token ile yenisini alır.
// Yenilenemezse oturum kapatılır ve giriş ekranına dönülür.
export function refreshSession() {
  refreshPromise ||= (async () => {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
    try {
      if (!refreshToken) throw new ApiError('not_authenticated', '');
      storeTokens(await send('/auth/refresh', { method: 'POST', body: { refresh_token: refreshToken } }));
    } catch (error) {
      // Sunucuya ulaşılamadıysa oturumu silme; bağlantı gelince kaldığı yerden devam eder
      if (error.code === 'network_error') throw error;
      clearTokens();
      location.hash = '#/auth';
      throw new ApiError('session_expired', 'Oturumun sona erdi, tekrar giriş yap.');
    }
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

const STAFF_AUTH_CODES = ['staff_session_required', 'staff_reauth_required'];

async function request(path, options) {
  try {
    return await send(path, options);
  } catch (error) {
    if (error.status !== 401) throw error;
    // Panel oturumu kapandı ya da kritik işlem şifre istiyor: access token'ı yenilemek
    // işe yaramaz. Panel şifreyi sorar, yeni panel oturumu açılır, istek bir kez tekrarlanır.
    if (STAFF_AUTH_CODES.includes(error.code)) {
      if (!staffAuthHandler) throw error;
      await staffAuthHandler(error.code);
      return send(path, options);
    }
    if (error.code?.startsWith('staff_')) throw error;
    await refreshSession();
    return send(path, options);
  }
}

// Para harcayan isteklerde gönderilir: bağlantı kopup istek tekrarlansa bile
// backend aynı anahtarı ikinci kez işlemez (çifte harcama olmaz).
const idempotencyHeader = () => ({
  'Idempotency-Key': crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
});

export const api = {
  isAuthenticated: () => Boolean(localStorage.getItem(STORAGE_KEYS.accessToken)),
  async login({ username, password }) {
    const data = await send('/auth/login', { method: 'POST', body: { username, password } });
    storeTokens(data);
    return data;
  },
  async register({ username, email, password, country }) {
    const data = await send('/auth/register', { method: 'POST', body: { username, email, password, country } });
    storeTokens(data);
    return data;
  },
  async loginAsGuest() {
    const data = await send('/auth/guest', { method: 'POST' });
    storeTokens(data);
    return data;
  },
  async logout() {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
    clearTokens();
    staffStorage.clear();
    // Sunucudaki oturumu da kapat; ulaşılamazsa bile bu cihazdan çıkış yapılmış olur
    if (refreshToken) await send('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }).catch(() => {});
  },
  async changePassword(payload) {
    const data = await request('/auth/change-password', { method: 'POST', body: payload });
    storeTokens(data);   // diğer cihazlar kapandı; bu cihaz yeni token ile devam eder
    return data;
  },
  async deleteAccount(password) {
    await request('/users/me', { method: 'DELETE', body: { password: password || null } });
    clearTokens();
  },
  getMe: () => request('/users/me'),
  searchUsers: (query) => request(`/users/search?query=${encodeURIComponent(query)}`),
  setBlocked: (userId, blocked) => request(`/users/${userId}/block`, { method: blocked ? 'PUT' : 'DELETE' }),
  listBlocked: () => request('/users/me/blocks'),
  // target_type: 'user' | 'room'; reason: spam | harassment | inappropriate | underage | fraud | other
  report: (payload) => request('/reports', { method: 'POST', body: payload }),
  listNotifications: () => request('/notifications'),
  getNotificationUnreadCount: async () => (await request('/notifications/unread-count')).unread_count,
  markNotificationsRead: () => request('/notifications/read', { method: 'POST' }),
  getIncome: () => request('/wallet/income'),
  exchangeDiamonds: (diamonds) => request('/wallet/exchange', { method: 'POST', body: { diamonds }, headers: idempotencyHeader() }),
  getUser: (id) => request(`/users/${id}`),
  getProfileExtras: (id) => request(`/users/${id}/profile`),
  // ── Anılar (Instagram benzeri paylaşımlar), ziyaretçiler, takipçiler ──
  // feed: 'explore' (herkes) | 'following' (takip ettiklerim); beforeId: daha eskileri için son anının id'si
  listMoments: ({ feed = 'explore', beforeId = '' } = {}) => request(`/moments?feed=${feed}${beforeId ? `&before_id=${beforeId}` : ''}`),
  listUserMoments: (userId) => request(`/users/${userId}/moments`),
  getMomentImageOptions: () => request('/moments/image-options'),
  createMoment: (payload) => request('/moments', { method: 'POST', body: payload }),
  deleteMoment: (id) => request(`/moments/${id}`, { method: 'DELETE' }),
  toggleMomentLike: (id) => request(`/moments/${id}/like`, { method: 'POST' }),
  listMomentComments: (id) => request(`/moments/${id}/comments`),
  addMomentComment: (id, text) => request(`/moments/${id}/comments`, { method: 'POST', body: { text } }),
  deleteMomentComment: (id, commentId) => request(`/moments/${id}/comments/${commentId}`, { method: 'DELETE' }),
  // Herhangi bir profilin takipçi / takip listesi (profildeki sayılara dokununca)
  listUserFollowers: (userId) => request(`/users/${userId}/followers`),
  listUserFollowing: (userId) => request(`/users/${userId}/following`),
  // Beni takip edenler: is_following=false olanlar "arkadaşlık isteği" (geri takip edince arkadaş)
  listFollowers: () => request('/users/me/followers'),
  listVisitors: () => request('/users/me/visitors'),
  // Yayın odam: sahibi olduğum odalar + takipçi/hediye sayıları
  listMyRooms: () => request('/rooms/mine'),
  listRoomFollowers: (roomId) => request(`/rooms/${roomId}/followers`),
  toggleFollow: (id) => request(`/users/${id}/follow`, { method: 'POST' }),
  updateProfile: (changes) => request('/users/me', { method: 'PATCH', body: changes }),
  getMediaOptions: () => request('/users/me/media-options'),
  toggleRoomFollow: (id) => request(`/rooms/${id}/follow`, { method: 'POST' }),
  listFollowedRooms: () => request('/rooms/followed'),
  // Giriş yapmadan okunur: örnek veri yüklüyse giriş ekranında demo hesabı gösterilir
  getAppInfo: () => request('/app-info'),
  // category: oda türü, 'pk' (PK'si sürenler) ya da 'live' (mikrofonunda biri olanlar);
  // country: oda sahibinin ülkesi ("TR"), boş = Genel; limit/offset: aşağı indikçe sayfa sayfa yükleme
  listRooms: ({ category = '', query = '', limit = 30, offset = 0, country = '' } = {}) => request(
    `/rooms?category=${encodeURIComponent(category)}&query=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}&country=${encodeURIComponent(country)}`,
  ),
  listRecentRooms: () => request('/rooms/recent'),
  listRoomCountries: () => request('/rooms/countries'),
  getRoom: (id) => request(`/rooms/${id}`),
  createRoom: (payload) => request('/rooms', { method: 'POST', body: payload }),
  takeSeat: (roomId, seatIndex) => request(`/rooms/${roomId}/seats/${seatIndex}`, { method: 'POST' }),
  leaveSeat: (roomId) => request(`/rooms/${roomId}/seats/me`, { method: 'DELETE' }),
  toggleMute: (roomId) => request(`/rooms/${roomId}/seats/me/mute`, { method: 'POST' }),
  updateRoom: (roomId, changes) => request(`/rooms/${roomId}`, { method: 'PATCH', body: changes }),
  closeRoom: (roomId) => request(`/rooms/${roomId}`, { method: 'DELETE' }),
  listRoomMembers: (roomId) => request(`/rooms/${roomId}/members`),
  // Sesli görüşmeye bağlanma bilgisi; biçimi sunucudaki ses sağlayıcısına göre değişir (bkz. js/voice/)
  getVoiceJoin: (roomId) => request(`/rooms/${roomId}/voice`),
  reportVoiceEvent: (report) => request('/diagnostics/voice', { method: 'POST', body: report }),
  // role: 'admin' | 'vip' | 'listener' (özel rolü geri al)
  setRoomRole: (roomId, userId, role) => request(`/rooms/${roomId}/roles/${userId}`, { method: 'PUT', body: { role } }),
  setSeatLock: (roomId, seatIndex, locked) => request(`/rooms/${roomId}/seats/${seatIndex}/lock`, { method: locked ? 'PUT' : 'DELETE' }),
  removeFromSeat: (roomId, seatIndex) => request(`/rooms/${roomId}/seats/${seatIndex}/user`, { method: 'DELETE' }),
  inviteToSeat: (roomId, userId) => request(`/rooms/${roomId}/seat-invites/${userId}`, { method: 'POST' }),
  setMicBlocked: (roomId, userId, blocked) => request(`/rooms/${roomId}/mic-blocks/${userId}`, { method: blocked ? 'PUT' : 'DELETE' }),
  // minutes: 5 | 30 | 60 | 1440; null → susturmayı kaldır
  setChatMute: (roomId, userId, minutes) => request(`/rooms/${roomId}/chat-mutes/${userId}`, minutes ? { method: 'PUT', body: { minutes } } : { method: 'DELETE' }),
  deleteChatMessage: (roomId, messageId) => request(`/rooms/${roomId}/messages/${encodeURIComponent(messageId)}`, { method: 'DELETE' }),
  kickFromRoom: (roomId, userId) => request(`/rooms/${roomId}/kicks/${userId}`, { method: 'POST' }),
  listSuggestedUsers: () => request('/users/suggested'),
  listGifts: () => request('/gifts'),
  sendGift: (payload) => request('/gifts/send', { method: 'POST', body: payload, headers: idempotencyHeader() }),
  listCoinPackages: () => request('/wallet/packages'),
  listStoreItems: (kind) => request(`/store/items${kind ? `?kind=${kind}` : ''}`),
  purchaseStoreItem: (itemId, days) => request(`/store/items/${itemId}/purchase`, { method: 'POST', body: { days }, headers: idempotencyHeader() }),
  equipStoreItem: (itemId, equipped) => request(`/store/items/${itemId}/equip`, { method: 'PUT', body: { equipped } }),
  listUserItems: (userId) => request(`/users/${userId}/items`),
  getVip: () => request('/vip'),
  purchaseVip: (level) => request('/vip/purchase', { method: 'POST', body: { level }, headers: idempotencyHeader() }),
  claimVipDailyReward: () => request('/vip/daily-reward', { method: 'POST' }),
  // ── Bağlılık: günlük giriş, görevler, aile, CP, sıralama, etkinlik ──
  getCheckin: () => request('/rewards/checkin'),
  claimCheckin: () => request('/rewards/checkin', { method: 'POST' }),
  listTasks: () => request('/tasks'),
  claimTask: (taskId) => request(`/tasks/${encodeURIComponent(taskId)}/claim`, { method: 'POST' }),
  listFamilies: (query = '') => request(`/families?query=${encodeURIComponent(query)}`),
  createFamily: (payload) => request('/families', { method: 'POST', body: payload }),
  getMyFamily: () => request('/families/me'),
  getFamily: (id) => request(`/families/${id}`),
  updateFamily: (id, changes) => request(`/families/${id}`, { method: 'PATCH', body: changes }),
  disbandFamily: (id) => request(`/families/${id}`, { method: 'DELETE' }),
  joinFamily: (id) => request(`/families/${id}/join`, { method: 'POST' }),
  leaveFamily: () => request('/families/me/membership', { method: 'DELETE' }),
  kickFamilyMember: (id, userId) => request(`/families/${id}/members/${userId}`, { method: 'DELETE' }),
  setFamilyRole: (id, userId, role) => request(`/families/${id}/members/${userId}/role`, { method: 'PUT', body: { role } }),
  listFamilyMessages: (id) => request(`/families/${id}/messages`),
  sendFamilyMessage: (id, text) => request(`/families/${id}/messages`, { method: 'POST', body: { text } }),
  getCouple: () => request('/couples/me'),
  proposeCouple: (userId) => request(`/couples/${userId}`, { method: 'POST' }),
  acceptCouple: (userId) => request(`/couples/${userId}/accept`, { method: 'POST' }),
  declineCouple: (userId) => request(`/couples/${userId}/request`, { method: 'DELETE' }),
  breakUpCouple: () => request('/couples/me', { method: 'DELETE' }),
  getLeaderboard: (kind, period) => request(`/leaderboards?kind=${kind}&period=${period}`),
  listEvents: () => request('/events'),
  getEvent: (id) => request(`/events/${id}`),
  // ── Oda içi etkinlikler (PK, birlikte izleme, karaoke); iki kişilik oyunlar WebSocket'te ──
  getActivities: (roomId) => request(`/rooms/${roomId}/activities`),
  startPk: (roomId, minutes) => request(`/rooms/${roomId}/pk`, { method: 'POST', body: { minutes } }),
  stopPk: (roomId) => request(`/rooms/${roomId}/pk`, { method: 'DELETE' }),
  setMedia: (roomId, url) => request(`/rooms/${roomId}/media`, { method: 'PUT', body: { url } }),
  controlMedia: (roomId, action, position) => request(`/rooms/${roomId}/media/control`, { method: 'POST', body: { action, position } }),
  stopMedia: (roomId) => request(`/rooms/${roomId}/media`, { method: 'DELETE' }),
  joinKaraoke: (roomId) => request(`/rooms/${roomId}/karaoke/queue`, { method: 'POST' }),
  leaveKaraoke: (roomId) => request(`/rooms/${roomId}/karaoke/queue`, { method: 'DELETE' }),
  nextSinger: (roomId) => request(`/rooms/${roomId}/karaoke/next`, { method: 'POST' }),
  // ── Yönetim paneli (yalnızca yöneticiler) ve ajans ──
  // Panel oturumu: şifreyle açılır; kritik işlemden önce de aynı çağrıyla tazelenir
  async adminStartSession(password) {
    const session = await request('/admin/session', { method: 'POST', body: { password } });
    staffStorage.set(session.staff_token);
    return session;
  },
  hasStaffSession: () => Boolean(staffStorage.get()),
  adminEndSession: () => staffStorage.clear(),
  adminSession: () => request('/admin/session'),
  adminStaff: () => request('/admin/staff'),
  adminSetStaffRole: (id, role) => request(`/admin/staff/${id}`, { method: 'PUT', body: { role } }),
  adminStaffActions: ({ actorId = '', beforeId = '' } = {}) => request(`/admin/staff/actions?limit=50${actorId ? `&actor_id=${actorId}` : ''}${beforeId ? `&before_id=${beforeId}` : ''}`),
  adminStats: () => request('/admin/stats'),
  adminReports: (status = 'open') => request(`/admin/reports?status=${status}`),
  adminResolveReport: (id, action, note = '') => request(`/admin/reports/${id}/resolve`, { method: 'POST', body: { action, note } }),
  adminUsers: (query = '', sort = 'newest') => request(`/admin/users?query=${encodeURIComponent(query)}&sort=${sort}`),
  adminFinance: (days = 14) => request(`/admin/finance?days=${days}`),
  adminTransactions: ({ type = '', userId = '', beforeId = '', limit = 50 } = {}) => request(`/admin/transactions?limit=${limit}${type ? `&type=${type}` : ''}${userId ? `&user_id=${userId}` : ''}${beforeId ? `&before_id=${beforeId}` : ''}`),
  adminConversations: (userId = '') => request(`/admin/conversations${userId ? `?user_id=${userId}` : ''}`),
  adminConversationMessages: (id) => request(`/admin/conversations/${id}/messages`),
  adminRoomMessages: (id) => request(`/admin/rooms/${id}/messages`),
  adminGifts: () => request('/admin/catalog/gifts'),
  adminUpdateGift: (id, changes) => request(`/admin/catalog/gifts/${id}`, { method: 'PATCH', body: changes }),
  adminPackages: () => request('/admin/catalog/packages'),
  adminUpdatePackage: (id, changes) => request(`/admin/catalog/packages/${id}`, { method: 'PATCH', body: changes }),
  adminGrantVip: (id, level, days) => request(`/admin/users/${id}/vip`, { method: 'POST', body: { level, days } }),
  adminBroadcast: (text) => request('/admin/broadcast', { method: 'POST', body: { text } }),
  adminUser: (id) => request(`/admin/users/${id}`),
  adminBan: (id, reason) => request(`/admin/users/${id}/ban`, { method: 'POST', body: { reason } }),
  adminUnban: (id) => request(`/admin/users/${id}/ban`, { method: 'DELETE' }),
  adminAdjustBalance: (id, payload) => request(`/admin/users/${id}/balance`, { method: 'POST', body: payload }),
  adminRooms: () => request('/admin/rooms'),
  adminCloseRoom: (id) => request(`/admin/rooms/${id}`, { method: 'DELETE' }),
  adminAgencies: () => request('/admin/agencies'),
  adminAgencySettlements: (month = '') => request(`/admin/agency-settlements${month ? `?month=${encodeURIComponent(month)}` : ''}`),
  adminSettleAgency: (agencyId, month) => request(`/admin/agencies/${agencyId}/settle`, { method: 'POST', body: { month } }),
  adminHostApplications: (status = 'pending') => request(`/admin/host-applications?status=${status}`),
  adminReviewHost: (id, approve, note = '') => request(`/admin/host-applications/${id}/review`, { method: 'POST', body: { approve, note } }),
  adminRevokeHost: (userId, note = '') => request(`/admin/hosts/${userId}/revoke`, { method: 'POST', body: { note } }),
  adminCreateAgency: (payload) => request('/admin/agencies', { method: 'POST', body: payload }),
  getMyAgency: () => request('/agencies/me'),
  listAgencies: (query = '') => request(`/agencies?query=${encodeURIComponent(query)}`),
  applyToAgency: (agencyId) => request(`/agencies/${agencyId}/apply`, { method: 'POST' }),
  withdrawAgencyApplication: () => request('/agencies/me/application', { method: 'DELETE' }),
  acceptAgencyApplication: (userId) => request(`/agencies/me/applications/${userId}/accept`, { method: 'POST' }),
  answerAgencyInvite: (accept) => request(`/agencies/me/invite/${accept ? 'accept' : 'decline'}`, { method: 'POST' }),
  leaveAgency: () => request('/agencies/me/membership', { method: 'DELETE' }),
  inviteToAgency: (userId) => request(`/agencies/me/members/${userId}`, { method: 'POST' }),
  setAgencyTarget: (userId, monthlyTarget) => request(`/agencies/me/members/${userId}/target`, { method: 'PUT', body: { monthly_target: monthlyTarget } }),
  removeAgencyMember: (userId) => request(`/agencies/me/members/${userId}`, { method: 'DELETE' }),
  getChest: (roomId) => request(`/rooms/${roomId}/chest`),
  claimChest: (roomId) => request(`/rooms/${roomId}/chest/claim`, { method: 'POST' }),
  purchaseCoins: (packageId) => request('/wallet/purchase', { method: 'POST', body: { package_id: packageId }, headers: idempotencyHeader() }),
  listTransactions: (currency = 'coin') => request(`/wallet/transactions?currency=${currency}`),
  listConversations: () => request('/conversations'),
  getConversation: (id) => request(`/conversations/${id}`),
  openConversationWith: async (userId) => (await request('/conversations', { method: 'POST', body: { user_id: userId } })).id,
  sendMessage: (id, text) => request(`/conversations/${id}/messages`, { method: 'POST', body: { text } }),
  markConversationRead: (id) => request(`/conversations/${id}/read`, { method: 'POST' }),
  // Sesli mesaj: gövde kaydın kendisi (Blob), süre saniye
  sendVoiceMessage: (id, blob, seconds) => request(`/conversations/${id}/voice?duration=${seconds}`, {
    method: 'POST', rawBody: blob, headers: { 'Content-Type': blob.type || 'audio/webm' },
  }),
  // Sesli mesaj dosyası token ister; <audio> etiketi başlık gönderemediği için dosya burada çekilir
  getMessageMedia: (mediaUrl) => request(mediaUrl, { asBlob: true }),
  sendConversationImage: (id, blob) => request(`/conversations/${id}/image`, {
    method: 'POST', rawBody: blob, headers: { 'Content-Type': blob.type || 'image/jpeg' },
  }),
  // Fotoğraf yükleme (profil, kapak, anı, oda kapağı). Cevaptaki url ilgili forma yazılır.
  // kind: 'avatar' | 'cover' | 'moment' | 'room_cover'
  uploadImage: (blob, kind) => request(`/media?kind=${kind}`, {
    method: 'POST', rawBody: blob, headers: { 'Content-Type': blob.type || 'image/jpeg' },
  }),
  // Yayıncılık
  getHostStatus: () => request('/hosts/me'),
  applyHost: (payload) => request('/hosts/apply', { method: 'POST', body: payload }),
  sendConversationGift: (id, giftId, quantity) => request(`/conversations/${id}/gift`, {
    method: 'POST', body: { gift_id: giftId, quantity }, headers: idempotencyHeader(),
  }),
  // Birebir arama (ücretli; bkz. backend services/call_service.py)
  getCallPrices: () => request('/calls/prices'),
  startCall: (calleeId, kind) => request('/calls', { method: 'POST', body: { callee_id: calleeId, kind } }),
  acceptCall: (id) => request(`/calls/${id}/accept`, { method: 'POST' }),
  declineCall: (id) => request(`/calls/${id}/decline`, { method: 'POST' }),
  endCall: (id) => request(`/calls/${id}/end`, { method: 'POST' }),
  getCallJoin: (id) => request(`/calls/${id}/join`),
  getUnreadCount: async () => (await request('/conversations/unread-count')).unread_count,
};
