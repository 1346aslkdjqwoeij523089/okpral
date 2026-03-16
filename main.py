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
import aiofiles

# Constants
TOKEN = 'your_token_here'  # Output this name

GUILD_ID = 1464682632204779602
COLOR = 0x004bae
PREFIX = '<'

# Channels
WELCOME_CHAN = 1464682633371062293
MEMBER_VC = 1471478613038600328
SESSION_CHAN = 1464682633559801939  # Main session actions chan
SESSION_STATUS_CHAN = 1480013219199451308
STAFFCHAT_CHAN = 1464682633853407327
LOG_CHAN = 1480024519677706382
PINNED_MSG_ID = 1480023088799416451  # Session chan pinned link msg ID

# Roles
EXEC_ROLE = 1466490625259212821
FOUNDATION_ROLE = 1464682632754233539
MGMT_ROLE = 1464682632754233535
DEV_ROLE = 1479003906531917886
SESSION_PING_ROLE = 1465771610312278180

# Staff perm lists
DMUSER_ROLES = [EXEC_ROLE, DEV_ROLE]
DMROLE_ROLES = [FOUNDATION_ROLE, DEV_ROLE]
SESSION_ROLES = [MGMT_ROLE]  # Add High if needed

# Emojis
OFFICIAL_EMOJI = '<:Offical_server:1475860128686411837>'
CHECK_EMOJI = '<:Checkmark:1480018743714386070>'

# Images
WELCOME_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ae06ca&is=69acb54a&hm=e3cf31d81d9dee35659908000b6d6ad4c2cc9831e57c719cac8c7a6e8d7bfc85&'
SESSION_IMG_TOP = 'https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&'
FOOTER_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&'

# Data dirs/files
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
tree = app_commands.CommandTree(bot)

# Slash versions of prefix cmds
@tree.command(guild=discord.Object(id=GUILD_ID), name='afk', description='Set AFK')
@app_commands.describe(reason='Reason')
async def slash_afk(interaction: discord.Interaction, reason: str = 'No reason'):
    member = interaction.guild.get_member(interaction.user.id)
    old_nick = member.nick or interaction.user.name
    new_nick = f'AFK • {old_nick}'
    await member.edit(nick=new_nick)
    
    afk_data = await load_json(AFK_FILE)
    afk_data[str(interaction.user.id)] = {'reason': reason, 'original_nick': old_nick, 'mentions': []}
    await save_json(AFK_FILE, afk_data)
    
    embed = await create_embed(f'**{interaction.user.display_name}**', f'> AFK for **{reason}** set.')
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(guild=discord.Object(id=GUILD_ID), name='dmuser', description='DM user')
@app_commands.describe(user='User', message='Msg')
async def slash_dmuser(interaction: discord.Interaction, user: discord.User, message: str):
    if not has_any_role(interaction.user, DMUSER_ROLES):
        return await interaction.response.send_message('No perms', ephemeral=True)
    try:
        embed = discord.Embed(title=f'{OFFICIAL_EMOJI} __𝓛𝓐𝓡𝓟 DM__', description=f'From **{interaction.user.display_name}**:\n> {message}', color=COLOR)
        embed.set_footer(text=f'Sent at <t:F>')
        await user.send(embed=embed)
        await interaction.response.send_message('Sent!', ephemeral=True)
    except:
        await interaction.response.send_message('DM fail', ephemeral=True)

@tree.command(guild=discord.Object(id=GUILD_ID), name='dmrole', description='DM role')
@app_commands.describe(role='Role', message='Msg')
async def slash_dmrole(interaction: discord.Interaction, role: discord.Role, message: str):
    if not has_any_role(interaction.user, DMROLE_ROLES):
        return await interaction.response.send_message('No perms', ephemeral=True)
    success = 0
    for m in role.members:
        try:
            embed = discord.Embed(title=f'{OFFICIAL_EMOJI} __𝓛𝓐𝓡𝓟 DM__', description=f'From **{interaction.user.display_name}**:\n> {message}', color=COLOR)
            embed.set_footer(text=f'Sent at <t:F>')
            await m.send(embed=embed)
            success += 1
        except:
            pass
    await interaction.response.send_message(f'Sent {success}/{len(role.members)}', ephemeral=True)

