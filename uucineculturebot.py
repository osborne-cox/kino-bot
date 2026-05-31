import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os
import json
import time
import hashlib
import sys

# --- ⚙️ НАСТРОЙКИ ---
API_TOKEN = '7561221615:AAHxyHTqOH1Hjqi9xBKXjW0tq85e-VBxZng'
ADMIN_ID = 627993386
BOT_USERNAME = "uucineculturebot"

# ЯКОРЬ: Жестко указываем путь к папке
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "sessions": os.path.join(BASE_DIR, "sessions.json"),
    "users": os.path.join(BASE_DIR, "all_users.json"),
    "afisha": os.path.join(BASE_DIR, "afisha.json"),
    "address": os.path.join(BASE_DIR, "address.json") # Новый файл для адреса
}
# --- КОНЕЦ НАСТРОЕК ---

bot = telebot.TeleBot(API_TOKEN)
admin_state = {}
temp_session_data = {}

# --- 🛠 РАБОТА С ФАЙЛАМИ ---

def log(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}")
    sys.stdout.flush()

def load_json(filename):
    if not os.path.exists(filename):
        return {} if filename != FILES["users"] else []
    try:
        with open(filename, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Ошибка чтения {filename}: {e}")
        return {} if filename != FILES["users"] else []

def save_json(filename, data):
    try:
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        log(f"Критическая ошибка сохранения {filename}: {e}")

def add_global_user(user_id):
    users = set(load_json(FILES["users"]))
    if user_id not in users:
        users.add(user_id)
        save_json(FILES["users"], list(users))

def is_admin(user_id):
    return user_id == ADMIN_ID

def generate_safe_id(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:10]

# --- 📱 МЕНЮ ---

def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin(user_id):
        # Добавил кнопку настройки адреса для админа
        markup.add("➕ Создать анонс", "📌 Обновить афишу")
        markup.add("📍 Обновить адрес", "👥 Списки гостей") 
        markup.add("📢 Рассылка (Текст)", "🗑 Удалить сеанс")
    else:
        # Добавил кнопку адреса для пользователя
        markup.add("📰 афиша месяца", "🎟 мои встречи")
        markup.add("🛎️ наш адрес", "🎞 о кинокультуре")
    return markup

# --- 🚀 СТАРТ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user_id = message.from_user.id
        add_global_user(user_id)
        
        user_info = {"name": message.from_user.first_name, "username": message.from_user.username, "id": user_id}
        parts = message.text.split()
        
        # Deep Link
        if len(parts) > 1:
            safe_id = parts[1].strip()
            all_sessions = load_json(FILES["sessions"])

            found_session = None
            for s_data in all_sessions.values():
                if s_data.get('safe_id') == safe_id:
                    found_session = s_data
                    break
            
            if not found_session and safe_id in all_sessions:
                found_session = all_sessions[safe_id]

            if found_session:
                attendees_ids = [u['id'] for u in found_session["attendees"]]
                
                if user_id in attendees_ids:
                    bot.reply_to(message, f"Ты уже в списках на *{found_session['name']}*. Ждем тебя!", 
                                 parse_mode="Markdown", reply_markup=get_main_menu(user_id))
                else:
                    found_session["attendees"].append(user_info)
                    # Сохраняем по ключу safe_id если он есть, иначе по старому ключу
                    key_to_save = found_session.get('safe_id', safe_id)
                    all_sessions[key_to_save] = found_session
                    save_json(FILES["sessions"], all_sessions)
                    
                    bot.reply_to(message, "Отлично, ты в списке! Ждем на поболтать и на посмотреть.", 
                                 reply_markup=get_main_menu(user_id))
                    
                    if user_id != ADMIN_ID:
                        try: bot.send_message(ADMIN_ID, f"👤 Новая запись: {user_info['name']} (на {found_session['name']})")
                        except: pass
            else:
                bot.reply_to(message, "❌ Этот сеанс не найден (возможно, удален).", reply_markup=get_main_menu(user_id))
        else:
            role = "Администратор" if is_admin(user_id) else "зритель"
            text = (f"Сайнуу / привет, {role}! \nТы запустил кинобота — помощника в организации кинокультуры.\n"
                    "О нас можно почитать, на встречу можно записаться. Технологии!")
            bot.reply_to(message, text, reply_markup=get_main_menu(user_id))
            
    except Exception as e:
        log(f"Error in start: {e}")
        bot.reply_to(message, "Ошибка старта. Нажмите /start еще раз.")

# --- 👤 ФУНКЦИИ ПОЛЬЗОВАТЕЛЯ ---

@bot.message_handler(func=lambda m: m.text == "📰 афиша месяца")
def show_afisha(message):
    afisha_data = load_json(FILES["afisha"])
    if afisha_data and "photo_id" in afisha_data and "url" in afisha_data:
        try:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("☰ ознакомиться с афишей месяца", url=afisha_data["url"]))
            bot.send_photo(message.chat.id, afisha_data["photo_id"], reply_markup=kb)
        except Exception:
            bot.reply_to(message, "Ошибка загрузки афиши.")
    else:
        bot.reply_to(message, "Афиша на этот месяц еще формируется.")

