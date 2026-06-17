import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional


logger = logging.getLogger("activity_cleanup")


class ActivityCleanup(commands.Cog):
    """Автоматическое удаление сообщений об активностях (Discord Activities)
    из текстовых каналов, когда пользователь выходит из активности.

    Три механизма удаления:
    1. on_message — трекаем сообщения об активностях в реальном времени
    2. on_voice_state_update — удаляем при выходе из войса (+ сканируем канал)
    3. Периодическая задача — каждые 2 мин проверяем, завершились ли активности
    """

    # Ключевые слова для определения activity embed
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
    ]

    # Системные типы сообщений для активностей
    ACTIVITY_MESSAGE_TYPES = {46, 47, 48}

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # user_id -> list of tracked dicts
        self._tracked: dict[int, list[dict]] = {}
        # Каналы, в которых мы видели activity-сообщения (для сканирования)
        self._activity_channels: set[int] = set()
        self._cleanup_stale.start()
        self._check_ended_activities.start()

    def cog_unload(self) -> None:
        self._cleanup_stale.cancel()
        self._check_ended_activities.cancel()

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------
    @staticmethod
    def _get_embed_full_text(embed: discord.Embed) -> str:
        """Собирает весь текст из всех полей embed-а."""
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

    @staticmethod
    def _extract_activity_name(message: discord.Message) -> Optional[str]:
        """Извлекает название активности из сообщения."""
        for embed in message.embeds:
            if embed.title:
                return embed.title.strip()
            if embed.author and embed.author.name:
                return embed.author.name.strip()
        if message.interaction is not None:
            return message.interaction.name
        content = message.content or ""
        for kw in ("использует", "is playing", "started"):
            if kw in content.lower():
                return content.strip()
        if message.author.bot:
            return message.author.name
        return None

    def _is_activity_message(self, message: discord.Message) -> bool:
        """Определяет, является ли сообщение уведомлением об активности."""
        # 1. Атрибут activity
        if message.activity is not None:
            return True

        # 2. Системные типы для активностей
        if message.type.value in self.ACTIVITY_MESSAGE_TYPES:
            return True

        # 3. Бот + embed с ключевыми словами (все поля embed-а)
        if message.author.bot and message.embeds:
            for embed in message.embeds:
                full_text = self._get_embed_full_text(embed)
                if any(kw in full_text for kw in self.ACTIVITY_EMBED_KEYWORDS):
                    return True

        # 4. Бот + interaction (кнопка "Запустить")
        if message.author.bot and message.interaction is not None:
            return True

        # 5. Бот + embed + компоненты (кнопки) — Activity-игры всегда имеют кнопку
        if message.author.bot and message.components and message.embeds:
            return True

        # 6. Не-default сообщение с ключевыми словами
        if message.type != discord.MessageType.default:
            content_lower = (message.content or "").lower()
            if any(kw in content_lower for kw in self.ACTIVITY_CONTENT_KEYWORDS):
                return True

        # 7. Любое сообщение с ключевыми словами + бот/упоминание
        content_lower = (message.content or "").lower()
        if any(kw in content_lower for kw in self.ACTIVITY_CONTENT_KEYWORDS):
            if message.author.bot or message.mentions:
                return True

        return False

    @staticmethod
    def _get_activity_user_id(message: discord.Message) -> Optional[int]:
        """Определяет ID пользователя, запустившего активность."""
        if message.interaction is not None:
            return message.interaction.user.id
        if message.type != discord.MessageType.default:
            return message.author.id
        if message.mentions:
            return message.mentions[0].id
        return None

    # ------------------------------------------------------------------
    # on_message — трекаем в реальном времени
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        # Подробный лог ВСЕХ бот-сообщений (помогает понять структуру)
        if message.author.bot:
            content_preview = (message.content or "")[:120]
            embed_info = []
            for emb in message.embeds:
                author_name = emb.author.name if emb.author else None
                embed_info.append(
                    f"title={emb.title!r}, desc={emb.description!r}, "
                    f"author={author_name!r}"
                )
            embed_str = "; ".join(embed_info) if embed_info else "нет"
            logger.info(
                "[ActivityCleanup] БОТ-MSG: name=%s, type=%s (val=%d), "
                "content=%r, embeds=[%s], components=%d, interaction=%s",
                message.author.name,
                message.type.name,
                message.type.value,
                content_preview,
                embed_str,
                len(message.components),
                message.interaction is not None,
            )

        # Лог системных сообщений (не от ботов)
        if message.type != discord.MessageType.default and not message.author.bot:
            logger.info(
                "[ActivityCleanup] SYS-MSG: author=%s, type=%s (val=%d), "
                "content=%r",
                message.author.name,
                message.type.name,
                message.type.value,
                (message.content or "")[:120],
            )

        if not self._is_activity_message(message):
            return

        self._track_message(message)

    # ------------------------------------------------------------------
    # Трекинг сообщения
    # ------------------------------------------------------------------
    def _track_message(self, message: discord.Message) -> None:
        """Добавляет сообщение в отслеживаемые."""
        user_id = self._get_activity_user_id(message)
        activity_name = self._extract_activity_name(message)
        key = user_id or 0

        # Проверяем, не трекается ли уже это сообщение
        if key in self._tracked:
            if any(e["message_id"] == message.id for e in self._tracked[key]):
                return

        if key not in self._tracked:
            self._tracked[key] = []

        self._tracked[key].append(
            {
                "message": message,
                "message_id": message.id,
                "channel_id": message.channel.id,
                "activity_name": activity_name,
                "tracked_at": datetime.now(tz=timezone.utc),
            }
        )

        self._activity_channels.add(message.channel.id)

        logger.info(
            "[ActivityCleanup] ✅ ОТСЛЕЖИВАЮ: msg_id=%d, type=%s, "
            "user=%d, activity=%r, channel=#%s",
            message.id,
            message.type.name,
            key,
            activity_name,
            message.channel.name,
        )

    # ------------------------------------------------------------------
    # on_presence_update — ловим завершение активности
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_presence_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        # Все активности (не только playing — Activities могут быть любого типа)
        before_activities = {a.name for a in before.activities if a.name}
        after_activities = {a.name for a in after.activities if a.name}

        stopped = before_activities - after_activities
        if not stopped:
            return

        if before.id not in self._tracked:
            return

        logger.info(
            "[ActivityCleanup] %s завершил: %s",
            before.display_name,
            ", ".join(stopped),
        )

        await asyncio.sleep(2)
        await self._delete_user_activity_messages(before.id, stopped)

    # ------------------------------------------------------------------
    # on_voice_state_update — удаляем при выходе из войса + сканируем канал
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
            logger.info(
                "[ActivityCleanup] %s вышел из войса (#%s)",
                member.display_name,
                before.channel.name,
            )

            # 1. Удаляем отслеженные сообщения
            if member.id in self._tracked:
                await self._delete_user_activity_messages(member.id)

            # 2. Фоллбэк: сканируем известные каналы на случай,
            #    если on_message не затрекал сообщения
            await self._scan_and_clean(member.guild, member.id)

    # ------------------------------------------------------------------
    # Сканирование каналов (фоллбэк, если on_message не поймал)
    # ------------------------------------------------------------------
    async def _scan_and_clean(
        self, guild: discord.Guild, user_id: int
    ) -> None:
        """Сканирует известные каналы и удаляет activity-сообщения пользователя."""
        if not self._activity_channels:
            # Если ни один канал ещё не известен — сканируем все текстовые
            channels_to_scan = [
                ch
                for ch in guild.text_channels
                if ch.permissions_for(guild.me).read_message_history
            ]
        else:
            channels_to_scan = [
                guild.get_channel(ch_id)
                for ch_id in self._activity_channels
                if guild.get_channel(ch_id) is not None
            ]

        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=2)
        total_deleted = 0

        for channel in channels_to_scan:
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                async for msg in channel.history(limit=50, after=cutoff):
                    if not self._is_activity_message(msg):
                        continue

                    msg_user = self._get_activity_user_id(msg)
                    if msg_user != user_id and msg_user is not None:
                        continue

                    try:
                        await msg.delete()
                        total_deleted += 1
                    except discord.NotFound:
                        total_deleted += 1
                    except discord.Forbidden:
                        logger.warning(
                            "[ActivityCleanup] Нет прав удалить msg_id=%d "
                            "в #%s",
                            msg.id,
                            channel.name,
                        )
                    except Exception as exc:
                        logger.error(
                            "[ActivityCleanup] Ошибка удаления при "
                            "сканировании: %s",
                            exc,
                        )
            except Exception as exc:
                logger.error(
                    "[ActivityCleanup] Ошибка сканирования #%s: %s",
                    channel.name,
                    exc,
                )

        if total_deleted > 0:
            logger.info(
                "[ActivityCleanup] 🔍 Сканирование: удалено %d сообщений "
                "(user=%d)",
                total_deleted,
                user_id,
            )

    # ------------------------------------------------------------------
    # Периодическая проверка: каждые 2 мин проверяем, закончились ли активности
    # ------------------------------------------------------------------
    @tasks.loop(minutes=2)
    async def _check_ended_activities(self) -> None:
        """Если у отслеживаемого пользователя нет активностей и он не
        в войсе — удаляем его сообщения и сканируем каналы."""
        if not self._tracked:
            return

        for user_id in list(self._tracked.keys()):
            if user_id == 0:
                continue

            # Ищем member в любом гильдии
            member: Optional[discord.Member] = None
            guild: Optional[discord.Guild] = None
            for g in self.bot.guilds:
                m = g.get_member(user_id)
                if m is not None:
                    member = m
                    guild = g
                    break

            if member is None:
                continue

            has_activity = bool(member.activities)
            in_voice = (
                member.voice is not None and member.voice.channel is not None
            )

            if not has_activity and not in_voice:
                logger.info(
                    "[ActivityCleanup] ⏰ %s неактивен (нет activities, "
                    "не в войсе), удаляю сообщения",
                    member.display_name,
                )
                await self._delete_user_activity_messages(user_id)
                await self._scan_and_clean(guild, user_id)

    @_check_ended_activities.before_loop
    async def _before_check_ended(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Удаление отслеженных сообщений
    # ------------------------------------------------------------------
    async def _delete_user_activity_messages(
        self,
        user_id: int,
        stopped_activities: Optional[set[str]] = None,
    ) -> None:
        """Удаляет отслеженные сообщения об активностях пользователя."""
        entries = self._tracked.get(user_id, [])
        if not entries:
            return

        remaining: list[dict] = []
        deleted_count = 0

        for entry in entries:
            should_delete = False

            if stopped_activities is None:
                should_delete = True
            else:
                activity_name = entry.get("activity_name") or ""
                for stopped in stopped_activities:
                    if (
                        stopped.lower() in activity_name.lower()
                        or activity_name.lower() in stopped.lower()
                    ):
                        should_delete = True
                        break
                # Если имя не определено — удаляем на всякий случай
                if not activity_name:
                    should_delete = True

            if should_delete:
                msg = entry["message"]
                try:
                    await msg.delete()
                    deleted_count += 1
                except discord.NotFound:
                    deleted_count += 1  # Уже удалено
                except discord.Forbidden:
                    logger.warning(
                        "[ActivityCleanup] Нет прав удалить msg_id=%d в #%s",
                        msg.id,
                        msg.channel.name,
                    )
                except Exception as exc:
                    logger.error(
                        "[ActivityCleanup] Ошибка удаления: %s", exc
                    )
            else:
                remaining.append(entry)

        if remaining:
            self._tracked[user_id] = remaining
        elif user_id in self._tracked:
            del self._tracked[user_id]

        if deleted_count > 0:
            logger.info(
                "[ActivityCleanup] 🗑️ Удалено %d отслеженных сообщений "
                "(user=%d)",
                deleted_count,
                user_id,
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
                e
                for e in self._tracked[uid]
                if e["message"].created_at > cutoff
            ]
            cleaned += original - len(self._tracked[uid])
            if not self._tracked[uid]:
                del self._tracked[uid]

        if cleaned > 0:
            logger.info(
                "[ActivityCleanup] Очистил %d устаревших записей", cleaned
            )

    @_cleanup_stale.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCleanup(bot))
