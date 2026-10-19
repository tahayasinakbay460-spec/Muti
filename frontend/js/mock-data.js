// Demo için sahte veri. Alan adları ileride backend'in döneceği JSON ile aynı tutulur.

const avatar = (name) => `assets/avatars/${name}.jpg`;
const cover = (name) => `assets/covers/${name}.jpg`;

export const CURRENT_USER_ID = 102938;

// VIP seviyeleri 0-3 (backend ile aynı); ana kullanıcı VIP değil, demoda VIP alınabilsin
export const users = [
  { id: CURRENT_USER_ID, username: 'muti', display_name: 'Muti', age: 26, city: 'Ankara', avatar_url: avatar('m1'), cover_url: cover('profile'), bio: 'Güzel insanlar, güzel sohbetler... 🌿', vip_level: 0, level: 28, is_verified: true, is_online: true, joined_days: 428, followers_count: 1200, following_count: 328, friends_count: 56, visitors_count: 12 },
  { id: 2001, username: 'merve', display_name: 'Merve', age: 25, city: 'İzmir', avatar_url: avatar('w1'), cover_url: cover('coast'), bio: 'Havuz Sohbeti her akşam 21:00 🌴', vip_level: 3, level: 41, is_verified: true, is_online: true, joined_days: 610, followers_count: 8400, following_count: 210, friends_count: 132, visitors_count: 94 },
  { id: 2002, username: 'kaan', display_name: 'Kaan', age: 27, city: 'Bursa', avatar_url: avatar('m2'), cover_url: cover('city'), bio: 'Gitar, kahve, gece sohbeti.', vip_level: 2, level: 19, is_verified: false, is_online: true, joined_days: 201, followers_count: 640, following_count: 180, friends_count: 44, visitors_count: 8 },
  { id: 2003, username: 'selin', display_name: 'Selin', age: 23, city: 'İstanbul', avatar_url: avatar('w2'), cover_url: cover('sky'), bio: 'Müzik olmadan olmaz 🎵', vip_level: 2, level: 33, is_verified: true, is_online: true, joined_days: 390, followers_count: 3100, following_count: 402, friends_count: 88, visitors_count: 31 },
  { id: 2004, username: 'emre', display_name: 'Emre', age: 26, city: 'İstanbul', avatar_url: avatar('m3'), cover_url: cover('night'), bio: 'Okey ve tavla ustası.', vip_level: 1, level: 15, is_verified: false, is_online: true, joined_days: 120, followers_count: 410, following_count: 256, friends_count: 37, visitors_count: 5 },
  { id: 2005, username: 'ada', display_name: 'Ada', age: 22, city: 'Antalya', avatar_url: avatar('w3'), cover_url: cover('beach'), bio: 'Yeni insanlarla tanışmayı severim.', vip_level: 2, level: 22, is_verified: false, is_online: true, joined_days: 95, followers_count: 980, following_count: 150, friends_count: 61, visitors_count: 17 },
  { id: 2006, username: 'burak', display_name: 'Burak', age: 29, city: 'Ankara', avatar_url: avatar('m4'), cover_url: cover('mountain'), bio: 'Dağ, kamp, sohbet.', vip_level: 1, level: 9, is_verified: false, is_online: false, joined_days: 60, followers_count: 150, following_count: 90, friends_count: 20, visitors_count: 3 },
  { id: 2007, username: 'ece', display_name: 'Ece', age: 24, city: 'Eskişehir', avatar_url: avatar('w4'), cover_url: cover('canal'), bio: 'Kitap kulübü odasının sahibi 📚', vip_level: 2, level: 17, is_verified: false, is_online: true, joined_days: 240, followers_count: 720, following_count: 310, friends_count: 52, visitors_count: 9 },
  { id: 2008, username: 'zeynep', display_name: 'Zeynep', age: 24, city: 'Ankara', avatar_url: avatar('w5'), cover_url: cover('terrace'), bio: 'Kahve ve uzun sohbetler ☕', vip_level: 1, level: 12, is_verified: false, is_online: true, joined_days: 75, followers_count: 530, following_count: 204, friends_count: 40, visitors_count: 11 },
  { id: 2009, username: 'defne', display_name: 'Defne', age: 23, city: 'İzmir', avatar_url: avatar('w6'), cover_url: cover('lighthouse'), bio: 'Şarkı söylemeyi çok severim.', vip_level: 2, level: 25, is_verified: true, is_online: true, joined_days: 310, followers_count: 2200, following_count: 180, friends_count: 73, visitors_count: 26 },
  { id: 2010, username: 'can', display_name: 'Can', age: 28, city: 'Adana', avatar_url: avatar('m5'), cover_url: cover('canyon'), bio: 'Her akşam oyun odasındayım 🎲', vip_level: 2, level: 30, is_verified: false, is_online: true, joined_days: 280, followers_count: 1500, following_count: 260, friends_count: 69, visitors_count: 14 },
  { id: 2011, username: 'elif', display_name: 'Elif', age: 25, city: 'Muğla', avatar_url: avatar('w7'), cover_url: cover('coast'), bio: 'Deniz, güneş, müzik.', vip_level: 1, level: 8, is_verified: false, is_online: false, joined_days: 40, followers_count: 210, following_count: 120, friends_count: 18, visitors_count: 4 },
  { id: 2012, username: 'mert', display_name: 'Mert', age: 30, city: 'İstanbul', avatar_url: avatar('m6'), cover_url: cover('guitar'), bio: 'Canlı müzik odası, her cuma.', vip_level: 3, level: 38, is_verified: true, is_online: true, joined_days: 520, followers_count: 5600, following_count: 300, friends_count: 110, visitors_count: 48 },
  { id: 2013, username: 'irem', display_name: 'İrem', age: 22, city: 'Konya', avatar_url: avatar('w8'), cover_url: cover('sky'), bio: 'Yeni buradayım, selam 👋', vip_level: 0, level: 3, is_verified: false, is_online: true, joined_days: 6, followers_count: 45, following_count: 60, friends_count: 7, visitors_count: 2 },
  { id: 2014, username: 'onur', display_name: 'Onur', age: 27, city: 'Trabzon', avatar_url: avatar('m7'), cover_url: cover('mountain'), bio: 'Futbol ve tavla.', vip_level: 1, level: 14, is_verified: false, is_online: true, joined_days: 150, followers_count: 380, following_count: 220, friends_count: 33, visitors_count: 6 },
  { id: 2015, username: 'naz', display_name: 'Naz', age: 24, city: 'İstanbul', avatar_url: avatar('w9'), cover_url: cover('night'), bio: 'Gece kuşu 🌙', vip_level: 3, level: 35, is_verified: true, is_online: true, joined_days: 400, followers_count: 4300, following_count: 190, friends_count: 95, visitors_count: 39 },
];

