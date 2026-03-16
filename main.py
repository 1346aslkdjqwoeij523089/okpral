import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiofiles
import json
import os
from datetime import datetime
import threading
from flask import Flask
import time
from discord.ui import View, Button, Select, Modal

# Constants
TOKEN = 'your_token_here'  # Replace with your bot token

GUILD_ID = 1464682632204779602
COLOR = 0x004bae
PREFIX = '<'

# Channels
WELCOME_CHAN = 1464682633371062293
MEMBER_VC = 1471478613038600328
SESSION_CHAN = 1464682633559801939
SESSION_STATUS_CHAN = 1480013219199451308
STAFFCHAT_CHAN = 1464682633853407327
LOG_CHAN = 1480024519677706382
PINNED_MSG_ID = 1480023088799416451

# Roles
EXEC_ROLE = 1466490625259212821
FOUNDATION_ROLE = 1464682632754233539
MGMT_ROLE = 1464682632754233535
DEV_ROLE = 1479003906531917886
SESSION_PING_ROLE = 1465771610312278180

# Staff perms
DMUSER_ROLES = [EXEC_ROLE, DEV_ROLE]
DMROLE_ROLES = [FOUNDATION_ROLE, DEV_ROLE]
SESSION_ROLES = [MGMT_ROLE]

# Emojis
OFFICIAL_EMOJI = '<:Offical_server:1475860128686411837>'
CHECK_EMOJI = '<:Checkmark:1480018743714386070>'

# Images
WELCOME_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ae06ca&is=69acb54a&hm=e3cf31d81d9dee35659908000b6d6ad4c2cc9831e57c719cac8c7a6e8d7bfc85&'
SESSION_IMG_TOP = 'https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&'
FOOTER_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&'

# Data
DATA_DIR = 'data'
AFK_FILE = os.path.join(DATA_DIR, 'afk.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')
LOGISTICS_DIR = os.path.join(DATA_DIR, 'logistics')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guild_messages = True
intents.message_reactions = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

flask_app = Flask(__name__)

@flask_app.route('/keepalive')
def keepalive():
    return 'alive'

async def create_embed(title, desc='', img_top=None, img_bot=None):
    embed = discord.Embed(title=title, description=desc, color=COLOR)
    if img_top:
        embed.set_image(url=img_top)
    if img_bot:
        embed.set_thumbnail(url=img_bot)
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text='Los Angeles Roleplay')
    return embed

async def load_json(path):
    try:
        async with aiofiles.open(path, 'r') as f:
            return json.loads(await f.read())
    except:
        return {}

async def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, 'w') as f:
        await f.write(json.dumps(data, indent=2))

def has_any_role(member, roles):
    return any(r.id in roles for r in member.roles)

async def log_action(action):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f'[{ts}] {action}\n'
    path = os.path.join(LOGISTICS_DIR, 'actions.txt')
    async with aiofiles.open(path, 'a') as f:
        await f.write(entry)

async def del_session_msgs(guild):
    chan = guild.get_channel(SESSION_CHAN)
    if not chan:
        return
    msg_list = [m async for m in chan.history(limit=100)]
    to_del = [m for m in msg_list if m.id != PINNED_MSG_ID]
    if to_del:
        await chan.delete_messages(to_del)

async def update_status(guild, active):
    chan = guild.get_channel(SESSION_STATUS_CHAN)
    if chan:
        name = 'Sessions: 🟢' if active else 'Sessions: 🔴'
        await chan.edit(name=name)

async def staff_announce(guild, title, desc, img_top=None, img_bot=None, ping=True):
    chan = guild.get_channel(STAFFCHAT_CHAN)
    if chan:
        embed = await create_embed(title, desc, img_top, img_bot)
        content = f'<@&{SESSION_PING_ROLE}> ' if ping else ''
        return await chan.send(content=content, embed=embed)

@bot.event
async def on_ready():
    synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'{bot.user} ready | Synced {len(synced)} cmds')
    member_count.start()
    session_check.start()

