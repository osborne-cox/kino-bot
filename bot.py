import hashlib
import json
import logging
import os
import time
from enum import Enum

import telebot
from dotenv import load_dotenv
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

API_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "627993386"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "uucineculturebot")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "sessions": os.path.join(BASE_DIR, "sessions.json"),
    "users":    os.path.join(BASE_DIR, "all_users.json"),
    "afisha":   os.path.join(BASE_DIR, "afisha.json"),
    "address":  os.path.join(BASE_DIR, "address.json"),
}


class AdminState(str, Enum):
    WAITING_NAME          = "WAITING_NAME"
    WAITING_READABLE_NAME = "WAITING_READABLE_NAME"
    WAITING_FORWARD       = "WAITING_FORWARD"
    WAITING_AFISHA_POST   = "WAITING_AFISHA_POST"
    WAITING_ADDRESS_POST  = "WAITING_ADDRESS_POST"
    WAITING_BROADCAST     = "WAITING_BROADCAST"


bot = telebot.TeleBot(API_TOKEN)
admin_state: dict[int, AdminState] = {}
temp_session_data: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("Failed to read %s", path)
        return default


def save_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        log.exception("Failed to write %s", path)


def register_user(user_id: int) -> None:
    users = set(load_json(FILES["users"], []))
    if user_id not in users:
        users.add(user_id)
        save_json(FILES["users"], list(users))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def make_session_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:10]


def main_menu(user_id: int) -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin(user_id):
        markup.add("➕ Создать анонс", "📌 Обновить афишу")
        markup.add("📍 Обновить адрес", "👥 Списки гостей")
        markup.add("📢 Рассылка (Текст)", "🗑 Удалить сеанс")
    else:
        markup.add("📰 афиша месяца", "🎟 мои встречи")
        markup.add("🛎️ наш адрес", "🎞 о кинокультуре")
    return markup


def find_session(sessions: dict, safe_id: str) -> dict | None:
    for s in sessions.values():
        if s.get("safe_id") == safe_id:
            return s
    # fallback для старых записей, где safe_id использовался как ключ
    return sessions.get(safe_id)


def broadcast_photo(users: list, photo_id: str, keyboard: InlineKeyboardMarkup) -> int:
    count = 0
    for uid in users:
        try:
            bot.send_photo(uid, photo_id, reply_markup=keyboard)
            count += 1
            time.sleep(0.05)
        except Exception:
            log.debug("Could not deliver photo to %s", uid)
    return count


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = message.from_user.id
    register_user(user_id)

    parts = message.text.split()
    if len(parts) > 1:
        _handle_deep_link(message, parts[1].strip())
        return

    role = "Администратор" if is_admin(user_id) else "зритель"
    bot.reply_to(
        message,
        f"Сайнуу / привет, {role}!\n"
        "Ты запустил кинобота — помощника в организации кинокультуры.\n"
        "О нас можно почитать, на встречу можно записаться. Технологии!",
        reply_markup=main_menu(user_id),
    )


def _handle_deep_link(message, safe_id: str) -> None:
    user_id = message.from_user.id
    user_info = {
        "name": message.from_user.first_name,
        "username": message.from_user.username,
        "id": user_id,
    }
    all_sessions = load_json(FILES["sessions"], {})
    session = find_session(all_sessions, safe_id)

    if not session:
        bot.reply_to(message, "❌ Этот сеанс не найден (возможно, удалён).", reply_markup=main_menu(user_id))
        return

    if any(g["id"] == user_id for g in session["attendees"]):
        bot.reply_to(
            message,
            f"Ты уже в списках на *{session['name']}*. Ждём тебя!",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id),
        )
        return

    session["attendees"].append(user_info)
    all_sessions[session.get("safe_id", safe_id)] = session
    save_json(FILES["sessions"], all_sessions)

    bot.reply_to(message, "Отлично, ты в списке! Ждём на поболтать и на посмотреть.", reply_markup=main_menu(user_id))

    if user_id != ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, f"👤 Новая запись: {user_info['name']} (на {session['name']})")
        except Exception:
            log.warning("Could not notify admin about new attendee")


