import os
import json
import requests
import base64
import re
from datetime import datetime
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8899543410:AAFae4tYHa-slIfGYH_pp65FuZzygT-os0c"
CHANNEL = "@ciorsa"
GITHUB_URL = "https://raw.githubusercontent.com/Wortex116/VPNfree/main/Free"

USERS_FILE = "users.json"
LINK_CACHE = "link.json"

app = Flask(__name__)

def get_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_user(user_id):
    users = get_users()
    users.add(user_id)
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def is_user(user_id):
    return user_id in get_users()

def get_vpn_link():
    if os.path.exists(LINK_CACHE):
        with open(LINK_CACHE, 'r') as f:
            data = json.load(f)
            if data.get('time', 0) > datetime.now().timestamp() - 7200:
                return data.get('link')
    
    try:
        r = requests.get(GITHUB_URL, timeout=10)
        if r.status_code == 200:
            keys = re.findall(r'vless://[a-f0-9-]+@[^?\s#]+', r.text)
            keys = [k for k in keys if 'error' not in k and 'META' not in k]
            if keys:
                encoded = base64.b64encode("\n".join(keys).encode()).decode()
                link = f"https://happ.dska.su/https://{encoded}"
                with open(LINK_CACHE, 'w') as f:
                    json.dump({'link': link, 'time': datetime.now().timestamp()}, f)
                return link
    except:
        pass
    return None

async def start(update: Update, context):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n/check - проверить подписку\n/vpn - получить VPN\n/help - помощь"
    )

async def check(update: Update, context):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            save_user(user_id)
            await update.message.reply_text("✅ Подписка подтверждена! Теперь /vpn")
        else:
            await update.message.reply_text(f"❌ Подпишись на {CHANNEL}")
    except:
        await update.message.reply_text("⚠️ Ошибка, попробуй позже")

async def vpn(update: Update, context):
    user_id = update.effective_user.id
    if not is_user(user_id):
        await update.message.reply_text(f"❌ Сначала нажми /check")
        return
    link = get_vpn_link()
    if link:
        await update.message.reply_text(f"🔗 {link}")
    else:
        await update.message.reply_text("❌ VPN временно недоступен")

async def help_cmd(update: Update, context):
    await update.message.reply_text(
        "📖 Команды:\n/start - Приветствие\n/check - Проверить подписку\n/vpn - Получить VPN\n/help - Помощь"
    )

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(), bot)
        application.process_update(update)
        return 'ok', 200
    except:
        return 'error', 500

@app.route('/', methods=['GET'])
def index():
    return 'VPN Bot is running!', 200

if __name__ == '__main__':
    bot = Bot(token=TOKEN)
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("vpn", vpn))
    application.add_handler(CommandHandler("help", help_cmd))
    
    print("🚀 Бот запущен на Render.com")
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

