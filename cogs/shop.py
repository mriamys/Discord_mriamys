import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.db import db
from config import COLOR_MAIN, COLOR_SUCCESS, COLOR_ERROR

# Информация о товарах в Магазине Рофлов
SHOP_ITEMS = {
    "nickname": {"name": "🏷️ Погоняло", "price": 1000, "desc": "Сменить ник любому участнику на 24 часа. (Пока реализована механика списания)"},
    "fake_status": {"name": "🎭 Фейковый статус", "price": 500, "desc": "Добавляет любую приписку или эмодзи к нику."},
    "bunker": {"name": "🏰 Личный бункер", "price": 2000, "desc": "Создает приватный текстовый канал только для тебя на 1 час."},
    "shut_up": {"name": "🤐 Заткнись!", "price": 5000, "desc": "Выдает мут выбранному человеку на 30 секунд. Дорого и больно!"}
}

class ShopView(View):
    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx
        
        # Динамически создаем кнопки для каждого товара
        for item_id, item_data in SHOP_ITEMS.items():
            button = Button(label=f"{item_data['name']} ({item_data['price']} 🪙)", style=discord.ButtonStyle.secondary, custom_id=item_id)
            button.callback = self.make_callback(item_id, item_data)
            self.add_item(button)

    def make_callback(self, item_id, item_data):
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.ctx.author.id:
                await interaction.response.send_message("Это не твой магазин!", ephemeral=True)
                return
                
            user_data = await db.get_user(str(interaction.user.id))
            balance = user_data.get("vibecoins", 0)
            price = item_data["price"]
            
            if balance < price:
                await interaction.response.send_message(f"❌ Не хватает **VibeКоинов**! У тебя {balance}/{price} 🪙", ephemeral=True)
                return
                
            # Списываем баланс
            new_balance = balance - price
            await db.update_user(str(interaction.user.id), vibecoins=new_balance)
            
            # Логика покупки (здесь просто вывод успешной покупки, механики надо детализировать отдельно)
            await interaction.response.send_message(f"✅ Ты успешно купил **{item_data['name']}**!\nОстаток: {new_balance} 🪙\n_Обратись к администратору или используй спец-команду для активации._", ephemeral=True)
            
        return button_callback

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop", description="Открыть Магазин Рофлов")
    async def shop(self, ctx):
        user_data = await db.get_user(str(ctx.author.id))
        balance = user_data.get("vibecoins", 0)
        
        embed = discord.Embed(
            title="🛒 Магазин Рофлов", 
            description=f"Твой баланс: **{balance} 🪙 VibeКоинов**\nВыбирай покупочки с умом!\n\n",
            color=COLOR_MAIN
        )
        
        for item in SHOP_ITEMS.values():
            embed.add_field(name=f"{item['name']} — {item['price']} 🪙", value=item['desc'], inline=False)
            
        view = ShopView(ctx)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Shop(bot))