# ---------------------------------------------------------------------------
# User handlers
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📰 афиша месяца")
def show_afisha(message):
    afisha = load_json(FILES["afisha"], {})
    if afisha.get("photo_id") and afisha.get("url"):
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("☰ ознакомиться с афишей месяца", url=afisha["url"])
        )
        try:
            bot.send_photo(message.chat.id, afisha["photo_id"], reply_markup=kb)
        except Exception:
            log.exception("Failed to send afisha photo")
            bot.reply_to(message, "Ошибка загрузки афиши.")
    else:
        bot.reply_to(message, "Афиша на этот месяц ещё формируется.")


@bot.message_handler(func=lambda m: m.text == "🛎️ наш адрес")
def show_address(message):
    addr = load_json(FILES["address"], {})
    if addr.get("chat_id"):
        try:
            bot.copy_message(message.chat.id, addr["chat_id"], addr["message_id"])
        except Exception:
            log.exception("Failed to copy address message")
            bot.reply_to(message, "Информация об адресе пока не загружена.")
    else:
        bot.reply_to(message, "Адрес скоро появится здесь.")


@bot.message_handler(func=lambda m: m.text == "🎟 мои встречи")
def show_my_tickets(message):
    user_id = message.from_user.id
    all_sessions = load_json(FILES["sessions"], {})
    my_sessions = [
        data["name"]
        for data in all_sessions.values()
        if any(g["id"] == user_id for g in data["attendees"])
    ]

    if my_sessions:
        text = "🎟 *Ваши планы на ближайшую субботу:*\n\n" + "\n".join(f"• {n}" for n in my_sessions)
    else:
        text = "Вы ещё не планировали встречу с нами? Надо скорей исправлять — ознакомьтесь с афишей месяца!"
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎞 о кинокультуре")
def show_info(message):
    text = (
        "Нас зовут Кристина и Данила, мы организаторы _кинокультуры_! "
        "Кристина выступает ведущим проекта, а Данила отвечает за техническое сопровождение.\n\n"
        "Наш киноклуб пустил корни и расцвёл в Старом городе @oldtownuu! "
        "И встречаемся мы в стенах родной Мастерской — самое уютное местечко в Улан-Удэ.\n\n"
        "Немного про то, как мы появились: команда СГ стремится к поднятию интереса к культуре "
        "и наследию Бурятии, но молодые кадры, как песок сквозь пальцы... утекают в перспективные столицы. "
        "Но родному городу все нужны! Ваш голос, ваши мечты и стремления, попытки что-то изменить. "
        "А что, если я скажу вам, что вы можете повлиять на облик своей родины? "
        "И именно Старый город х _кинокультура_ станут вашими проводниками.\n\n"
        "И как раз тогда, когда стало ясно, что молодёжи нужно своё коммьюнити в рамках интереса "
        "к локальной идентичности, её поиску и развитию, родилась идея публичного клуба. "
        "На наших встречах мы всё также стремимся заинтересовать горожан вопросами социального "
        "и культурного характера, а для этого крутим классное фестивальное, независимое кино "
        "с выраженной авторской позицией.\n\n"
        "Заглавная тема проекта — это диалог: немного контекста перед показом, обсуждение после, "
        "живые мысли и разные взгляды. Теперь у каждого есть возможность найти что-то своё "
        "в показанных картинах, но самое главное, это разделить с нами ваши мысли и идеи. "
        "Открытая к коллаборациям и предложениям, _кинокультура_ будет становиться круче и круче, "
        "собирая исключительную аудиторию: вдохновлённую, неравнодушную, открытую. Присоединяйся к нам!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Admin: /cancel
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["cancel"])
def cancel_action(message):
    if is_admin(message.from_user.id) and ADMIN_ID in admin_state:
        admin_state.pop(ADMIN_ID, None)
        temp_session_data.pop(ADMIN_ID, None)
        bot.reply_to(message, "🚫 Действие отменено.")
    else:
        bot.reply_to(message, "Нечего отменять.")


# ---------------------------------------------------------------------------
# Admin: address
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📍 Обновить адрес" and is_admin(m.from_user.id))
def admin_set_address_start(message):
    admin_state[ADMIN_ID] = AdminState.WAITING_ADDRESS_POST
    bot.reply_to(message, "Перешлите мне пост (с картой или видео) из канала, где показан ваш адрес.")