const seat = (index, user_id = null, opts = {}) => ({ index, user_id, is_muted: false, is_locked: false, ...opts });

export const rooms = [
  {
    id: 102938, title: 'Havuz Sohbeti 🌴', category: 'chat', cover_url: cover('beach'), is_live: false, listener_count: 28,
    host_id: 2001, hourly_rank: 1, announcement: 'Yeni gelenler kendini tanıtsın, herkese saygı şart.',
    seats: [seat(0, 2001), seat(1, 2002, { is_muted: true }), seat(2, 2003), seat(3, 2004), seat(4, 2005), seat(5, 2006, { is_muted: true }), seat(6, 2007), seat(7, null, { is_locked: true })],
  },
  {
    id: 104211, title: 'Gece Muhabbeti', category: 'chat', cover_url: cover('night'), is_live: true, listener_count: 18,
    host_id: 2015, hourly_rank: 4, announcement: 'Gece 3\'e kadar buradayız.',
    seats: [seat(0, 2015), seat(1, 2008), seat(2, 2014, { is_muted: true }), seat(3, null), seat(4, 2011), seat(5, null), seat(6, null), seat(7, null, { is_locked: true })],
  },
  {
    id: 105876, title: 'Canlı Müzik', category: 'music', cover_url: cover('music'), is_live: false, listener_count: 32,
    host_id: 2012, hourly_rank: 2, announcement: 'İstek parça için sohbete yazın.',
    seats: [seat(0, 2012), seat(1, 2009), seat(2, 2003, { is_muted: true }), seat(3, 2002), seat(4, null), seat(5, null), seat(6, null), seat(7, null)],
  },
  {
    id: 107340, title: 'Oyun Odası', category: 'game', cover_url: cover('game'), is_live: true, listener_count: 21,
    host_id: 2010, hourly_rank: 3, announcement: 'Zar turnuvası 22:00\'de başlıyor.',
    seats: [seat(0, 2010), seat(1, 2004), seat(2, 2014), seat(3, 2006, { is_muted: true }), seat(4, null), seat(5, null), seat(6, null), seat(7, null)],
  },
  {
    id: 108102, title: 'Kahve Molası ☕', category: 'new_people', cover_url: cover('cafe'), is_live: false, listener_count: 14,
    host_id: 2008, hourly_rank: 7, announcement: 'Yeni gelenlere özel tanışma odası.',
    seats: [seat(0, 2008), seat(1, 2013), seat(2, null), seat(3, null), seat(4, 2005), seat(5, null), seat(6, null), seat(7, null)],
  },
  {
    id: 109455, title: 'Akustik Akşamlar', category: 'music', cover_url: cover('guitar'), is_live: true, listener_count: 26,
    host_id: 2002, hourly_rank: 5, announcement: 'Bu akşam Türkçe akustik.',
    seats: [seat(0, 2002), seat(1, 2009), seat(2, 2007), seat(3, null), seat(4, null), seat(5, null), seat(6, null), seat(7, null, { is_locked: true })],
  },
  {
    id: 110027, title: 'Kitap Kulübü 📚', category: 'chat', cover_url: cover('terrace'), is_live: false, listener_count: 9,
    host_id: 2007, hourly_rank: 12, announcement: 'Bu hafta: Kürk Mantolu Madonna.',
    seats: [seat(0, 2007), seat(1, 2013), seat(2, null), seat(3, null), seat(4, null), seat(5, null), seat(6, null), seat(7, null)],
  },
  {
    id: 111390, title: 'Yeni Tanışanlar', category: 'new_people', cover_url: cover('city'), is_live: true, listener_count: 37,
    host_id: 2005, hourly_rank: 6, announcement: 'Herkes kısaca kendini tanıtsın.',
    seats: [seat(0, 2005), seat(1, 2011), seat(2, 2014), seat(3, 2013), seat(4, 2006), seat(5, null), seat(6, null), seat(7, null)],
  },
];

