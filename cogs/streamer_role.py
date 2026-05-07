import discord
from discord.ext import commands, tasks
import logging
import os
from datetime import datetime, timedelta, timezone
from utils.db import db

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Настройка: имя роли или ID роли из .env
# ─────────────────────────────────────────────────────────────────────────────
STREAMER_ROLE_ID = os.getenv("STREAMER_ROLE_ID")
STREAMER_ROLE_NAME = os.getenv("STREAMER_ROLE_NAME", "[🎥] Стример")

# Сколько дней без стрима → роль снимается
INACTIVE_DAYS = 30


def _get_streamer_role(guild: discord.Guild) -> discord.Role | None:
    """Ищет роль стримера по ID (из .env) или по имени."""
    if STREAMER_ROLE_ID and STREAMER_ROLE_ID.isdigit():
        role = guild.get_role(int(STREAMER_ROLE_ID))
        if role:
            return role
    return discord.utils.get(guild.roles, name=STREAMER_ROLE_NAME)


def _is_streaming(member: discord.Member) -> bool:
    """Проверяет, стримит ли участник прямо сейчас в Discord (Go Live)."""
    for activity in member.activities:
        if isinstance(activity, discord.Streaming):
            return True
    return False


class StreamerRole(commands.Cog):
    """
    Автоматически выдаёт и убирает роль стримера при Discord Go Live.
    Если участник не стримил более INACTIVE_DAYS дней — роль снимается.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_inactive_streamers.start()

    def cog_unload(self):
        self.check_inactive_streamers.cancel()

    # ──────────────────────────────────────────────
    # БД: обновить дату последнего стрима
    # ──────────────────────────────────────────────
    async def _update_last_stream(self, user_id: int):
        """Записывает текущее время как дату последнего стрима."""
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO streamer_activity (user_id, last_streamed_at)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE last_streamed_at = VALUES(last_streamed_at)
                """, (str(user_id), datetime.utcnow()))

    async def _get_last_stream(self, user_id: int) -> datetime | None:
        """Возвращает дату последнего стрима или None."""
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT last_streamed_at FROM streamer_activity WHERE user_id = %s",
                    (str(user_id),)
                )
                row = await cur.fetchone()
                return row["last_streamed_at"] if row else None

    async def _get_all_streamer_ids(self) -> list[str]:
        """Возвращает список всех user_id из таблицы."""
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT user_id FROM streamer_activity")
                rows = await cur.fetchall()
                return [r["user_id"] for r in rows]

    async def _delete_streamer_record(self, user_id: int):
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM streamer_activity WHERE user_id = %s",
                    (str(user_id),)
                )

    # ──────────────────────────────────────────────
    # on_presence_update — выдаём / убираем роль
    # ──────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild
        role = _get_streamer_role(guild)
        if role is None:
            return

        was_streaming = _is_streaming(before)
        now_streaming = _is_streaming(after)

        if was_streaming == now_streaming:
            return

        try:
            if now_streaming and role not in after.roles:
                await after.add_roles(role, reason="Discord Go Live — стрим начался")
                await self._update_last_stream(after.id)
                logger.info(f"[StreamerRole] ✅ Выдана роль '{role.name}' → {after} ({after.id})")

            elif not now_streaming and role in after.roles:
                # Роль НЕ снимаем сразу — только обновляем дату
                await self._update_last_stream(after.id)
                logger.info(f"[StreamerRole] 🎬 Стрим завершён: {after} ({after.id}), роль сохранена")

        except discord.Forbidden:
            logger.error(
                f"[StreamerRole] Нет прав для управления ролью '{role.name}' у {after}. "
                "Убедись, что роль бота выше роли стримера в иерархии."
            )
        except discord.HTTPException as e:
            logger.error(f"[StreamerRole] HTTP ошибка при изменении роли: {e}")

    # ──────────────────────────────────────────────
    # Ежедневная проверка неактивных стримеров
    # ──────────────────────────────────────────────
    @tasks.loop(hours=24)
    async def check_inactive_streamers(self):
        """Раз в сутки проверяет: у кого роль есть, но не стримил > INACTIVE_DAYS дней."""
        logger.info("[StreamerRole] 🔍 Проверка неактивных стримеров...")
        cutoff = datetime.utcnow() - timedelta(days=INACTIVE_DAYS)

        for guild in self.bot.guilds:
            role = _get_streamer_role(guild)
            if role is None:
                continue

            for member in role.members:
                if member.bot:
                    continue

                last = await self._get_last_stream(member.id)

                # Нет записи вообще → запись существует давно, убираем роль
                if last is None or last < cutoff:
                    try:
                        await member.remove_roles(
                            role,
                            reason=f"Нет стримов более {INACTIVE_DAYS} дней — роль снята автоматически"
                        )
                        await self._delete_streamer_record(member.id)
                        logger.info(
                            f"[StreamerRole] ⏰ Роль снята за неактивность: {member} ({member.id}), "
                            f"последний стрим: {last}"
                        )

                        # Уведомление в ЛС
                        try:
                            embed = discord.Embed(
                                title="⏰ Роль стримера снята",
                                description=(
                                    f"Привет, **{member.display_name}**!\n\n"
                                    f"Роль **{role.name}** была автоматически снята, "
                                    f"так как ты не стримил(а) более **{INACTIVE_DAYS} дней**.\n\n"
                                    f"Просто включи стрим в Discord — роль вернётся мгновенно! 🎥"
                                ),
                                color=0xED4245,
                            )
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            pass  # ЛС закрыты — молча пропускаем

                    except (discord.Forbidden, discord.HTTPException) as e:
                        logger.error(f"[StreamerRole] Ошибка снятия роли у {member}: {e}")

    @check_inactive_streamers.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ──────────────────────────────────────────────
    # Команды администратора
    # ──────────────────────────────────────────────
    @commands.command(name="streamer_check")
    @commands.has_permissions(administrator=True)
    async def streamer_check(self, ctx: commands.Context):
        """!streamer_check — показывает текущих стримеров и состояние роли."""
        role = _get_streamer_role(ctx.guild)

        embed = discord.Embed(title="🎥 Статус роли Стримера", color=0x9146FF)

        if role is None:
            embed.description = (
                f"⚠️ Роль **{STREAMER_ROLE_NAME}** не найдена на сервере.\n\n"
                "Создай роль с таким именем или укажи `STREAMER_ROLE_ID` в `.env`."
            )
            await ctx.send(embed=embed)
            return

        embed.add_field(name="Роль", value=f"{role.mention} (ID: `{role.id}`)", inline=False)
        embed.add_field(name="Порог неактивности", value=f"`{INACTIVE_DAYS}` дней", inline=True)

        # Кто стримит сейчас
        streaming_now = [m for m in ctx.guild.members if _is_streaming(m) and not m.bot]
        embed.add_field(
            name="🔴 Стримят сейчас",
            value="\n".join(m.mention for m in streaming_now) or "никого",
            inline=False,
        )

        # Участники с ролью + дата последнего стрима
        members_with_role = [m for m in role.members if not m.bot]
        if members_with_role:
            cutoff = datetime.utcnow() - timedelta(days=INACTIVE_DAYS)
            lines = []
            for m in members_with_role:
                last = await self._get_last_stream(m.id)
                if last is None:
                    status = "⚠️ нет данных"
                else:
                    days_ago = (datetime.utcnow() - last).days
                    warn = " ⚠️ скоро слетит!" if last < cutoff - timedelta(days=5) else ""
                    status = f"{last.strftime('%d.%m.%Y')}{warn} ({days_ago}д назад)"
                lines.append(f"{m.mention} — {status}")
            embed.add_field(
                name=f"С ролью ({len(members_with_role)})",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(name=f"С ролью", value="никого", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="streamer_sync")
    @commands.has_permissions(administrator=True)
    async def streamer_sync(self, ctx: commands.Context):
        """!streamer_sync — принудительно синхронизирует роль у всех участников."""
        role = _get_streamer_role(ctx.guild)
        if role is None:
            await ctx.send(f"⚠️ Роль **{STREAMER_ROLE_NAME}** не найдена.")
            return

        added, removed, errors = 0, 0, 0

        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                if _is_streaming(member) and role not in member.roles:
                    await member.add_roles(role, reason="!streamer_sync")
                    await self._update_last_stream(member.id)
                    added += 1
                elif not _is_streaming(member) and role in member.roles:
                    await member.remove_roles(role, reason="!streamer_sync")
                    removed += 1
            except Exception:
                errors += 1

        embed = discord.Embed(title="🔄 Синхронизация завершена", color=0x57F287)
        embed.add_field(name="✅ Выдано", value=str(added), inline=True)
        embed.add_field(name="❌ Убрано", value=str(removed), inline=True)
        if errors:
            embed.add_field(name="⚠️ Ошибок", value=str(errors), inline=True)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StreamerRole(bot))
