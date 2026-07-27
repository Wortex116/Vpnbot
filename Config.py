# config.py — НАСТРОЙКИ (заполни перед запуском)

# Токен бота от @BotFather
BOT_TOKEN = "8812589164:AAHdsyvrSYP7iCecbcot0EyUxE0fFczaCdw"

# API данные с my.telegram.org
API_ID = 29478542
API_HASH = "d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"

# Твой Telegram ID (узнать через @userinfobot)
ADMIN_ID = 8176196456

# Твои аккаунты для сноса (5 штук)
# Если есть 2FA — укажи пароль в поле "2fa", если нет — оставь None
ACCOUNTS = [
    {"phone": "+79161234567", "name": "Аккаунт 1", "2fa": None},
    {"phone": "+79161234568", "name": "Аккаунт 2", "2fa": None},
    {"phone": "+79161234569", "name": "Аккаунт 3", "2fa": None},
    {"phone": "+79161234570", "name": "Аккаунт 4", "2fa": None},
    {"phone": "+79161234571", "name": "Аккаунт 5", "2fa": None},
]

# Количество сессий на каждый аккаунт (1-11)
SESSIONS_PER_ACCOUNT = 11

# Задержка между волнами атаки (секунды)
ATTACK_WAVE_DELAY = 2
