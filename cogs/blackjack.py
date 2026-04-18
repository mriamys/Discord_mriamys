import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
from utils.db import db

# Символы мастей для красоты
SUITS = ['♠️', '♣️', '❤️', '♦️']
RANKS = {
    2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10',
    11: 'Ace', 12: 'Jack', 13: 'Queen', 14: 'King'
}

def get_card_val(rank):
    if rank <= 10: return rank
    if rank <= 14: return 10 # Картинки весят 10
    if rank == 11: return 11 # Туз
    return 0

def format_hand(hand):
    """Превращает список карт в красивую строку."""
    res = []
    for rank, suit in hand:
        name = RANKS[rank]
        res.append(f"`{name} {suit}`")
    return " ".join(res)

class BlackjackGame:
    def __init__(self, bet):
        self.bet = bet
        # Колода: (номинал, масть)
        self.deck = []
        for suit in SUITS:
            for rank in range(2, 15):
                self.deck.append((rank, suit))
        random.shuffle(self.deck)
        
        self.player_hand = [self.draw(), self.draw()]
        self.dealer_hand = [self.draw(), self.draw()]
        self.status = "playing"

    def draw(self):
        return self.deck.pop()

    def get_score(self, hand):
        score = 0
        aces = 0
        for rank, suit in hand:
            if rank == 11: # Туз
                aces += 1
                score += 11
            elif rank >= 12: # Картинки
                score += 10
            else:
                score += rank
        
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

# ─── СОЛО ИГРА ────────────────────────────────────────────────────────────────

