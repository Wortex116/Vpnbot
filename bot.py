#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MULTI-SNOS v8.0 — GitHub Edition
# Клонирование: git clone <repo_url> && cd snos-tg && pip install -r requirements.txt
# Запуск: python3 main.py

import asyncio
import json
import os
import random
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, List

from pyrogram import Client, filters, types
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
)
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, SessionPasswordNeeded

# Импорт конфига
from config import BOT_TOKEN, API_ID, API_HASH, ADMIN_ID, ACCOUNTS, SESSIONS_PER_ACCOUNT, ATTACK_WAVE_DELAY

# ===========================================================================
# КОНСТАНТЫ
# ===========================================================================
SESSIONS_DIR = "sessions"
DATA_FILE = "snos_data.json"

APP_NAMES = [
    "Telegram Android", "Telegram Desktop", "Telegram Web",
    "Telegram X", "Nicegram", "64Gram",
    "Pyrogram A", "Pyrogram B", "Telethon A",
    "Telethon B", "MadelineProto"
]

# ===========================================================================
# БАЗА ДАННЫХ
# ===========================================================================
class DB:
    @staticmethod
    def load() -> dict:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {"attacks": {}, "sessions": {}}
    
    @staticmethod
    def save(data: dict):
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def get_attacks(cls) -> dict:
        return cls.load().get("attacks", {})
    
    @classmethod
    def save_attack(cls, aid: str, data: dict):
        all_data = cls.load()
        all_data["attacks"][aid] = data
        cls.save(all_data)

# ===========================================================================
# МЕНЕДЖЕР АККАУНТОВ
# ===========================================================================
class AccountManager:
    def __init__(self):
        self.clients: Dict[str, List[Client]] = {}
        self.authorized: Dict[str, bool] = {}
    
    async def init_sessions(self):
        """Загрузка сохранённых сессий при старте"""
        for acc in ACCOUNTS:
            phone = acc["phone"]
            clean = phone.replace("+", "")
            
            for i in range(SESSIONS_PER_ACCOUNT):
                session_path = os.path.join(SESSIONS_DIR, f"{clean}_app{i}")
                if os.path.exists(session_path + ".session"):
                    try:
                        client = Client(
                            name=session_path,
                            api_id=API_ID,
                            api_hash=API_HASH,
                            phone_number=phone,
                            workdir=SESSIONS_DIR
                        )
                        await client.connect()
                        me = await client.get_me()
                        if me:
                            if phone not in self.clients:
                                self.clients[phone] = []
                            self.clients[phone].append(client)
                            self.authorized[phone] = True
                    except:
                        pass
                    await asyncio.sleep(0.1)
    
    async def authorize(self, phone: str, code: str, password: str = None) -> bool:
        """Авторизация аккаунта: создание всех сессий"""
        if phone not in self.clients:
            self.clients[phone] = []
        
        clean = phone.replace("+", "")
        
        for i in range(SESSIONS_PER_ACCOUNT):
            session_path = os.path.join(SESSIONS_DIR, f"{clean}_app{i}")
            
            if os.path.exists(session_path + ".session"):
                try:
                    client = Client(
                        name=session_path,
                        api_id=API_ID,
                        api_hash=API_HASH,
                        phone_number=phone,
                        workdir=SESSIONS_DIR
                    )
                    await client.connect()
                    if await client.get_me():
                        self.clients[phone].append(client)
                        continue
                except:
                    pass
            
            try:
                client = Client(
                    name=session_path,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    phone_number=phone,
                    device_model=random.choice(["iPhone 15", "Samsung S24", "Pixel 8"]),
                    app_version=f"{random.randint(8,11)}.{random.randint(0,9)}.{random.randint(0,9)}",
                    workdir=SESSIONS_DIR
                )
                await client.connect()
                
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeeded:
                    if password:
                        await client.check_password(password)
                    else:
                        await client.disconnect()
                        continue
                
                self.clients[phone].append(client)
                await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"[-] {phone} app{i}: {e}")
        
        self.authorized[phone] = len(self.clients.get(phone, [])) > 0
        return self.authorized[phone]
    
    async def report(self, phone: str, target: str, method: str) -> int:
        """Отправить жалобы через все сессии одного аккаунта"""
        if phone not in self.clients:
            return 0
        
        reason_map = {
            "spam": types.InputReportReasonSpam(),
            "violence": types.InputReportReasonViolence(),
            "pornography": types.InputReportReasonPornography(),
            "csam": types.InputReportReasonChildAbuse(),
            "phishing": types.InputReportReasonOther(),
            "drugs": types.InputReportReasonOther(),
            "terrorism": types.InputReportReasonOther(),
        }
        
        reason = reason_map.get(method, types.InputReportReasonSpam())
        success = 0
        
        for client in self.clients[phone]:
            try:
                if client.is_connected:
                    peer = await client.resolve_peer(target)
                    await client.invoke(types.account.ReportPeer(peer=peer, reason=reason))
                    success += 1
                    await asyncio.sleep(0.05)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except:
                pass
        
        return success
    
    def get_stats(self) -> dict:
        total = sum(len(v) for v in self.clients.values())
        auth = sum(1 for v in self.authorized.values() if v)
        return {
            "total_accounts": len(ACCOUNTS),
            "authorized": auth,
            "total_sessions": total,
            "reports_per_minute": int(total * (60 / ATTACK_WAVE_DELAY)),
            "accounts": {
                acc["phone"]: {
                    "sessions": len(self.clients.get(acc["phone"], [])),
                    "authorized": self.authorized.get(acc["phone"], False)
                }
                for acc in ACCOUNTS
            }
        }