export const banners = [
  { id: 1, title: "Sesin, Sohbetin,\nOyunların\nMuti'de!", cta: 'Hemen Katıl', image_url: cover('music'), target: '#/explore' },
  { id: 2, title: 'Odana\nOyun Aç', cta: 'Oyun Odaları', image_url: cover('banner2'), target: '#/explore?category=game' },
  { id: 3, title: 'İlk alımına\n%50 bonus', cta: 'Coin Al', image_url: cover('banner3'), target: '#/wallet' },
];

export const gifts = [
  { id: 1, name: 'Gül', emoji: '🌹', price: 10 },
  { id: 2, name: 'Kalp', emoji: '💖', price: 20 },
  { id: 3, name: 'Kahve', emoji: '☕', price: 30 },
  { id: 4, name: 'Mikrofon', emoji: '🎤', price: 50 },
  { id: 5, name: 'Pasta', emoji: '🎂', price: 99 },
  { id: 6, name: 'Taç', emoji: '👑', price: 299 },
  { id: 7, name: 'Spor Araba', emoji: '🏎️', price: 999 },
  { id: 8, name: 'Yat', emoji: '🛥️', price: 2999 },
  { id: 9, name: 'Şato', emoji: '🏰', price: 5999 },
  { id: 10, name: 'Roket', emoji: '🚀', price: 9999 },
  { id: 11, name: 'Ejderha', emoji: '🐉', price: 19999 },
  { id: 12, name: 'Gezegen', emoji: '🪐', price: 49999 },
  // Şanslı hediyeler: gönderen coin geri kazanabilir
  { id: 13, name: 'Şanslı Yonca', emoji: '🍀', price: 10, is_lucky: true },
  { id: 14, name: 'Şans Kurabiyesi', emoji: '🥠', price: 50, is_lucky: true },
  { id: 15, name: 'Altın Zar', emoji: '🎲', price: 100, is_lucky: true },
];

