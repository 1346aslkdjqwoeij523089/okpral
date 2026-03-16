import asyncio
import nextcord
from nextcord.ext import commands, tasks
import json
import os
from datetime import datetime
import threading
from flask import Flask

TOKEN = 'your_token_here'

GUILD_ID = 1464682632204779602
COLOR = 0x004bae

WELCOME_CHAN = 1464682633371062293
MEMBER_VC = 1471478613038600328
SESSION_CHAN = 1464682633559801939
STATUS_CHAN = 1480013219199451308
STAFF_CHAN = 1464682633853407327

EXEC = 1466490625259212821
FOUNDATION = 1464682632754233539
MGMT = 1464682632754233535
DEV = 1479003906531917886
SESSION_PING = 1465771610312278180

DMUSER = [EXEC, DEV]
DMROLE = [FOUNDATION, DEV]
SESSION_MGMT = [MGMT]

OFFICIAL = '<:Offical_server:1475860128686411837>'
CHECK = '<:Checkmark:1480018743714386070>'

WELCOME_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479260063192584273/welcomelarp.png?ex=69ae06ca&is=69acb54a&hm=e3cf31d81d9dee35659908000b6d6ad4c2cc9831e57c719cac8c7a6e8d7bfc85&'
SESSION_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1480012702364729364/sessionlarp.png?ex=69ae20bd&is=69accf3d&hm=13f0c90d0443f5e92ad69c9fd2202cef84d275e77b66c202feef7c5adc6a2e02&'
FOOTER_IMG = 'https://cdn.discordapp.com/attachments/1479259996846948483/1479264148000084051/larpfooter.png?ex=69ae0a98&is=69acb918&hm=db4ef1355243a7819a118ee42334cf234f8362d362bb73ed3aa1f589f9762d2e&'

AFK_FILE = 'afk.json'
SESSION_FILE = 'sessions.json'
LOGS_FILE = 'logs.txt'

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

client = commands.Bot(command_prefix='<', intents=intents)

flask_app = Flask(__name__)

@flask_app.route('/')
def keepalive():
    return 'LARP alive'

def create_embed(title, desc, img_top=None, img_bot=None):
    embed = nextcord.Embed(title=title, description=desc, color=COLOR)
    if img_top:
        embed.set_image(url=img_top)
    if img_bot:
        embed.set_thumbnail(url=img_bot)
    embed.timestamp = datetime.now()
    embed.set_footer(text='Los Angeles Roleplay')
    return embed

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def has_role(member, roles):
    return any(r.id in roles for r in member.roles)

async def log_action(action):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(LOGS_FILE, 'a') as f:
        f.write(f'[{ts}] {action}\n')

async def del_msgs(guild):
    chan = guild.get_channel(SESSION_CHAN)
    if chan:
        msg_list = []
        async for m in chan.history(limit=100):
            if m.id != PINNED_MSG_ID:
                msg_list.append(m)
        if msg_list:
            await chan.delete_messages(msg_list)

async def update_status(guild, active):
    chan = guild.get_channel(STATUS_CHAN)
    if chan:
        name = 'Sessions: 🟢' if active else 'Sessions: 🔴'
        await chan.edit(name=name)

async def staff_msg(guild, title, desc, img_top=None, img_bot=None, ping=True):
    chan = guild.get_channel(STAFF_CHAN)
    if chan:
        embed = create_embed(title, desc, img_top, img_bot)
        content = f'<@&{SESSION_PING_ROLE}>' if ping else ''
        return await chan.send(content=content, embed=embed)

@client.event
async def on_ready():
    synced = await client.sync_all_application_commands()
    print(f'{client.user} ready. Synced {synced}')
    member_count.start()
    session_check.start()

@client.event
async def on_member_join(member):
    chan = client.get_channel(WELCOME_CHAN)
    if chan:
        embed = create_embed('', img_top=WELCOME_IMG)
        await chan.send(f'{member.mention}', embed=embed)

@client.event
async def on_message(msg):
    if msg.author.bot:
        return
    afk = load_json(AFK_FILE)
    uid = str(msg.author.id)
    if uid in afk:
        old_nick = afk[uid].get('orig_nick', msg.author.display_name)
        await msg.author.edit(nick=old_nick)
        mentions = afk[uid].get('mentions', [])
        reason = afk[uid]['reason']
        desc = f'You are back from AFK ({reason}). Missed {len(mentions)} mentions.'
        embed = create_embed(f'{msg.author.display_name}', desc)
        await msg.reply(embed=embed)
        del afk[uid]
        save_json(AFK_FILE, afk)
    for m in msg.mentions:
        mid = str(m.id)
        if mid in afk:
            await msg.reply(f'{m.display_name} is AFK: {afk[mid]["reason"]}')
            afk[mid]['mentions'].append(msg.id)
    save_json(AFK_FILE, afk)
    await client.process_commands(msg)

