#!/usr/bin/env python3
import interactions
import os
import sys
import logging
import time
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from discordUser import *
from database import *
from constants import GUILDS, ROLES, MESSAGES, CHANNELS, USERS, roleText
from embeds import WELCOME, PLAYER_CARD, BYE
from custom_formatter import CustomFormatter

load_dotenv(".env")
DEBUG = int(os.environ.get("DEBUG", "0"))
TOKEN = os.environ.get("TOKEN")
bot = interactions.Client(
    token=TOKEN,
    default_scope=GUILDS.LEAGUE_OF_PIXELS,
    # TODO: Reduce Intents.ALL once the deployed interactions.py version's
    # intent enum names are confirmed for messages, members, reactions, and commands.
    intents=interactions.Intents.ALL
)

logger = logging.getLogger("Logger")
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler("kopbot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf8')
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter())
logger.addHandler(stream_handler)

self_user_id = None
cached_member_count = None
XP_COOLDOWN_SECONDS = 60
user_cache = {}
last_xp_at = {}

def insert_user(author):
    db = create_connection(DATABASE)
    if db is None:
        raise RuntimeError(f"Could not connect to database to insert user {author.id}")

    try:
        db.cursor().execute(
            """INSERT OR IGNORE INTO Users(discord_id, avatar, discriminator, username, level, xp_level, xp_cap, total_xp, message_count)
            VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0);""",
            (
                str(author.id),
                getattr(author, "avatar", None),
                getattr(author, "discriminator", None),
                getattr(author, "username", None),
            )
        )
        db.commit()
    finally:
        db.close()

def get_or_create_user(author):
    discord_id = str(author.id)
    cached_user = user_cache.get(discord_id)
    if cached_user is not None:
        return cached_user

    try:
        discord_user = discordUser(discord_id, logger)
    except Exception:
        logger.exception("Failed to load user; attempting to create missing row for discord_id=%s", discord_id)
        insert_user(author)
        discord_user = discordUser(discord_id, logger)

    user_cache[discord_id] = discord_user
    return discord_user

