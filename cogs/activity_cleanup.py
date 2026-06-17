import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional


class ActivityCleanup(commands.Cog):
    """Автоматическое удаление сообщений об активностях (Discord Activities)
    из текстовых каналов, когда пользователь выходит из активности."""

    # Ключевые слова для определения сообщений-приглашений в активности
    ACTIVITY_EMBED_KEYWORDS = [
        "приглашение в игру",
        "invitation to play",
        "играют:",
        "playing:",
    ]

    # Ключевые слова в контенте системных сообщений
    ACTIVITY_CONTENT_KEYWORDS = [
        "использует",
        "запустить",
        "started an activity",
        "is playing",
    ]

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # user_id -> list of tracked message info dicts
        # Каждый dict: {"message": Message, "activity_name": str}
        self._tracked: dict[int, list[dict]] = {}
        self._cleanup_stale.start()

    def cog_unload(self) -> None:
        self._cleanup_stale.cancel()

    # ------------------------------------------------------------------
    # Утилита: извлечь название активности из сообщения
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_activity_name(message: discord.Message) -> Optional[str]:
        """Извлекает название активности из embed-а или контента сообщения."""
        # Из embed-ов (сообщения от ботов-активностей типа Farm Merge Valley)
        for embed in message.embeds:
            title = embed.title or ""
            if title:
                return title.strip()

        # Из контента ("Mriamys использует Farm Merge Valley")
        content = message.content or ""
        for kw in ("использует", "is playing", "started"):
            if kw in content.lower():
                return content

        return None

    # ------------------------------------------------------------------
    # Утилита: проверить, является ли сообщение приглашением в активность
    # ------------------------------------------------------------------
    @staticmethod
    def _is_activity_message(message: discord.Message) -> bool:
        """Определяет, является ли сообщение уведомлением об активности."""
        # 1. Системное сообщение с атрибутом activity
        if message.activity is not None:
            return True

        # 2. Системные типы Discord для активностей (type value 46, 47, 48)
        if message.type.value in (46, 47, 48):
            return True

        # 3. Сообщения от ботов с embed-приглашениями в игру
        if message.author.bot and message.embeds:
            for embed in message.embeds:
                title = (embed.title or "").lower()
                desc = (embed.description or "").lower()
                combined = f"{title} {desc}"
                if any(
                    kw in combined for kw in ActivityCleanup.ACTIVITY_EMBED_KEYWORDS
                ):
                    return True

        # 4. Системные сообщения с типичными паттернами активности в контенте
        if message.type != discord.MessageType.default:
            content_lower = (message.content or "").lower()
            if any(
                kw in content_lower for kw in ActivityCleanup.ACTIVITY_CONTENT_KEYWORDS
            ):
                return True

        return False

    # ------------------------------------------------------------------
    # Утилита: определить user_id автора/инициатора активности
    # ------------------------------------------------------------------
    @staticmethod
    def _get_activity_user_id(message: discord.Message) -> Optional[int]:
        """Пытается определить, кто запустил активность."""
        # Если это системное сообщение — автор = инициатор
        if message.type != discord.MessageType.default:
            return message.author.id

        # Если в сообщении есть упоминания — первый упомянутый
        if message.mentions:
            return message.mentions[0].id

        # Для ботов-активностей: ищем в interaction
        if message.interaction is not None:
            return message.interaction.user.id

        return None

    # ------------------------------------------------------------------
    # on_message — трекаем сообщения об активностях
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        if not self._is_activity_message(message):
            return

        user_id = self._get_activity_user_id(message)
        activity_name = self._extract_activity_name(message)

        # Если не смогли определить пользователя — трекаем под ID 0 (общий пул)
        key = user_id or 0

        if key not in self._tracked:
            self._tracked[key] = []

        self._tracked[key].append({"message": message, "activity_name": activity_name})

        logging.info(
            f"[ActivityCleanup] Отслеживаю сообщение об активности "
            f"(id={message.id}, user={key}, activity={activity_name}) "
            f"в #{message.channel.name}"
        )

    # ------------------------------------------------------------------
    # on_presence_update — ловим момент когда пользователь выходит из активности
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_presence_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        # Определяем активности-игры до и после
        before_activities = {
            a.name
            for a in before.activities
            if isinstance(a, (discord.Game, discord.Activity))
            and a.type == discord.ActivityType.playing
        }
        after_activities = {
            a.name
            for a in after.activities
            if isinstance(a, (discord.Game, discord.Activity))
            and a.type == discord.ActivityType.playing
        }

        # Активности, из которых пользователь вышел
        stopped = before_activities - after_activities
        if not stopped:
            return

        logging.info(
            f"[ActivityCleanup] {before.display_name} завершил активности: "
            f"{', '.join(stopped)}"
        )

        # Небольшая задержка — Discord может обновить presence раньше,
        # чем сообщение будет отправлено
        await asyncio.sleep(2)

        await self._delete_user_activity_messages(before.id, stopped)

    # ------------------------------------------------------------------
    # on_voice_state_update — бэкап: чистим когда пользователь выходит из войса
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Пользователь полностью вышел из войса
        if before.channel is not None and after.channel is None:
            if member.id in self._tracked:
                logging.info(
                    f"[ActivityCleanup] {member.display_name} вышел из войса, "
                    f"удаляю все отслеженные сообщения об активностях"
                )
                await self._delete_user_activity_messages(member.id)

    # ------------------------------------------------------------------
    # Удаление сообщений конкретного пользователя
    # ------------------------------------------------------------------
    async def _delete_user_activity_messages(
        self,
        user_id: int,
        stopped_activities: Optional[set[str]] = None,
    ) -> None:
        """Удаляет отслеженные сообщения об активностях пользователя.

        Args:
            user_id: ID пользователя.
            stopped_activities: Названия завершённых активностей.
                Если None — удаляет все сообщения пользователя.
        """
        entries = self._tracked.get(user_id, [])
        if not entries:
            return

        remaining = []
        deleted_count = 0

        for entry in entries:
            should_delete = False

            if stopped_activities is None:
                # Удаляем всё
                should_delete = True
            else:
                # Удаляем только сообщения, связанные с завершёнными активностями
                activity_name = entry.get("activity_name") or ""
                for stopped in stopped_activities:
                    if (
                        stopped.lower() in activity_name.lower()
                        or activity_name.lower() in stopped.lower()
                    ):
                        should_delete = True
                        break

                # Если не смогли сопоставить по имени — тоже удаляем
                # (лучше удалить лишнее, чем оставить спам)
                if not activity_name:
                    should_delete = True

            if should_delete:
                msg = entry["message"]
                try:
                    await msg.delete()
                    deleted_count += 1
                except discord.NotFound:
                    pass  # Уже удалено
                except discord.Forbidden:
                    logging.warning(
                        f"[ActivityCleanup] Нет прав удалить сообщение "
                        f"(id={msg.id}) в #{msg.channel.name}"
                    )
                except Exception as e:
                    logging.error(f"[ActivityCleanup] Ошибка удаления: {e}")
            else:
                remaining.append(entry)

        if remaining:
            self._tracked[user_id] = remaining
        elif user_id in self._tracked:
            del self._tracked[user_id]

        if deleted_count > 0:
            logging.info(
                f"[ActivityCleanup] Удалено {deleted_count} сообщений "
                f"об активностях пользователя (id={user_id})"
            )

    # ------------------------------------------------------------------
    # Фоновая задача: чистим устаревшие записи каждые 30 минут
    # ------------------------------------------------------------------
    @tasks.loop(minutes=30)
    async def _cleanup_stale(self) -> None:
        """Удаляет из трекера записи старше 6 часов."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=6)
        cleaned = 0

        for uid in list(self._tracked.keys()):
            original = len(self._tracked[uid])
            self._tracked[uid] = [
                e for e in self._tracked[uid] if e["message"].created_at > cutoff
            ]
            cleaned += original - len(self._tracked[uid])
            if not self._tracked[uid]:
                del self._tracked[uid]

        if cleaned > 0:
            logging.info(f"[ActivityCleanup] Очистил {cleaned} устаревших записей")

    @_cleanup_stale.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCleanup(bot))
