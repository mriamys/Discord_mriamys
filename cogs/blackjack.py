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
        name = RANKS[rank]
        res.append(f"`{name} {suit}`")
    return " ".join(res)

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
        score, aces = 0, 0
        for rank, suit in hand:
            if rank == 11: aces += 1; score += 11
            elif rank >= 12: score += 10
            else: score += rank
        while score > 21 and aces > 0: score -= 10; aces -= 1
        return score

class BlackjackView(View):
    def __init__(self, bot, member, bet, user_data):
        super().__init__(timeout=60)
        self.bot, self.member, self.bet, self.user_data = bot, member, bet, user_data
        self.game = BlackjackGame(bet)

    def create_embed(self):
        p_score = self.game.get_score(self.game.player_hand)
        d_score = self.game.get_score(self.game.dealer_hand)
        embed = discord.Embed(title="🃏 Блэкджек: Игровой стол", color=0x2b2d31)
        embed.add_field(name=f"👤 {self.member.display_name}", value=f"Карты: {format_hand(self.game.player_hand)}\nСчет: **{p_score}**", inline=False)
        if self.game.status == "playing":
            d_cards = f"`{RANKS[self.game.dealer_hand[0][0]]} {self.game.dealer_hand[0][1]}` ` ? `"
            embed.add_field(name="🤖 Дилер", value=f"Карты: {d_cards}\nСчет: **?**", inline=False)
            embed.description = f"💰 Ставка: **{self.bet} 🪙**"
        else:
            embed.add_field(name="🤖 Дилер", value=f"Карты: {format_hand(self.game.dealer_hand)}\nСчет: **{d_score}**", inline=False)
            if self.game.status == "player_win": embed.description = f"🎉 **ВЫИГРЫШ!** +**{self.bet * 2} 🪙**"; embed.color = 0x2ECC71
            elif self.game.status == "dealer_win": embed.description = f"💔 **ПРОИГРЫШ.**"; embed.color = 0xE74C3C
            elif self.game.status == "draw": embed.description = f"🤝 **НИЧЬЯ.**"; embed.color = 0xF1C40F
            elif self.game.status == "bust": embed.description = f"💥 **ПЕРЕБОР!** (>21)"; embed.color = 0xE74C3C
        return embed

    @discord.ui.button(label="Взять (Hit)", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        self.game.player_hand.append(self.game.draw())
        if self.game.get_score(self.game.player_hand) > 21:
            self.game.status = "bust"; await self.end_game(interaction)
        else: await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Стоп (Stand)", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        while self.game.get_score(self.game.dealer_hand) < 17: self.game.dealer_hand.append(self.game.draw())
        p_score, d_score = self.game.get_score(self.game.player_hand), self.game.get_score(self.game.dealer_hand)
        if d_score > 21 or p_score > d_score: self.game.status = "player_win"
        elif p_score < d_score: self.game.status = "dealer_win"
        else: self.game.status = "draw"
        await self.end_game(interaction)

    async def end_game(self, interaction):
        for child in self.children: child.disabled = True
        payout = self.bet * 2 if self.game.status == "player_win" else (self.bet if self.game.status == "draw" else 0)
        user_data = await db.get_user(str(self.member.id))
        new_balance = user_data.get('vibecoins', 0) - self.bet + payout
        await db.update_user(str(self.member.id), vibecoins=new_balance, bj_wins=user_data.get('bj_wins', 0) + (1 if self.game.status == "player_win" else 0))
        self.bot.dispatch("balance_updated", self.member, new_balance)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
        await asyncio.sleep(2)
        desc = "**ПРАВИЛА:**\nНабери больше дилера, но не более 21. J,Q,K=10, Туз=1 или 11."
        await interaction.channel.send(embed=discord.Embed(title="🃏 БЛЭКДЖЕК", description=desc, color=0x2ECC71), view=BlackjackRoomView(self.bot))

class BlackjackDuelView(View):
    def __init__(self, bot, p1, p2, bet):
        super().__init__(timeout=300)
        self.bot, self.bet, self.turn = bot, bet, p1.id
        self.players = {p.id: {"member": p, "hand": [None, None], "status": "playing"} for p in [p1, p2]}
        self.deck = []
        for suit in SUITS:
            for rank in range(2, 15): self.deck.append((rank, suit))
        random.shuffle(self.deck)
        for pid in self.players: self.players[pid]["hand"] = [self.deck.pop(), self.deck.pop()]

    def get_score(self, hand):
        score, aces = 0, 0
        for rank, suit in hand:
            if rank == 11: aces += 1; score += 11
            elif rank >= 12: score += 10
            else: score += rank
        while score > 21 and aces > 0: score -= 10; aces -= 1
        return score

    def create_embed(self):
        embed = discord.Embed(title="⚔️ Блэкджек Дуэль", color=0xE74C3C)
        for pid, data in self.players.items():
            score = self.get_score(data["hand"])
            status = "🎯 ХОДИТ" if self.turn == pid and data["status"] == "playing" else data["status"].upper()
            embed.add_field(name=f"👤 {data['member'].display_name}", value=f"Карты: {format_hand(data['hand'])}\nСчет: **{score}**\nСтатус: `{status}`", inline=False)
        embed.description = f"💰 Банк: **{self.bet * 2} 🪙**\nОчередь: <@{self.turn}>"
        return embed

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.turn: return
        self.players[self.turn]["hand"].append(self.deck.pop())
        if self.get_score(self.players[self.turn]["hand"]) > 21:
            self.players[self.turn]["status"] = "bust"; await self.next_turn(interaction)
        else: await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.turn: return
        self.players[self.turn]["status"] = "stand"; await self.next_turn(interaction)

    async def next_turn(self, interaction):
        p_ids = list(self.players.keys())
        idx = p_ids.index(self.turn)
        next_pid = p_ids[(idx + 1) % 2]
        if self.players[next_pid]["status"] == "playing": self.turn = next_pid; await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else: await self.resolve_winner(interaction)

    async def resolve_winner(self, interaction):
        for child in self.children: child.disabled = True
        scores = {pid: (self.get_score(d["hand"]) if d["status"] != "bust" else -1) for pid, d in self.players.items()}
        p1_id, p2_id = list(self.players.keys())
        winner_id = p1_id if scores[p1_id] > scores[p2_id] else (p2_id if scores[p2_id] > scores[p1_id] else None)
        embed = self.create_embed()
        if winner_id:
            winner = self.players[winner_id]["member"]
            embed.description = f"🏆 **ПОБЕДИТЕЛЬ: {winner.mention}!**\nЗабрал банк: **{self.bet * 2} 🪙**"
            w_data = await db.get_user(str(winner_id))
            await db.update_user(str(winner_id), vibecoins=w_data['vibecoins'] + self.bet * 2, bj_wins=w_data.get('bj_wins', 0) + 1)
        else:
            embed.description = "🤝 **НИЧЬЯ!** Ставки возвращены."
            for pid in self.players:
                u_data = await db.get_user(str(pid))
                await db.update_user(str(pid), vibecoins=u_data['vibecoins'] + self.bet)
        await interaction.response.edit_message(embed=embed, view=self)
        await asyncio.sleep(3); await interaction.channel.send(embed=discord.Embed(title="🃏 БЛЭКДЖЕК", description="Выбирай режим:", color=0x2ECC71), view=BlackjackRoomView(self.bot))

class BlackjackRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🃏 Соло (500 🪙)", style=discord.ButtonStyle.primary, custom_id="bj_solo_v3")
    async def solo(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.response.send_message("❌ Мало денег!", ephemeral=True); return
        view = BlackjackView(self.bot, interaction.user, 500, user_data)
        await interaction.response.send_message(embed=view.create_embed(), view=view)
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="⚔️ С другом (500 🪙)", style=discord.ButtonStyle.success, custom_id="bj_duel_v3")
    async def invite(self, interaction: discord.Interaction, button: Button):
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("🃏 Выбери друга для игры:", view=GameDuelSelectView(self.bot, interaction.user.id, 500, "bj"), ephemeral=True)

    @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.danger, custom_id="bj_close_v3")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Закрываю..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(BlackjackRoomView(bot))

async def setup(bot): await bot.add_cog(Blackjack(bot))