@bot.message_handler(
    content_types=["text", "photo", "video", "document", "location", "venue"],
    func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_ADDRESS_POST,
)
def admin_save_address(message):
    chat_id = message.chat.id
    msg_id = message.message_id
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id

    save_json(FILES["address"], {"chat_id": chat_id, "message_id": msg_id})
    admin_state.pop(ADMIN_ID, None)
    bot.reply_to(message, "✅ Адрес сохранён! Проверьте кнопку.")


# ---------------------------------------------------------------------------
# Admin: afisha
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📌 Обновить афишу" and is_admin(m.from_user.id))
def admin_set_afisha_start(message):
    admin_state[ADMIN_ID] = AdminState.WAITING_AFISHA_POST
    bot.reply_to(message, "1️⃣ Опубликуйте афишу В КАНАЛЕ.\n2️⃣ Перешлите её мне сюда.")


@bot.message_handler(
    content_types=["photo"],
    func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_AFISHA_POST,
)
def admin_save_afisha(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ Это не пересылка из канала.")
        return

    msg_id = message.forward_from_message_id
    channel_username = message.forward_from_chat.username
    save_json(FILES["afisha"], {
        "photo_id": message.photo[-1].file_id,
        "url": f"https://t.me/{channel_username}/{msg_id}",
    })

    admin_state.pop(ADMIN_ID, None)
    bot.reply_to(message, "✅ Афиша обновлена!")


# ---------------------------------------------------------------------------
# Admin: announcement wizard
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "➕ Создать анонс" and is_admin(m.from_user.id))
def wizard_step1(message):
    admin_state[ADMIN_ID] = AdminState.WAITING_NAME
    temp_session_data[ADMIN_ID] = {}
    bot.reply_to(
        message,
        "🎬 *Создание анонса*\n\n"
        "1️⃣ Придумайте ID сеанса (любой, хоть по-русски).\n"
        "Например: `Кино 24.01`",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_NAME)
def wizard_step2(message):
    safe_id = make_session_id(message.text.strip())
    all_sessions = load_json(FILES["sessions"], {})

    if any(s.get("safe_id") == safe_id for s in all_sessions.values()):
        bot.reply_to(message, "⚠️ Такой ID уже есть.")
        return

    temp_session_data[ADMIN_ID]["safe_id"] = safe_id
    admin_state[ADMIN_ID] = AdminState.WAITING_READABLE_NAME
    bot.reply_to(message, "2️⃣ Введите красивое название для списков (например: `Мир 17.01`).", parse_mode="Markdown")


@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_READABLE_NAME)
def wizard_step3(message):
    temp_session_data[ADMIN_ID]["name"] = message.text.strip()
    admin_state[ADMIN_ID] = AdminState.WAITING_FORWARD
    bot.reply_to(
        message,
        "3️⃣ *Инструкция:*\n\n"
        "1. Опубликуйте пост с анонсом в канале (с картинкой).\n"
        "2. Перешлите этот пост мне сюда.\n\n"
        "Я добавлю к нему кнопку.",
        parse_mode="Markdown",
    )


