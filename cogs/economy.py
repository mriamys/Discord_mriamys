import discord
from discord.ext import commands, tasks
import time
import math
import random
from utils.db import db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from config import PREFIX

# Константы системы восстановления стриков
STREAK_MAX_RESTORES_PER_MONTH = 3
STREAK_RESTORE_WINDOW_HOURS = 48

STREAK_RESTORE_NOTIFIED_KEY = "streak_restore_notified"


class StreakRestoreView(discord.ui.View):
    """View с кнопкой восстановления стрика (TikTok-стиль).

    Persistent view — после перезапуска бота state (user_id и т.д.) теряется,
    поэтому кнопка определяет владельца через interaction.user.id и берёт
    данные о стрике из БД.
    """

    def __init__(self, user_id: str | None = None, lost_streak: int = 0, restores_left: int = 0):
        super().__init__(timeout=None)
        # Эти поля используются ТОЛЬКО при первой отправке сообщения,
        # после рестарта бота они будут None/0 — и это ок.
        self.user_id = user_id
        self.lost_streak = lost_streak
        self.restores_left = restores_left

    @discord.ui.button(
        label="🔄 Восстановить стрик",
        style=discord.ButtonStyle.success,
        custom_id="streak_restore_btn",
    )
    async def restore_streak(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Определяем user_id из interaction — работает и после рестарта
        uid = str(interaction.user.id)

        user_data = await db.get_user(uid)
        streak_lost_at = user_data.get("streak_lost_at")

        # Проверяем что стрик ещё в состоянии "потерян"
        if not streak_lost_at:
            await interaction.response.send_message(
                "✅ Твой стрик уже восстановлен или активен!", ephemeral=True
            )
            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            return

        # Проверяем 48ч окно
        if isinstance(streak_lost_at, str):
            streak_lost_at = datetime.strptime(
                str(streak_lost_at).split(".")[0], "%Y-%m-%d %H:%M:%S"
            )
        hours_passed = (datetime.utcnow() - streak_lost_at).total_seconds() / 3600
        if hours_passed > STREAK_RESTORE_WINDOW_HOURS:
            await interaction.response.send_message(
                f"⏰ Окно восстановления ({STREAK_RESTORE_WINDOW_HOURS}ч) истекло. Стрик сброшен.",
                ephemeral=True,
            )
            await db.update_user(
                uid,
                streak=1,
                streak_lost_at=None,
                streak_before_loss=0,
            )
            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            return

        # Проверяем лимит попыток (с автосбросом при смене месяца)
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        current_month = datetime.now(kyiv_tz).month
        restores_month = user_data.get("streak_restores_month", 0)
        restores_used = user_data.get("streak_restores_used", 0)

        if restores_month != current_month:
            restores_used = 0
            restores_month = current_month

        if restores_used >= STREAK_MAX_RESTORES_PER_MONTH:
            await interaction.response.send_message(
                f"❌ Ты уже использовал все **{STREAK_MAX_RESTORES_PER_MONTH}** восстановления в этом месяце.",
                ephemeral=True,
            )
            await db.update_user(
                uid,
                streak=1,
                streak_lost_at=None,
                streak_before_loss=0,
            )
            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
            return

        # Восстанавливаем стрик!
        restored_streak = user_data.get("streak_before_loss", 0) or self.lost_streak
        if restored_streak < 1:
            restored_streak = 1
        restores_used += 1

        await db.update_user(
            uid,
            streak=restored_streak,
            streak_lost_at=None,
            streak_before_loss=0,
            streak_restores_used=restores_used,
            streak_restores_month=restores_month,
            last_daily=datetime.utcnow(),
        )

        remaining = STREAK_MAX_RESTORES_PER_MONTH - restores_used
        embed = discord.Embed(
            title="🔥 СТРИК ВОССТАНОВЛЕН!",
            description=(
                f"Твой стрик вернулся: **{restored_streak} дней** 🎉\n\n"
                f"Осталось восстановлений в этом месяце: **{remaining}/{STREAK_MAX_RESTORES_PER_MONTH}**"
            ),
            color=0x57F287,
        )

        button.disabled = True
        button.label = "✅ Восстановлено!"
        await interaction.response.edit_message(embed=embed, view=self)


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # {user_id: join_timestamp}
        self.msg_cooldowns = {}  # {user_id: last_msg_timestamp}
        self.save_voice_sessions.start()
        self.check_boost_expirations.start()
        self.check_streak_risks.start()
        # Регистрируем persistent view для кнопки восстановления стрика
        self.bot.add_view(StreakRestoreView())

    def cog_unload(self):
        self.save_voice_sessions.cancel()
        self.check_boost_expirations.cancel()
        self.check_streak_risks.cancel()

    @tasks.loop(minutes=1)
    async def check_boost_expirations(self):
        expired = await db.get_expired_boosts()
        for row in expired:
            user_id = row["user_id"]
            xp_gained = row.get("xp_boost_xp_gained", 0)
            coins_gained = row.get("xp_boost_coins_gained", 0)

            # Сбрасываем буст полностью
            await db.update_user(
                user_id,
                xp_boost_until=None,
                xp_boost_remaining=0,
                xp_boost_xp_gained=0,
                xp_boost_coins_gained=0,
            )

            member = None
            guild = None
            for g in self.bot.guilds:
                member = g.get_member(int(user_id))
                if member:
                    guild = g
                    break

            if member and guild:
                embed = discord.Embed(
                    title="⚡ Буст опыта x2 завершен",
                    description=f"{member.mention}, время действия твоего буста истекло.",
                    color=0xFFD700,
                )
                embed.add_field(
                    name="📊 Отчет по бусту",
                    value=(
                        f"▫️ Получено опыта: **+{int(xp_gained)} XP**\n"
                        f"▫️ Получено коинов: **+{int(coins_gained)} 🪙**"
                    ),
                )
                embed.set_footer(
                    text="Буст работал только во время активного фарма опыта."
                )

                chan = discord.utils.get(guild.text_channels, name="📜┃ранг")
                try:
                    if chan:
                        await chan.send(content=member.mention, embed=embed)
                    else:
                        await member.send(embed=embed)
                except:
                    pass

    @tasks.loop(minutes=2)
    async def save_voice_sessions(self):
        now = time.time()
        for user_id, join_time in list(self.voice_sessions.items()):
            duration = int(now - join_time)
            if duration >= 60:
                user = None
                for guild in self.bot.guilds:
                    user = guild.get_member(int(user_id))
                    if user:
                        break
                if not user:
                    user = self.bot.get_user(int(user_id))

                await self._process_voice_duration(user, user_id, duration)
                if user_id in self.voice_sessions:
                    self.voice_sessions[user_id] = now

    def _is_eligible(self, member):
        if not member or member.bot:
            return False
        if not member.voice or not member.voice.channel:
            return False

        # AFK канал
        if (
            member.guild.afk_channel
            and member.voice.channel.id == member.guild.afk_channel.id
        ):
            return False

        # Мут ушей
        if member.voice.self_deaf or member.voice.deaf:
            return False

        # Один в канале
        non_bots = [m for m in member.voice.channel.members if not m.bot]
        if len(non_bots) < 2:
            return False

        return True

    @commands.Cog.listener()
    async def on_ready(self):
        now = time.time()
        eligible_ids = set()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if self._is_eligible(member):
                        user_id = str(member.id)
                        eligible_ids.add(user_id)
                        if user_id not in self.voice_sessions:
                            self.voice_sessions[user_id] = now
                            await self._manage_boost_state(member, True)

        # Дополнительная проверка: если у кого-то буст активен (есть xp_boost_until),
        # но он сейчас НЕ eligible (нет в войсе с людьми) — ставим на паузу.
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT user_id, xp_boost_until FROM users WHERE xp_boost_until IS NOT NULL"
                )
                active_boosts = await cur.fetchall()

                for row in active_boosts:
                    uid = row["user_id"]
                    if uid not in eligible_ids:
                        # Ищем объект member, чтобы вызвать метод паузы
                        m = None
                        for g in self.bot.guilds:
                            m = g.get_member(int(uid))
                            if m:
                                break

                        if m:
                            await self._manage_boost_state(m, False)
                        else:
                            # Если юзера нет на сервере, просто считаем остаток и сносим until в БД напрямую
                            boost_until = row["xp_boost_until"]
                            if isinstance(boost_until, str):
                                boost_until = datetime.strptime(
                                    str(boost_until).split(".")[0], "%Y-%m-%d %H:%M:%S"
                                )

                            utcnow = datetime.utcnow()
                            if boost_until > utcnow:
                                remaining = int((boost_until - utcnow).total_seconds())
                                await db.update_user(
                                    uid,
                                    xp_boost_until=None,
                                    xp_boost_remaining=remaining,
                                )

        # Одноразовая рассылка: восстановление стриков для тех, кому не пришло уведомление
        await self._streak_amnesty_broadcast()

    async def _streak_amnesty_broadcast(self):
        """Одноразовая рассылка: находит юзеров, чей стрик тихо сбросился,
        определяет стрик по ачивкам и шлёт DM с кнопкой восстановления."""
        amnesty_done = await db.get_setting("streak_amnesty_done")
        if amnesty_done == "1":
            return

        logger = logging.getLogger("economy")
        logger.info("[StreakAmnesty] Запуск одноразовой рассылки...")

        # Маппинг ачивок на минимальный стрик
        achievement_to_streak = {
            "streak_365": 365,
            "streak_100": 100,
            "streak_69": 69,
            "streak_67": 67,
            "streak_50": 50,
            "streak_30": 30,
            "streak_21": 21,
            "streak_14": 14,
            "streak_10": 10,
            "no_lifer": 7,
            "streak_5": 5,
            "streak_3": 3,
        }

        try:
            lost_users = await db.get_silently_lost_streaks()
        except Exception as exc:
            logger.error("[StreakAmnesty] Ошибка запроса: %s", exc)
            return

        notified = 0

        for row in lost_users:
            user_id = row["user_id"]
            achievements_str = row.get("achievements", "") or ""
            achievements = achievements_str.split(",")

            # Определяем максимальный стрик по ачивкам
            best_streak = 0
            for ach_id, streak_val in achievement_to_streak.items():
                if ach_id in achievements and streak_val > best_streak:
                    best_streak = streak_val

            if best_streak < 3:
                continue

            # Помечаем стрик как потерянный
            await db.update_user(
                user_id,
                streak_lost_at=datetime.utcnow(),
                streak_before_loss=best_streak,
            )

            # Ищем юзера
            member = None
            guild = None
            for g in self.bot.guilds:
                member = g.get_member(int(user_id))
                if member:
                    guild = g
                    break

            if not member:
                continue

            kyiv_tz = ZoneInfo("Europe/Kyiv")
            current_month = datetime.now(kyiv_tz).month
            restores_month = row.get("streak_restores_month", 0)
            restores_used = row.get("streak_restores_used", 0)
            if restores_month != current_month:
                restores_used = 0
            restores_left = STREAK_MAX_RESTORES_PER_MONTH - restores_used

            embed = discord.Embed(
                title="🔧 ВОССТАНОВЛЕНИЕ СТРИКА",
                description=(
                    f"Из-за бага уведомление о потере стрика не было отправлено.\n\n"
                    f"Твой стрик был минимум **{best_streak} дней** 🔥 (по ачивкам).\n"
                    f"У тебя есть **{STREAK_RESTORE_WINDOW_HOURS} часов** чтобы восстановить его!\n\n"
                    f"Нажми кнопку ниже или используй `/restore-streak`"
                ),
                color=0xFFA500,
            )

            view = StreakRestoreView(user_id, best_streak, restores_left)

            try:
                await member.send(embed=embed, view=view)
                notified += 1
            except discord.Forbidden:
                if guild:
                    chan = discord.utils.get(guild.text_channels, name="📜┃ранг")
                    if chan:
                        try:
                            await chan.send(
                                content=member.mention, embed=embed, view=view
                            )
                            notified += 1
                        except Exception:
                            pass
            except Exception as exc:
                logger.warning(
                    "[StreakAmnesty] Не удалось отправить DM user=%s: %s",
                    user_id,
                    exc,
                )

        # Помечаем как выполненное, чтобы не спамить при перезапуске
        await db.set_setting("streak_amnesty_done", "1")
        logger.info(
            "[StreakAmnesty] Рассылка завершена. Уведомлено: %d юзеров", notified
        )


    @commands.Cog.listener()
    async def on_message(self, message):
        if (
            message.author.bot
            or not message.guild
            or message.content.startswith(PREFIX)
        ):
            return

        now = time.time()
        user_id = str(message.author.id)

        last_msg = self.msg_cooldowns.get(user_id, 0)
        if now - last_msg < 15:
            return
        self.msg_cooldowns[user_id] = now

        user_data = await db.get_user(user_id)

        xp_multiplier = 1
        is_boosted = False
        xp_boost_until = user_data.get("xp_boost_until")

        if xp_boost_until:
            if isinstance(xp_boost_until, str):
                xp_boost_until = datetime.strptime(
                    str(xp_boost_until).split(".")[0], "%Y-%m-%d %H:%M:%S"
                )
            if xp_boost_until > datetime.utcnow():
                xp_multiplier = 2
                is_boosted = True

        coins_add = random.randint(1, 3)
        xp_base = random.randint(15, 25)
        xp_add = xp_base * xp_multiplier

        new_coins = user_data.get("vibecoins", 0) + coins_add
        new_xp = user_data.get("xp", 0) + xp_add

        # Обновляем статистику буста если активен
        boost_xp_stats = user_data.get("xp_boost_xp_gained", 0)
        boost_coins_stats = user_data.get("xp_boost_coins_gained", 0)
        if is_boosted:
            boost_xp_stats += xp_add - xp_base  # Только бонусная часть
            boost_coins_stats += coins_add  # Коины тоже считаем в отчет

        await db.update_user(
            user_id,
            vibecoins=new_coins,
            xp=new_xp,
            msg_count=user_data.get("msg_count", 0) + 1,
            xp_boost_xp_gained=boost_xp_stats,
            xp_boost_coins_gained=boost_coins_stats,
        )

        self.bot.dispatch("xp_updated", message.author, new_xp)
        if message.reference and isinstance(
            message.reference.resolved, discord.Message
        ):
            replied_to = message.reference.resolved.author
            if replied_to.id != message.author.id and not replied_to.bot:
                self.bot.dispatch(
                    "message_reply_interaction", message.author, replied_to
                )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        users_to_check = {member}
        if before.channel:
            users_to_check.update(before.channel.members)
        if after.channel:
            users_to_check.update(after.channel.members)

        now = time.time()
        for u in users_to_check:
            eligible = self._is_eligible(u)
            user_id = str(u.id)

            if eligible and user_id not in self.voice_sessions:
                self.voice_sessions[user_id] = now
                # Снимаем буст с паузы
                await self._manage_boost_state(u, True)
                self.bot.dispatch("voice_role_interaction", u, u.voice.channel.members)
            elif not eligible and user_id in self.voice_sessions:
                join_time = self.voice_sessions.pop(user_id)
                duration = int(now - join_time)
                await self._process_voice_duration(u, user_id, duration)
                # Ставим буст на паузу
                await self._manage_boost_state(u, False)

    async def _manage_boost_state(self, member, active: bool):
        user_id = str(member.id)
        user_data = await db.get_user(user_id)
        now = datetime.utcnow()

        if active:
            # Снимаем с паузы
            remaining = user_data.get("xp_boost_remaining", 0)
            if remaining > 0:
                new_until = now + timedelta(seconds=remaining)
                await db.update_user(
                    user_id, xp_boost_until=new_until, xp_boost_remaining=0
                )
        else:
            # Ставим на паузу
            boost_until = user_data.get("xp_boost_until")
            if boost_until:
                if isinstance(boost_until, str):
                    boost_until = datetime.strptime(
                        str(boost_until).split(".")[0], "%Y-%m-%d %H:%M:%S"
                    )

                if boost_until > now:
                    remaining = int((boost_until - now).total_seconds())
                    await db.update_user(
                        user_id, xp_boost_until=None, xp_boost_remaining=remaining
                    )
                else:
                    # Буст уже истек, пока он сидел
                    pass

    async def _process_voice_duration(self, u, user_id, duration):
        if duration <= 0:
            return
        user_data = await db.get_user(user_id)

        old_seconds = user_data.get("voice_time_seconds", 0)
        total_voice_time = old_seconds + duration
        delta_minutes = (total_voice_time // 60) - (old_seconds // 60)

        # Стрик система с мягким сбросом (TikTok-стиль)
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        today = datetime.now(kyiv_tz).date()
        last_daily = user_data.get("last_daily")
        streak = user_data.get("streak", 0)
        streak_lost_at = user_data.get("streak_lost_at")
        last_daily_date = None
        streak_bonus = 0
        streak_xp_bonus = 0

        if last_daily:
            if isinstance(last_daily, str):
                last_daily = datetime.strptime(
                    str(last_daily).split(".")[0], "%Y-%m-%d %H:%M:%S"
                )
            last_daily_date = (
                last_daily.replace(tzinfo=ZoneInfo("UTC")).astimezone(kyiv_tz).date()
            )

        if last_daily_date == today:
            # Уже заходил сегодня — ничего не делаем со стриком
            pass
        elif streak_lost_at:
            # Стрик уже помечен как потерянный — проверяем 48ч окно
            if isinstance(streak_lost_at, str):
                streak_lost_at = datetime.strptime(
                    str(streak_lost_at).split(".")[0], "%Y-%m-%d %H:%M:%S"
                )
            hours_passed = (datetime.utcnow() - streak_lost_at).total_seconds() / 3600

            if hours_passed > STREAK_RESTORE_WINDOW_HOURS:
                # Окно истекло — финальный сброс
                streak = 1
                last_daily = datetime.utcnow()
                streak_bonus = min(streak * 100, 5000)
                streak_xp_bonus = streak_bonus // 2
                await db.update_user(
                    user_id,
                    streak_lost_at=None,
                    streak_before_loss=0,
                )
            else:
                # Ещё в окне восстановления — не трогаем стрик, не начисляем бонус
                # Обновляем last_daily чтобы не спамить повторно
                last_daily = datetime.utcnow()
        elif last_daily_date == today - timedelta(days=1):
            # Стрик продолжается!
            streak += 1
            last_daily = datetime.utcnow()
            streak_bonus = min(streak * 100, 5000)
            streak_xp_bonus = streak_bonus // 2
        elif last_daily_date is not None:
            # Пропущен день — мягкий сброс
            if streak > 1:
                current_month = datetime.now(kyiv_tz).month
                restores_month = user_data.get("streak_restores_month", 0)
                restores_used = user_data.get("streak_restores_used", 0)

                if restores_month != current_month:
                    restores_used = 0

                restores_left = STREAK_MAX_RESTORES_PER_MONTH - restores_used

                if restores_left > 0:
                    # Есть попытки — помечаем потерю, отправляем DM
                    await db.update_user(
                        user_id,
                        streak_lost_at=datetime.utcnow(),
                        streak_before_loss=streak,
                    )
                    # Обновляем last_daily чтобы не спамить повторно
                    last_daily = datetime.utcnow()

                    if u:
                        embed = discord.Embed(
                            title="💔 СТРИК ПОД УГРОЗОЙ!",
                            description=(
                                f"Ты пропустил день и можешь потерять свой стрик: **{streak} дней** 🔥\n\n"
                                f"У тебя есть **{STREAK_RESTORE_WINDOW_HOURS} часов** чтобы восстановить его!\n"
                                f"Попыток осталось: **{restores_left}/{STREAK_MAX_RESTORES_PER_MONTH}** в этом месяце"
                            ),
                            color=0xFF4500,
                        )
                        view = StreakRestoreView(user_id, streak, restores_left)
                        try:
                            await u.send(embed=embed, view=view)
                        except Exception:
                            pass
                else:
                    # Попыток нет — жёсткий сброс
                    streak = 1
                    last_daily = datetime.utcnow()
                    streak_bonus = min(streak * 100, 5000)
                    streak_xp_bonus = streak_bonus // 2
            else:
                # Стрик был 0 или 1 — начинаем заново
                streak = 1
                last_daily = datetime.utcnow()
                streak_bonus = min(streak * 100, 5000)
                streak_xp_bonus = streak_bonus // 2
        else:
            # Первый вход — last_daily_date is None
            streak = 1
            last_daily = datetime.utcnow()
            streak_bonus = min(streak * 100, 5000)
            streak_xp_bonus = streak_bonus // 2

        # Отправляем уведомление о стрик-бонусе
        if streak_bonus > 0 and u:
            embed = discord.Embed(
                title="🔥 ТВОЙ ВОЙС-СТРИК ОБНОВЛЕН!",
                description=(
                    f"Твоя серия общения продолжается! День: **{streak}**\n\n"
                    f"Бонус за сегодня:\n"
                    f"💰 **{streak_bonus} 🪙**\n"
                    f"⭐ **{streak_xp_bonus} XP**"
                ),
                color=0xFF4500,
            )

            # Попытка выдать ежедневное задание
            tasks_cog = self.bot.get_cog("DailyTasks")
            if tasks_cog:
                new_task = await tasks_cog.assign_new_task(u)
                if new_task:
                    embed.add_field(
                        name="🌟 НОВОЕ ЗАДАНИЕ",
                        value=(
                            f"**{new_task['name']}**\n"
                            f"└ {new_task['desc']}\n\n"
                            f"💰 Награда: **{new_task['reward_coins']} 🪙** | "
                            f"**{new_task['reward_xp']} XP**"
                        ),
                        inline=False,
                    )

            try:
                await u.send(embed=embed)
            except Exception:
                pass
            self.bot.dispatch("streak_updated", u, streak)

        # Проверка буста
        xp_multiplier = 1
        is_boosted = False
        xp_boost_until = user_data.get("xp_boost_until")
        if xp_boost_until:
            if isinstance(xp_boost_until, str):
                xp_boost_until = datetime.strptime(
                    str(xp_boost_until).split(".")[0], "%Y-%m-%d %H:%M:%S"
                )
            if xp_boost_until > datetime.utcnow():
                xp_multiplier = 2
                is_boosted = True

        coins_add = (delta_minutes * 6) + streak_bonus
        xp_base = delta_minutes * 10
        xp_add = (xp_base * xp_multiplier) + streak_xp_bonus

        boost_xp_stats = user_data.get("xp_boost_xp_gained", 0)
        boost_coins_stats = user_data.get("xp_boost_coins_gained", 0)
        if is_boosted:
            boost_xp_stats += xp_add - xp_base
            boost_coins_stats += delta_minutes * 6

        await db.update_user(
            user_id,
            vibecoins=user_data.get("vibecoins", 0) + coins_add,
            xp=user_data.get("xp", 0) + xp_add,
            voice_time_seconds=total_voice_time,
            streak=streak,
            last_daily=last_daily,
            xp_boost_xp_gained=boost_xp_stats,
            xp_boost_coins_gained=boost_coins_stats,
        )

        if u and delta_minutes > 0:
            self.bot.dispatch("xp_updated", u, user_data.get("xp", 0) + xp_add)
            self.bot.dispatch("voice_time_updated", u, total_voice_time, delta_minutes)

    @discord.app_commands.command(
        name="give-money", description="[Admin] Выдать VibeКоины пользователю"
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def give_money(
        self, interaction: discord.Interaction, member: discord.Member, amount: int
    ):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ Только для владельца.", ephemeral=True
            )
        user_data = await db.get_user(str(member.id))
        new_coins = user_data.get("vibecoins", 0) + amount
        await db.update_user(str(member.id), vibecoins=new_coins)
        await interaction.response.send_message(
            f"✅ Выдано **{amount} 🪙** {member.mention}. Итого: **{new_coins} 🪙**"
        )

    @discord.app_commands.command(
        name="give-streak",
        description="[Admin] Установить стрик пользователю",
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def give_streak(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Только для администраторов.", ephemeral=True
            )

        if amount < 0:
            return await interaction.response.send_message(
                "❌ Стрик не может быть отрицательным.", ephemeral=True
            )

        await db.update_user(
            str(member.id),
            streak=amount,
            last_daily=datetime.utcnow(),
            streak_lost_at=None,
            streak_before_loss=0,
        )

        await interaction.response.send_message(
            f"✅ Стрик {member.mention} установлен на **{amount} 🔥**"
        )

        self.bot.dispatch("streak_updated", member, amount)

    # ------------------------------------------------------------------
    # Фоновая задача: проактивная проверка стриков (каждые 2 часа)
    # ------------------------------------------------------------------
    @tasks.loop(hours=2)
    async def check_streak_risks(self):
        """Проверяет юзеров, пропустивших день, и шлёт DM с кнопкой восстановления.

        Работает НЕЗАВИСИМО от того, зашёл юзер в войс или нет.
        """
        try:
            at_risk = await db.get_at_risk_streaks()
        except Exception as exc:
            logging.getLogger("economy").error(
                "[StreakRisk] Ошибка запроса at_risk_streaks: %s", exc
            )
            return

        kyiv_tz = ZoneInfo("Europe/Kyiv")
        today = datetime.now(kyiv_tz).date()

        for row in at_risk:
            user_id = row["user_id"]
            streak = row.get("streak", 0)
            last_daily = row.get("last_daily")

            if not last_daily or streak <= 1:
                continue

            if isinstance(last_daily, str):
                last_daily = datetime.strptime(
                    str(last_daily).split(".")[0], "%Y-%m-%d %H:%M:%S"
                )

            last_daily_date = (
                last_daily.replace(tzinfo=ZoneInfo("UTC")).astimezone(kyiv_tz).date()
            )

            # Стрик ещё актуален (сегодня или вчера)
            if last_daily_date >= today - timedelta(days=1):
                continue

            # Считаем оставшиеся восстановления
            current_month = datetime.now(kyiv_tz).month
            restores_month = row.get("streak_restores_month", 0)
            restores_used = row.get("streak_restores_used", 0)

            if restores_month != current_month:
                restores_used = 0

            restores_left = STREAK_MAX_RESTORES_PER_MONTH - restores_used

            if restores_left <= 0:
                # Попыток нет — жёсткий сброс
                await db.update_user(
                    user_id,
                    streak=1,
                    streak_lost_at=None,
                    streak_before_loss=0,
                    last_daily=datetime.utcnow(),
                )
                continue

            # Помечаем потерю и отправляем уведомление
            await db.update_user(
                user_id,
                streak_lost_at=datetime.utcnow(),
                streak_before_loss=streak,
            )

            # Отправляем DM
            member = None
            for guild in self.bot.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    break

            if not member:
                continue

            embed = discord.Embed(
                title="💔 СТРИК ПОД УГРОЗОЙ!",
                description=(
                    f"Ты пропустил день и можешь потерять свой стрик: **{streak} дней** 🔥\n\n"
                    f"У тебя есть **{STREAK_RESTORE_WINDOW_HOURS} часов** чтобы восстановить его!\n"
                    f"Попыток осталось: **{restores_left}/{STREAK_MAX_RESTORES_PER_MONTH}** в этом месяце\n\n"
                    f"Нажми кнопку ниже или используй `/restore-streak`"
                ),
                color=0xFF4500,
            )
            view = StreakRestoreView(user_id, streak, restores_left)

            try:
                await member.send(embed=embed, view=view)
            except discord.Forbidden:
                # ЛС закрыты — пытаемся отправить в канал
                for guild in self.bot.guilds:
                    chan = discord.utils.get(guild.text_channels, name="📜┃ранг")
                    if chan:
                        try:
                            await chan.send(
                                content=member.mention, embed=embed, view=view
                            )
                        except Exception:
                            pass
                        break
            except Exception as exc:
                logging.getLogger("economy").warning(
                    "[StreakRisk] Не удалось отправить DM user=%s: %s",
                    user_id,
                    exc,
                )

    @check_streak_risks.before_loop
    async def before_check_streak_risks(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # /restore-streak — ручное восстановление стрика
    # ------------------------------------------------------------------
    @discord.app_commands.command(
        name="restore-streak",
        description="Восстановить потерянный стрик (если есть попытки)",
    )
    async def restore_streak_cmd(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = await db.get_user(user_id)

        streak_lost_at = user_data.get("streak_lost_at")
        streak = user_data.get("streak", 0)
        streak_before_loss = user_data.get("streak_before_loss", 0)

        # Проверяем, есть ли вообще что восстанавливать
        if not streak_lost_at and streak_before_loss == 0:
            return await interaction.response.send_message(
                "✅ Твой стрик активен, восстанавливать нечего!", ephemeral=True
            )

        if not streak_lost_at:
            return await interaction.response.send_message(
                "❌ Стрик не помечен как потерянный.", ephemeral=True
            )

        # Проверяем 48ч окно
        if isinstance(streak_lost_at, str):
            streak_lost_at = datetime.strptime(
                str(streak_lost_at).split(".")[0], "%Y-%m-%d %H:%M:%S"
            )
        hours_passed = (datetime.utcnow() - streak_lost_at).total_seconds() / 3600

        if hours_passed > STREAK_RESTORE_WINDOW_HOURS:
            await db.update_user(
                user_id,
                streak=1,
                streak_lost_at=None,
                streak_before_loss=0,
            )
            return await interaction.response.send_message(
                f"⏰ Окно восстановления ({STREAK_RESTORE_WINDOW_HOURS}ч) истекло. "
                f"Стрик сброшен до 1.",
                ephemeral=True,
            )

        # Проверяем лимит попыток
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        current_month = datetime.now(kyiv_tz).month
        restores_month = user_data.get("streak_restores_month", 0)
        restores_used = user_data.get("streak_restores_used", 0)

        if restores_month != current_month:
            restores_used = 0
            restores_month = current_month

        if restores_used >= STREAK_MAX_RESTORES_PER_MONTH:
            await db.update_user(
                user_id,
                streak=1,
                streak_lost_at=None,
                streak_before_loss=0,
            )
            return await interaction.response.send_message(
                f"❌ Ты уже использовал все **{STREAK_MAX_RESTORES_PER_MONTH}** "
                f"восстановления в этом месяце. Стрик сброшен.",
                ephemeral=True,
            )

        # Восстанавливаем!
        restored_streak = streak_before_loss if streak_before_loss > 0 else streak
        restores_used += 1

        await db.update_user(
            user_id,
            streak=restored_streak,
            streak_lost_at=None,
            streak_before_loss=0,
            streak_restores_used=restores_used,
            streak_restores_month=restores_month,
            last_daily=datetime.utcnow(),
        )

        remaining = STREAK_MAX_RESTORES_PER_MONTH - restores_used
        embed = discord.Embed(
            title="🔥 СТРИК ВОССТАНОВЛЕН!",
            description=(
                f"Твой стрик вернулся: **{restored_streak} дней** 🎉\n\n"
                f"Осталось восстановлений в этом месяце: **{remaining}/{STREAK_MAX_RESTORES_PER_MONTH}**"
            ),
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # /grant-streak-restore — админская выдача возможности восстановить стрик
    # ------------------------------------------------------------------
    @discord.app_commands.command(
        name="grant-streak-restore",
        description="[Admin] Дать юзеру возможность восстановить стрик (без траты лимита)",
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def grant_streak_restore(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        streak_value: int,
    ):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message(
                "❌ Только для владельца.", ephemeral=True
            )

        if streak_value <= 0:
            return await interaction.response.send_message(
                "❌ Значение стрика должно быть > 0.", ephemeral=True
            )

        user_id = str(member.id)

        # Помечаем стрик как потерянный с указанным значением
        await db.update_user(
            user_id,
            streak_lost_at=datetime.utcnow(),
            streak_before_loss=streak_value,
        )

        # Отправляем DM юзеру
        embed = discord.Embed(
            title="💔 СТРИК ПОД УГРОЗОЙ!",
            description=(
                f"Тебе выдана возможность восстановить стрик: **{streak_value} дней** 🔥\n\n"
                f"У тебя есть **{STREAK_RESTORE_WINDOW_HOURS} часов** чтобы восстановить его!\n\n"
                f"Нажми кнопку ниже или используй `/restore-streak`"
            ),
            color=0xFF4500,
        )

        user_data = await db.get_user(user_id)
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        current_month = datetime.now(kyiv_tz).month
        restores_month = user_data.get("streak_restores_month", 0)
        restores_used = user_data.get("streak_restores_used", 0)
        if restores_month != current_month:
            restores_used = 0
        restores_left = STREAK_MAX_RESTORES_PER_MONTH - restores_used

        view = StreakRestoreView(user_id, streak_value, restores_left)

        try:
            await member.send(embed=embed, view=view)
            dm_status = "DM отправлен ✉️"
        except Exception:
            dm_status = "⚠️ DM не дошёл (закрыты ЛС)"
            # Фоллбэк в канал
            chan = discord.utils.get(
                interaction.guild.text_channels, name="📜┃ранг"
            )
            if chan:
                try:
                    await chan.send(
                        content=member.mention, embed=embed, view=view
                    )
                    dm_status = "Отправлено в #📜┃ранг"
                except Exception:
                    pass

        await interaction.response.send_message(
            f"✅ {member.mention} может восстановить стрик до **{streak_value} 🔥**\n"
            f"Статус: {dm_status}",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))

