import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
from utils.db import db

SUITS = ['♠️', '♣️', '❤️', '♦️']
RANKS = {
    2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10',
    11: 'Ace', 12: 'Jack', 13: 'Queen', 14: 'King'
}

def format_hand(hand):
    res = []
    for rank, suit in hand:
        name = RANKS.get(rank, str(rank))
        res.append(f"`{name} {suit}`")
    return " ".join(res)

def calculate_score(hand):
    score, aces = 0, 0
    for rank, _ in hand:
        if rank == 11:
            aces += 1
            score += 11
        elif rank >= 12:
            score += 10
        else:
            score += rank
    
    # Запоминаем изначальный счет с Ace=11
    original_score = score
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    
    # Если счет изменился из-за тузов, значит у нас есть "мягкий" туз
    # Мы показываем "мягкий" счет только если он <= 21
    soft = original_score != score and score <= 21
    return score, soft, original_score

class BlackjackGame:
    def __init__(self, bet):
        self.bet = bet
        self.deck = []
        for suit in SUITS:
            for rank in range(2, 15): self.deck.append((rank, suit))
        random.shuffle(self.deck)
        self.player_hand = [self.draw(), self.draw()]
        self.dealer_hand = [self.draw(), self.draw()]
        self.status = "playing"
    def draw(self): return self.deck.pop()
    def get_score(self, hand):
        s, _, _ = calculate_score(hand)
        return s

class BlackjackBetModal(discord.ui.Modal):
    def __init__(self, bot, game_type, target=None):
        super().__init__(title="🎰 Введите вашу ставку")
        self.bot, self.game_type, self.target = bot, game_type, target
        self.bet_input = discord.ui.TextInput(label="Сумма ставки", placeholder="Например: 1000", min_length=1, max_length=10)
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value)
            if bet < 10: raise ValueError
        except:
            await interaction.response.send_message("❌ Введите корректное число (минимум 10)!", ephemeral=True); return
        
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < bet:
            await interaction.response.send_message("❌ У тебя нет столько коинов!", ephemeral=True); return

        if self.game_type == "solo":
            view = BlackjackView(self.bot, interaction.user, bet)
            await interaction.response.send_message(embed=await view.create_embed(), view=view)
        else:
            from cogs.shop import GameDuelSelectView
            await interaction.response.send_message(f"🃏 Вызываем на дуэль! Ставка: **{bet} 🪙**", view=GameDuelSelectView(self.bot, interaction.user.id, bet, "bj"), ephemeral=True)

class BlackjackBetView(View):
    def __init__(self, bot, game_type):
        super().__init__(timeout=60)
        self.bot, self.game_type = bot, game_type

    @discord.ui.button(label="100", style=discord.ButtonStyle.secondary)
    async def bet_100(self, interaction, button): await self.start(interaction, 100)
    @discord.ui.button(label="500", style=discord.ButtonStyle.secondary)
    async def bet_500(self, interaction, button): await self.start(interaction, 500)
    @discord.ui.button(label="1000", style=discord.ButtonStyle.secondary)
    async def bet_1k(self, interaction, button): await self.start(interaction, 1000)
    @discord.ui.button(label="Своя ставка", style=discord.ButtonStyle.primary)
    async def bet_custom(self, interaction, button): 
        await interaction.response.send_modal(BlackjackBetModal(self.bot, self.game_type))

    async def start(self, interaction, bet):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < bet:
            await interaction.response.send_message("❌ Недостаточно коинов!", ephemeral=True); return
        
        if self.game_type == "solo":
            view = BlackjackView(self.bot, interaction.user, bet)
            await interaction.response.send_message(embed=await view.create_embed(), view=view)
        else:
            from cogs.shop import GameDuelSelectView
            await interaction.response.send_message(f"🃏 Вызываем на дуэль! Ставка: **{bet} 🪙**", view=GameDuelSelectView(self.bot, interaction.user.id, bet, "bj"), ephemeral=True)