def get_member_count_safely(guild):
    for attr in ("member_count", "approximate_member_count", "members_count"):
        value = getattr(guild, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                logger.debug("Guild member count attribute %s was not numeric: %r", attr, value)
    return cached_member_count

async def updateStatus():
    global cached_member_count

    lop = await interactions.get(bot, interactions.Guild, object_id=GUILDS.LEAGUE_OF_PIXELS)
    user_number = get_member_count_safely(lop)

    if DEBUG == 1:
        presence_message = "Under maintenance"
        presence_status = interactions.StatusType.DND
    elif user_number is not None:
        cached_member_count = user_number
        presence_message = f"over {user_number} users"
        presence_status = interactions.StatusType.ONLINE
    else:
        presence_message = "over our users"
        presence_status = interactions.StatusType.ONLINE
    
    await bot.change_presence(interactions.api.models.presence.ClientPresence(
            since=None,
            activities=[
            interactions.api.models.presence.PresenceActivity(
                name=presence_message,
                type=interactions.PresenceActivityType.WATCHING,
                
            )],
            afk=False,  
            status=presence_status
        )
    )
    logger.debug(f'Changed status to: {presence_message}')


@bot.command()
@interactions.option(interactions.Member, name="user", description="Choose username", required=False)
async def rank(ctx, user:interactions.Member = None):
    """Check your or anyone rank and XP ammount"""
    if user == None:
        user = ctx.author

    logger.debug(f'User {ctx.author.username} used command /rank')

    discord_user = discordUser(str(user.id), logger)
    if discord_user.updateData(user):
        discord_user.commitChanges()
    rank = discord_user.getRank()

    await ctx.send(embeds = [PLAYER_CARD(discord_user, rank)])
    channel = await ctx.get_channel()
    logger.debug(f'Embed has been sent to channel: #{channel.id}')

@bot.command()
async def top(ctx):
    """Get TOP3 discord chatters"""
    logger.debug(f'User {ctx.member.username} used command /top')
    embeds = []
    db = create_connection(DATABASE)
    if db is None:
        await ctx.send("Could not connect to the database.")
        return
    try:
        result = db.cursor().execute(
            """
            SELECT * 
            FROM Users 
            ORDER BY total_xp DESC 
            LIMIT 3""", 
            ()
        ).fetchall()
        logger.debug(f'Database Query: SELECT * FROM Users ORDER BY total_xp DESC LIMIT 3')
        if not result:
            await ctx.send("No users in the database yet.")
            return
        for row in result:
            try:
                guild_member = await interactions.get(bot, interactions.Member, object_id=row[DISCORD_USER_ID], guild_id=GUILDS.LEAGUE_OF_PIXELS)
                user_db = discordUser(str(guild_member.id), logger)
                if user_db.updateData(guild_member):
                    user_db.commitChanges()
            except Exception:
                logger.exception("Failed to refresh top user from Discord; using cached DB row for discord_id=%s", row[DISCORD_USER_ID])
                user_db = discordUser(str(row[DISCORD_USER_ID]), logger)

            rank = user_db.getRank()
            embeds.append(PLAYER_CARD(user_db, rank))

        await ctx.send(embeds = embeds)
        channel = await ctx.get_channel()
        logger.debug(f'Embed has been sent to channel: #{channel.id}')
    finally:
        if db is not None:
            db.close()


async def update_server_roles(level, id):
    guild_member = await interactions.get(bot, interactions.Member, object_id=id, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    if guild_member == None:
        return

    try:
        logger.debug(f'Fetching {guild_member.username}')
    except Exception:
        logger.debug(f'Fetching {guild_member.id}')

    server_roles = {(ROLES.USER, 1), (ROLES.MINION, 10), (ROLES.KNIGHT, 20), (ROLES.CHAMPION, 30), (ROLES.HERO, 40)}

    for role, min_level in server_roles:
        if level >= min_level and role not in guild_member.roles:
            role = await interactions.get(bot, interactions.Role, object_id=role, guild_id=GUILDS.LEAGUE_OF_PIXELS)
            await guild_member.add_role(role)
            try:
                logger.debug(f'User {guild_member.username} got new role {role.name}')
            except Exception:
                logger.debug(f'User {guild_member.id} got new role {role.name}')


@bot.event
async def on_start():
    logger.info("Starting bot")
    initialize_database(logger)

@bot.event
async def on_ready():
    global self_user_id

    logger.info("Bot is ready")
    if DEBUG == 1:
        logger.warning("DEBUG mode ENABLED")
    else:
        logger.info("DEBUG mode disabled")
    try:
        self_user = await bot.get_self_user()
        self_user_id = self_user.id
    except Exception:
        logger.exception("Failed to cache bot self user ID")
    await updateStatus() 

@bot.event
async def on_guild_member_add(guild_member):
    global cached_member_count

    # Add basic role to the user
    user_role = await interactions.get(bot, interactions.Role, object_id=ROLES.USER, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await guild_member.add_role(user_role)
    try:
        logger.debug(f'User {guild_member.username} got new role User')
    except Exception:
        logger.debug(f'User {guild_member.id} got new role User')


    # Update Discord's presence status
    if cached_member_count is not None:
        cached_member_count += 1
    await updateStatus()

    # Send message to bot channel
    bot_channel = await interactions.get(bot, interactions.Channel, object_id=CHANNELS.BOT, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await bot_channel.send(embeds = [WELCOME(guild_member)])
    logger.debug(f'Embed has been sent to channel: bot-channel')
    
    try:
        user = getattr(guild_member, "user", guild_member)
        get_or_create_user(user)
    except Exception:
        logger.exception("Failed to create or cache joined user discord_id=%s", getattr(guild_member, "id", None))

@bot.event
async def on_guild_member_remove(guild_member):
    global cached_member_count

    # Update Discord's presence status
    if cached_member_count is not None and cached_member_count > 0:
        cached_member_count -= 1
    await updateStatus()

    # Send message to bot channel
    bot_channel = await interactions.get(bot, interactions.Channel, object_id=CHANNELS.BOT, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await bot_channel.send(embeds = [BYE(guild_member)])
    logger.debug(f'Embed has been sent to channel: bot-channel')
    
@bot.event
async def on_message_create(message):
    author_id = message.author.id

    if self_user_id is not None and author_id == self_user_id:
        return

    if self_user_id is None:
        try:
            self_user = await bot.get_self_user()
            if author_id == self_user.id:
                return
        except Exception:
            logger.exception("Failed to fetch bot self user during message filter")
    
    if author_id == USERS.SYSTEM:
        return
    
    now = time.monotonic()
    author_key = str(author_id)
    if now - last_xp_at.get(author_key, 0) < XP_COOLDOWN_SECONDS:
        return

    try:
        discord_user = get_or_create_user(message.author)
        discord_user.updateData(message.author)
        if discord_user.addXP():
            channel = await interactions.get(bot, interactions.Channel, object_id=message.channel_id, guild_id=GUILDS.LEAGUE_OF_PIXELS)
            await channel.send(f"GG {message.author.mention}, you just advanced to level {discord_user.level}!")
            try:
                logger.debug(f'User {message.author.nickname} just advanced to level {discord_user.level}')
            except Exception:
                logger.debug(f'User {message.author.id} just advanced to level {discord_user.level}')
            await update_server_roles(discord_user.level, author_id)

        discord_user.commitChanges()
        last_xp_at[author_key] = now
    except Exception:
        logger.exception("Failed to process XP for discord_id=%s", author_id)

@bot.event
async def on_message_reaction_add(reaction):
    # Handle LFG Role
    if reaction.message_id == MESSAGES.LOOKING_FOR_GAME and reaction.emoji.name == '🎮':
        role = await interactions.get(bot, interactions.Role, object_id=ROLES.LOOKING_FOR_GAME, guild_id=GUILDS.LEAGUE_OF_PIXELS)
        await reaction.member.add_role(role)
        logger.debug(f'User {reaction.member.username} got new role {role.name}')

@bot.event
async def on_message_reaction_remove(reaction):
    # Handle LFG Role
    if reaction.message_id == MESSAGES.LOOKING_FOR_GAME and reaction.emoji.name == '🎮':
        role = await interactions.get(bot, interactions.Role, object_id=ROLES.LOOKING_FOR_GAME, guild_id=GUILDS.LEAGUE_OF_PIXELS)
        member = await interactions.get(bot, interactions.Member, object_id=reaction.user_id, guild_id=GUILDS.LEAGUE_OF_PIXELS)
        await member.remove_role(role)
        logger.debug(f'User {member.username} lost role {role.name}')

bot.start()