@client.hybrid_command(guild_ids=[GUILD_ID])
async def afk(ctx, reason: str = "No reason"):
    afk = load_json(AFK_FILE)
    uid = str(ctx.author.id)
    old_nick = ctx.author.display_name
    await ctx.author.edit(nick=f'AFK • {old_nick}')
    afk[uid] = {'reason': reason, 'orig_nick': old_nick, 'mentions': []}
    save_json(AFK_FILE, afk)
    embed = create_embed(f'{ctx.author.display_name}', f'AFK: {reason}')
    await ctx.reply(embed=embed)

@client.hybrid_command(guild_ids=[GUILD_ID])
async def dmuser(ctx, user: nextcord.User, *, msg: str):
    if not has_role(ctx.author, DMUSER_ROLES):
        return await ctx.reply('No perms', ephemeral=True)
    embed = create_embed('LARP DM', f'From **{ctx.author.display_name}**:\n> {msg}')
    embed.set_footer(text=f'Sent at <t:F>')
    await user.send(embed=embed)
    await ctx.reply('Sent', ephemeral=True)

@client.hybrid_command(guild_ids=[GUILD_ID])
async def dmrole(ctx, role: nextcord.Role, *, msg: str):
    if not has_role(ctx.author, DMROLE_ROLES):
        return await ctx.reply('No perms', ephemeral=True)
    success = 0
    for m in role.members:
        try:
            embed = create_embed('LARP DM', f'From **{ctx.author.display_name}**:\n> {msg}')
            embed.set_footer(text=f'Sent at <t:F>')
            await m.send(embed=embed)
            success += 1
        except:
            pass
    await ctx.reply(f'Sent to {success}/{len(role.members)}', ephemeral=True)

class VoteModal(Modal):
    def __init__(self):
        super().__init__(title="Votes Needed")
        self.add_item(nextcord.ui.TextInput(label="Votes needed", default="10"))

    async def callback(self, interaction):
        try:
            need = int(self.children[0].value)
        except:
            return await interaction.response.send_message("Invalid", ephemeral=True)
        guild = interaction.guild
        embed = create_embed("Session Voting", f"Voting by {interaction.user.mention}. React {CHECK_EMOJI} {need} times.", SESSION_IMG, FOOTER_IMG)
        msg = await staff_msg(guild, "", "", True)
        await msg.add_reaction(CHECK_EMOJI)
        sessions = load_json(SESSION_FILE)
        sessions['voting_id'] = msg.id
        sessions['vote_need'] = need
        save_json(SESSION_FILE, sessions)
        await interaction.response.send_message(f"Voting: {need}", ephemeral=True)

class SessionView(View):
    def __init__(self):
        super().__init__(timeout=900)
        self.add_item(Button(label="Boost", style=ButtonStyle.blurple, custom_id="boost"))
        self.add_item(Button(label="Shutdown", style=ButtonStyle.red, custom_id="shutdown"))
        self.add_item(Button(label="Full", style=ButtonStyle.green, custom_id="full"))
        self.add_item(Button(label="Vote", style=ButtonStyle.grey, custom_id="vote"))
        self.add_item(Button(label="Start", style=ButtonStyle.blue, custom_id="start"))

    async def boost_callback(self, interaction):
        guild = interaction.guild
        sessions = load_json(SESSION_FILE)
        if not sessions.get('active'):
            await interaction.response.send_message("Not active", ephemeral=True)
            return
        desc = "Session low on players. Join up!"
        embed = create_embed("Session Boost", desc, img_bot=FOOTER_IMG)
        chan = guild.get_channel(STAFF_CHAN)
        await chan.send(f'<@&{SESSION_PING_ROLE}>', embed=embed)
        await del_msgs(guild)
        await interaction.response.send_message("Boosted", ephemeral=True)

    # Add other callbacks similarly

@tasks.loop(minutes=15)
async def member_count():
    guild = client.get_guild(GUILD_ID)
    if guild:
        humans = guild.member_count - len([m for m in guild.members if m.bot])
        vc = guild.get_channel(MEMBER_VC)
        if vc:
            await vc.edit(name=f'Members: {humans}')

if __name__ == '__main__':
    threading.Thread(target=flask_app.run, kwargs={'port': 5000, 'debug': False}, daemon=True).start()
    os.makedirs('data', exist_ok=True)
    client.run(TOKEN)