# ===========================================================================
# ОРКЕСТРАТОР АТАК
# ===========================================================================
class AttackOrchestrator:
    def __init__(self, acc_manager: AccountManager):
        self.acc = acc_manager
        self.active: Dict[str, dict] = {}
    
    async def launch(self, target: str, method: str) -> str:
        aid = uuid.uuid4().hex[:8]
        stats = self.acc.get_stats()
        
        self.active[aid] = {
            "id": aid, "target": target, "method": method,
            "sessions": stats["total_sessions"],
            "started": time.time(), "status": "running", "sent": 0
        }
        DB.save_attack(aid, self.active[aid])
        
        asyncio.create_task(self._loop(aid, target, method))
        return aid
    
    async def _loop(self, aid: str, target: str, method: str):
        wave = 0
        while aid in self.active and self.active[aid]["status"] == "running":
            wave += 1
            tasks = [
                self.acc.report(acc["phone"], target, method)
                for acc in ACCOUNTS
                if self.acc.authorized.get(acc["phone"])
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            sent = sum(r for r in results if isinstance(r, int))
            
            self.active[aid]["sent"] += sent
            DB.save_attack(aid, self.active[aid])
            
            print(f"[Волна {wave}] +{sent} жалоб | Всего: {self.active[aid]['sent']}")
            await asyncio.sleep(ATTACK_WAVE_DELAY)
    
    def stop(self, aid: str):
        if aid in self.active:
            self.active[aid]["status"] = "stopped"
            DB.save_attack(aid, self.active[aid])

# ===========================================================================
# КЛАВИАТУРЫ
# ===========================================================================
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚀 СНОС")],
        [KeyboardButton("📊 СТАТ"), KeyboardButton("👤 АККИ")],
        [KeyboardButton("📋 АТАКИ"), KeyboardButton("🔄 АВТОРИЗАЦИЯ")],
    ], resize_keyboard=True)

def method_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Спам", callback_data="m_spam"),
         InlineKeyboardButton("🎣 Фишинг", callback_data="m_phishing")],
        [InlineKeyboardButton("🚫 CSAM (99%)", callback_data="m_csam"),
         InlineKeyboardButton("💣 Терроризм", callback_data="m_terrorism")],
        [InlineKeyboardButton("💊 Наркотики", callback_data="m_drugs"),
         InlineKeyboardButton("🔪 Насилие", callback_data="m_violence")],
        [InlineKeyboardButton("◀️ Отмена", callback_data="cancel")],
    ])

