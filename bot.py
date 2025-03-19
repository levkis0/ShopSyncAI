from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import os
import re
import asyncio

# Завантажуємо токен із .env
load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Функція для розпізнавання оголошень
def parse_announcement(text):
    text = text.lower().strip()
    # Перевіряємо, чи є ознаки відсутності товару
    out_of_stock_keywords = ["нема в наявності", "закінчився", "продано", "немає", "нема"]
    if any(keyword in text for keyword in out_of_stock_keywords):
        return None

    # Регулярний вираз для формату "Назва - Ціна грн"
    pattern = r"(.+?)\s*-\s*(\d+(?:\.\d+)?)\s*грн"
    match = re.match(pattern, text, re.IGNORECASE)
    if not match:
        return None

    name, price = match.groups()
    # Перевіряємо наявність
    available = "в наявності" in text or not any(keyword in text for keyword in ["в наявності"] + out_of_stock_keywords)
    if available:
        return {"name": name.strip(), "price": float(price), "available": True}
    return None

# Перевірка, чи товар уже був опублікований
processed_messages = set()

# Обробка всіх нових повідомлень у будь-якому чаті
@dp.message_handler(content_types=['text'])
async def process_new_announcement(message: types.Message):
    msg_id = message.message_id
    chat_id = message.chat.id  # Отримуємо ID чату з повідомлення
    if msg_id in processed_messages:
        return
    item = parse_announcement(message.text)
    if item:
        text = (
            f"Товар: {item['name']}\n"
            f"Ціна: {item['price']} грн\n"
            f"Наявність: Так\n"
            f"Додав: @{message.from_user.username or 'Невідомо'}"
        )
        await bot.send_message(chat_id, text)  # Надсилаємо в той же чат
        processed_messages.add(msg_id)

# Обробка старих повідомлень при старті для всіх чатів, де бот є
async def process_old_messages():
    # Отримуємо список чатів, де бот є адміністратором
    chats = await bot.get_chat_administrators(chat_id=None)  # Не працює прямо так, але можна обійти
    # Для простоти обробляємо тільки чат, де бот отримує перше повідомлення
    # Тому пропускаємо цей крок і обробляємо старі повідомлення в реальному чаті при першому запуску
    pass  # Якщо потрібна повна обробка всіх чатів, додамо пізніше

# Запуск бота
async def on_startup(_):
    print("Бот запущено! Додавай мене в канал, і я почну працювати.")
    # Обробка старих повідомлень відкладена до першого повідомлення

if __name__ == '__main__':
    dp.startup.register(on_startup)
    dp.run_polling(bot)
