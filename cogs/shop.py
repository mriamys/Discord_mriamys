import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.db import db
from config import COLOR_MAIN, COLOR_SUCCESS, COLOR_ERROR

# Информация о товарах в Магазине Рофлов
SHOP_ITEMS = {
    "nickname": {"name": "🏷️ Погоняло", "price": 1000, "desc": "Сменить ник любому участнику на 1 час. (Передача валюты)"},
    "fake_status": {"name": "🎭 Фейковый статус", "price": 500, "desc": "Добавляет любую приписку или эмодзи к нику на 1 час."},
    "bunker": {"name": "🏰 Личный бункер", "price": 2000, "desc": "Создает приватный текстовый канал только для тебя на 1 час."},
    "shut_up": {"name": "🤐 Заткнись!", "price": 5000, "desc": "Выдает мут выбранному человеку на 30 секунд. Дорого и больно!"},
    "test_role": {"name": "💎 VIP Роль", "price": 15000, "desc": "Эксклюзивная роль VIP.", "role_name": "VIP"}
}

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # Динамически создаем кнопки для каждого товара
        for item_id, item_data in SHOP_ITEMS.items():
            button = Button(label=f"{item_data['name']} ({item_data['price']} 🪙)", style=discord.ButtonStyle.secondary, custom_id=f"shop_{item_id}")
            button.callback = self.make_callback(item_id, item_data)
            self.add_item(button)

    def make_callback(self, item_id, item_data):
        async def button_callback(interaction: discord.Interaction):
            user_data = await db.get_user(str(interaction.user.id))
            balance = user_data.get("vibecoins", 0)
            price = item_data["price"]
            
            if balance < price:
                await interaction.response.send_message(f"❌ Не хватает **VibeКоинов**! У тебя {balance}/{price} 🪙", ephemeral=True)
                return
                
            # Списываем баланс и учитываем траты
            new_balance = balance - price
            shop_spent = user_data.get("shop_spent", 0) + price
            nick_changes = user_data.get("nick_changes", 0)
            if item_id in ['nickname', 'fake_status']:
                nick_changes += 1
                
            await db.update_user(str(interaction.user.id), vibecoins=new_balance, shop_spent=shop_spent, nick_changes=nick_changes)
            interaction.client.dispatch("shop_purchased", interaction.user, item_id, shop_spent, nick_changes)
            
            # Логика выдачи роли
            given_msg = ""
            if "role_name" in item_data:
                role = discord.utils.get(interaction.guild.roles, name=item_data["role_name"])
                if role:
                    try:
                        await interaction.user.add_roles(role)
                        given_msg = f"\nТебе выдана роль: {role.mention} 🎉"
                    except Exception as e:
                        given_msg = "\n⚠️ Возникла ошибка при выдаче роли (возможно, бот находится ниже роли в иерархии)."
                else:
                    given_msg = f"\n⚠️ Роль `{item_data['role_name']}` не найдена на сервере. Обратись к админам!"
            
            # Логика покупки (здесь просто вывод успешной покупки)
            await interaction.response.send_message(
                f"✅ Ты успешно купил **{item_data['name']}**!\nОстаток: {new_balance} 🪙{given_msg}\n_Если это товар-кастом (бэйдж, ник), обратись к администратору._", 
                ephemeral=True
            )
            
        return button_callback

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop", description="Узнать свой баланс VibeКоинов")
    async def shop(self, ctx):
        user_data = await db.get_user(str(ctx.author.id))
        balance = user_data.get("vibecoins", 0)
        await ctx.send(f"🪙 Твой баланс: **{balance} VibeКоинов**\nЗагляни в канал покупок, чтобы потратить их!", ephemeral=True)

    @commands.command(name="setup_shop", aliases=["setup_store", "создать_магазин", "магазин_сетап", "магаз", "магазин"])
    @commands.has_permissions(administrator=True)
    async def setup_shop(self, ctx):
        embed = discord.Embed(
            title="🛒 Магазин Рофлов", 
            description="Здесь ты можешь потратить свои **VibeКоины** на крутые фичи!\nНажми на кнопку ниже, чтобы купить товар.",
            color=COLOR_MAIN
        )
        
        # Добавляем красивую гифку-баннер для магазина
        embed.set_image(url="https://media.giphy.com/media/xUPGGw7jzcqeMw5dI8/giphy.gif")
        
        for item in SHOP_ITEMS.values():
            embed.add_field(name=f"{item['name']} — {item['price']} 🪙", value=item['desc'], inline=False)
            
        view = ShopView()
        await ctx.send(embed=embed, view=view)
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(Shop(bot))