@bot.event
async def on_member_join(member):
    chan = bot.get_channel(WELCOME_CHAN)
    if chan:
        embed = await create_embed('Welcome', img_top=WELCOME_IMG)
        await chan.send(f'{member.mention}', embed=embed)

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    afk = await load_json(AFK_FILE)
    uid = str(msg.author.id)
    if uid in afk:
        old_nick = afk[uid].get('orig_nick', msg.author.nick or msg.author.name)
        await msg.author.edit(nick=old_nick)
        mentions = afk[uid].get('mentions', [])
        reason = afk[uid]['reason']
        desc = f'**{msg.author.display_name}** is back from AFK ({reason}). Missed {len(mentions)} mentions.'
        embed = await create_embed('AFK Off', desc)
        await msg.reply(embed=embed)
        del afk[uid]
        await save_json(AFK_FILE, afk)
    for m in msg.mentions:
        mid = str(m.id)
        if mid in afk:
            await msg.reply(f'{m.display_name} is AFK: {afk[mid]["reason"]}')
            afk[mid]['mentions'].append(str(msg.id))
    if any(mid in afk for mid in [str(m.id) for m in msg.mentions]):
        await save_json(AFK_FILE, afk)
    await bot.process_commands(msg)

@bot.command()
async def afk(ctx, *, reason="No reason"):
    afk = await load_json(AFK_FILE)
    uid = str(ctx.author.id)
    old_nick = ctx.author.nick or ctx.author.name
    await ctx.author.edit(nick=f'AFK • {old_nick}')
    afk[uid] = {'reason': reason, 'orig_nick': old_nick, 'mentions': []}
    await save_json(AFK_FILE, afk)
    embed = await create_embed(f'{ctx.author.display_name}', f'AFK: {reason}')
    await ctx.reply(embed=embed)

@bot.command(name='dmuser')
async def dm_user(ctx, user: discord.User, *, msg):
    if not has_any_role(ctx.author, DMUSER_ROLES):
        return await ctx.reply('No permission', delete_after=5)
    embed = discord.Embed(title=f'{OFFICIAL_EMOJI} LARP DM', description=f'From **{ctx.author.display_name}**:\n> {msg}', color=COLOR)
    embed.set_footer(text=f'Sent at <t:F>')
    await user.send(embed=embed)
    await ctx.reply('DM sent', ephemeral=True)

@bot.command(name='dmrole')
async def dm_role(ctx, role: discord.Role, *, msg):
    if not has_any_role(ctx.author, DMROLE_ROLES):
        return await ctx.reply('No permission', delete_after=5)
    success = 0
    for m in role.members:
        try:
            embed = discord.Embed(title=f'{OFFICIAL_EMOJI} LARP DM', description=f'From **{ctx.author.display_name}**:\n> {msg}', color=COLOR)
            embed.set_footer(text=f'Sent at <t:F>')
            await m.send(embed=embed)
            success += 1
        except:
            pass
    await ctx.reply(f'DM to {success}/{len(role.members)}', ephemeral=True)

@bot.command(name='sessions', aliases=['p', 'pr', 'pri', 'priv', 'priva', 'privat'])
async def sessions(ctx):
    if not has_any_role(ctx.author, SESSION_ROLES):
        embed = discord.Embed(description='Management+ only.', color=COLOR)
        await ctx.reply(embed=embed, ephemeral=True)
        await ctx.message.delete()
        return
    status_chan = bot.get_channel(SESSION_STATUS_CHAN)
    active = '🟢' in status_chan.name if status_chan else False
    desc = f'Welcome <@{ctx.author.id}>. Session **currently {"active" if active else "inactive"}**.'
    if active:
        desc += '\\nBoost | Shutdown | Full'
    else:
        desc += '\\nVote | Start'
    embed = await create_embed(f'{OFFICIAL_EMOJI} Session Mgmt', desc)
    embed.set_image(url=SESSION_IMG_TOP)
    view = SessionView()
    await ctx.reply(embed=embed, view=view, ephemeral=True)