@tree.command(guild=discord.Object(id=GUILD_ID), name='sessions', description='Session panel (private)')
async def slash_sessions(interaction: discord.Interaction):
    if not has_any_role(interaction.user, SESSION_ROLES):
        embed = discord.Embed(description='Only Management+ permitted.', color=COLOR)
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    status_chan = bot.get_channel(SESSION_STATUS_CHAN)
    active = status_chan and '🟢' in status_chan.name if status_chan else False
    desc = '**Session Management**\\nWelcome {mention}.\\nStatus: {"active" if active else "inactive"}'
    if active:
        desc += '\\nBoost, Shutdown, Full'
    else:
        desc += '\\nVote, Start'
    embed = await create_embed(f'{OFFICIAL_EMOJI} Session Mgmt', desc.format(mention=interaction.user.mention))
    embed.set_image(url=SESSION_IMG_TOP)
    view = SessionView()  # Step 7
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

flask_app = Flask(__name__)

@flask_app.route('/keepalive')
def keepalive():
    return 'Bot is alive!'

async def create_embed(title, description='', img_top=None, img_bot=None, fields=None):
    embed = discord.Embed(title=title, description=description, color=COLOR)
    if img_top:
        embed.set_image(url=img_top)
    if img_bot:
        embed.set_thumbnail(url=img_bot)  # or set_footer icon?
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    embed.timestamp = datetime.now()
    embed.set_footer(text='Los Angeles Roleplay')
    return embed

async def load_json(file_path):
    try:
        async with aiofiles.open(file_path, 'r') as f:
            return json.loads(await f.read())
    except FileNotFoundError:
        return {}

async def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    async with aiofiles.open(file_path, 'w') as f:
        await f.write(json.dumps(data, indent=2))