class BlackjackView(View):
    def __init__(self, bot, member, bet, user_data):
        super().__init__(timeout=60)
        self.bot = bot
        self.member = member
        self.bet = bet
        self.user_data = user_data
        self.game = BlackjackGame(bet)

    def create_embed(self):
        p_score = self.game.get_score(self.game.player_hand)
        d_score = self.game.get_score(self.game.dealer_hand)
        
        embed = discord.Embed(title="🃏 Блэкджек: Стол №1", color=0x2b2d31)
        embed.add_field(name=f"👤 {self.member.display_name}", value=f"Карты: {format_hand(self.game.player_hand)}\nСчет: **{p_score}**", inline=False)
        
        if self.game.status == "playing":
            d_cards = f"`{RANKS[self.game.dealer_hand[0][0]]} {self.game.dealer_hand[0][1]}` ` ? `"
            embed.add_field(name="🤖 Дилер", value=f"Карты: {d_cards}\nСчет: **?**", inline=False)
            embed.description = f"💰 Ставка: **{self.bet} 🪙**\n*Взять карту или остановиться?*"
        else:
            embed.add_field(name="🤖 Дилер", value=f"Карты: {format_hand(self.game.dealer_hand)}\nСчет: **{d_score}**", inline=False)
            
            if self.game.status == "player_win":
                embed.description = f"🎉 **ПОБЕДА! Вы выиграли {self.bet * 2} 🪙!**"
                embed.color = discord.Color.green()
            elif self.game.status == "dealer_win":
                embed.description = f"💔 **ДИЛЕР ВЫИГРАЛ. Вы проиграли {self.bet} 🪙.**"
                embed.color = discord.Color.red()
            elif self.game.status == "draw":
                embed.description = f"🤝 **НИЧЬЯ. Ставка возвращена.**"
                embed.color = discord.Color.gold()
            elif self.game.status == "bust":
                embed.description = f"💥 **ПЕРЕБОР! Вы проиграли {self.bet} 🪙.**"
                embed.color = discord.Color.red()
                
        return embed

    @discord.ui.button(label="Взять (Hit)", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        
        self.game.player_hand.append(self.game.draw())
        if self.game.get_score(self.game.player_hand) > 21:
            self.game.status = "bust"
            await self.end_game(interaction)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Стоп (Stand)", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        
        # Дилер обязан брать до 17
        while self.game.get_score(self.game.dealer_hand) < 17:
            self.game.dealer_hand.append(self.game.draw())
        
        p_score = self.game.get_score(self.game.player_hand)
        d_score = self.game.get_score(self.game.dealer_hand)
        
        if d_score > 21 or p_score > d_score:
            self.game.status = "player_win"
        elif p_score < d_score:
            self.game.status = "dealer_win"
        else:
            self.game.status = "draw"
            
        await self.end_game(interaction)

    async def end_game(self, interaction):
        for child in self.children: child.disabled = True
        payout = 0
        if self.game.status == "player_win": payout = self.bet * 2
        elif self.game.status == "draw": payout = self.bet
            
        user_data = await db.get_user(str(self.member.id))
        new_balance = user_data.get('vibecoins', 0) - self.bet + payout
        bj_wins = user_data.get('bj_wins', 0) + (1 if self.game.status == "player_win" else 0)
        
        await db.update_user(str(self.member.id), vibecoins=new_balance, bj_wins=bj_wins)
        self.bot.dispatch("blackjack_win", self.member, bj_wins)
        self.bot.dispatch("balance_updated", self.member, new_balance)
            
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

        # Ресенд меню румы
        await interaction.channel.send(content=self.member.mention, embed=discord.Embed(title="🃏 БЛЭКДЖЕК", description="Выбирай режим игры:", color=0x2ECC71), view=BlackjackRoomView(self.bot))

# ─── ДУЭЛЬ ────────────────────────────────────────────────────────────────────

class BlackjackDuelView(View):
    def __init__(self, bot, p1, p2, bet):
        super().__init__(timeout=300)
        self.bot = bot
        self.players = {
            p1.id: {"member": p1, "hand": [], "status": "playing"},
            p2.id: {"member": p2, "hand": [], "status": "playing"}
        }
        self.bet = bet
        self.deck = []
        for suit in SUITS:
            for rank in range(2, 15):
                self.deck.append((rank, suit))
        random.shuffle(self.deck)
        
        for pid in self.players:
            self.players[pid]["hand"] = [self.draw(), self.draw()]
            
        self.turn = p1.id

    def draw(self): return self.deck.pop()

    def get_score(self, hand):
        score, aces = 0, 0
        for rank, suit in hand:
            if rank == 11: aces += 1; score += 11
            elif rank >= 12: score += 10
            else: score += rank
        while score > 21 and aces > 0: score -= 10; aces -= 1
        return score

    def create_embed(self):
        embed = discord.Embed(title="⚔️ Блэкджек Дуэль", color=discord.Color.red())
        for pid, data in self.players.items():
            score = self.get_score(data["hand"])
            status = "🎯 ХОДИТ" if self.turn == pid and data["status"] == "playing" else data["status"].upper()
            embed.add_field(
                name=f"👤 {data['member'].display_name}", 
                value=f"Карты: {format_hand(data['hand'])}\nСчет: **{score}**\nСтатус: `{status}`", 
                inline=False
            )
        embed.description = f"💰 Банк: **{self.bet * 2} 🪙**\nСейчас очередь: <@{self.turn}>"
        return embed

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.turn: return
        p_data = self.players[self.turn]
        p_data["hand"].append(self.draw())
        if self.get_score(p_data["hand"]) > 21:
            p_data["status"] = "bust"
            await self.next_turn(interaction)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.turn: return
        self.players[self.turn]["status"] = "stand"
        await self.next_turn(interaction)

    async def next_turn(self, interaction):
        p_ids = list(self.players.keys())
        current_idx = p_ids.index(self.turn)
        next_found = False
        for i in range(1, len(p_ids)):
            next_pid = p_ids[(current_idx + i) % len(p_ids)]
            if self.players[next_pid]["status"] == "playing":
                self.turn = next_pid
                next_found = True
                break
        
        if not next_found: await self.resolve_winner(interaction)
        else: await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def resolve_winner(self, interaction):
        for child in self.children: child.disabled = True
        scores = {pid: (self.get_score(d["hand"]) if d["status"] != "bust" else -1) for pid, d in self.players.items()}
        p1_id, p2_id = list(self.players.keys())
        s1, s2 = scores[p1_id], scores[p2_id]
        
        winner_id = None
        if s1 > s2: winner_id = p1_id
        elif s2 > s1: winner_id = p2_id
        
        embed = self.create_embed()
        if winner_id:
            winner = self.players[winner_id]["member"]
            embed.description = f"🏆 **ПОБЕДИТЕЛЬ: {winner.mention}!**\nЗабрал банк: **{self.bet * 2} 🪙**"
            embed.color = discord.Color.green()
            w_data = await db.get_user(str(winner_id))
            await db.update_user(str(winner_id), vibecoins=w_data['vibecoins'] + self.bet * 2, bj_wins=w_data.get('bj_wins', 0) + 1)
        else:
            embed.description = "🤝 **НИЧЬЯ!** Ставки возвращены."
            embed.color = discord.Color.gold()
            for pid in self.players:
                u_data = await db.get_user(str(pid))
                await db.update_user(str(pid), vibecoins=u_data['vibecoins'] + self.bet)
        await interaction.response.edit_message(embed=embed, view=self)

# ─── МЕНЮ КОМНАТЫ (РУМА) ──────────────────────────────────────────────────────

class BlackjackRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🃏 Соло Игра (500 🪙)", style=discord.ButtonStyle.primary, custom_id="bj_room_solo")
    async def solo(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.response.send_message("❌ Недостаточно коинов!", ephemeral=True)
            return
            
        view = BlackjackView(self.bot, interaction.user, 500, user_data)
        # Отправляем новое сообщение с игрой
        await interaction.response.send_message(embed=view.create_embed(), view=view)
        
        # Удаляем старое меню румы
        try:
            await interaction.message.delete()
        except:
            pass

    @discord.ui.button(label="⚔️ Вызвать игрока", style=discord.ButtonStyle.success, custom_id="bj_room_duel")
    async def invite(self, interaction: discord.Interaction, button: Button):
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("🃏 Выбери оппонента для дуэли (ставка 500):", view=GameDuelSelectView(self.bot, interaction.user, 500, "bj"), ephemeral=True)

    @discord.ui.button(label="📜 Правила", style=discord.ButtonStyle.secondary, custom_id="bj_room_rules")
    async def rules(self, interaction: discord.Interaction, button: Button):
        rules_text = (
            "**Цель игры:** Набрать больше очков, чем у дилера, но не более **21**.\n\n"
            "🔹 **Туз (Ace):** 1 или 11 очков (выбирается автоматически в вашу пользу).\n"
            "🔹 **Картинки (J, Q, K):** 10 очков.\n"
            "🔹 **Числа:** по своему номиналу.\n\n"
            "📜 **Ход игры:** Вы получаете 2 карты. Вы можете 'Взять' (Hit) еще или 'Стоп' (Stand).\n"
            "🧨 Если у вас больше 21 — это **перебор**, вы проигрываете сразу.\n"
            "🤖 Дилер обязан брать карты, пока у него меньше 17 очков."
        )
        await interaction.response.send_message(rules_text, ephemeral=True)

    @discord.ui.button(label="❌ Выйти", style=discord.ButtonStyle.danger, custom_id="bj_room_exit")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("👋 Стол закрыт.")
        await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Blackjack(bot))