export const coinPackages = [
  // Hediye paketleri: coinin yanında mağaza eşyası verir
  { id: 7, title: 'Başlangıç Paketi', coins: 600, bonus: 300, price_label: '₺19,99', item_id: 2, item_days: 7, is_one_time: true },
  { id: 8, title: 'Kraliyet Paketi', coins: 8000, bonus: 2000, price_label: '₺399,99', item_id: 103, item_days: 30 },
  { id: 1, coins: 600, bonus: 0, price_label: '₺29,99' },
  { id: 2, coins: 1500, bonus: 150, price_label: '₺69,99' },
  { id: 3, coins: 3200, bonus: 480, price_label: '₺149,99', is_popular: true },
  { id: 4, coins: 6800, bonus: 1360, price_label: '₺299,99' },
  { id: 5, coins: 14000, bonus: 3500, price_label: '₺599,99' },
  { id: 6, coins: 36000, bonus: 10800, price_label: '₺1.499,99', is_best_value: true },
];

export const conversations = [
  { id: 1, user_id: 2001, unread_count: 2, messages: [
    { from_me: false, text: 'Bu akşam odaya gelecek misin?', time: '21:02' },
    { from_me: true, text: 'Gelirim, 10 dakikaya oradayım.', time: '21:05' },
    { from_me: false, text: 'Süper, koltuk ayırıyorum 🎤', time: '21:06' },
  ] },
  { id: 2, user_id: 2003, unread_count: 0, messages: [
    { from_me: true, text: 'Dünkü şarkının adı neydi?', time: 'Dün' },
    { from_me: false, text: 'Listeyi sana atıyorum 🎵', time: 'Dün' },
  ] },
  { id: 3, user_id: 2010, unread_count: 1, messages: [
    { from_me: false, text: 'Zar turnuvasına takım lazım, var mısın?', time: '18:40' },
  ] },
  { id: 4, user_id: 2008, unread_count: 0, messages: [
    { from_me: false, text: 'Hediye için teşekkürler 🌹', time: 'Pzt' },
    { from_me: true, text: 'Rica ederim 🙂', time: 'Pzt' },
  ] },
];

export const wallPosts = [
  { id: 1, time_label: '2 gün önce', text: 'Harika bir geceydi, güzel insanlar 🔥', image_urls: [cover('terrace'), cover('night'), cover('music')], like_count: 128, comment_count: 24 },
  { id: 2, time_label: '1 hafta önce', text: 'Yeni avatar çerçevemi aldım 🎮', image_urls: [cover('city')], like_count: 86, comment_count: 11 },
];

// Mağaza eşyaları (backend demo/seed.py STORE_ITEMS ile aynı)
export const storeItems = [
  { id: 1, kind: 'frame', name: 'Klasik', style: 'frame-classic', emoji: '', price_7d: 300, price_30d: 900, vip_level_required: 0 },
  { id: 2, kind: 'frame', name: 'Neon', style: 'frame-neon', emoji: '', price_7d: 500, price_30d: 1500, vip_level_required: 0 },
  { id: 3, kind: 'frame', name: 'Altın', style: 'frame-gold', emoji: '', price_7d: 1000, price_30d: 3000, vip_level_required: 0 },
  { id: 4, kind: 'frame', name: 'Buz', style: 'frame-ice', emoji: '', price_7d: 500, price_30d: 1500, vip_level_required: 0 },
  { id: 5, kind: 'frame', name: 'Alev', style: 'frame-fire', emoji: '', price_7d: 800, price_30d: 2400, vip_level_required: 0 },
  { id: 6, kind: 'frame', name: 'Orman', style: 'frame-forest', emoji: '', price_7d: 500, price_30d: 1500, vip_level_required: 0 },
  { id: 7, kind: 'frame', name: 'Galaksi', style: 'frame-galaxy', emoji: '', price_7d: 1500, price_30d: 4500, vip_level_required: 0 },
  { id: 8, kind: 'frame', name: 'Kraliyet', style: 'frame-royal', emoji: '', price_7d: 2500, price_30d: 7500, vip_level_required: 2 },
  { id: 101, kind: 'entry_effect', name: 'Kıvılcım', style: 'entry-spark', emoji: '✨', price_7d: 500, price_30d: 1500, vip_level_required: 0 },
  { id: 102, kind: 'entry_effect', name: 'Spor Araba', style: 'entry-car', emoji: '🏎️', price_7d: 1200, price_30d: 3600, vip_level_required: 0 },
  { id: 103, kind: 'entry_effect', name: 'Roket', style: 'entry-rocket', emoji: '🚀', price_7d: 2000, price_30d: 6000, vip_level_required: 0 },
  { id: 104, kind: 'entry_effect', name: 'Taç', style: 'entry-crown', emoji: '👑', price_7d: 3000, price_30d: 9000, vip_level_required: 2 },
  { id: 105, kind: 'entry_effect', name: 'Ejderha', style: 'entry-dragon', emoji: '🐉', price_7d: 5000, price_30d: 15000, vip_level_required: 3 },
  { id: 201, kind: 'chat_bubble', name: 'Pembe', style: 'bubble-pink', emoji: '💗', price_7d: 300, price_30d: 900, vip_level_required: 0 },
  { id: 202, kind: 'chat_bubble', name: 'Okyanus', style: 'bubble-ocean', emoji: '🌊', price_7d: 300, price_30d: 900, vip_level_required: 0 },
  { id: 203, kind: 'chat_bubble', name: 'Altın', style: 'bubble-gold', emoji: '⭐', price_7d: 800, price_30d: 2400, vip_level_required: 0 },
  { id: 204, kind: 'chat_bubble', name: 'Neon', style: 'bubble-neon', emoji: '💜', price_7d: 1200, price_30d: 3600, vip_level_required: 1 },
];

