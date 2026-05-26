# bot.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (с импортом sqlite3)
import asyncio
import json
import re
import sqlite3
from datetime import datetime
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

from config import *
from database import *
from utils import *

bot = Bot(token=VK_TOKEN)

# Хранилище состояний пользователей
user_states = {}
user_temp = {}
question_index = {}

# === КЛАВИАТУРЫ ===
def main_keyboard():
    """Основная клавиатура с двумя кнопками"""
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text("✅ Консультация"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("✉️ Сообщение"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

def service_keyboard():
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("🐶 Первичная консультация"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("🐕 Повторная консультация"))
    return keyboard

def extract_keyboard():
    keyboard = Keyboard(one_time=True)
    keyboard.add(Text("📎 Приложить выписку"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("⏩ Пропустить"), color=KeyboardButtonColor.SECONDARY)
    return keyboard

async def ask_next_question(message: Message):
    user_id = message.from_id
    if user_id not in question_index:
        question_index[user_id] = 0
    idx = question_index[user_id]
    if idx < len(QUESTIONS):
        await message.answer(QUESTIONS[idx])
        user_states[user_id] = "answering"
    else:
        answers = user_temp.get(user_id, {}).get("answers", [])
        save_user_data(user_id, "answers", json.dumps(answers, ensure_ascii=False))
        await ask_for_extract(message)

async def ask_for_extract(message: Message):
    keyboard = extract_keyboard()
    await message.answer(
        "📋 Если у вас есть выписка от предыдущего врача — приложите её (фото или файл).\n"
        "Или нажмите 'Пропустить':",
        keyboard=keyboard
    )
    user_states[message.from_id] = "wait_extract"

async def ask_payment(message: Message):
    user_id = message.from_id
    data = get_user_data(user_id)
    price = data.get("price", 2000)
    pet_info = user_temp.get(user_id, {}).get("pet_info", "питомец")
    
    await message.answer(
        f"💳 Стоимость консультации: {price} руб.\n\n"
        f"💳 Номер карты для оплаты: {CARD_NUMBER}\n\n"
        f"📝 В назначении платежа укажите кличку питомца и промокод (если он у вас есть)\n\n"
        f"📸 После перевода отправьте СКРИНШОТ чека сюда.\n\n"
        f"⏳ Оплата подтверждается только после получения скриншота!"
    )
    user_states[user_id] = "wait_screenshot"

async def send_final_message(message: Message):
    user_id = message.from_id
    pet_info = user_temp.get(user_id, {}).get("pet_info", "питомца")
    
    final_text = (
        f"✅ Заявка на консультацию получена!\n\n"
        f"📌 Ожидайте подтверждения от администратора.\n"
        f"👨‍⚕️ Свяжемся с вами в ближайшее время.\n\n"
        f"📸 Пожалуйста, приложите ФОТО или ВИДЕО глаза/глаз {pet_info}.\n"
        f"Это поможет врачу оценить состояние до консультации.\n\n"
        f"⚠️ ВАЖНО: Онлайн-консультация НЕ заменяет очный прием врача.\n"
        f"При ухудшении состояния — срочно обратитесь к ветеринару очно!\n\n"
        f"По всем вопросам пишите сюда."
    )
    await message.answer(final_text, keyboard=main_keyboard())
    
    user_states[user_id] = "manual"
    
    if user_id in question_index:
        del question_index[user_id]
    if user_id in user_temp:
        user_temp[user_id] = {}

async def notify_admin(user_id: int):
    data = get_user_data(user_id)
    answers = json.loads(data.get("answers", "[]"))
    
    admin_msg = (
        f"🆕 НОВАЯ ЗАЯВКА от пользователя vk.com/id{user_id}\n\n"
        f"🩺 Услуга: {'Первичная' if data.get('service')=='primary' else 'Повторная'}\n"
        f"💰 Сумма к оплате: {data.get('price', '-')} руб.\n\n"
        f"📋 Анамнез:\n"
        f"1. Причина обращения: {answers[0] if len(answers)>0 else '-'}\n"
        f"2. Информация о питомце: {answers[1] if len(answers)>1 else '-'}\n"
        f"3. Длительность проблемы: {answers[2] if len(answers)>2 else '-'}\n"
        f"4. Беспокоит ли животное: {answers[3] if len(answers)>3 else '-'}\n"
        f"5. Выделения: {answers[4] if len(answers)>4 else '-'}\n"
        f"6. Был у врача: {answers[5] if len(answers)>5 else '-'}\n"
        f"7. Препараты: {answers[6] if len(answers)>6 else '-'}\n"
    )
    
    await bot.api.messages.send(user_id=ADMIN_VK_ID, message=admin_msg, random_id=0)
    
    extract_msg_id = data.get('extract_msg_id')
    if extract_msg_id and extract_msg_id != 0:
        await asyncio.sleep(0.5)
        await bot.api.messages.send(user_id=ADMIN_VK_ID, message="📎 Выписка:", random_id=0)
        await bot.api.messages.send(
            user_id=ADMIN_VK_ID,
            peer_id=user_id,
            forward_messages=extract_msg_id,
            random_id=0
        )
    
    screenshot_msg_id = data.get('screenshot_msg_id')
    if screenshot_msg_id:
        await asyncio.sleep(0.5)
        await bot.api.messages.send(user_id=ADMIN_VK_ID, message="💳 Скриншот оплаты:", random_id=0)
        await bot.api.messages.send(
            user_id=ADMIN_VK_ID,
            peer_id=user_id,
            forward_messages=screenshot_msg_id,
            random_id=0
        )

# === ОБРАБОТЧИКИ ===

@bot.on.message(text="/admin")
async def admin_panel(message: Message):
    if message.from_id != ADMIN_VK_ID:
        await message.answer("⛔ Доступ запрещён.")
        return
    
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE status = 'pending' ORDER BY created_at DESC")
    requests = cur.fetchall()
    conn.close()
    
    if not requests:
        # Сбрасываем состояние админа, если нет заявок
        if message.from_id in user_states:
            user_states[message.from_id] = None
        await message.answer("📭 Нет активных заявок.")
        return
    
    keyboard = Keyboard(one_time=False)
    for req in requests:
        user_id = req[0]
        keyboard.add(Text(f"✅ Завершить (id{user_id})"), color=KeyboardButtonColor.POSITIVE)
        keyboard.row()
    
    keyboard.add(Text("🔄 Обновить"), color=KeyboardButtonColor.PRIMARY)
    
    await message.answer(
        f"📋 Список заявок ({len(requests)}):\n\n"
        f"Нажмите «Завершить (id...)», чтобы уведомить пользователя",
        keyboard=keyboard
    )
    user_states[message.from_id] = "admin_select"

@bot.on.message(text="🔄 Обновить")
async def refresh_admin(message: Message):
    if message.from_id == ADMIN_VK_ID and user_states.get(message.from_id) == "admin_select":
        await admin_panel(message)

@bot.on.message(text="✅ Консультация")
async def start_consultation_button(message: Message):
    user_id = message.from_id
    
    # Если админ в админ-панели - выходим из неё
    if user_id == ADMIN_VK_ID and user_states.get(user_id) == "admin_select":
        user_states[user_id] = None
        await message.answer("🔄 Выход из админ-панели. Начинаем новую консультацию от имени пользователя? Если нет - просто напишите /admin", keyboard=main_keyboard())
        return
    
    data = get_user_data(user_id)
    if data and data.get("status") in ["pending", "confirmed"]:
        await message.answer(
            "⚠️ У вас уже есть активная заявка.\n"
            "Дождитесь её обработки администратором.\n\n"
            "Для записи на новую консультацию дождитесь завершения текущей.",
            keyboard=main_keyboard()
        )
        return
    
    if user_states.get(user_id) == "manual":
        user_states[user_id] = None
        if user_id in user_temp:
            user_temp[user_id] = {}
    
    user_states[user_id] = "wait_service"
    user_temp[user_id] = {"answers": []}
    save_user_data(user_id, "status", "in_progress")
    await message.answer("🩺 Выберите тип консультации:", keyboard=service_keyboard())

@bot.on.message(text="✉️ Сообщение")
async def forward_to_admin(message: Message):
    user_id = message.from_id
    await message.answer(
        "📝 Режим общения с администратором включён.\n\n"
        "Теперь вы можете просто писать свои сообщения в этот чат — они не будут мешать работе бота.\n"
        "Администратор увидит их и ответит вам.\n\n"
        "Если захотите записаться на консультацию — нажмите кнопку «Консультация».",
        keyboard=main_keyboard()
    )
    user_states[user_id] = "forwarding_first"

@bot.on.message(text="/start")
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_id
    
    # Сбрасываем состояние админа, если он в админ-панели
    if user_id == ADMIN_VK_ID and user_states.get(user_id) == "admin_select":
        user_states[user_id] = None
    
    # Сбрасываем состояние обычного пользователя
    if user_states.get(user_id) == "manual":
        user_states[user_id] = None
    
    data = get_user_data(user_id)
    if data and data.get("status") in ["pending", "confirmed"]:
        await message.answer(
            "⚠️ У вас уже есть активная заявка.\n"
            "Дождитесь её обработки администратором.\n\n"
            "Для записи на новую консультацию дождитесь завершения текущей.",
            keyboard=main_keyboard()
        )
    else:
        await message.answer(
            "🐾 Онлайн-консультация ветеринарного офтальмолога\n\n"
            "Здесь можно оставить заявку на онлайн-консультацию.\n"
            "Бот не ведёт запись на очный приём в клинику.\n\n"
            "📞 Запись на очный приём:\n"
            "+7 (812) 646-76-26\n\n"
            "⚠️ Важно:\n"
            "• Онлайн-консультация не заменяет полноценный очный осмотр\n"
            "• Получить срочную онлайн-консультацию можно только в дневное время\n\n"
            "Чем полезна онлайн-консультация:\n"
            "• Оценить ситуацию — нужен ли срочный визит\n"
            "• В некоторых случаях — получить рекомендацию препаратов до визита к специалисту\n"
            "• Получить рекомендации по первичной диагностике\n"
            "• Узнать, какие анализы можно сдать заранее\n\n"
            "После консультации врач может рекомендовать очный приём для точной диагностики и лечения.\n\n"
            "💬 Чтобы задать вопрос о срочности состояния (подразумевет краткий ответ без развёрнутого объяснения и рекомендаций) или если у вас есть вопрос, не связанный с получением консультации —\n"
            "нажмите кнопку «Сообщение», а затем просто напишите свой вопрос.\n"
            "Администратор увидит его и ответит.\n\n"
            "Для создания заявки нажмите кнопку «Консультация» 👇",
            keyboard=main_keyboard()
        )

@bot.on.message()
async def handle_messages(message: Message):
    user_id = message.from_id
    
    if user_id == ADMIN_VK_ID and user_states.get(user_id) == "admin_select":
        await admin_actions(message)
        return
    
    state = user_states.get(user_id)
    
    if state == "forwarding_first":
        await bot.api.messages.send(
            user_id=ADMIN_VK_ID,
            message=f"✉️ Сообщение от пользователя vk.com/id{user_id}:\n\n{message.text}",
            random_id=0
        )
        if message.attachments:
            await asyncio.sleep(0.3)
            await bot.api.messages.send(user_id=ADMIN_VK_ID, message="📎 Вложения:", random_id=0)
            await bot.api.messages.send(
                user_id=ADMIN_VK_ID,
                peer_id=user_id,
                forward_messages=message.id,
                random_id=0
            )
        
        await message.answer("✅ Сообщение передано администратору.", keyboard=main_keyboard())
        user_states[user_id] = "manual"
        return
    
    if state == "manual":
        return
    
    if state is None:
        data = get_user_data(user_id)
        if data and data.get("status") in ["pending", "confirmed"]:
            await message.answer(
                "⚠️ У вас уже есть активная заявка.\n"
                "Дождитесь её обработки администратором.\n\n"
                "Для записи на новую консультацию дождитесь завершения текущей.",
                keyboard=main_keyboard()
            )
        else:
            await message.answer(
                "🐾 Онлайн-консультация ветеринарного офтальмолога\n\n"
                "Здесь можно оставить заявку на онлайн-консультацию.\n"
                "Бот не ведёт запись на очный приём в клинику.\n\n"
                "📞 Запись на очный приём:\n"
                "+7 (812) 646-76-26\n\n"
                "⚠️ Важно:\n"
                "• Онлайн-консультация не заменяет полноценный очный осмотр\n"
                "• Получить срочную онлайн-консультацию можно только в дневное время\n\n"
                "Чем полезна онлайн-консультация:\n"
                "• Оценить ситуацию — нужен ли срочный визит\n"
                "• В некоторых случаях — получить рекомендацию препаратов до визита к специалисту\n"
                "• Получить рекомендации по первичной диагностике\n"
                "• Узнать, какие анализы можно сдать заранее\n\n"
                "После консультации врач может рекомендовать очный приём для точной диагностики и лечения.\n\n"
                "💬 Чтобы задать вопрос о срочности состояния (подразумевет краткий ответ без развёрнутого объяснения и рекомендаций) или если у вас есть вопрос, не связанный с получением консультации —\n"
                "нажмите кнопку «Сообщение», а затем просто напишите свой вопрос.\n"
                "Администратор увидит его и ответит.\n\n"
                "Для создания заявки нажмите кнопку «Консультация» 👇",
                keyboard=main_keyboard()
            )
        return
    
    if state == "wait_service":
        if message.text == "🐶 Первичная консультация":
            save_user_data(user_id, "service", "primary")
            save_user_data(user_id, "price", PRICES["primary"])
            await message.answer(f"💰 Стоимость первичной консультации: {PRICES['primary']} руб.\n\nПожалуйста, ответьте на несколько вопросов о питомце:")
            user_states[user_id] = "ask_questions"
            await ask_next_question(message)
        elif message.text == "🐕 Повторная консультация":
            save_user_data(user_id, "service", "repeat")
            save_user_data(user_id, "price", PRICES["repeat"])
            await message.answer(f"💰 Стоимость повторной консультации: {PRICES['repeat']} руб.\n\nПожалуйста, ответьте на несколько вопросов о питомце:")
            user_states[user_id] = "ask_questions"
            await ask_next_question(message)
        else:
            await message.answer(
                "❌ Пожалуйста, выберите тип консультации, нажав на одну из кнопок:",
                keyboard=service_keyboard()
            )
    
    elif state == "answering":
        if user_id not in user_temp:
            user_temp[user_id] = {"answers": []}
        user_temp[user_id]["answers"].append(message.text)
        
        if len(user_temp[user_id]["answers"]) == 2:
            user_temp[user_id]["pet_info"] = message.text
        
        if user_id not in question_index:
            question_index[user_id] = 0
        question_index[user_id] += 1
        await ask_next_question(message)
    
    elif state == "wait_extract":
        if message.attachments:
            save_user_data(user_id, "extract_msg_id", message.id)
            await ask_payment(message)
        elif message.text == "⏩ Пропустить":
            save_user_data(user_id, "extract_msg_id", 0)
            await ask_payment(message)
        elif message.text == "📎 Приложить выписку":
            await message.answer("📎 Отправьте файл с выпиской (фото или документ):")
        else:
            await message.answer(
                "❌ Пожалуйста, приложите файл с выпиской или нажмите 'Пропустить'.",
                keyboard=extract_keyboard()
            )
    
    elif state == "wait_screenshot":
        if not message.attachments:
            await message.answer("❌ Пожалуйста, отправьте скриншот перевода (фото)")
            return
        
        save_user_data(user_id, "screenshot_msg_id", message.id)
        save_user_data(user_id, "status", "pending")
        
        await notify_admin(user_id)
        await send_final_message(message)
    
    else:
        await message.answer(
            "🐾 Я бот-помощник ветеринарного офтальмолога.\n"
            "Нажмите «✅ Консультация», чтобы оставить заявку.\n"
            "Или «✉️ Сообщение», чтобы написать администратору.",
            keyboard=main_keyboard()
        )

async def admin_actions(message: Message):
    user_id = message.from_id
    if user_id != ADMIN_VK_ID:
        return
    
    text = message.text
    
    if text == "🔄 Обновить":
        await admin_panel(message)
        return
    
    match = re.search(r'id(\d+)', text)
    if not match:
        await message.answer("❌ Не удалось определить пользователя. Нажмите на кнопку «Завершить (id...)».")
        return
    
    target_user_id = int(match.group(1))
    
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'completed' WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    
    await bot.api.messages.send(
        user_id=target_user_id,
        message="✅ Администратор завершил обработку вашей заявки.\n\nВы можете записаться на новую консультацию, нажав кнопку «✅ Консультация».",
        random_id=0,
        keyboard=main_keyboard().get_json()
    )
    
    if target_user_id in user_states:
        user_states[target_user_id] = None
    if target_user_id in user_temp:
        user_temp[target_user_id] = {}
    if target_user_id in question_index:
        del question_index[target_user_id]
    
    await message.answer(f"✅ Заявка пользователя id{target_user_id} завершена. Пользователь уведомлён.")
    
    # Обновляем админ-панель (если есть заявки - покажет, если нет - сбросит состояние)
    await admin_panel(message)

if __name__ == "__main__":
    print("🐾 Бот запущен...")
    print(f"✅ Администратор: vk.com/id{ADMIN_VK_ID}")
    init_db()
    bot.run_forever()
