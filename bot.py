import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import re
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Завантажуємо змінні з .env
load_dotenv()

# Налаштування з .env
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN or not SUPABASE_URL or not SUPABASE_KEY or not ADMIN_ID:
    raise ValueError("Не вистачає однієї з обов'язкових змінних у .env!")

ADMIN_ID = int(ADMIN_ID)

bot = Bot(token=TOKEN)
dp = Dispatcher()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Функція для завантаження фото в Supabase Storage (якщо ми додали раніше)
async def upload_image_to_supabase(file_id: str, product_title: str) -> str:
    file = await bot.get_file(file_id)
    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)
    file_name = f"{product_title.replace(' ', '_')}_{file_id}.jpg"
    supabase.storage.from_("product_images").upload(file_name, downloaded_file.read(), {
        "content-type": "image/jpeg"
    })
    return supabase.storage.from_("product_images").get_public_url(file_name)


# Команда для перевірки статусу бота (тільки для адміна)
@dp.message(Command("status"))
async def check_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Ви не адміністратор!")
        return
    await message.reply("Бот працює! Моніторю канали, де я є адміністратором.")

# Перевірка, чи є повідомлення оголошенням
def is_sale_post(message: str) -> bool:
    keywords = ["продам", "продаж", "купити", "ціна", "грн", "$"]
    return any(keyword.lower() in message.lower() for keyword in keywords)


# Перевірка, чи товар продано
def is_sold_out(message: str) -> bool:
    sold_keywords = ["продано", "sold out", "немає в наявності", "закінчилось"]
    return any(keyword.lower() in message.lower() for keyword in sold_keywords)


# Витягування даних з повідомлення
async def extract_product_info(message: types.Message) -> dict:
    text = message.text or message.caption or ""
    price_match = re.search(r"(\d+\s*(грн|\$|uah|usd))", text, re.IGNORECASE)
    price = price_match.group(0) if price_match else "Невідомо"
    categories = {"одяг": "одяг", "взуття": "взуття", "аксесуари": "аксесуари"}
    category = "Інше"
    for key, value in categories.items():
        if key in text.lower():
            category = value
            break

    image_url = None
    if message.photo:
        file_id = message.photo[-1].file_id
        title = text.split("\n")[0][:50]
        image_url = await upload_image_to_supabase(file_id, title)

    return {
        "title": text.split("\n")[0][:50],
        "description": text,
        "price": price,
        "category": category,
        "image_url": image_url,
        "seller_username": message.from_user.username or "невідомо",
        "shop_name": message.chat.title or "невідомо",
        "created_at": message.date.isoformat()
    }


# Обробка нових повідомлень
@dp.message()
async def handle_channel_message(message: types.Message):
    chat_member = await bot.get_chat_member(message.chat.id, bot.id)
    if chat_member.status != "administrator":
        return
    if not is_sale_post(message.text or message.caption or ""):
        return
    if is_sold_out(message.text or message.caption or ""):
        return

    product_info = await extract_product_info(message)
    try:
        response = supabase.table("products").insert(product_info).execute()
        if response.data:
            print(f"Додано товар: {product_info['title']}")
    except Exception as e:
        print(f"Помилка: {e}")


# Команда для сканування історії
@dp.message(Command("scan_history"))
async def scan_history(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Ви не адміністратор!")
        return

    chat_id = message.chat.id
    await message.reply("Сканую історію каналу...")

    async for msg in bot.get_chat_history(chat_id, limit=1000):  # Ліміт 1000 повідомлень
        if not is_sale_post(msg.text or msg.caption or ""):
            continue
        if is_sold_out(msg.text or msg.caption or ""):
            continue

        product_info = await extract_product_info(msg)
        try:
            # Перевіряємо, чи товар уже є в базі (за title і shop_name)
            existing = supabase.table("products").select("*").eq("title", product_info["title"]).eq("shop_name",
                                                                                                    product_info[
                                                                                                        "shop_name"]).execute()
            if not existing.data:  # Якщо немає, додаємо
                response = supabase.table("products").insert(product_info).execute()
                if response.data:
                    print(f"Додано старий товар: {product_info['title']}")
        except Exception as e:
            print(f"Помилка при скануванні: {e}")

    await message.reply("Сканування завершено!")


# Команда для статусу
@dp.message(Command("status"))
async def check_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Ви не адміністратор!")
        return
    await message.reply("Бот працює! Моніторю канали, де я є адміністратором.")


# Запуск бота
async def main():
    print("Бот запущений!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())