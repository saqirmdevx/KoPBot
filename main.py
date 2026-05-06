#!/usr/bin/env python3
import interactions
import os
import sys
import logging

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
    intents=interactions.Intents.ALL
)

logger = logging.getLogger("Logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("kopbot.log", encoding='utf8')
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomFormatter())
logger.addHandler(stream_handler)

last_message = None

async def updateStatus():
    lop = await interactions.get(bot, interactions.Guild, object_id=GUILDS.LEAGUE_OF_PIXELS)
    user_number = len(await lop.get_members().flatten())

    if DEBUG == 1:
        presence_message = "Under maintenance"
        presence_status = interactions.StatusType.DND
    else:
        presence_message = f"over {user_number} users"
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
    discord_user.updateData(user)
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
        logger.debug(f'Database Querry: SELECT * FROM Users ORDER BY total_xp DESC LIMIT 3')
        if not result:
            await ctx.send("No users in the database yet.")
            return
        for row in result:
            try:
                guild_member = await interactions.get(bot, interactions.Member, object_id=row[DISCORD_USER_ID], guild_id=GUILDS.LEAGUE_OF_PIXELS)
                user_db = discordUser(str(guild_member.id), logger)
                user_db.updateData(guild_member)
            except Exception:
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
    try:
        logger.debug(f'Fetching {guild_member.username}')
    except:
        logger.debug(f'Fetching {guild_member.id}')

    if guild_member == None:
        return

    server_roles = {(ROLES.USER, 1), (ROLES.MINION, 10), (ROLES.KNIGHT, 20), (ROLES.CHAMPION, 30), (ROLES.HERO, 40)}

    for role, min_level in server_roles:
        if level >= min_level and role not in guild_member.roles:
            role = await interactions.get(bot, interactions.Role, object_id=role, guild_id=GUILDS.LEAGUE_OF_PIXELS)
            await guild_member.add_role(role)
            try:
                logger.debug(f'User {guild_member.username} got new role {role.name}')
            except:
                logger.debug(f'User {guild_member.id} got new role {role.name}')


@bot.event
async def on_start():
    logger.info("Starting bot")

@bot.event
async def on_ready():
    logger.info("Bot is ready")
    if DEBUG == 1:
        logger.warning("DEBUG mode ENABLED")
    else:
        logger.info("DEBUG mode disabled")
    await updateStatus() 

@bot.event
async def on_guild_member_add(guild_member):
    # Add basic role to the user
    user_role = await interactions.get(bot, interactions.Role, object_id=ROLES.USER, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await guild_member.add_role(user_role)
    try:
        logger.debug(f'User {guild_member.username} got new role User')
    except:
        logger.debug(f'User {guild_member.id} got new role User')


    # Update Discord's presence status
    await updateStatus()

    # Send message to bot channel
    bot_channel = await interactions.get(bot, interactions.Channel, object_id=CHANNELS.BOT, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await bot_channel.send(embeds = [WELCOME(guild_member)])
    logger.debug(f'Embed has been sent to channel: bot-channel')
    
    try:
        discord_user = discordUser(str(guild_member.user.id), logger)
    except Exception:
        u = guild_member.user
        db = create_connection(DATABASE)
        if db is not None:
            try:
                db.cursor().execute(
                    """INSERT INTO Users(discord_id, avatar, discriminator, username, level, xp_level, xp_cap, total_xp, message_count)
                    VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0);""", (str(u.id), u.avatar, u.discriminator, u.username)
                )
                db.commit()
            finally:
                db.close()
            logger.debug(f'Database Querry: INSERT INTO Users(discord_id, avatar, discriminator, username, level, xp_level, xp_cap, total_xp, message_count) VALUES ({str(u.id)}, {u.avatar}, {u.discriminator}, {u.username}, 0, 0, 0, 0, 0)')

@bot.event
async def on_guild_member_remove(guild_member):
    # Update Discord's presence status
    await updateStatus()

    # Send message to bot channel
    bot_channel = await interactions.get(bot, interactions.Channel, object_id=CHANNELS.BOT, guild_id=GUILDS.LEAGUE_OF_PIXELS)
    await bot_channel.send(embeds = [BYE(guild_member)])
    logger.debug(f'Embed has been sent to channel: bot-channel')
    
@bot.event
async def on_message_create(message):
    global last_message

    if message.author == await bot.get_self_user():
        return
    
    if message.author.id == USERS.SYSTEM:
        return
    
    if message.author.id != last_message:
        try:
            discord_user = discordUser(str(message.author.id), logger)
        except Exception:
            db = create_connection(DATABASE)
            if db is not None:
                try:
                    db.cursor().execute(
                        """INSERT INTO Users(discord_id, avatar, discriminator, username, level, xp_level, xp_cap, total_xp, message_count)
                        VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0);""", (str(message.author.id), message.author.avatar, message.author.discriminator, message.author.username)
                    )
                    db.commit()
                finally:
                    db.close()
                logger.debug(f'Database Querry: INSERT INTO Users(discord_id, avatar, discriminator, username, level, xp_level, xp_cap, total_xp, message_count) VALUES ({str(message.author.id)}, {message.author.avatar}, {message.author.discriminator}, {message.author.username}, 0, 0, 0, 0, 0)')
        discord_user = discordUser(str(message.author.id), logger) 

        if discord_user.addXP():
            channel = await interactions.get(bot, interactions.Channel, object_id=message.channel_id, guild_id=GUILDS.LEAGUE_OF_PIXELS)
            await channel.send(f"GG {message.author.mention}, you just advanced to level {discord_user.level}!")
            try:
                logger.debug(f'User {message.author.nickname} just advanced to level {discord_user.level}')
            except:
                logger.debug(f'User {message.author.id} just advanced to level {discord_user.level}')

        discord_user.commitChanges()

        if discord_user.level >= 10:
            await update_server_roles(discord_user.level, message.author.id)

        last_message = message.author.id

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