@bot.message_handler(
    content_types=["photo"],
    func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_FORWARD,
)
def wizard_finish(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ Это не пересылка из канала.")
        return

    data = temp_session_data[ADMIN_ID]
    safe_id = data["safe_id"]
    name = data["name"]

    channel_id = message.forward_from_chat.id
    channel_username = message.forward_from_chat.username
    message_id = message.forward_from_message_id
    photo_id = message.photo[-1].file_id

    post_url = f"https://t.me/{channel_username}/{message_id}"
    bot_link = f"https://t.me/{BOT_USERNAME}?start={safe_id}"

    kb_channel = InlineKeyboardMarkup().add(InlineKeyboardButton("☰ я приду на встречу", url=bot_link))
    try:
        bot.edit_message_reply_markup(channel_id, message_id, reply_markup=kb_channel)
        bot.reply_to(message, f"✅ Кнопка добавлена!\nID сеанса: `{safe_id}`", parse_mode="Markdown")
    except Exception:
        log.exception("Failed to add button to channel post")
        bot.reply_to(message, "⚠️ Не смог добавить кнопку к посту в канале.")

    sessions = load_json(FILES["sessions"], {})
    sessions[safe_id] = {"name": name, "safe_id": safe_id, "attendees": []}
    save_json(FILES["sessions"], sessions)

    users = load_json(FILES["users"], [])
    if users:
        bot.send_message(message.chat.id, f"🚀 Рассылка по {len(users)} чел...")
        kb_pm = InlineKeyboardMarkup().add(
            InlineKeyboardButton("☰ узнать подробности новой встречи", url=post_url)
        )
        count = broadcast_photo(users, photo_id, kb_pm)
        bot.send_message(message.chat.id, f"🏁 Доставлено: {count}/{len(users)}")

    admin_state.pop(ADMIN_ID, None)
    temp_session_data.pop(ADMIN_ID, None)


# ---------------------------------------------------------------------------
# Admin: guests & delete
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "👥 Списки гостей" and is_admin(m.from_user.id))
def admin_guests_menu(message):
    all_sessions = load_json(FILES["sessions"], {})
    if not all_sessions:
        bot.reply_to(message, "База сеансов пуста.")
        return
    kb = InlineKeyboardMarkup()
    for s_id, s_data in all_sessions.items():
        kb.add(InlineKeyboardButton(f"📂 {s_data['name']} ({len(s_data['attendees'])})", callback_data=f"guests_{s_id}"))
    bot.reply_to(message, "Выберите сеанс:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "🗑 Удалить сеанс" and is_admin(m.from_user.id))
def admin_delete_menu(message):
    all_sessions = load_json(FILES["sessions"], {})
    if not all_sessions:
        bot.reply_to(message, "Нечего удалять.")
        return
    kb = InlineKeyboardMarkup()
    for s_id, s_data in all_sessions.items():
        kb.add(InlineKeyboardButton(f"❌ {s_data['name']}", callback_data=f"del_{s_id}"))
    bot.reply_to(message, "Нажмите для удаления:", reply_markup=kb)


# ---------------------------------------------------------------------------
# Admin: broadcast
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка (Текст)" and is_admin(m.from_user.id))
def admin_broadcast_start(message):
    admin_state[ADMIN_ID] = AdminState.WAITING_BROADCAST
    bot.reply_to(message, "✍️ Напишите текст сообщения для всех пользователей.\n/cancel для отмены.")


@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == AdminState.WAITING_BROADCAST)
def process_broadcast(message):
    users = load_json(FILES["users"], [])
    bot.reply_to(message, f"🚀 Рассылка ({len(users)} чел)...")
    count = 0
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
            time.sleep(0.05)
        except Exception:
            log.debug("Could not deliver broadcast to %s", uid)
    bot.reply_to(message, f"✅ Успешно: {count}")
    admin_state.pop(ADMIN_ID, None)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data.startswith("guests_") and is_admin(call.from_user.id):
        s_id = call.data[7:]
        sessions = load_json(FILES["sessions"], {})
        if s_id in sessions:
            guests = sessions[s_id]["attendees"]
            lines = [f"📂 {sessions[s_id]['name']} ({len(guests)} чел.):\n"]
            for i, g in enumerate(guests, 1):
                mention = f"@{g['username']}" if g["username"] else "—"
                lines.append(f"{i}. {g['name']} ({mention})")
            try:
                bot.send_message(call.message.chat.id, "\n".join(lines))
            except Exception:
                log.exception("Failed to send guest list")
        bot.answer_callback_query(call.id)

    elif call.data.startswith("del_") and is_admin(call.from_user.id):
        s_id = call.data[4:]
        sessions = load_json(FILES["sessions"], {})
        if s_id in sessions:
            name = sessions.pop(s_id)["name"]
            save_json(FILES["sessions"], sessions)
            bot.edit_message_text(f"🗑 Сеанс «{name}» удалён.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Уже удалено.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Бот запущен")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception:
            log.exception("Ошибка сети, перезапуск через 5 сек")
            time.sleep(5)
