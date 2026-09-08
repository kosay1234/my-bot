import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
import json
import os
import asyncio

# إعداد الصلاحيات والنوايا
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = True 

bot = commands.Bot(command_prefix="!", intents=intents)

ALLOWED_CHANNEL_IDS = [
    1546775803616960582,
    1546775788269867058,
    1546775771035734026
]

DATA_FILE = "ranks.json"

def load_ranks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_ranks(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

user_mvp_points = load_ranks()

async def update_player_nickname(member: discord.Member, points: int):
    try:
        # إزالة الـ Rank القديم من الاسم لو كان موجوداً لتجنب التكرار
        clean_name = member.display_name
        if " | " in clean_name and clean_name.startswith("RANK "):
            clean_name = clean_name.split(" | ", 1)[1]
        
        new_nickname = f"RANK {points} | {clean_name}"
        if len(new_nickname) <= 32:  # شرط ديسكورد لطول الاسم الأقصى 32 حرف
            await member.edit(nick=new_nickname)
    except Exception as e:
        print(f"فشل في تغيير اسم اللاعب {member.display_name}: {e}")

def add_mvp_point(user_id):
    str_id = str(user_id)
    user_mvp_points[str_id] = user_mvp_points.get(str_id, 0) + 1
    save_ranks(user_mvp_points)
    return user_mvp_points[str_id]

def get_mvp_rank(user_id):
    str_id = str(user_id)
    return user_mvp_points.get(str_id, 0)

def get_user_device(member: discord.Member):
    if not member or not hasattr(member, 'status') or member.status == discord.Status.offline:
        return "💻"
    if hasattr(member, 'mobile_status') and member.mobile_status != discord.Status.offline:
        return "📱"
    return "💻"

class RoomDetailsModal(Modal, title="تفاصيل روم Free Fire"):
    room_id = TextInput(label="ID الروم (Room ID)", placeholder="أدخل أيدي الروم هنا...", required=True)
    room_pass = TextInput(label="كلمة السر (Password)", placeholder="أدخل كود الروم هنا...", required=True)

    def __init__(self, match_lobby):
        super().__init__()
        self.match_lobby = match_lobby

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.match_lobby.start_match_with_details(interaction, self.room_id.value, self.room_pass.value)

class VotingView(View):
    def __init__(self, all_players, text_channel, v1, v2):
        super().__init__(timeout=None)
        self.all_players = all_players
        self.text_channel = text_channel
        self.v1 = v1
        self.v2 = v2
        self.votes_best = {}
        self.votes_worst = {}

        options_best = [discord.SelectOption(label=f"{m.display_name} (MVP Rank #{get_mvp_rank(m.id)})", value=str(m.id)) for m in all_players]
        options_worst = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in all_players]

        self.select_best = Select(placeholder="🌟 اختر أفضل لاعب (MVP)", options=options_best, custom_id="vote_best")
        self.select_best.callback = self.vote_best_callback
        self.add_item(self.select_best)

        self.select_worst = Select(placeholder="💀 اختر أسوأ لاعب", options=options_worst, custom_id="vote_worst")
        self.select_worst.callback = self.vote_worst_callback
        self.add_item(self.select_worst)

    async def vote_best_callback(self, interaction: discord.Interaction):
        chosen_id = interaction.data['values'][0]
        self.votes_best[interaction.user.id] = chosen_id
        await interaction.response.send_message("✅ تم تسجيل تصويتك لأفضل لاعب!", ephemeral=True)

    async def vote_worst_callback(self, interaction: discord.Interaction):
        chosen_id = interaction.data['values'][0]
        self.votes_worst[interaction.user.id] = chosen_id
        await interaction.response.send_message("✅ تم تسجيل تصويتك لأسوأ لاعب!", ephemeral=True)

    @discord.ui.button(label="🏁 إنهاء التصويت وإظهار النتائج", style=discord.ButtonStyle.success, row=2)
    async def finish_voting(self, interaction: discord.Interaction, button: Button):
        if not self.votes_best:
            return await interaction.response.send_message("لم يقم أحد بالتصويت بعد!", ephemeral=True)

        from collections import Counter
        best_counts = Counter(self.votes_best.values())
        mvp_id = int(best_counts.most_common(1)[0][0])
        mvp_member = interaction.guild.get_member(mvp_id)

        worst_text = "لا يوجد"
        if self.votes_worst:
            worst_counts = Counter(self.votes_worst.values())
            worst_id = int(worst_counts.most_common(1)[0][0])
            worst_member = interaction.guild.get_member(worst_id)
            worst_text = worst_member.mention if worst_member else "لاعب"

        new_rank = 0
        if mvp_member:
            new_rank = add_mvp_point(mvp_member.id)
            # تحديث اسم اللاعب في السيرفر أوتوماتيكياً بالشكل المطلوب
            await update_player_nickname(mvp_member, new_rank)

        embed = discord.Embed(title="📊 نتائج مباراة Free Fire", color=discord.Color.gold())
        embed.add_field(name="🌟 أفضل لاعب (MVP)", value=f"{mvp_member.mention if mvp_member else 'غير معروف'} (⭐ Rank #{new_rank})", inline=False)
        embed.add_field(name="💀 أسوأ لاعب", value=worst_text, inline=False)

        await interaction.response.send_message(embed=embed)
        await interaction.followup.send("🧹 **سيتم حذف جميع رومات الماتش تلقائياً خلال 5 ثوانٍ...**")
        
        button.disabled = True
        await interaction.message.edit(view=self)

        await asyncio.sleep(5)
        
        try:
            if self.v1: await self.v1.delete()
            if self.v2: await self.v2.delete()
            if self.text_channel: await self.text_channel.delete()
        except Exception as e:
            print(f"خطأ أثناء حذف الرومات: {e}")

class ModeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1v1 Match", value="1", description="مواجهة فردية (1 ضد 1)"),
            discord.SelectOption(label="2v2 Match", value="2", description="مواجهة ثنائية (2 ضد 2)"),
            discord.SelectOption(label="3v3 Match", value="3", description="مواجهة ثلاثية (3 ضد 3)"),
            discord.SelectOption(label="4v4 Match", value="4", description="مواجهة رباعية (4 ضد 4)"),
        ]
        super().__init__(placeholder="اختر نمط المواجهة (Mode)...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        team_size = int(self.values[0])
        lobby_view = MatchLobby(host=interaction.user, team_size=team_size)
        embed = lobby_view.create_embed()
        await interaction.response.send_message(embed=embed, view=lobby_view)

class ModeSelectionView(View):
    def __init__(self, host: discord.Member):
        super().__init__(timeout=60)
        self.host = host
        self.add_item(ModeSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب الأمر فقط يمكنه اختيار النمط!", ephemeral=True)
            return False
        return True

class MatchLobby(View):
    def __init__(self, host: discord.Member, team_size: int):
        super().__init__(timeout=None)
        self.host = host
        self.team_size = team_size
        self.team1 = []
        self.team2 = []
        self.match_text_channel = None
        self.v1 = None
        self.v2 = None

    def create_embed(self):
        status = "Ready" if len(self.team1) == self.team_size and len(self.team2) == self.team_size else "Waiting..."
        
        t1_text = "\n".join([f"{get_user_device(m)} {m.mention}" for m in self.team1]) if self.team1 else "فارغ"
        t2_text = "\n".join([f"{get_user_device(m)} {m.mention}" for m in self.team2]) if self.team2 else "فارغ"

        description = f"**Host:** {self.host.mention}\n"
        description += f"**Type:** {self.team_size}v{self.team_size} | **Status:** **{status}**\n"
        description += f"───────────────────────\n\n"
        description += f"🟢 **Team 1** ({len(self.team1)}/{self.team_size})\n{t1_text}\n\n"
        description += f"───────────────────────\n\n"
        description += f"🔴 **Team 2** ({len(self.team2)}/{self.team_size})\n{t2_text}"

        embed = discord.Embed(
            description=description,
            color=0x2b2d31
        )
        return embed

    def remove_user(self, user):
        if user in self.team1: self.team1.remove(user)
        if user in self.team2: self.team2.remove(user)

    @discord.ui.button(label="Join Team 1", style=discord.ButtonStyle.success)
    async def join_team_1(self, interaction: discord.Interaction, button: Button):
        if len(self.team1) >= self.team_size and interaction.user not in self.team1:
            return await interaction.response.send_message("الفريق الأول مكتمل!", ephemeral=True)
        self.remove_user(interaction.user)
        self.team1.append(interaction.user)
        
        if len(self.team1) == self.team_size and len(self.team2) == self.team_size:
            await interaction.response.send_modal(RoomDetailsModal(self))
            await interaction.message.edit(embed=self.create_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Join Team 2", style=discord.ButtonStyle.danger)
    async def join_team_2(self, interaction: discord.Interaction, button: Button):
        if len(self.team2) >= self.team_size and interaction.user not in self.team2:
            return await interaction.response.send_message("الفريق الثاني مكتمل!", ephemeral=True)
        self.remove_user(interaction.user)
        self.team2.append(interaction.user)

        if len(self.team1) == self.team_size and len(self.team2) == self.team_size:
            await interaction.response.send_modal(RoomDetailsModal(self))
            await interaction.message.edit(embed=self.create_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_team(self, interaction: discord.Interaction, button: Button):
        self.remove_user(interaction.user)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Cancel Game", style=discord.ButtonStyle.red)
    async def cancel_game(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.host:
            return await interaction.response.send_message("مؤسس الماتش فقط يمكنه الإلغاء!", ephemeral=True)
        self.stop()
        await interaction.response.edit_message(content="❌ تم إلغاء الماتش.", embed=None, view=None)

    async def start_match_with_details(self, interaction: discord.Interaction, room_id: str, room_pass: str):
        guild = interaction.guild
        category = interaction.channel.category
        all_players = self.team1 + self.team2

        overwrites_text = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            **{m: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True) for m in all_players}
        }

        overwrites_t1 = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            **{m: discord.PermissionOverwrite(view_channel=True, connect=True) for m in self.team1}
        }
        overwrites_t2 = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            **{m: discord.PermissionOverwrite(view_channel=True, connect=True) for m in self.team2}
        }

        self.match_text_channel = await guild.create_text_channel(
            name="🎮-match",
            category=category,
            overwrites=overwrites_text
        )

        self.v1 = await guild.create_voice_channel(
            name=f"🔴 Team 1 ({self.team_size}v{self.team_size})", 
            category=category, 
            overwrites=overwrites_t1
        )
        self.v2 = await guild.create_voice_channel(
            name=f"🟢 Team 2 ({self.team_size}v{self.team_size})", 
            category=category, 
            overwrites=overwrites_t2
        )

        for member in self.team1:
            if member.voice and member.voice.channel:
                try: await member.move_to(self.v1)
                except: pass
        for member in self.team2:
            if member.voice and member.voice.channel:
                try: await member.move_to(self.v2)
                except: pass

        embed_room = discord.Embed(
            title="🎮 بيانات روم Free Fire",
            description="يرجى استخدام الأيدي والكود للدخول إلى اللعبة فوراً:",
            color=discord.Color.blue()
        )
        embed_room.add_field(name="🆔 ID الروم:", value=f"`{room_id}`", inline=False)
        embed_room.add_field(name="🔑 الكود (Pass):", value=f"`{room_pass}`", inline=False)

        finish_view = View(timeout=None)
        finish_btn = Button(label="🏁 إنهاء المباراة والبدء بالتصويت", style=discord.ButtonStyle.primary)

        async def finish_callback(btn_interaction):
            voting_view = VotingView(all_players, self.match_text_channel, self.v1, self.v2)
            await btn_interaction.response.send_message("🗳️ **بدأ التصويت!** اختر أفضل لاعب وأسوأ لاعب:", view=voting_view)

        finish_btn.callback = finish_callback
        finish_view.add_item(finish_btn)

        mentions = " ".join([m.mention for m in all_players])
        await self.match_text_channel.send(content=f"🔔 تنبيه للاعبين: {mentions}", embed=embed_room, view=finish_finish_view if 'finish_finish_view' in locals() else finish_view)

@bot.event
async def on_ready():
    print(f"تم تشغيل البوت بنجاح باسم: {bot.user}")

@bot.command()
async def play(ctx):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        return await ctx.send("❌ لا يمكنك استخدام هذا الأمر إلا في الرومات المخصصة للألعاب!", delete_after=5)

    view = ModeSelectionView(host=ctx.author)
    await ctx.send("اختر نمط اللعبة للبدء:", view=view)

@bot.command()
async def rank(ctx, member: discord.Member = None):
    target = member or ctx.author
    rank_pts = get_mvp_rank(target.id)
    await ctx.send(f"👤 **{target.display_name}** عنده ⭐ **Rank #{rank_pts}** (MVP)")

bot.run('')