import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional


class ActivityCleanup(commands.Cog):
    """Автоматическое удаление сообщений об активностях (Discord Activities)
    из текстовых каналов, когда пользователь выходит из активности."""

    # Ключевые слова для определения сообщений-приглашений в активности (embed)
    ACTIVITY_EMBED_KEYWORDS = [
        "приглашение в игру",
        "invitation to play",
        "играют:",
        "playing:",
        "игра завершена",
        "начать новую",
        "game over",
        "play again",
        "join game",
        "присоединиться",
    ]

    # Ключевые слова в контенте сообщений
    ACTIVITY_CONTENT_KEYWORDS = [
        "использует",
        "запустить",
        "started an activity",
        "is playing",
        "started playing",
    ]

    # Известные типы системных сообщений для активностей
    ACTIVITY_MESSAGE_TYPES = {46, 47, 48}

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # user_id -> list of tracked message info dicts
        self._tracked: dict[int, list[dict]] = {}
        self._cleanup_stale.start()

    def cog_unload(self) -> None:
        self._cleanup_stale.cancel()

    # ------------------------------------------------------------------
    # Утилита: собрать весь текст из embed-а для анализа
    # ------------------------------------------------------------------
    @staticmethod
    def _get_embed_full_text(embed: discord.Embed) -> str:
        """Собирает весь текст из embed-а (title, description, author,
        footer, fields) в одну строку для поиска ключевых слов."""
        parts: list[str] = []
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        if embed.author and embed.author.name:
            parts.append(embed.author.name)
        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)
        for field in embed.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)
        return " ".join(parts).lower()

    # ------------------------------------------------------------------
    # Утилита: извлечь название активности из сообщения
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_activity_name(message: discord.Message) -> Optional[str]:
        """Извлекает название активности из embed-а или контента сообщения."""
        # Из embed-ов
        for embed in message.embeds:
            if embed.title:
                return embed.title.strip()
            if embed.author and embed.author.name:
                return embed.author.name.strip()

        # Из interaction metadata
        if message.interaction is not None:
            return message.interaction.name

        # Из контента ("Mriamys использует Farm Merge Valley")
        content = message.content or ""
        for kw in ("использует", "is playing", "started"):
            if kw in content.lower():
                return content.strip()

        return None

    # ------------------------------------------------------------------
    # Утилита: проверить, является ли сообщение приглашением в активность
    # ------------------------------------------------------------------
    def _is_activity_message(self, message: discord.Message) -> bool:
        """Определяет, является ли сообщение уведомлением об активности."""
        # 1. Системное сообщение с атрибутом activity
        if message.activity is not None:
            return True

        # 2. Системные типы Discord для активностей
        if message.type.value in self.ACTIVITY_MESSAGE_TYPES:
            return True

        # 3. Сообщения от ботов с embed-приглашениями в игру
        #    Проверяем ВСЕ текстовые поля embed-а, а не только title/description
        if message.author.bot and message.embeds:
            for embed in message.embeds:
                full_text = self._get_embed_full_text(embed)
                if any(kw in full_text for kw in self.ACTIVITY_EMBED_KEYWORDS):
                    return True

        # 4. Сообщения от ботов, запущенных через interaction (кнопка "Запустить")
        if message.author.bot and message.interaction is not None:
            return True

        # 5. Сообщения с компонентами (кнопками) от ботов — Activity-игры
        #    всегда отправляют embed + кнопку "Играть"/"Play"
        if message.author.bot and message.components:
            has_embed = bool(message.embeds)
            if has_embed:
                return True

        # 6. Системные сообщения (не default) с паттернами активности
        if message.type != discord.MessageType.default:
            content_lower = (message.content or "").lower()
            if any(kw in content_lower for kw in self.ACTIVITY_CONTENT_KEYWORDS):
                return True

        # 7. Любые сообщения с контентом об активностях + упоминания/боты
        content_lower = (message.content or "").lower()
        if any(kw in content_lower for kw in self.ACTIVITY_CONTENT_KEYWORDS):
            if message.author.bot or message.mentions:
                return True

        return False

    # ------------------------------------------------------------------
    # Утилита: определить user_id автора/инициатора активности
    # ------------------------------------------------------------------
    @staticmethod
    def _get_activity_user_id(message: discord.Message) -> Optional[int]:
        """Пытается определить, кто запустил активность."""
        # Из interaction (пользователь нажал кнопку "Запустить")
        if message.interaction is not None:
            return message.interaction.user.id

        # Если это системное сообщение — автор = инициатор
        if message.type != discord.MessageType.default:
            return message.author.id

        # Если в сообщении есть упоминания — первый упомянутый
        if message.mentions:
            return message.mentions[0].id

        return None

    # ------------------------------------------------------------------
    # on_message — трекаем сообщения об активностях
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        # Дебаг-лог для всех сообщений от ботов с embed-ами
        if message.author.bot and message.embeds:
            for i, embed in enumerate(message.embeds):
                author_name = embed.author.name if embed.author else None
                logging.debug(
                    f"[ActivityCleanup] Бот-сообщение: "
                    f"author={message.author.name!r}, "
                    f"msg_type={message.type!r} (value={message.type.value}), "
                    f"embed[{i}] title={embed.title!r}, "
                    f"desc={embed.description!r}, "
                    f"embed_author={author_name!r}, "
                    f"interaction={message.interaction!r}, "
                    f"components={len(message.components)}"
                )

        if not self._is_activity_message(message):
            return

        user_id = self._get_activity_user_id(message)
        activity_name = self._extract_activity_name(message)

        # Если не смогли определить пользователя — трекаем под ID 0 (общий пул)
        key = user_id or 0

        if key not in self._tracked:
            self._tracked[key] = []

        self._tracked[key].append(
            {
                "message": message,
                "channel_id": message.channel.id,
                "activity_name": activity_name,
            }
        )

        logging.info(
            f"[ActivityCleanup] Отслеживаю сообщение об активности "
            f"(id={message.id}, type={message.type!r}, user={key}, "
            f"activity={activity_name!r}) в #{message.channel.name}"
        )

    # ------------------------------------------------------------------
    # on_presence_update — ловим момент когда пользователь выходит из активности
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_presence_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        # Собираем ВСЕ активности (playing, streaming, custom, unknown — любые)
        # Discord Activities не всегда помечены как ActivityType.playing
        before_activities = {a.name for a in before.activities if a.name}
        after_activities = {a.name for a in after.activities if a.name}

        # Активности, из которых пользователь вышел
        stopped = before_activities - after_activities
        if not stopped:
            return

        # Проверяем есть ли отслеженные сообщения для этого пользователя
        if before.id not in self._tracked:
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