# Views & Modals
class VoteModal(Modal):
    def __init__(self):
        super().__init__(title="Votes Needed")
        self.threshold = ui.TextInput(label="Votes to start session", default="10")

    async def on_submit(self, interaction):
        try:
            need = int(self.threshold.value)
        except:
            return await interaction.response.send_message("Invalid number", ephemeral=True)
        guild = interaction.guild
        embed = await create_embed("LARP Session Voting", f"Voting started by {interaction.user.display_name}. React {CHECK_EMOJI} {need} times.", SESSION_IMG_TOP, FOOTER_IMG)
        msg = await staff_announce(guild, "", "", True)
        await msg.add_reaction(CHECK_EMOJI)
        sessions = await load_json(SESSIONS_FILE)
        sessions['voting_msg_id'] = msg.id
        sessions['vote_need'] = need
        await save_json(SESSIONS_FILE, sessions)
        await interaction.response.send_message("Voting started", ephemeral=True)

class SessionView(View):
    def __init__(self):
        super().__init__(timeout=15*60)
        self.add_item(Button(label="Boost", style=ButtonStyle.blurple, custom_id="boost"))
        self.add_item(Button(label="Shutdown", style=ButtonStyle.red, custom_id="shutdown"))
        self.add_item(Button(label="Full", style=ButtonStyle.green, custom_id="full"))
        self.add_item(Button(label="Vote", style=ButtonStyle.grey, custom_id="vote"))
        self.add_item(Button(label="Start", style=ButtonStyle.blue, custom_id="start"))

    @discord.ui.button(label="Boost", style=discord.ButtonStyle.blurple, custom_id="boost")
    async def boost(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if not sessions.get('active'):
            return await interaction.response.send_message("Inactive", ephemeral=True)
        desc = "@here <@&1465771610312278180>\\nSession low on players, please join!"
        embed = await create_embed("Session Boost", desc, img_bot=FOOTER_IMG)
        chan = guild.get_channel(STAFFCHAT_CHAN)
        await chan.send(embed=embed)
        await del_session_msgs(guild)
        await interaction.response.send_message("Boosted", ephemeral=True)

    @discord.ui.button(label="Shutdown", style=discord.ButtonStyle.danger, custom_id="shutdown")
    async def shutdown(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if time.time() - sessions.get('start_time', 0) < 900:
            return await interaction.response.send_message("15min cooldown", ephemeral=True)
        sessions['active'] = False
        await save_json(SESSIONS_FILE, sessions)
        await update_status(guild, False)
        desc = f"Shutdown by **{interaction.user.display_name}**. Thanks for joining."
        embed = await create_embed("Session Shutdown", desc, img_bot=FOOTER_IMG)
        chan = guild.get_channel(STAFFCHAT_CHAN)
        await chan.send(embed=embed)
        await del_session_msgs(guild)
        await interaction.response.send_message("Shutdown", ephemeral=True)

    @discord.ui.button(label="Full", style=discord.ButtonStyle.success, custom_id="full")
    async def full(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if not sessions.get('active'):
            return await interaction.response.send_message("Inactive", ephemeral=True)
        desc = "Session full! Thanks for activity. Queue possible."
        embed = await create_embed("Session Full", desc, img_bot=FOOTER_IMG)
        chan = guild.get_channel(STAFFCHAT_CHAN)
        await chan.send(embed=embed)
        await interaction.response.send_message("Full announced", ephemeral=True)

    @discord.ui.button(label="Vote", style=discord.ButtonStyle.secondary, custom_id="vote")
    async def vote(self, interaction: discord.Interaction, button: Button):
        modal = VoteModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Start", style=discord.ButtonStyle.primary, custom_id="start")
    async def start(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if sessions.get('active'):
            return await interaction.response.send_message("Already active", ephemeral=True)
        sessions['active'] = True
        sessions['starter_id'] = str(interaction.user.id)
        sessions['start_time'] = time.time()
        await save_json(SESSIONS_FILE, sessions)
        await update_status(guild, True)
        desc = "Session started. In-Game Code: L"
        embed = await create_embed("LARP Session", desc, SESSION_IMG_TOP, FOOTER_IMG)
        chan = guild.get_channel(STAFFCHAT_CHAN)
        await chan.send(f'<@&{SESSION_PING_ROLE}>', embed=embed)
        await del_session_msgs(guild)
        await interaction.response.send_message("Started", ephemeral=True)

class SessionCheckView(View):
    def __init__(self):
        super().__init__(timeout=7200)
        options = [discord.SelectOption(label='Yes'), discord.SelectOption(label='No')]
        self.select = Select(placeholder='Session still active?', options=options, callback=self.check)
        self.add_item(self.select)

    async def check(self, interaction):
        guild = bot.get_guild(GUILD_ID)
        if 'No' in interaction.data['values']:
            sessions = await load_json(SESSIONS_FILE)
            sessions['active'] = False
            await save_json(SESSIONS_FILE, sessions)
            await update_status(guild, False)
            embed = await create_embed("Session Shutdown", "Auto shutdown from check.", img_bot=FOOTER_IMG)
            chan = guild.get_channel(STAFFCHAT_CHAN)
            await chan.send(embed=embed)
            await del_session_msgs(guild)
        await interaction.response.send_message("Noted", ephemeral=True)

@tasks.loop(seconds=900)
async def member_count():
    guild = bot.get_guild(GUILD_ID)
    if guild:
        humans = len([m for m in guild.members if not m.bot])
        vc = guild.get_channel(MEMBER_VC)
        if vc:
            await vc.edit(name=f'Members: {humans}')

@tasks.loop(seconds=3600)
async def session_check():
    sessions = await load_json(SESSIONS_FILE)
    if sessions.get('active'):
        start = sessions.get('start_time', 0)
        if time.time() - start > 7200:
            # auto shutdown 2h
            sessions['active'] = False
            await save_json(SESSIONS_FILE, sessions)
            guild = bot.get_guild(GUILD_ID)
            await update_status(guild, False)
            embed = await create_embed("Auto Shutdown", "No response after 2h.")
            chan = guild.get_channel(STAFFCHAT_CHAN)
            await chan.send(embed=embed)
            await del_session_msgs(guild)
            return
        if time.time() - sessions.get('last_ping', start) > 3600:
            # ping exec mgmt
            guild = bot.get_guild(GUILD_ID)
            embed = await create_embed("Session Check", "Is session still active?", SESSION_IMG_TOP, FOOTER_IMG)
            view = SessionCheckView()
            for role_id in [EXEC_ROLE, MGMT_ROLE]:
                role = guild.get_role(role_id)
                if role:
                    for m in role.members[:10]:  # limit
                        try:
                            await m.send(embed=embed, view=view)
                        except:
                            pass
            sessions['last_ping'] = time.time()
            await save_json(SESSIONS_FILE, sessions)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id or payload.channel_id != STAFFCHAT_CHAN:
        return
    if str(payload.emoji) != CHECK_EMOJI:
        return
    sessions = await load_json(SESSIONS_FILE)
    if 'voting_msg_id' not in sessions or payload.message_id != sessions['voting_msg_id']:
        return
    chan = bot.get_channel(payload.channel_id)
    msg = await chan.fetch_message(payload.message_id)
    reaction = discord.utils.find(lambda r: str(r.emoji) == CHECK_EMOJI, msg.reactions)
    if reaction and reaction.count - 1 >= sessions['vote_need']:
        guild = bot.get_guild(GUILD_ID)
        starter_id = sessions['vote_starter']
        content = f'<@{starter_id}>: Session Vote reached `{reaction.count - 1}/{sessions["vote_need"]}`. Begin?'
        await chan.send(content)
        # start
        sessions['active'] = True
        sessions['starter_id'] = starter_id
        sessions['start_time'] = time.time()
        del sessions['voting_msg_id']
        await save_json(SESSIONS_FILE, sessions)
        await update_status(guild, True)
        desc = "Session begun. In-Game Code: L"
        embed = await create_embed("LARP Session Start", desc, SESSION_IMG_TOP, FOOTER_IMG)
        await staff_announce(guild, "", "", True)
        await del_session_msgs(guild)
        await log_action("Session from vote")

@bot.tree.command(guild=discord.Object(id=GUILD_ID), name="logs", description="Recent logs")
async def slash_logs(interaction):
    path = os.path.join(LOGISTICS_DIR, 'actions.txt')
    if not os.path.exists(path):
        return await interaction.response.send_message("No logs", ephemeral=True)
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()
    lines = content.splitlines()[-10:]
    desc = "\n".join(lines) if lines else "Empty"
    embed = await create_embed("Recent Actions", desc)
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == '__main__':
    threading.Thread(target=flask_app.run, port=5000, threaded=True, daemon=True).start()
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGISTICS_DIR, exist_ok=True)
    bot.run(TOKEN)