class BlackjackView(View):
    def __init__(self, bot, member, bet):
        super().__init__(timeout=60)
        self.bot, self.member, self.bet = bot, member, bet
        self.game = BlackjackGame(bet)
        self.processing = False

    async def create_embed(self):
        user_data = await db.get_user(str(self.member.id))
        balance = user_data.get('vibecoins', 0)
        p_score, p_soft, p_orig = calculate_score(self.game.player_hand)
        
        embed = discord.Embed(title="🃏 БЛЭКДЖЕК (SOLO)", color=0x2b2d31)
        embed.set_author(name=self.member.display_name, icon_url=self.member.display_avatar.url)
        
        # Если туз сейчас считается за 1, но мог бы считаться за 11 (без перебора), показываем оба варианта
        # В нашей реализации s, soft, orig: s - итоговый, orig - со всеми тузами по 11
        # Если s < orig, значит мы уже убавили тузы. 
        # Если orig <= 21, значит у нас "мягкая" рука.
        if p_orig <= 21 and p_orig != p_score:
            score_display = f"{p_orig} / {p_score}"
        else:
            score_display = f"{p_score}"
            
        embed.add_field(name="👤 ВАШИ КАРТЫ", value=f"{format_hand(self.game.player_hand)}\nСчет: **{score_display}**", inline=False)
        
        if self.game.status == "playing":
            d_cards = f"`{RANKS.get(self.game.dealer_hand[0][0])} {self.game.dealer_hand[0][1]}` ` ❓ `"
            embed.add_field(name="🤖 ДИЛЕР", value=f"Карты: {d_cards}\nСчет: **?**", inline=False)
            embed.description = f"💰 Ставка: **{self.bet} 🪙** | Баланс: **{balance:,} 🪙**"
        else:
            d_score, _, _ = calculate_score(self.game.dealer_hand)
            embed.add_field(name="🤖 ДИЛЕР", value=f"Карты: {format_hand(self.game.dealer_hand)}\nСчет: **{d_score}**", inline=False)
            
            if self.game.status == "player_win": 
                embed.description = f"🎉 **ПОБЕДА!**\nВыигрыш: **+{self.bet} 🪙**"; embed.color = 0x57F287
            elif self.game.status == "dealer_win": 
                embed.description = f"💔 **ПОРАЖЕНИЕ.**\nУбыток: **-{self.bet} 🪙**"; embed.color = 0xED4245
            elif self.game.status == "draw": 
                embed.description = f"🤝 **НИЧЬЯ.**\nСтавка сохранена."; embed.color = 0xF1C40F
            elif self.game.status == "bust": 
                embed.description = f"💥 **ПЕРЕБОР!**\nУбыток: **-{self.bet} 🪙**"; embed.color = 0xED4245
                
            embed.set_footer(text=f"Новый баланс: {balance:,} 🪙")
        return embed

    @discord.ui.button(label="Взять (Hit)", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id or self.processing: return
        self.processing = True
        self.game.player_hand.append(self.game.draw())
        p_score, _, _ = calculate_score(self.game.player_hand)
        if p_score > 21:
            self.game.status = "bust"; await self.end_game(interaction)
        else:
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)
            self.processing = False

    @discord.ui.button(label="Стоп (Stand)", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id or self.processing: return
        self.processing = True
        while True:
            d_score, _, _ = calculate_score(self.game.dealer_hand)
            if d_score < 17:
                self.game.dealer_hand.append(self.game.draw())
            else:
                break
        
        p_score, _, _ = calculate_score(self.game.player_hand)
        d_score, _, _ = calculate_score(self.game.dealer_hand)
        
        if d_score > 21 or p_score > d_score: self.game.status = "player_win"
        elif p_score < d_score: self.game.status = "dealer_win"
        else: self.game.status = "draw"
        await self.end_game(interaction)

    async def end_game(self, interaction):
        for child in self.children: child.disabled = True
        user_data = await db.get_user(str(self.member.id))
        
        payout = 0
        if self.game.status == "player_win": 
            multiplier = random.uniform(1.1, 2.5)
            payout = int(self.bet * multiplier)
        elif self.game.status in ["dealer_win", "bust"]: 
            payout = -self.bet
            
        new_balance = max(0, user_data.get('vibecoins', 0) + payout)
        new_bj_wins = user_data.get('bj_wins', 0) + (1 if self.game.status == "player_win" else 0)
        await db.update_user(str(self.member.id), vibecoins=new_balance, bj_wins=new_bj_wins)
        
        if self.game.status == "player_win":
            self.bot.dispatch("blackjack_win", self.member, new_bj_wins)
        
        await interaction.response.edit_message(embed=await self.create_embed(), view=self)
        await asyncio.sleep(3)
        await interaction.channel.send(embed=discord.Embed(title="🃏 БЛЭКДЖЕК", description="Хотите сыграть еще?", color=0x2b2d31), view=BlackjackRoomView(self.bot))

class BlackjackDuelView(View):
    def __init__(self, bot, p1, p2, bet):
        super().__init__(timeout=300)
        self.bot, self.bet, self.turn = bot, bet, p1.id
        self.players = {p.id: {"member": p, "hand": [], "status": "playing"} for p in [p1, p2]}
        self.p_ids = list(self.players.keys())
        self.deck = []
        for suit in SUITS:
            for rank in range(2, 15): self.deck.append((rank, suit))
        random.shuffle(self.deck)
        for pid in self.players: self.players[pid]["hand"] = [self.deck.pop(), self.deck.pop()]
        self.processing = False
        self.game_over = False

    async def create_embed(self):
        embed = discord.Embed(title="⚔️ БЛЭКДЖЕК: ДУЭЛЬ", color=0xED4245)
        embed.description = f"💰 СТАВКА: **{self.bet} 🪙**\n"
        
        for pid, data in self.players.items():
            member = data['member']
            status_text = ""
            cards_text = ""
            score_text = ""
            
            p_score, p_soft, p_orig = calculate_score(data["hand"])
            
            if self.game_over:
                cards_text = format_hand(data["hand"])
                score_text = f"Счет: **{p_score}**"
                status_text = f"`{data['status'].upper()}`"
            else:
                # Если игрок уже завершил ход (Stand или Bust), показываем его карты полностью
                if data["status"] != "playing":
                    status_text = f"`{data['status'].upper()}`"
                    cards_text = format_hand(data["hand"])
                    score_text = f"Счет: **{p_score}**"
                elif self.turn == pid:
                    status_text = "🎯 **ВАШ ХОД**"
                    cards_text = format_hand(data["hand"])
                    if p_orig <= 21 and p_orig != p_score:
                        score_display = f"{p_orig} / {p_score}"
                    else:
                        score_display = f"{p_score}"
                    score_text = f"Счет: **{score_display}**"
                else:
                    status_text = "⌛ ОЖИДАНИЕ..."
                    first_card = f"`{RANKS.get(data['hand'][0][0])} {data['hand'][0][1]}`"
                    others = " ".join(["`❓`" for _ in range(len(data['hand'])-1)])
                    cards_text = f"{first_card} {others}"
                    score_text = "Счет: **?**"
            
            embed.add_field(name=f"👤 {member.display_name}", value=f"{status_text}\n{cards_text}\n{score_text}", inline=False)
            
        return embed

    def get_score(self, hand):
        s, _, _ = calculate_score(hand)
        return s

    @discord.ui.button(label="Взять (Hit)", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in self.players: return
        if interaction.user.id != self.turn or self.processing:
            await interaction.response.send_message("❌ Сейчас не ваш ход!", ephemeral=True); return
        
        self.processing = True
        self.players[self.turn]["hand"].append(self.deck.pop())
        p_score, _, _ = calculate_score(self.players[self.turn]["hand"])
        
        if p_score > 21:
            self.players[self.turn]["status"] = "bust"
            await self.next_turn(interaction)
        else:
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)
            self.processing = False

    @discord.ui.button(label="Стоп (Stand)", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in self.players: return
        if interaction.user.id != self.turn or self.processing:
            await interaction.response.send_message("❌ Сейчас не ваш ход!", ephemeral=True); return
        
        self.processing = True
        self.players[self.turn]["status"] = "stand"
        await self.next_turn(interaction)

    async def next_turn(self, interaction):
        if self.players[self.turn]["status"] != "playing":
            idx = self.p_ids.index(self.turn)
            if idx == 0:
                self.turn = self.p_ids[1]
                if self.players[self.turn]["status"] == "playing":
                    await interaction.response.edit_message(embed=await self.create_embed(), view=self)
                    self.processing = False
                else:
                    await self.resolve_winner(interaction)
            else:
                await self.resolve_winner(interaction)
        else:
            await interaction.response.edit_message(embed=await self.create_embed(), view=self)
            self.processing = False

    async def resolve_winner(self, interaction):
        if self.game_over: return
        self.game_over = True
        for child in self.children: child.disabled = True
        
        p1_id, p2_id = self.p_ids
        s1, _, _ = calculate_score(self.players[p1_id]["hand"])
        s2, _, _ = calculate_score(self.players[p2_id]["hand"])
        
        b1, b2 = s1 > 21, s2 > 21
        
        winner_id = None
        if b1 and b2: pass
        elif b1: winner_id = p2_id
        elif b2: winner_id = p1_id
        else:
            if s1 > s2: winner_id = p1_id
            elif s2 > s1: winner_id = p2_id
            
        embed = await self.create_embed()
        if winner_id:
            loser_id = p1_id if winner_id == p2_id else p2_id
            winner, loser = self.players[winner_id]["member"], self.players[loser_id]["member"]
            embed.description = f"🏆 **ПОБЕДИТЕЛЬ: {winner.mention}!**\nЗабрал у оппонента: **{self.bet} 🪙**"
            
            w_data = await db.get_user(str(winner_id))
            new_wins = w_data.get('bj_wins', 0) + 1
            await db.update_user(str(winner_id), vibecoins=w_data['vibecoins'] + (self.bet * 2), bj_wins=new_wins)
            self.bot.dispatch("blackjack_win", winner, new_wins)
        else:
            embed.description = "🤝 **НИЧЬЯ!** Ставки возвращены."
            for pid in self.p_ids:
                u_data = await db.get_user(str(pid))
                await db.update_user(str(pid), vibecoins=u_data['vibecoins'] + self.bet)
            
        await interaction.response.edit_message(embed=embed, view=self)
        await asyncio.sleep(5)
        
        cont_view = BlackjackDuelContinueView(self.bot, self.players[p1_id]["member"], self.players[p2_id]["member"], self.bet)
        await interaction.channel.send(
            content=f"⚔️ {self.players[p1_id]['member'].mention} {self.players[p2_id]['member'].mention}, играем дальше?", 
            view=cont_view
        )

class BlackjackDuelContinueView(View):
    def __init__(self, bot, p1, p2, bet):
        super().__init__(timeout=60)
        self.bot, self.p1, self.p2, self.bet = bot, p1, p2, bet
        self.started = False

    @discord.ui.button(label="🔄 Реванш (Та же ставка)", style=discord.ButtonStyle.primary)
    async def rematch(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in [self.p1.id, self.p2.id] or self.started: return
        self.started = True
        
        await interaction.response.defer()
        u1_data = await db.get_user(str(self.p1.id))
        u2_data = await db.get_user(str(self.p2.id))
        
        if u1_data.get('vibecoins', 0) < self.bet or u2_data.get('vibecoins', 0) < self.bet:
            await interaction.followup.send("❌ У кого-то недостаточно коинов для реванша!", ephemeral=True)
            self.started = False
            return

        await db.update_user(str(self.p1.id), vibecoins=u1_data['vibecoins'] - self.bet)
        await db.update_user(str(self.p2.id), vibecoins=u2_data['vibecoins'] - self.bet)
        
        view = BlackjackDuelView(self.bot, self.p1, self.p2, self.bet)
        await interaction.channel.send(embed=await view.create_embed(), view=view)
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="💰 Сменить ставку", style=discord.ButtonStyle.secondary)
    async def change_bet(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in [self.p1.id, self.p2.id]: return
        await interaction.response.send_message("💰 Выберите новую ставку:", view=BlackjackBetView(self.bot, "duel"), ephemeral=True)

    @discord.ui.button(label="❌ Покинуть стол", style=discord.ButtonStyle.danger)
    async def exit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in [self.p1.id, self.p2.id]: return
        await interaction.response.send_message(f"🚪 {interaction.user.display_name} покинул игру.")
        await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class BlackjackRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🃏 Соло Режим", style=discord.ButtonStyle.primary, custom_id="bj_solo_btn")
    async def solo(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("💰 Выберите размер вашей ставки:", view=BlackjackBetView(self.bot, "solo"), ephemeral=True)

    @discord.ui.button(label="⚔️ Вызвать на Дуэль", style=discord.ButtonStyle.success, custom_id="bj_duel_btn")
    async def invite(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("💰 На какую сумму играем?", view=BlackjackBetView(self.bot, "duel"), ephemeral=True)

    @discord.ui.button(label="❌ Покинуть стол", style=discord.ButtonStyle.danger, custom_id="bj_close_btn")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Уходим из казино..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(BlackjackRoomView(bot))

    @commands.command(name="bj_setup", aliases=["блэкджек", "bj"])
    @commands.has_permissions(administrator=True)
    async def setup_blackjack(self, ctx):
        """Создаёт панель для игры в Блэкджек (только для админов)."""
        embed = discord.Embed(
            title="🃏 ИГРОВОЙ СТОЛ: БЛЭКДЖЕК",
            description=(
                "Добро пожаловать в элитный клуб! Здесь вы можете испытать удачу в классической игре.\n\n"
                "🔹 **Соло:** Играйте против дилера с множителем до **2.5x**!\n"
                "🔹 **Дуэль:** Вызовите друга на честный поединок.\n\n"
                "*Помните: казино всегда в плюсе... или нет?*"
            ),
            color=0x2b2d31
        )
        embed.set_image(url="https://media.giphy.com/media/l41lUj8pB7S4N4bba/giphy.gif")
        await ctx.send(embed=embed, view=BlackjackRoomView(self.bot))
        await ctx.message.delete()

async def setup(bot): await bot.add_cog(Blackjack(bot))