# ===========================================================================
# БОТ
# ===========================================================================
bot = Client("control_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
acc_mgr = AccountManager()
attacker = AttackOrchestrator(acc_mgr)
state: Dict[int, dict] = {}

@bot.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def cmd_start(_, msg):
    s = acc_mgr.get_stats()
    await msg.reply(
        f"🔥 <b>MULTI-SNOS v8.0</b>\n\n"
        f"├ Аккаунтов: <code>{s['total_accounts']}</code>\n"
        f"├ Авторизовано: <code>{s['authorized']}</code>\n"
        f"├ Сессий: <code>{s['total_sessions']}</code>\n"
        f"└ Жалоб/мин: <code>{s['reports_per_minute']}</code>\n\n"
        f"<b>Схема:</b> {s['total_accounts']} акк × {SESSIONS_PER_ACCOUNT} сессий = "
        f"<code>{s['total_sessions']}</code> одновременных жалоб\n\n"
        f"🚀 СНОС — начать атаку\n"
        f"🔄 АВТОРИЗАЦИЯ — войти в аккаунты",
        reply_markup=main_kb()
    )

@bot.on_message(filters.text & filters.user(ADMIN_ID))
async def cmd_text(_, msg):
    t = msg.text.strip()
    uid = msg.from_user.id
    
    if t == "🚀 СНОС":
        s = acc_mgr.get_stats()
        if s["authorized"] == 0:
            await msg.reply("❌ Нет авторизованных аккаунтов. Жми 🔄 АВТОРИЗАЦИЯ")
            return
        state[uid] = {}
        await msg.reply("🎯 <b>Отправь цель:</b>\n\nФорматы:\n@username\n+79161234567\nhttps://t.me/username\nhttps://t.me/+ABCDEF",
                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Отмена", callback_data="cancel")]]))
    
    elif t == "📊 СТАТ":
        s = acc_mgr.get_stats()
        txt = "📊 <b>СТАТИСТИКА</b>\n\n"
        for phone, data in s["accounts"].items():
            emoji = "🟢" if data["authorized"] else "🔴"
            txt += f"{emoji} {phone}: <code>{data['sessions']}</code> сессий\n"
        txt += f"\n<b>Всего:</b> <code>{s['total_sessions']}</code> сессий\n"
        txt += f"<b>Жалоб/мин:</b> <code>{s['reports_per_minute']}</code>"
        await msg.reply(txt)
    
    elif t == "👤 АККИ":
        txt = "👤 <b>АККАУНТЫ:</b>\n\n"
        for i, acc in enumerate(ACCOUNTS, 1):
            auth = acc_mgr.authorized.get(acc["phone"], False)
            cnt = len(acc_mgr.clients.get(acc["phone"], []))
            emoji = "🟢" if auth else "🔴"
            txt += f"{emoji} <b>#{i}</b> {acc['phone']} — <code>{cnt}/{SESSIONS_PER_ACCOUNT}</code> сессий\n"
            if acc["2fa"]: txt += f"   🔐 2FA: есть\n"
            txt += "\n"
        await msg.reply(txt)
    
    elif t == "📋 АТАКИ":
        attacks = DB.get_attacks()
        if not attacks:
            await msg.reply("📋 Нет атак")
            return
        txt = "📋 <b>АТАКИ:</b>\n\n"
        for aid, data in list(attacks.items())[-10:]:
            emoji = "🟢" if data["status"] == "running" else "✅" if data["status"] == "stopped" else "⏳"
            txt += f"{emoji} <b>#{aid}</b>\n"
            txt += f"├ {data.get('target','?')}\n"
            txt += f"├ {data.get('method','?')}\n"
            txt += f"└ {data.get('sent',0)} жалоб\n\n"
        await msg.reply(txt)
    
    elif t == "🔄 АВТОРИЗАЦИЯ":
        await msg.reply(
            "🔄 <b>АВТОРИЗАЦИЯ</b>\n\n"
            "Отправь <b>/auth</b> для запуска.\n"
            "Бот запросит код для каждого аккаунта.\n"
            "Формат ввода кода: <code>/code +79161234567 12345</code>\n"
            "Если есть 2FA: <code>/2fa +79161234567 пароль</code>"
        )

@bot.on_message(filters.command("auth") & filters.user(ADMIN_ID))
async def cmd_auth(_, msg):
    status = await msg.reply("🔄 Начинаю авторизацию...")
    
    for i, acc in enumerate(ACCOUNTS):
        phone = acc["phone"]
        clean = phone.replace("+", "")
        
        await status.edit(f"📱 <b>Аккаунт {i+1}/{len(ACCOUNTS)}</b>\n{phone}\n\nОтправляю код...")
        
        try:
            temp = Client(
                name=os.path.join(SESSIONS_DIR, f"temp_{clean}"),
                api_id=API_ID, api_hash=API_HASH,
                phone_number=phone, workdir=SESSIONS_DIR
            )
            await temp.connect()
            sent = await temp.send_code(phone)
            
            state[msg.from_user.id] = {
                "step": "awaiting_code",
                "phone": phone,
                "phone_hash": sent.phone_code_hash,
                "status_msg": status,
                "account_index": i
            }
            
            await status.edit(
                f"📱 <b>{phone}</b>\n\n"
                f"✉️ Код отправлен!\n\n"
                f"Введи: <code>/code {phone} 12345</code>\n"
                f"2FA: <code>/2fa {phone} пароль</code>"
            )
            await temp.disconnect()
            return
            
        except Exception as e:
            await status.edit(f"❌ {phone}: {e}")
            await asyncio.sleep(1)
    
    await status.edit("✅ Готово! Проверь 👤 АККИ")

@bot.on_message(filters.command("code") & filters.user(ADMIN_ID))
async def cmd_code(_, msg):
    parts = msg.text.split()
    if len(parts) < 3:
        await msg.reply("❌ /code +79161234567 12345")
        return
    
    phone, code = parts[1], parts[2]
    st = state.get(msg.from_user.id, {})
    status = st.get("status_msg")
    
    if not status:
        await msg.reply("❌ Сначала /auth")
        return
    
    await status.edit(f"🔄 {phone}: проверка кода...")
    
    password = None
    for acc in ACCOUNTS:
        if acc["phone"] == phone:
            password = acc["2fa"]
            break
    
    ok = await acc_mgr.authorize(phone, code, password)
    
    if ok:
        cnt = len(acc_mgr.clients.get(phone, []))
        await status.edit(f"✅ {phone}: <code>{cnt}/{SESSIONS_PER_ACCOUNT}</code> сессий")
    else:
        await status.edit(f"❌ {phone}: ошибка")
    
    state.pop(msg.from_user.id, None)
    
    # Запускаем следующий аккаунт
    await asyncio.sleep(2)
    await cmd_auth(_, msg)

@bot.on_message(filters.command("2fa") & filters.user(ADMIN_ID))
async def cmd_2fa(_, msg):
    parts = msg.text.split()
    if len(parts) < 3:
        await msg.reply("❌ /2fa +79161234567 пароль")
        return
    
    phone, pwd = parts[1], parts[2]
    for acc in ACCOUNTS:
        if acc["phone"] == phone:
            acc["2fa"] = pwd
            await msg.reply(f"✅ 2FA для {phone} сохранён")
            return
    
    await msg.reply("❌ Аккаунт не найден")

@bot.on_message(filters.text & filters.user(ADMIN_ID))
async def target_input(_, msg):
    uid = msg.from_user.id
    st = state.get(uid, {})
    
    if st.get("step") == "awaiting_code":
        return  # Ждём код, не обрабатываем текст
    
    if "target" not in st:
        target = msg.text.strip()
        target = target.replace("https://t.me/", "").replace("http://t.me/", "")
        
        state.setdefault(uid, {})["target"] = target
        
        await msg.reply(f"✅ <b>Цель:</b> <code>{target}</code>\n\n⚡ <b>Выбери метод:</b>", reply_markup=method_kb())

@bot.on_callback_query()
async def callback(_, cb: CallbackQuery):
    uid = cb.from_user.id
    
    if uid != ADMIN_ID:
        await cb.answer("⛔", show_alert=True)
        return
    
    data = cb.data
    
    if data == "cancel":
        await cb.message.delete()
        state.pop(uid, None)
        return
    
    if data.startswith("m_"):
        method = data.replace("m_", "")
        st = state.get(uid, {})
        target = st.get("target")
        
        if not target:
            await cb.answer("❌ Сначала отправь цель", show_alert=True)
            return
        
        s = acc_mgr.get_stats()
        
        await cb.message.edit_text(
            f"🚀 <b>ЗАПУСК!</b>\n\n"
            f"├ Цель: <code>{target}</code>\n"
            f"├ Метод: <code>{method}</code>\n"
            f"├ Сессий: <code>{s['total_sessions']}</code>\n"
            f"├ Жалоб/мин: <code>{s['reports_per_minute']}</code>\n"
            f"└ Бан: <b>2-5 мин</b>\n\n⏳ Поехали..."
        )
        
        aid = await attacker.launch(target, method)
        await asyncio.sleep(1)
        
        await cb.message.edit_text(
            f"🔥 <b>СНОС ПОШЁЛ!</b>\n\n"
            f"├ ID: <code>#{aid}</code>\n"
            f"├ Цель: <code>{target}</code>\n"
            f"├ Метод: <code>{method}</code>\n"
            f"├ Сессий: <code>{s['total_sessions']}</code>\n"
            f"└ Статус: 🟢 АТАКА\n\n"
            f"🛑 /stop {aid}",
            reply_markup=main_kb()
        )
        state.pop(uid, None)

@bot.on_message(filters.command("stop") & filters.user(ADMIN_ID))
async def cmd_stop(_, msg):
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.reply("❌ /stop id_атаки")
        return
    attacker.stop(parts[1])
    await msg.reply(f"🛑 Атака #{parts[1]} остановлена")

# ===========================================================================
# ЗАПУСК
# ===========================================================================
async def main():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    print("=" * 40)
    print("MULTI-SNOS v8.0 | GitHub Edition")
    print(f"Аккаунтов: {len(ACCOUNTS)}")
    print(f"Сессий/акк: {SESSIONS_PER_ACCOUNT}")
    print(f"Всего сессий: {len(ACCOUNTS) * SESSIONS_PER_ACCOUNT}")
    print(f"Жалоб/мин: {len(ACCOUNTS) * SESSIONS_PER_ACCOUNT * (60 // ATTACK_WAVE_DELAY)}")
    print("=" * 40)
    
    print("[*] Загрузка сессий...")
    await acc_mgr.init_sessions()
    s = acc_mgr.get_stats()
    print(f"[+] Авторизовано: {s['authorized']}/{s['total_accounts']}")
    print(f"[+] Сессий: {s['total_sessions']}")
    print("[*] Запуск бота...")
    
    await bot.run()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
    