// VIP kademeleri (backend services/vip_service.py VIP_TIERS ile aynı)
export const vipTiers = [
  { level: 1, name: 'Gümüş', price_30d: 3000, daily_coins: 60, item_ids: [3, 204], perks: ['VIP 1 rozeti', 'Altın çerçeve', 'Neon sohbet balonu', 'Her gün 60 coin'] },
  { level: 2, name: 'Altın', price_30d: 8000, daily_coins: 180, item_ids: [8, 104, 204], perks: ['VIP 2 rozeti', 'Kraliyet çerçevesi', 'Taç giriş efekti', 'Neon sohbet balonu', 'Her gün 180 coin'] },
  { level: 3, name: 'Elmas', price_30d: 20000, daily_coins: 500, item_ids: [8, 105, 204], perks: ['VIP 3 rozeti', 'Kraliyet çerçevesi', 'Ejderha giriş efekti', 'Neon sohbet balonu', 'Her gün 500 coin', 'Bütün VIP eşyalarını satın alabilme'] },
];

export const achievements = [
  { id: 1, name: 'Zar Ustası', emoji: '🎲', detail: 'Seviye 5' },
  { id: 2, name: 'Çark Şampiyonu', emoji: '🎡', detail: 'Seviye 3' },
  { id: 3, name: 'Sohbet Yıldızı', emoji: '⭐', detail: 'Seviye 4' },
  { id: 4, name: 'Turnuva', emoji: '🏆', detail: 'İlk 100' },
];

export const recentRewards = [
  { id: 1, name: 'Altın Kupa', emoji: '🏆', date_label: '15.09.2026' },
  { id: 2, name: 'Özel Çerçeve', emoji: '💠', date_label: '01.09.2026' },
  { id: 3, name: '365 Gün Rozeti', emoji: '🎖️', date_label: '28.08.2026' },
  { id: 4, name: '1000 Coin', emoji: '🪙', date_label: '20.08.2026' },
];

// Oda içi canlı sohbet simülasyonu için hazır cümleler
export const chatLines = [
  'Harika bir ortam 👏', 'Bu gece oyun var mı? 🎲', 'Herkes hoşgeldin 🎉', 'Müzik süper 🎵',
  'Yeni gelenler kendini tanıtsın 😄', 'Selam millet!', 'Kim nereden katılıyor?', 'Bu odayı takibe aldım',
  'Mikrofona çıkabilir miyim?', 'Dün geceki sohbet efsaneydi', 'Bir şarkı isteğim var', 'Ankara\'dan selamlar 👋',
];

// Bildirim merkezi (alan adları API ile aynı: GET /notifications)
export const notifications = [
  { id: 3, type: 'gift_received', text: 'Merve sana 🌹 Gül x5 gönderdi (+25 elmas).', actor_id: 2001, data: {}, is_read: false, time_label: '5 dk önce' },
  { id: 2, type: 'follow', text: 'Selin seni takip etmeye başladı.', actor_id: 2003, data: { user_id: 2003 }, is_read: false, time_label: '1 saat önce' },
  { id: 1, type: 'level_up', text: 'Tebrikler! Lv.12 oldun 🎉', actor_id: null, data: {}, is_read: true, time_label: 'Dün' },
];