@bot.message_handler(func=lambda m: m.text == "🛎️ наш адрес")
def show_address(message):
    address_data = load_json(FILES["address"])
    if address_data and "chat_id" in address_data:
        try:
            # Просто копируем пост с адресом (карта/видео/текст) из канала
            bot.copy_message(message.chat.id, address_data["chat_id"], address_data["message_id"])
        except Exception:
            bot.reply_to(message, "Информация об адресе пока не загружена.")
    else:
        bot.reply_to(message, "Адрес скоро появится здесь.")

@bot.message_handler(func=lambda m: m.text == "🎟 мои встречи")
def show_my_tickets(message):
    user_id = message.from_user.id
    all_sessions = load_json(FILES["sessions"])
    my_sessions = []
    for s_id, data in all_sessions.items():
        for guest in data['attendees']:
            if guest['id'] == user_id:
                my_sessions.append(data['name'])
    
    if my_sessions:
        text = "🎟 *Ваши планы на ближайшую субботу:*\n\n" + "\n".join([f"• {name}" for name in my_sessions])
    else:
        text = "Вы еще не планировали встречу с нами? Надо скорей исправлять — ознакомьтесь с афишей месяца!"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎞 о кинокультуре")
def show_info(message):
    text = """Нас зовут Кристина и Данила, мы организаторы _кинокультуры_! Кристина выступает ведущим проекта, а Данила отвечает за техническое сопровождение.

Наш киноклуб пустил корни и расцвел в Старом городе @oldtownuu ! И встречаемся мы в стенах родной Мастерской — самое уютное местечко в Улан-Удэ.

Немного про то, как мы появились: команда СГ стремится к поднятию интереса к культуре и наследию Бурятии, но молодые кадры, как песок сквозь пальцы... утекают в перспективные столицы. Но родному городу все нужны! Ваш голос, ваши мечты и стремления, попытки что-то изменить. А что, если я скажу вам, что вы можете повлиять на облик своей родины? И именно Старый город х _кинокультура_ станут вашими проводниками.

И как раз тогда, когда стало ясно, что молодежи нужно свое коммьюнити в рамках интереса к локальной идентичности, ее поиску и развитию, родилась идея публичного клуба. На наших встречах мы все также стремимся заинтересовать горожан вопросами социального и культурного характера, а для этого крутим классное фестивальное, независимое кино с выраженной авторской позицией. 

Заглавная тема проекта — это диалог: немного контекста перед показом, обсуждение после, живые мысли и разные взгляды. Теперь у каждого есть возможность найти что-то свое в показанных картинах, но самое главное, это разделить с нами ваши мысли и идеи. Открытая к коллаборациям и предложениям, _кинокультура_ будет становиться круче и круче, собирая исключительную аудиторию: вдохновленную, неравнодушную, открытую. Присоединяйся к нам!"""
    bot.reply_to(message, text, parse_mode="Markdown")

# --- 👑 ФУНКЦИИ АДМИНИСТРАТОРА ---

@bot.message_handler(commands=['cancel'])
def cancel_action(message):
    if is_admin(message.from_user.id) and ADMIN_ID in admin_state:
        del admin_state[ADMIN_ID]
        if ADMIN_ID in temp_session_data: del temp_session_data[ADMIN_ID]
        bot.reply_to(message, "🚫 Действие отменено.")
    else:
        bot.reply_to(message, "Нечего отменять.")

