import asyncio
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import openai
import requests
from io import BytesIO
from PIL import Image
from telegram import Bot
import json
from datetime import datetime, timezone
import os

# === НАСТРОЙКИ через переменные окружения ===
api_id = int(os.getenv("21923802"))
api_hash = os.getenv("b2cfccddfc864fb5f1db80bc12e7f9b3")
openai.api_key = os.getenv("OPENAI_API_KEY")
telegram_bot_token = os.getenv("7356315664:AAH0YYQx0kULG_iLrHDv28ELob5ZvSAsZXQ")
channel_to_post = os.getenv("@govnokall")

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
            prompt = f"Переделай новость ниже в грубую, язвительную, саркастичную 2-строчную шутку с нормальным матом и нотками чёрного юмора. Без соплей, как будто жизнь — это ржавая сковородка по ебалу.\n\n{message.message}"
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.95
                )
                joke = response.choices[0].message.content.strip()
                print(f"💬 GPT ответ: {joke}")
            except Exception as e:
                joke = f"[GPT сдох. Ошибка: {e}]"
                print(joke)

            # === Генерация изображения через DALL-E ===
            try:
                dalle_response = openai.Image.create(
                    prompt=joke,
                    n=1,
                    size="512x512"
                )
                img_url = dalle_response['data'][0]['url']
                img_data = requests.get(img_url).content
                image = BytesIO(img_data)
                print("🖼 Картинка успешно сгенерирована")
            except Exception as e:
                joke += f"\n\n[Ошибка генерации изображения: {e}]"
                image = None
                print(joke)

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
