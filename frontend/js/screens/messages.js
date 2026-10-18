// Mesajlar: sohbet listesi ve birebir sohbet ekranı
import { api } from '../api.js';
import { USE_MOCK } from '../config.js';
import { esc, icon, avatarImg } from '../ui.js';

export async function renderMessages(root) {
  const conversations = await api.listConversations();

  root.innerHTML = `
    <header class="topbar"><h1 class="page-title">Mesajlar</h1></header>
    <div class="conversation-list">
      ${conversations.length ? conversations.map((c) => `
        <a class="conversation" href="#/chat/${c.id}">
          <span class="conversation-avatar">${avatarImg(c.user, 'avatar-md')}${c.user.is_online ? '<span class="online-dot"></span>' : ''}</span>
          <span class="conversation-body">
            <b>${esc(c.user.display_name)}</b>
            <small>${c.last_message ? `${c.last_message.from_me ? 'Sen: ' : ''}${esc(c.last_message.text)}` : 'Sohbeti başlat'}</small>
          </span>
          <span class="conversation-meta">
            <small>${esc(c.last_message?.time || '')}</small>
            ${c.unread_count ? `<i class="unread">${c.unread_count}</i>` : ''}
          </span>
        </a>`).join('') : '<div class="empty"><p>Henüz mesajın yok.</p></div>'}
    </div>`;
}

const AUTO_REPLIES = ['Tamamdır 🙂', 'Odada görüşürüz!', 'Haha aynen 😄', 'Birazdan yazıyorum.'];

export async function renderChat(root, { params }) {
  const conversation = await api.getConversation(params[0]);
  const { user } = conversation;

  const bubble = (m) => `<div class="bubble ${m.from_me ? 'is-mine' : ''}"><p>${esc(m.text)}</p><small>${esc(m.time)}</small></div>`;

  root.innerHTML = `
    <div class="chat-screen">
      <header class="topbar topbar-solid">
        <a class="icon-btn" href="#/messages" aria-label="Geri">${icon('chevron-left', 22)}</a>
        <a class="chat-peer" href="#/profile/${user.id}">
          ${avatarImg(user, 'avatar-sm')}
          <span><b>${esc(user.display_name)}</b><small>${user.is_online ? 'Çevrimiçi' : 'Çevrimdışı'}</small></span>
        </a>
      </header>
      <div class="chat-thread" id="thread">${conversation.messages.map(bubble).join('')}</div>
      <form class="composer" id="composer">
        <input name="text" placeholder="Mesaj yaz..." autocomplete="off" maxlength="300" />
        <button class="icon-btn icon-btn-primary" type="submit" aria-label="Gönder">${icon('send', 18)}</button>
      </form>
    </div>`;

  const thread = root.querySelector('#thread');
  const scrollDown = () => { thread.scrollTop = thread.scrollHeight; };
  scrollDown();

  let replyTimer;
  root.querySelector('#composer').addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = event.target.elements.text;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    const message = await api.sendMessage(conversation.id, text);
    thread.insertAdjacentHTML('beforeend', bubble(message));
    scrollDown();

    // Yalnızca mock: karşı taraf kısa süre sonra yanıt verir. Gerçek backend'de
    // karşı tarafın mesajı sohbet yeniden açılınca görünür (anlık bildirim henüz yok).
    if (!USE_MOCK) return;
    clearTimeout(replyTimer);
    replyTimer = setTimeout(() => {
      const reply = { from_me: false, text: AUTO_REPLIES[Math.floor(Math.random() * AUTO_REPLIES.length)], time: 'Şimdi' };
      conversation.messages.push(reply);
      thread.insertAdjacentHTML('beforeend', bubble(reply));
      scrollDown();
    }, 1600);
  });

  return () => clearTimeout(replyTimer);
}