async def log_action(action: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f'[{timestamp}] {action}\\n'
    log_file = os.path.join(LOGISTICS_DIR, 'actions.txt')
    async with aiofiles.open(log_file, 'a') as f:
        await f.write(log_entry)

async def del_session_msgs(guild):
    chan = guild.get_channel(SESSION_CHAN)
    if not chan:
        return
    msgs = [m async for m in chan.history(limit=100)]
    to_del = [m for m in msgs if m.id != PINNED_MSG_ID]
    if to_del:
        await chan.delete_messages(to_del)
    
async def update_status_chan(guild, active):
    chan = guild.get_channel(SESSION_STATUS_CHAN)
    if chan:
        name = 'Sessions: 🟢' if active else 'Sessions: 🔴'
        await chan.edit(name=name)

async def send_staff_announce(guild, title, desc, img_top=None, img_bot=None, ping_session=True):
    chan = guild.get_channel(STAFFCHAT_CHAN)
    if chan:
        embed = await create_embed(title, desc, img_top, img_bot)
        content = f'{bot.get_role(SESSION_PING_ROLE).mention}' if ping_session else ''
        msg = await chan.send(content=content, embed=embed)
        return msg

def has_any_role(member, role_ids):
    return any(role.id in role_ids for role in member.roles)

@bot.event
async def on_ready():
    print(f'{bot.user} logged in')
    synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f'Synced {len(synced)} slash cmds')
    member_count_task.start()
    session_check_task.start()

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHAN)
    if channel:
        embed = await create_embed('Welcome!', img_top=WELCOME_IMG)
        await channel.send(f'{member.mention}', embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    afk_data = await load_json(AFK_FILE)
    user_id = str(message.author.id)
    
    # Check if author is AFK, remove on first msg
    if user_id in afk_data:
        # Remove AFK
        old_nick = afk_data[user_id].get('original_nick', message.author.nick or message.author.name)
        await message.author.edit(nick=old_nick)
        mentions = afk_data[user_id].get('mentions', [])
        reason = afk_data[user_id]['reason']
        
        desc = f'**{message.author.display_name}**\n> You are now back from AFK [{reason}].\n'
        if mentions:
            desc += f'> Missed mentions from: {len(mentions)} users.'
        embed = await create_embed('AFK Status', desc)
        await message.reply(embed=embed, mention_author=False)
        
        del afk_data[user_id]
        await save_json(AFK_FILE, afk_data)
    
    # Check mentions for AFK users
    for mention in message.mentions:
        afk_id = str(mention.id)
        if afk_id in afk_data:
            reason = afk_data[afk_id]['reason']
            await message.reply(f'{mention.display_name} is currently AFK: {reason}', mention_author=False)
    
    # Add msg to afk mentions
    afk_changed = False
    for mention in message.mentions:
        afk_id = str(mention.id)
        if afk_id in afk_data:
            afk_data[afk_id]['mentions'].append(str(message.id))
            afk_changed = True
    if afk_changed:
        await save_json(AFK_FILE, afk_data)
    
    await bot.process_commands(message)

@bot.command()
async def afk(ctx, *, reason='No reason provided'):
    afk_data = await load_json(AFK_FILE)
    user_id = str(ctx.author.id)
    old_nick = ctx.author.nick or ctx.author.name
    new_nick = f'AFK • {old_nick}'
    
    await ctx.author.edit(nick=new_nick)
    afk_data[user_id] = {'reason': reason, 'original_nick': old_nick, 'mentions': []}
    await save_json(AFK_FILE, afk_data)
    
    embed = await create_embed(
        f'**{ctx.author.display_name}**',
        f'> You are now away from your keyboard [AFK] for **{reason}**.\\n> Members will be notified about your status.'
    )
    await ctx.reply(embed=embed, mention_author=False)

@bot.command(name='dmuser')
async def dm_user(ctx, user: discord.User, *, message=''):
    if not has_any_role(ctx.author, DMUSER_ROLES):
        await ctx.reply('No perms', ephemeral=True, delete_after=5)
        return
    try:
        embed = discord.Embed(
            title=f'{OFFICIAL_EMOJI} __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__',
            description=f'> From **{ctx.author.nick or ctx.author.name}**:\\n> {message}',
            color=COLOR
        )
        embed.set_footer(text=f'Sent at <t:F>')
        await user.send(embed=embed)
        await ctx.reply('DM sent!', ephemeral=True)
    except:
        await ctx.reply('Failed to DM', ephemeral=True)

@bot.command(name='dmrole')
async def dm_role(ctx, role: discord.Role, *, message=''):
    if not has_any_role(ctx.author, DMROLE_ROLES):
        await ctx.reply('No perms', ephemeral=True, delete_after=5)
        return
    guild = ctx.guild
    success = 0
    for member in role.members:
        try:
            embed = discord.Embed(
                title=f'{OFFICIAL_EMOJI} __𝓛𝓐𝓡𝓟 - New Direct Message (DM)__',
                description=f'> From **{ctx.author.nick or ctx.author.name}**:\\n> {message}',
                color=COLOR
            )
            embed.set_footer(text=f'Sent at <t:F>')
            await member.send(embed=embed)
            success += 1
        except:
            pass
await ctx.reply(f'DM sent to {success}/{len(role.members)}', ephemeral=True)

class VoteModal(Modal):
    title = 'Session Vote - Votes Needed'
    
    threshold = ui.TextInput(
        label='How many votes would you like the session vote to receive in order to start up a session?',
        placeholder='e.g. 10',
        default='10'
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            need = int(self.threshold.value)
            if need < 1:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message('Invalid positive integer.', ephemeral=True)
        
        guild = interaction.guild
        embed = await create_embed(
            f'{OFFICIAL_EMOJI} | 𝓛𝓐𝓡𝓟 Session Voting',
            f'A session voting has been started by **{interaction.user.display_name}**. \n> - If you would like the session to start, please react below with {CHECK_EMOJI}. Once the session reaches **{need}**, the session will begin. \n> - Votes: 0/{need}',
            SESSION_IMG_TOP,
            FOOTER_IMG
        )
        msg = await send_staff_announce(guild, '', '', ping_session=True)
        await msg.add_reaction(CHECK_EMOJI)
        
        sessions = await load_json(SESSIONS_FILE)
        sessions['voting_msg_id'] = msg.id
        sessions['vote_need'] = need
        sessions['vote_current'] = 1  # bot
        sessions['vote_starter'] = str(interaction.user.id)
        await save_json(SESSIONS_FILE, sessions)
        
        await log_action(f'Session vote initiated by {interaction.user.display_name} (need {need})')
        await interaction.response.send_message(f'Session vote started! Need {need} votes.', ephemeral=True)

class SessionView(View):
    def __init__(self):
        super().__init__(timeout=900)
        self.boost_btn = Button(label='Boost', style=discord.ButtonStyle.blurple, custom_id='boost_s')
        self.shutdown_btn = Button(label='Shutdown', style=discord.ButtonStyle.danger, custom_id='shutdown_s')
        self.full_btn = Button(label='Full', style=discord.ButtonStyle.success, custom_id='full_s')
        self.vote_btn = Button(label='Vote', style=discord.ButtonStyle.secondary, custom_id='vote_s')
        self.start_btn = Button(label='Start', style=discord.ButtonStyle.primary, custom_id='start_s')
        self.add_item(self.boost_btn)
        self.add_item(self.shutdown_btn)
        self.add_item(self.full_btn)
        self.add_item(self.vote_btn)
        self.add_item(self.start_btn)

    @boost_btn.callback
    async def boost_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if not sessions.get('active', False):
            return await interaction.response.send_message('Session not active.', ephemeral=True)
        
        low_desc = '@everyone, {session_ping}\\nThe session is currently running **low** on players. Please join up to ensure that the server can be full!'
        # ping already in send_staff_announce
        await send_staff_announce(guild, f'{OFFICIAL_EMOJI} Session Low', low_desc.replace('{session_ping}', f'<@&{SESSION_PING_ROLE}>'), img_bot=FOOTER_IMG)
        await del_session_msgs(guild)
        await log_action(f'Session boosted by {interaction.user.display_name}')
        await interaction.response.send_message('Boost announced.', ephemeral=True)

    @shutdown_btn.callback
    async def shutdown_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        start_time = sessions.get('start_time', 0)
        if time.time() - start_time < 900:
            return await interaction.response.send_message('Cannot shutdown within 15 minutes of start.', ephemeral=True)
        
        sessions['active'] = False
        await save_json(SESSIONS_FILE, sessions)
        await update_status_chan(guild, False)
        shutdown_desc = f'A session has been shut down by **{interaction.user.display_name}**. Thank you for joining today’s session. See you soon!'
        await send_staff_announce(guild, 'Session Shutdown', shutdown_desc, img_bot=FOOTER_IMG, ping_session=False)
        await del_session_msgs(guild)
        await log_action(f'Session shutdown by {interaction.user.display_name}')
        await interaction.response.send_message('Shutdown complete.', ephemeral=True)

    @full_btn.callback
    async def full_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if not sessions.get('active', False):
            return await interaction.response.send_message('Session not active.', ephemeral=True)
        
        full_desc = 'The session has officially become full. Thank you so much for bringing up activity! There may be a queue in Los Angeles Roleplay.'
        await send_staff_announce(guild, 'Session Full', full_desc, img_bot=FOOTER_IMG, ping_session=False)
        # no del for full
        await log_action(f'Session full alert by {interaction.user.display_name}')
        await interaction.response.send_message('Full alert sent.', ephemeral=True)

    @vote_btn.callback
    async def vote_callback(self, interaction: discord.Interaction):
        modal = VoteModal()
        await interaction.response.send_modal(modal)

    @start_btn.callback
    async def start_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        sessions = await load_json(SESSIONS_FILE)
        if sessions.get('active', False):
            return await interaction.response.send_message('Session already active.', ephemeral=True)
        
        sessions['active'] = True
        sessions['starter_id'] = str(interaction.user.id)
        sessions['start_time'] = time.time()
        await save_json(SESSIONS_FILE, sessions)
        await update_status_chan(guild, True)
        start_desc = 'After votes have been received, a session has begun in Los Angeles Roleplay. Please refer below for more information. \n- In-Game Code: L'
        await send_staff_announce(guild, f'{OFFICIAL_EMOJI} | 𝓛𝓐𝓡𝓟 Session Start', start_desc, SESSION_IMG_TOP, FOOTER_IMG, ping_session=True)
        await del_session_msgs(guild)
        await log_action(f'Session started by {interaction.user.display_name}')
        await interaction.response.send_message('Session started.', ephemeral=True)

class SessionCheckView(View):
    def __init__(self):
        super().__init__(timeout=7200)  # 2h
        options = [
            discord.SelectOption(label='Yes', value='yes'),
            discord.SelectOption(label='No', value='no')
        ]
        self.select = Select(placeholder='Is the session still active?', options=options)
        self.select.callback = self.select_cb
        self.add_item(self.select)

    async def select_cb(self, interaction: discord.Interaction):
        guild = bot.get_guild(GUILD_ID)
        if interaction.data['values'][0] == 'no':
            sessions = await load_json(SESSIONS_FILE)
            sessions['active'] = False
            await save_json(SESSIONS_FILE, sessions)
            await update_status_chan(guild, False)
            shutdown_desc = 'Session auto shutdown from check.'
            await send_staff_announce(guild, 'Session Shutdown', shutdown_desc, img_bot=FOOTER_IMG)
            await del_session_msgs(guild)
            await log_action(f'Session shutdown from DM check by {interaction.user.display_name}')
        await interaction.response.send_message('Response noted.', ephemeral=True)

# Add prefix sessions
@bot.command(name='sessions', aliases=['p', 'pr', 'pri', 'priv', 'priva', 'privat'])
async def prefix_sessions(ctx):
    if not has_any_role(ctx.author, SESSION_ROLES):
        embed = discord.Embed(description='Only Management+ staff members of Los Angeles Roleplay are permitted to manage a session. Refrain from using this command again, unless you become Management.', color=COLOR)
        await ctx.reply(embed=embed, ephemeral=True)
        try:
            await ctx.message.delete()
        except:
            pass
        return
    
    status_chan = bot.get_channel(SESSION_STATUS_CHAN)
    active_text = 'currently active' if status_chan and '🟢' in status_chan.name else 'currently inactive'
    desc = f'Welcome, {ctx.author.mention}. Thanks for opening Los Angeles Roleplay\\'s Session Management panel.\\n\\nThe Session is **{active_text}**.\\n\\n'
    if status_chan and '🟢' in status_chan.name:
        desc += '> - 1. **Boost** the Session. \n> - 2. **Shutdown** the Session. \n> - 3. **Alert** that the Session is full.'
    else:
        desc += '> - 1. Initiate a Session **Vote**. \n> - 2. **Start** a new Session.'
    
    embed1 = discord.Embed(title=f'{OFFICIAL_EMOJI} | Session Management__', description=desc, color=COLOR)
    embed1.set_image(url=SESSION_IMG_TOP)
    
    embed2 = discord.Embed().set_thumbnail(url=FOOTER_IMG)
    
    view = SessionView()
    await ctx.reply(embeds=[embed1, embed2], view=view, ephemeral=True)

# Tasks placeholder
@tasks.loop(seconds=900)
async def member_count_task():
    guild = bot.get_guild(GUILD_ID)
    if not guild or not guild.chunked:
        return
    humans = sum(1 for m in guild.members if not m.bot)
    voice = guild.get_channel(MEMBER_VC)
    if voice and voice.guild_permissions_for(guild.me).manage_channels:
        await voice.edit(name=f'Members: {humans}')
    print(f'Updated member count to {humans}')

@tasks.loop(seconds=3600)
async def session_check_task():
    sessions = await load_json(SESSIONS_FILE)
    if not sessions.get('active'):
        return
    start_time = sessions.get('start_time', 0)
    if time.time() - start_time < 3600:
        return
    starter_id = sessions.get('starter_id')
    starter = bot.get_user(int(starter_id)) if starter_id else None
    if starter:
        embed = await create_embed(
            f'{OFFICIAL_EMOJI} | Session Management',
            'As the session was started by you approximately an hour ago, please answer this question:\\n> Is it currently still active?'
        )
        embed.set_image(url=SESSION_IMG_TOP)
        embed.set_thumbnail(url=FOOTER_IMG)
        view = SessionCheckView(bot, sessions['message_id'])  # Later define
        try:
            msg = await starter.send(embed=embed, view=view)
            sessions['dm_msg_id'] = msg.id
            await save_json(SESSIONS_FILE, sessions)
        except discord.Forbidden:
            pass  # Later escalate
    # TODO: escalate to Exec/Mgmt if no resp after 1h, auto shutdown 2h

if __name__ == '__main__':
    # Start flask in thread
    threading.Thread(target=flask_app.run, kwargs={'port': 5000, 'threaded': True}, daemon=True).start()
    
    # Ensure data dir
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGISTICS_DIR, exist_ok=True)
    
    bot.run(TOKEN)
