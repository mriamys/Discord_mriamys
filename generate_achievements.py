# -*- coding: utf-8 -*-
import json
import math

achievements = {
    # Messages
    "first_msg": {"name": "Первый шаг в Бездну", "desc": "Написать 1 сообщение.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3c6.png", "emoji": "🏆", "rarity": "common"},
    "msg_10": {"name": "Свежая кровь", "desc": "Написать 10 сообщений. Ты только начал.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1fae8.png", "emoji": "🩸", "rarity": "common"},
    "msg_50": {"name": "Разогрев пальцев", "desc": "Написать 50 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f44d.png", "emoji": "👍", "rarity": "common"},
    "msg_100": {"name": "Скуфятана", "desc": "Написать 100 сообщений. Пальцы только разогрелись.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f913.png", "emoji": "🤓", "rarity": "common"},
    "msg_250": {"name": "Местный спамер", "desc": "Написать 250 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4dd.png", "emoji": "📝", "rarity": "common"},
    "msg_500": {"name": "Травитель баек", "desc": "Написать 500 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f5e3.png", "emoji": "🗣️", "rarity": "rare"},
    "msg_1000": {"name": "Клавиатурный токсик", "desc": "Написать 1,000 сообщений. Трава давно не трогана.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f92c.png", "emoji": "🤬", "rarity": "rare"},
    "msg_2500": {"name": "Непробиваемый", "desc": "Написать 2,500 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6e1.png", "emoji": "🛡️", "rarity": "rare"},
    "msg_5000": {"name": "Писатель романов", "desc": "Написать 5,000 сообщений. Лев Толстой отдыхает.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4d6.png", "emoji": "📖", "rarity": "epic"},
    "keyboard_rambo": {"name": "Клавиатурный Рэмбо", "desc": "Написать 10,000 сообщений в чатах. Клавиатура стерта до дыр.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4ac.png", "emoji": "⌨️", "rarity": "epic"},
    "msg_20000": {"name": "Без тормозов", "desc": "Написать 20,000 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f680.png", "emoji": "🚀", "rarity": "epic"},
    "msg_50000": {"name": "Забаньте его", "desc": "Спанч Боб со своими 50,000 сообщений...", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6ab.png", "emoji": "🚫", "rarity": "legendary"},
    "msg_100000": {"name": "Нейросеть", "desc": "Написать 100,000 сообщений. Ты точно не бот?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f916.png", "emoji": "🤖", "rarity": "legendary"},
    "msg_250000": {"name": "Дискорд-шизоид", "desc": "Написать 250,000 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f92a.png", "emoji": "🤪", "rarity": "legendary"},
    "msg_500000": {"name": "Библиотека Ватикана", "desc": "Написать 500,000 сообщений.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3db.png", "emoji": "🏛️", "rarity": "mythic"},
    "msg_1000000": {"name": "Вечный Лог", "desc": "Написать 1,000,000 сообщений. Мемы сломлены.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4dc.png", "emoji": "📜", "rarity": "mythic"},

    # Voice (in seconds logic inside cog, here is meta)
    "voice_10m": {"name": "Проверка микро", "desc": "Посидеть 10 минут в голосе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3a4.png", "emoji": "🎙️", "rarity": "common"},
    "voice_1h": {"name": "Ракушка", "desc": "Насидеть первый час в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f41a.png", "emoji": "🐚", "rarity": "common"},
    "chair_glued": {"name": "Сросся со стулом", "desc": "5 часов в голосе суммарно.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1fa91.png", "emoji": "🪑", "rarity": "rare"},
    "voice_10h": {"name": "Диктор с радио", "desc": "10 часов войса.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4fb.png", "emoji": "📻", "rarity": "rare"},
    "voice_24h": {"name": "Сутки на пролет", "desc": "24 часа в дискорде.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31d.png", "emoji": "🌝", "rarity": "rare"},
    "voice_50h": {"name": "Войсовый сталкер", "desc": "50 часов в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f440.png", "emoji": "👀", "rarity": "epic"},
    "voice_100h": {"name": "Дискордный Батя", "desc": "100 часов в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f468.png", "emoji": "👨", "rarity": "epic"},
    "voice_250h": {"name": "Эхолокатор", "desc": "250 часов в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f987.png", "emoji": "🦇", "rarity": "legendary"},
    "voice_500h": {"name": "Страж Канала", "desc": "500 часов в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f5ff.png", "emoji": "🗿", "rarity": "legendary"},
    "voice_1000h": {"name": "Квартирант", "desc": "1,000 часов в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3e0.png", "emoji": "🏠", "rarity": "legendary"},
    "voice_5000h": {"name": "Голос Свыше", "desc": "5,000 часов. Единое целое с матрицей.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f324.png", "emoji": "🌤️", "rarity": "mythic"},

    # Shop Spent
    "store_100": {"name": "Первая покупка", "desc": "Потратить 100 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b8.png", "emoji": "💸", "rarity": "common"},
    "store_500": {"name": "Транжира", "desc": "Потратить 500 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b0.png", "emoji": "💰", "rarity": "common"},
    "store_1000": {"name": "Гой прогрев", "desc": "Потратил 1,000 VibeКоинов в магазине.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6d2.png", "emoji": "🛒", "rarity": "common"},
    "ludoman": {"name": "Лудоман", "desc": "Потратить 5,000 VibeКоинов в Магазине.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3b0.png", "emoji": "🎰", "rarity": "rare"},
    "store_20000": {"name": "Мамонт-дознаватель", "desc": "Потратить целых 20,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9a3.png", "emoji": "🦣", "rarity": "epic"},
    "store_50000": {"name": "Шопоголик", "desc": "Потратить 50,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6cd.png", "emoji": "🛍️", "rarity": "epic"},
    "store_100000": {"name": "Спонсор Кринжа", "desc": "Остапить 100,000 VibeКоинов в магазине.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b5.png", "emoji": "💵", "rarity": "legendary"},
    "store_500000": {"name": "Олигарх", "desc": "Потратить 500,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b1.png", "emoji": "💱", "rarity": "legendary"},
    "store_1000000": {"name": "Владелец сервера", "desc": "Потратил 1,000,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3e2.png", "emoji": "🏢", "rarity": "mythic"},

    # Balances
    "businessman": {"name": "Мамкин Бизнесмен", "desc": "Накопить баланс 10,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4bc.png", "emoji": "💼", "rarity": "rare"},
    "crypto_hamster": {"name": "Криптохомяк", "desc": "Накопить баланс 50,000 VibeКоинов. Ты тапал?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f439.png", "emoji": "🐹", "rarity": "epic"},
    "bal_100000": {"name": "Скрудж МакДак", "desc": "Накопить 100,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f911.png", "emoji": "🤑", "rarity": "epic"},
    "bal_500000": {"name": "Инфоцыган", "desc": "Накопить 500,000 VibeКоинов. Научишь?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4b8.png", "emoji": "💸", "rarity": "legendary"},
    "bal_1000000": {"name": "Форбс", "desc": "1,000,000 VibeКоинов.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48e.png", "emoji": "💎", "rarity": "mythic"},

    # Levels
    "level_1": {"name": "Пробуждение", "desc": "Достичь 1 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f476.png", "emoji": "👶", "rarity": "common"},
    "level_5": {"name": "Школьник", "desc": "Достичь 5 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f392.png", "emoji": "🎒", "rarity": "common"},
    "level_10": {"name": "Первая Кровь", "desc": "Достичь 10 уровня. Ты еще только учишься ходить.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1fae8.png", "emoji": "🩸", "rarity": "common"},
    "level_20": {"name": "Почти взрослый", "desc": "Достичь 20 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f37b.png", "emoji": "🍻", "rarity": "rare"},
    "level_30": {"name": "Опытный", "desc": "Достичь 30 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9d4.png", "emoji": "🧔", "rarity": "rare"},
    "level_40": {"name": "Кризис среднего возраста", "desc": "Достичь 40 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f697.png", "emoji": "🚗", "rarity": "epic"},
    "level_50": {"name": "Экватор Кринжа", "desc": "Взять 50 уровень (Гигачад). Полпути к Абсолюту.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f5ff.png", "emoji": "🗿", "rarity": "epic"},
    "level_60": {"name": "Дед-Инсайд", "desc": "Достичь 60 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f474.png", "emoji": "👴", "rarity": "epic"},
    "level_69": {"name": "Nice.", "desc": "Достичь 69 уровня. Хи-хи-хи.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f346.png", "emoji": "🍆", "rarity": "epic"},
    "level_75": {"name": "Магистр", "desc": "Достичь 75 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9d9.png", "emoji": "🧙", "rarity": "legendary"},
    "level_80": {"name": "Архимаг", "desc": "Достичь 80 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2728.png", "emoji": "✨", "rarity": "legendary"},
    "level_90": {"name": "Полубог", "desc": "Достичь 90 уровня.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26a1.png", "emoji": "⚡", "rarity": "legendary"},
    "level_99": {"name": "Один шаг", "desc": "Достичь 99 уровня. Только не сдавайся.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/23f1.png", "emoji": "⏱️", "rarity": "legendary"},
    "absolute": {"name": "Абсолют", "desc": "Получить Абсолют ранг (100 лвл). Игра пройдена.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f30c.png", "emoji": "🌌", "rarity": "mythic"},

    # Streaks
    "streak_3": {"name": "Оно еще живо", "desc": "Заработать стрик 3🔥.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9df.png", "emoji": "🧟", "rarity": "common"},
    "streak_5": {"name": "Пятидневка", "desc": "Стрик 5🔥. Почти рабочая неделя.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4bc.png", "emoji": "💼", "rarity": "rare"},
    "no_lifer": {"name": "Безработный", "desc": "Стрик 7🔥.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6cf.png", "emoji": "🛋️", "rarity": "rare"},
    "streak_10": {"name": "Десяточка", "desc": "Стрик 10🔥.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f51f.png", "emoji": "🔟", "rarity": "rare"},
    "streak_14": {"name": "Скинул кандалы", "desc": "Стрик 14🔥. Полмесяца без личной жизни.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/26d3.png", "emoji": "⛓️", "rarity": "epic"},
    "streak_21": {"name": "Формирование привычки", "desc": "Стрик 21🔥. Привычка формируется за 21 день.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e0.png", "emoji": "🧠", "rarity": "epic"},
    "streak_30": {"name": "Айтишник Куколд", "desc": "Стрик 30🔥. Прошёл месяц в войсе.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4bb.png", "emoji": "💻", "rarity": "epic"},
    "streak_50": {"name": "Полвека Дискорда", "desc": "Стрик 50🔥. Ты солнце вообще видел?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2600.png", "emoji": "☀️", "rarity": "legendary"},
    "streak_69": {"name": "Стрик Nice.", "desc": "Стрик 69🔥.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4a6.png", "emoji": "💦", "rarity": "legendary"},
    "streak_100": {"name": "Ветеран Войса", "desc": "Стрик 100🔥. Это вообще легально?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3c5.png", "emoji": "🏅", "rarity": "mythic"},
    "streak_365": {"name": "Год без улицы", "desc": "Стрик 365🔥. Ты погубил год своей жизни.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f38a.png", "emoji": "🎊", "rarity": "mythic"},

    # Nicknames & Specific
    "nick_1": {"name": "Смена личности", "desc": "Первый раз сменил ник.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3ad.png", "emoji": "🎭", "rarity": "common"},
    "nick_5": {"name": "Ищущий себя", "desc": "Сменил ник 5 раз.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f50d.png", "emoji": "🔍", "rarity": "common"},
    "jester": {"name": "Главный Шут", "desc": "Сменил ник 10 раз.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f921.png", "emoji": "🤡", "rarity": "rare"},
    "nick_15": {"name": "Под прикрытием", "desc": "Сменил ник 15 раз.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f575.png", "emoji": "🕵️", "rarity": "rare"},
    "tilting_player": {"name": "Тильтующий игрок", "desc": "Переименовать себя 20 раз.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f643.png", "emoji": "🙃", "rarity": "epic"},
    "nick_50": {"name": "Шизофрения", "desc": "Сменил ник 50 раз. Кто ты сегодня?", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e0.png", "emoji": "🧠", "rarity": "legendary"},
    "nick_100": {"name": "Многоликий", "desc": "Сменил ник 100 раз.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f465.png", "emoji": "👥", "rarity": "mythic"},

    "cringe_prisoner": {"name": "Узник Кринжа", "desc": "Получить свой первый мут через кнопку 'Заткнись!'", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f480.png", "emoji": "💀", "rarity": "epic"},
    "fake_status": {"name": "Врун", "desc": "Купил фейковый статус.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f925.png", "emoji": "🤥", "rarity": "rare"},
    "bunker": {"name": "Мизантроп", "desc": "Купил личный бункер.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f573.png", "emoji": "🕳️", "rarity": "rare"},
    
    # Meme Role Interactions
    "ach_woman": {"name": "Посидел с женщиной", "desc": "Зайти в войс, где есть девушка. Миссия выполнена.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f469.png", "emoji": "👩", "rarity": "rare"},
    "ach_woman_reply": {"name": "Заговорил с женщиной", "desc": "Ответил девушке в чате. Теперь ты альфа.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f48c.png", "emoji": "💌", "rarity": "epic"},
    "ach_skuf": {"name": "Подземелье Скуфа", "desc": "Находиться в войсе со скуфом. Осторожно, танцы!", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3ba.png", "emoji": "🎺", "rarity": "common"},
    "ach_admin": {"name": "Соприкосновение с властью", "desc": "Попасть в один войс с администратором.", "icon_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f6e1.png", "emoji": "🛡️", "rarity": "epic"}
}

# The dictionaries for the cog logic:
msg_thresholds = {
    1: 'first_msg', 10: 'msg_10', 50: 'msg_50', 100: 'msg_100', 250: 'msg_250', 
    500: 'msg_500', 1000: 'msg_1000', 2500: 'msg_2500', 5000: 'msg_5000', 
    10000: 'keyboard_rambo', 20000: 'msg_20000', 50000: 'msg_50000', 
    100000: 'msg_100000', 250000: 'msg_250000', 500000: 'msg_500000', 
    1000000: 'msg_1000000'
}

voice_thresholds = {
    600: 'voice_10m', 3600: 'voice_1h', 18000: 'chair_glued',
    36000: 'voice_10h', 86400: 'voice_24h', 180000: 'voice_50h',
    360000: 'voice_100h', 900000: 'voice_250h', 1800000: 'voice_500h',
    3600000: 'voice_1000h', 18000000: 'voice_5000h'
}

shop_thresholds = {
    100: 'store_100', 500: 'store_500', 1000: 'store_1000', 
    5000: 'ludoman', 20000: 'store_20000', 50000: 'store_50000',
    100000: 'store_100000', 500000: 'store_500000', 1000000: 'store_1000000'
}

bal_thresholds = {
    10000: 'businessman', 50000: 'crypto_hamster', 100000: 'bal_100000',
    500000: 'bal_500000', 1000000: 'bal_1000000'
}

nick_thresholds = {
    1: 'nick_1', 5: 'nick_5', 10: 'jester', 15: 'nick_15', 20: 'tilting_player',
    50: 'nick_50', 100: 'nick_100'
}

streak_thresholds = {
    3: 'streak_3', 5: 'streak_5', 7: 'no_lifer', 10: 'streak_10',
    14: 'streak_14', 21: 'streak_21', 30: 'streak_30', 50: 'streak_50',
    69: 'streak_69', 100: 'streak_100', 365: 'streak_365'
}

# Formula reverse: xp = (level / 0.023)^2
def get_xp(lvl):
    return int((lvl / 0.023) ** 2)

level_achievements = {
    1: 'level_1', 5: 'level_5', 10: 'level_10', 20: 'level_20',
    30: 'level_30', 40: 'level_40', 50: 'level_50', 60: 'level_60',
    69: 'level_69', 75: 'level_75', 80: 'level_80', 90: 'level_90',
    99: 'level_99', 100: 'absolute'
}

level_thresholds = {get_xp(lvl): ach_name for lvl, ach_name in level_achievements.items()}

cog_code = f'''import discord
from discord.ext import commands
from utils.db import db
from utils.achievements_data import ACHIEVEMENTS
import logging

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.msg_thresholds = {msg_thresholds}
        self.voice_thresholds = {voice_thresholds}
        self.shop_thresholds = {shop_thresholds}
        self.bal_thresholds = {bal_thresholds}
        self.nick_thresholds = {nick_thresholds}
        self.streak_thresholds = {streak_thresholds}
        self.level_thresholds = {level_thresholds}

    async def grant_achievement(self, member: discord.Member, achievement_id: str):
        if achievement_id not in ACHIEVEMENTS:
            return
            
        success = await db.add_achievement(str(member.id), achievement_id)
        if success:
            ach_data = ACHIEVEMENTS[achievement_id]
            rank_channel = discord.utils.get(member.guild.text_channels, name="📜┃ранг")
            embed = discord.Embed(
                title=f"🏆 ПОЛУЧЕНО ДОСТИЖЕНИЕ: {{ach_data['name']}}!",
                description=f"**{{ach_data['desc']}}**\\n\\nМожешь проверить свою коллекцию в `!profile`!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=ach_data['icon_url'])
            
            try:
                if rank_channel:
                    await rank_channel.send(content=member.mention, embed=embed)
                else:
                    await member.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to send achievement msg: {{e}}")

    @commands.Cog.listener()
    async def on_message_sent(self, member, msg_count):
        # We need to check if they passed specific milestones exactly, or just hit >= threshold?
        # Typically the db counter goes 1 by 1.
        if msg_count in self.msg_thresholds:
            await self.grant_achievement(member, self.msg_thresholds[msg_count])

    @commands.Cog.listener()
    async def on_voice_time_updated(self, member, total_voice_time):
        # voice time might skip exact seconds if bulk updated.
        for threshold, ach_id in self.voice_thresholds.items():
            if total_voice_time >= threshold:
                await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_shop_purchased(self, member, item_id, shop_spent, nick_changes):
        # shop_spent can skip amounts
        for threshold, ach_id in self.shop_thresholds.items():
            if shop_spent >= threshold:
                await self.grant_achievement(member, ach_id)
                
        # nick changes can skip if multiple bought, but usually goes 1 by 1.
        for threshold, ach_id in self.nick_thresholds.items():
            if nick_changes >= threshold:
                await self.grant_achievement(member, ach_id)
                
        if item_id == "shut_up":
            await self.grant_achievement(member, "cringe_prisoner")
        elif item_id == "fake_status":
            await self.grant_achievement(member, "fake_status")
        elif item_id == "bunker":
            await self.grant_achievement(member, "bunker")

    @commands.Cog.listener()
    async def on_xp_updated(self, member, new_xp):
        # xp skips thresholds easily
        for threshold, ach_id in self.level_thresholds.items():
            if new_xp >= threshold:
                await self.grant_achievement(member, ach_id)
            
        user_data = await db.get_user(str(member.id))
        vibecoins = user_data.get('vibecoins', 0)
        
        for threshold, ach_id in self.bal_thresholds.items():
            if vibecoins >= threshold:
                await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_streak_updated(self, member, new_streak):
        if new_streak in self.streak_thresholds:
            await self.grant_achievement(member, self.streak_thresholds[new_streak])

    @commands.Cog.listener()
    async def on_voice_role_interaction(self, member, channel_members):
        role_keywords = {{
            "девушка": "ach_woman",
            "тяночка": "ach_woman",
            "woman": "ach_woman",
            "женщина": "ach_woman",
            "скуф": "ach_skuf",
            "админ": "ach_admin",
            "создатель": "ach_admin",
            "admin": "ach_admin"
        }}
        
        for m in channel_members:
            if m.id == member.id or m.bot:
                continue
                
            if hasattr(m, 'roles'):
                for role in m.roles:
                    role_name_lo = role.name.lower()
                    for kw, ach_id in role_keywords.items():
                        if kw in role_name_lo:
                            await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_message_reply_interaction(self, member, replied_to_member):
        role_keywords = {{
            "девушка": "ach_woman_reply",
            "тяночка": "ach_woman_reply",
            "женщина": "ach_woman_reply"
        }}
        if hasattr(replied_to_member, 'roles'):
            for role in replied_to_member.roles:
                role_name_lo = role.name.lower()
                for kw, ach_id in role_keywords.items():
                    if kw in role_name_lo:
                        await self.grant_achievement(member, ach_id)

async def setup(bot):
    await bot.add_cog(Achievements(bot))
'''

def run():
    with open("utils/achievements_data.py", "w", encoding="utf-8") as f:
        f.write("ACHIEVEMENTS = \\\n")
        f.write(json.dumps(achievements, indent=4, ensure_ascii=False))
        f.write("\n")
        
    with open("cogs/achievements.py", "w", encoding="utf-8") as f:
        f.write(cog_code)

if __name__ == "__main__":
    run()
    print("Files successfully generated.")