# --- НАСТРОЙКА АДРЕСА ---
@bot.message_handler(func=lambda m: m.text == "📍 Обновить адрес" and is_admin(m.from_user.id))
def admin_set_address_start(message):
    admin_state[ADMIN_ID] = "WAITING_ADDRESS_POST"
    bot.reply_to(message, "Перешлите мне пост (с картой или видео) из канала, где показан ваш адрес.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'location', 'venue'], 
                     func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_ADDRESS_POST")
def admin_save_address(message):
    chat_id = message.chat.id
    msg_id = message.message_id
    
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        msg_id = message.forward_from_message_id
        
    save_json(FILES["address"], {"chat_id": chat_id, "message_id": msg_id})
    del admin_state[ADMIN_ID]
    bot.reply_to(message, "✅ Адрес сохранен! Проверьте кнопку.")

# --- НАСТРОЙКА АФИШИ ---
@bot.message_handler(func=lambda m: m.text == "📌 Обновить афишу" and is_admin(m.from_user.id))
def admin_set_afisha_start(message):
    admin_state[ADMIN_ID] = "WAITING_AFISHA_POST"
    bot.reply_to(message, "1️⃣ Опубликуйте афишу В КАНАЛЕ.\n2️⃣ Перешлите её мне сюда.")

@bot.message_handler(content_types=['photo'], 
                     func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_AFISHA_POST")
def admin_save_afisha(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ Это не пересылка из канала.")
        return
    
    photo_id = message.photo[-1].file_id
    channel_username = message.forward_from_chat.username
    msg_id = message.forward_from_message_id
    post_url = f"https://t.me/{channel_username}/{msg_id}"

    save_json(FILES["afisha"], {
        "photo_id": photo_id,
        "url": post_url
    })
    
    del admin_state[ADMIN_ID]
    bot.reply_to(message, "✅ Афиша обновлена!")

# --- WIZARD (СОЗДАНИЕ АНОНСА) ---

@bot.message_handler(func=lambda m: m.text == "➕ Создать анонс" and is_admin(m.from_user.id))
def wizard_step1_id(message):
    admin_state[ADMIN_ID] = "WAITING_NAME"
    temp_session_data[ADMIN_ID] = {}
    bot.reply_to(message, "🎬 *Создание анонса*\n\n1️⃣ Придумайте ID сеанса (ЛЮБОЙ, хоть по-русски).\nНапример: `Кино 24.01`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_NAME")
def wizard_step2_readable_name(message):
    raw_id = message.text.strip()
    safe_id = generate_safe_id(raw_id)
    
    # Проверка (на всякий случай)
    all_sessions = load_json(FILES["sessions"])
    for s in all_sessions.values():
        if s.get('safe_id') == safe_id:
            bot.reply_to(message, "⚠️ Такой ID уже есть.")
            return

    temp_session_data[ADMIN_ID]['safe_id'] = safe_id
    admin_state[ADMIN_ID] = "WAITING_READABLE_NAME"
    bot.reply_to(message, "2️⃣ Введите КРАСИВОЕ название для списков (например: `Мир 17.01`).", parse_mode="Markdown")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_READABLE_NAME")
def wizard_step3_content(message):
    temp_session_data[ADMIN_ID]['name'] = message.text.strip()
    admin_state[ADMIN_ID] = "WAITING_FORWARD"
    bot.reply_to(message, 
                 "3️⃣ **ИНСТРУКЦИЯ:**\n\n"
                 "1. Опубликуйте пост с анонсом в КАНАЛЕ (с картинкой).\n"
                 "2. **Перешлите** этот пост мне сюда.\n\n"
                 "Я добавлю к нему кнопку.", 
                 parse_mode="Markdown")

@bot.message_handler(content_types=['photo'], 
                     func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_FORWARD")
def wizard_finish(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ Это не пересылка из канала.")
        return

    data = temp_session_data[ADMIN_ID]
    safe_id = data['safe_id']
    name = data['name']
    
    channel_id = message.forward_from_chat.id
    channel_username = message.forward_from_chat.username
    message_id = message.forward_from_message_id
    photo_id = message.photo[-1].file_id
    
    post_url = f"https://t.me/{channel_username}/{message_id}"
    
    url_start = f"https://t.me/{BOT_USERNAME}?start={safe_id}"
    kb_channel = InlineKeyboardMarkup().add(InlineKeyboardButton("☰ я приду на встречу", url=url_start))
    
    try:
        bot.edit_message_reply_markup(channel_id, message_id, reply_markup=kb_channel)
        bot.reply_to(message, f"✅ Кнопка добавлена!\nID сеанса: `{safe_id}`")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Не смог добавить кнопку: {e}")
    
    sessions = load_json(FILES["sessions"])
    sessions[safe_id] = {
        "name": name, 
        "safe_id": safe_id,
        "attendees": []
    }
    save_json(FILES["sessions"], sessions)
    
    users = load_json(FILES["users"])
    if users:
        bot.send_message(message.chat.id, f"🚀 Рассылка по {len(users)} чел...")
        kb_pm = InlineKeyboardMarkup().add(InlineKeyboardButton("☰ узнать подробности новой встречи", url=post_url))
        count = 0
        for uid in users:
            try:
                bot.send_photo(uid, photo_id, reply_markup=kb_pm)
                count += 1
                time.sleep(0.05)
            except: pass
        bot.send_message(message.chat.id, f"🏁 Доставлено: {count}/{len(users)}")
    
    del admin_state[ADMIN_ID]
    del temp_session_data[ADMIN_ID]

# --- АДМИНСКИЕ ФУНКЦИИ ---

@bot.message_handler(func=lambda m: m.text == "👥 Списки гостей" and is_admin(m.from_user.id))
def admin_guests_menu(message):
    all_sessions = load_json(FILES["sessions"])
    if not all_sessions:
        bot.reply_to(message, "База сеансов пуста.")
        return
    keyboard = InlineKeyboardMarkup()
    for s_id, s_data in all_sessions.items():
        count = len(s_data['attendees'])
        keyboard.add(InlineKeyboardButton(f"📂 {s_data['name']} ({count})", callback_data=f"guests_{s_id}"))
    bot.reply_to(message, "Выберите сеанс:", reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить сеанс" and is_admin(m.from_user.id))
def admin_delete_menu(message):
    all_sessions = load_json(FILES["sessions"])
    if not all_sessions:
        bot.reply_to(message, "Нечего удалять.")
        return
    keyboard = InlineKeyboardMarkup()
    for s_id, s_data in all_sessions.items():
        keyboard.add(InlineKeyboardButton(f"❌ {s_data['name']}", callback_data=f"del_{s_id}"))
    bot.reply_to(message, "Нажмите для удаления:", reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text == "📢 Рассылка (Текст)" and is_admin(m.from_user.id))
def admin_broadcast_start(message):
    admin_state[ADMIN_ID] = "WAITING_BROADCAST"
    bot.reply_to(message, "✍️ Напишите текст сообщения для всех пользователей.\n/cancel для отмены.")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_state.get(ADMIN_ID) == "WAITING_BROADCAST")
def process_broadcast(message):
    users = load_json(FILES["users"])
    bot.reply_to(message, f"🚀 Рассылка ({len(users)} чел)...")
    count = 0
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
            time.sleep(0.05)
        except: pass
    bot.reply_to(message, f"✅ Успешно: {count}")
    del admin_state[ADMIN_ID]

# --- CALLBACKS ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data.startswith('guests_') and is_admin(call.from_user.id):
        s_id = call.data[7:]
        sessions = load_json(FILES["sessions"])
        if s_id in sessions:
            guests = sessions[s_id]['attendees']
            
            # --- ИСПРАВЛЕНИЕ БАГА: УБРАЛИ MARKDOWN ---
            # Формируем список обычным текстом, чтобы ники с "_" не ломали бота
            text = f"📂 {sessions[s_id]['name']} ({len(guests)} чел.):\n\n"
            for i, g in enumerate(guests, 1):
                un = f"@{g['username']}" if g['username'] else "---"
                text += f"{i}. {g['name']} ({un})\n"
            
            # Отправляем БЕЗ parse_mode="Markdown"
            try:
                bot.send_message(call.message.chat.id, text)
            except Exception as e:
                bot.send_message(call.message.chat.id, f"Ошибка вывода списка: {e}")
                
            bot.answer_callback_query(call.id)
            
    elif call.data.startswith('del_') and is_admin(call.from_user.id):
        s_id = call.data[4:]
        sessions = load_json(FILES["sessions"])
        if s_id in sessions:
            name = sessions[s_id]['name']
            del sessions[s_id]
            save_json(FILES["sessions"], sessions)
            bot.edit_message_text(f"🗑 Сеанс {name} удален.", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Уже удалено.")

# --- 🔥 БЕССМЕРТНЫЙ РЕЖИМ 🔥 ---
if __name__ == '__main__':
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка сети: {e}")
            time.sleep(5)
