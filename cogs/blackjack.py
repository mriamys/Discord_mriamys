import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
from utils.db import db

class BlackjackGame:
    def __init__(self, bet):
        self.bet = bet
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(self.deck)
        self.player_hand = [self.draw(), self.draw()]
        self.dealer_hand = [self.draw(), self.draw()]
        self.status = "playing" # playing, player_win, dealer_win, draw, bust

    def draw(self):
        return self.deck.pop()

    def get_score(self, hand):
        score = sum(hand)
        aces = hand.count(11)
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

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
        
        embed = discord.Embed(title="🃏 Блэкджек (Соло)", color=0x2b2d31)
        embed.add_field(name=f"👤 {self.member.display_name}", value=f"Карты: `{self.game.player_hand}`\nСчет: **{p_score}**", inline=True)
        
        if self.game.status == "playing":
            embed.add_field(name="🤖 Дилер", value=f"Карты: `[{self.game.dealer_hand[0]}, ?]`\nСчет: **?**", inline=True)
            embed.description = f"Ваша ставка: **{self.bet} 🪙**\nЧто будете делать?"
        else:
            embed.add_field(name="🤖 Дилер", value=f"Карты: `{self.game.dealer_hand}`\nСчет: **{d_score}**", inline=True)
            
            if self.game.status == "player_win":
                embed.description = f"🎉 **Вы выиграли {self.bet * 2} 🪙!**"
                embed.color = discord.Color.green()
            elif self.game.status == "dealer_win":
                embed.description = f"💔 **Дилер выиграл. Вы потеряли {self.bet} 🪙.**"
                embed.color = discord.Color.red()
            elif self.game.status == "draw":
                embed.description = f"🤝 **Ничья. Ставка возвращена.**"
                embed.color = discord.Color.gold()
            elif self.game.status == "bust":
                embed.description = f"💥 **Перебор! Вы проиграли {self.bet} 🪙.**"
                embed.color = discord.Color.red()
                
        return embed

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        
        self.game.player_hand.append(self.game.draw())
        if self.game.get_score(self.game.player_hand) > 21:
            self.game.status = "bust"
            await self.end_game(interaction)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.member.id: return
        
        # Дилер играет
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
        for child in self.children:
            child.disabled = True
            
        payout = 0
        if self.game.status == "player_win":
            payout = self.bet * 2
        elif self.game.status == "draw":
            payout = self.bet
            
        new_balance = self.user_data.get('vibecoins', 0) - self.bet + payout
        new_spent = self.user_data.get('casino_spent', 0) + self.bet
        new_wins = self.user_data.get('casino_wins', 0) + payout
        bj_wins = self.user_data.get('bj_wins', 0)
        
        if self.game.status == "player_win":
            bj_wins += 1
        
        await db.update_user(str(self.member.id), vibecoins=new_balance, casino_spent=new_spent, casino_wins=new_wins, bj_wins=bj_wins)
        self.bot.dispatch("casino_played", self.member, new_spent, new_wins, payout, self.bet)
        if self.game.status == "player_win":
            self.bot.dispatch("blackjack_win", self.member, bj_wins)
            
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

# ─── ДУЭЛЬ БЛЭКДЖЕК ───────────────────────────────────────────────────────────

class BlackjackDuelView(View):
    def __init__(self, bot, p1, p2, bet):
        super().__init__(timeout=300)
        self.bot = bot
        self.players = {p1.id: {"member": p1, "hand": [], "status": "playing"},
                        p2.id: {"member": p2, "hand": [], "status": "playing"}}
        self.bet = bet
        self.deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(self.deck)
        
        # Раздаем начальные карты
        for pid in self.players:
            self.players[pid]["hand"] = [self.draw(), self.draw()]
            
        self.turn = p1.id # Очередь игрока 1

    def draw(self):
        return self.deck.pop()

    def get_score(self, hand):
        score = sum(hand)
        aces = hand.count(11)
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def create_embed(self):
        embed = discord.Embed(title="⚔️ Блэкджек Дуэль", color=discord.Color.red())
        for pid, data in self.players.items():
            score = self.get_score(data["hand"])
            status_text = "🎯 Ходит" if self.turn == pid and data["status"] == "playing" else data["status"].capitalize()
            embed.add_field(
                name=f"👤 {data['member'].display_name}", 
                value=f"Карты: `{data['hand']}`\nСчет: **{score}**\nСтатус: `{status_text}`", 
                inline=True
            )
        embed.description = f"Общий банк: **{self.bet * 2} 🪙**\nСейчас очередь: <@{self.turn}>"
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
        
        # Ищем следующего, кто еще играет
        next_found = False
        for i in range(1, len(p_ids)):
            next_pid = p_ids[(current_idx + i) % len(p_ids)]
            if self.players[next_pid]["status"] == "playing":
                self.turn = next_pid
                next_found = True
                break
        
        if not next_found:
            await self.resolve_winner(interaction)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def resolve_winner(self, interaction):
        for child in self.children: child.disabled = True
        
        scores = {}
        for pid, data in self.players.items():
            score = self.get_score(data["hand"])
            scores[pid] = score if data["status"] != "bust" else -1
            
        p1_id, p2_id = list(self.players.keys())
        s1, s2 = scores[p1_id], scores[p2_id]
        
        winner_id = None
        if s1 > s2: winner_id = p1_id
        elif s2 > s1: winner_id = p2_id
        
        embed = self.create_embed()
        if winner_id:
            winner = self.players[winner_id]["member"]
            embed.description = f"🏆 **Победитель: {winner.mention}!**\nЗабрал банк: **{self.bet * 2} 🪙**"
            embed.color = discord.Color.green()
            
            # Обновляем БД
            w_data = await db.get_user(str(winner_id))
            bj_wins = w_data.get('bj_wins', 0) + 1
            await db.update_user(str(winner_id), vibecoins=w_data.get('vibecoins', 0) + self.bet * 2, bj_wins=bj_wins)
            self.bot.dispatch("blackjack_win", winner, bj_wins)
        else:
            embed.description = "🤝 **Ничья!** Ставки возвращены."
            embed.color = discord.Color.gold()
            for pid in self.players:
                u_data = await db.get_user(str(pid))
                await db.update_user(str(pid), vibecoins=u_data.get('vibecoins', 0) + self.bet)
                
        await interaction.response.edit_message(embed=embed, view=self)

class BlackjackRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🃏 Играть Соло (500 🪙)", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.response.send_message("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return
            
        # Списываем напрямую
        new_bal = user_data.get('vibecoins', 0) - 500
        await db.update_user(str(interaction.user.id), vibecoins=new_bal)
        # Диспатчим обновление баланса для магазина
        self.bot.dispatch("balance_updated", interaction.user, new_bal)
        
        view = BlackjackView(self.bot, interaction.user, 500, user_data)
        await interaction.response.send_message(embed=view.create_embed(), view=view)

    @discord.ui.button(label="⚔️ Вызвать игрока (500 🪙)", style=discord.ButtonStyle.success)
    async def invite(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.response.send_message("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return
            
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("🃏 Выбери оппонента для игры в Блэкджек:", view=GameDuelSelectView(self.bot, interaction.user, 500, "bj"), ephemeral=True)

    @discord.ui.button(label="❌ Выйти", style=discord.ButtonStyle.danger)
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("👋 Стол закрыт. Удачи!")
        await asyncio.sleep(3)
        try: await interaction.channel.delete()
        except: pass

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Blackjack(bot))
