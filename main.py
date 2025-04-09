import asyncio
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import openai
import requests
from io import BytesIO
from telegram import Bot
import json
from datetime import datetime, timezone
import os

# === НАСТРОЙКИ через переменные окружения ===
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
openai.api_key = os.getenv("OPENAI_API_KEY")
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
channel_to_post = os.getenv("CHANNEL_TO_POST")

channels_to_parse = [
    'toporlive',
    'readovkanews',
    'breakingmash',
    'rian_ru',
    'meduzalive',
    'ksonline',         # экономика
    'banksta',          # экономика/финансы
    'rosnedvizhimost',  # недвижимость
    'autonewsru'        # авто
]

client = TelegramClient('anon', api_id, api_hash)
bot = Bot(token=telegram_bot_token)

# === ЗАГРУЗКА ID опубликованных сообщений ===
posted_ids_file = 'posted_ids.json'
try:
    with open(posted_ids_file, 'r') as f:
        posted_messages = set(json.load(f))
except (FileNotFoundError, json.JSONDecodeError):
    posted_messages = set()

async def main():
    await client.start()
    now = datetime.now(timezone.utc)

    for channel in channels_to_parse:
        print(f'📡 Читаем канал: {channel}')
        entity = await client.get_entity(channel)
        history = await client(GetHistoryRequest(
            peer=entity,
            limit=10,
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))

        for message in history.messages:
            if not message.message:
                print(f"⏩ Пропущено пустое сообщение {message.id}")
                continue

            if message.id in posted_messages:
                print(f"⏩ Пропущено сообщение {message.id} — уже публиковалось")
                continue

            print(f"\n🧠 Обрабатываем сообщение {message.id}: {message.message[:100]}...")

            # === Генерация шутки ===
            prompt = f"Сделай из этой новости глумливую, агрессивную, чёрную шутку с адекватным количеством мата. Без цензуры. Без морали. Просто жёстко и смешно.\n\n{message.message}"
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.98
                )
                joke = response.choices[0].message.content.strip()
                print(f"💬 GPT ответ: {joke}")
            except Exception as e:
                joke = f"[GPT сдох. Ошибка: {e}]"
                print(joke)

            # === Извлечение картинки из поста ===
            image = None
            if message.media and message.photo:
                try:
                    image = BytesIO()
                    await client.download_media(message, file=image)
                    image.seek(0)
                    print("🖼 Картинка из поста сохранена")
                except Exception as e:
                    print(f"❌ Ошибка при загрузке картинки: {e}")

            # === Публикация ===
            try:
                if image:
                    await bot.send_photo(chat_id=channel_to_post, photo=image, caption=joke)
                else:
                    await bot.send_message(chat_id=channel_to_post, text=joke)
                posted_messages.add(message.id)

                # Сохраняем обновлённый список
                with open(posted_ids_file, 'w') as f:
                    json.dump(list(posted_messages), f)

                print(f"✅ Опубликовано сообщение {message.id}")
            except Exception as e:
                print(f"❌ Ошибка при отправке: {e}")

with client:
    client.loop.run_until_complete(main())
