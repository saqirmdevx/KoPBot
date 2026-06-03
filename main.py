#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands
from dotenv import load_dotenv

from constants import CHANNELS, GUILDS, MESSAGES, ROLES, USERS
from custom_formatter import CustomFormatter
from database import get_or_create_user, get_rank, get_user, initialize_database, top_users, update_user
from embeds import goodbye, player_card, welcome
from users import XP_COOLDOWN_SECONDS, add_xp, update_profile


load_dotenv(".env")

DEBUG = int(os.environ.get("DEBUG", "0"))
TOKEN = os.environ.get("TOKEN")
GUILD = discord.Object(id=GUILDS.LEAGUE_OF_PIXELS)
GAMEPAD = "\U0001F3AE"


def is_debug() -> bool:
    return DEBUG == 1


def configure_logger() -> logging.Logger:
    logger = logging.getLogger("kopbot")
    logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler("kopbot.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s"))
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(CustomFormatter())

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = configure_logger()


def avatar_key(user: discord.abc.User) -> str | None:
    return user.avatar.key if user.avatar else None


def discriminator(user: discord.abc.User) -> str | None:
    value = getattr(user, "discriminator", None)
    return str(value) if value is not None else None


def display_name(user: discord.abc.User) -> str | None:
    return getattr(user, "display_name", None) or getattr(user, "name", None)


def guild_role(member: discord.Member, role_id: int) -> discord.Role | None:
    return member.guild.get_role(role_id)


class KoPBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.reactions = True

        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.cached_member_count: int | None = None
        self.last_xp_at: dict[int, float] = {}

    async def setup_hook(self) -> None:
        if not is_debug():
            initialize_database()
        self.tree.copy_global_to(guild=GUILD)
        await self.tree.sync(guild=GUILD)

    async def on_ready(self) -> None:
        logger.info("Bot is ready")
        logger.warning("DEBUG mode ENABLED") if DEBUG == 1 else logger.info("DEBUG mode disabled")
        await self.update_status()

    async def update_status(self) -> None:
        guild = self.get_guild(GUILDS.LEAGUE_OF_PIXELS)
        if guild is None:
            guild = await self.fetch_guild(GUILDS.LEAGUE_OF_PIXELS)

        member_count = getattr(guild, "member_count", None) or getattr(guild, "approximate_member_count", None)

        if is_debug():
            activity = discord.Activity(type=discord.ActivityType.watching, name="Under maintenance")
            await self.change_presence(status=discord.Status.dnd, activity=activity)
            return

        if member_count is not None:
            self.cached_member_count = int(member_count)
            message = f"over {member_count} users"
        else:
            message = "over our users"

        activity = discord.Activity(type=discord.ActivityType.watching, name=message)
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def update_level_roles(self, member: discord.Member, level: int) -> None:
        if is_debug():
            logger.debug("DEBUG mode: skipped level role updates for member_id=%s", member.id)
            return

        level_roles = (
            (ROLES.USER, 1),
            (ROLES.MINION, 10),
            (ROLES.KNIGHT, 20),
            (ROLES.CHAMPION, 30),
            (ROLES.HERO, 40),
        )

        member_role_ids = {role.id for role in member.roles}
        for role_id, min_level in level_roles:
            if level < min_level or role_id in member_role_ids:
                continue

            role = guild_role(member, role_id)
            if role is None:
                logger.warning("Could not find role_id=%s for member_id=%s", role_id, member.id)
                continue

            await member.add_roles(role)
            logger.debug("User %s got new role %s", member.id, role.name)

    async def on_member_join(self, member: discord.Member) -> None:
        if self.cached_member_count is not None:
            self.cached_member_count += 1
        await self.update_status()

        if is_debug():
            logger.debug("DEBUG mode: skipped join role/database writes for member_id=%s", member.id)
            return

        role = guild_role(member, ROLES.USER)
        if role is not None:
            await member.add_roles(role)
            logger.debug("User %s got new role %s", member.id, role.name)

        channel = member.guild.get_channel(CHANNELS.BOT)
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(embed=welcome(member))

        get_or_create_user(member.id, avatar_key(member), discriminator(member), display_name(member))

    async def on_member_remove(self, member: discord.Member) -> None:
        if self.cached_member_count is not None and self.cached_member_count > 0:
            self.cached_member_count -= 1
        await self.update_status()

        if is_debug():
            logger.debug("DEBUG mode: skipped leave message for member_id=%s", member.id)
            return

        channel = member.guild.get_channel(CHANNELS.BOT)
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(embed=goodbye(member))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.author.id == USERS.SYSTEM or not isinstance(message.author, discord.Member):
            return

        if is_debug():
            logger.debug("DEBUG mode: skipped XP/database writes for member_id=%s", message.author.id)
            return

        now = time.monotonic()
        if now - self.last_xp_at.get(message.author.id, 0) < XP_COOLDOWN_SECONDS:
            return

        user = get_or_create_user(
            message.author.id,
            avatar_key(message.author),
            discriminator(message.author),
            display_name(message.author),
        )
        update_profile(
            user,
            username=display_name(message.author),
            avatar=avatar_key(message.author),
            discriminator=discriminator(message.author),
        )

        if add_xp(user):
            await message.channel.send(f"GG {message.author.mention}, you just advanced to level {user.level}!")
            await self.update_level_roles(message.author, user.level)

        update_user(user)
        self.last_xp_at[message.author.id] = now

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.message_id != MESSAGES.LOOKING_FOR_GAME or str(payload.emoji) != GAMEPAD:
            return

        if is_debug():
            logger.debug("DEBUG mode: skipped LFG role add for user_id=%s", payload.user_id)
            return

        guild = self.get_guild(payload.guild_id) if payload.guild_id else None
        if guild is None or payload.member is None:
            return

        role = guild.get_role(ROLES.LOOKING_FOR_GAME)
        if role is not None:
            await payload.member.add_roles(role)
            logger.debug("User %s got new role %s", payload.user_id, role.name)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.message_id != MESSAGES.LOOKING_FOR_GAME or str(payload.emoji) != GAMEPAD:
            return

        if is_debug():
            logger.debug("DEBUG mode: skipped LFG role remove for user_id=%s", payload.user_id)
            return

        guild = self.get_guild(payload.guild_id) if payload.guild_id else None
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            member = await guild.fetch_member(payload.user_id)

        role = guild.get_role(ROLES.LOOKING_FOR_GAME)
        if role is not None:
            await member.remove_roles(role)
            logger.debug("User %s lost role %s", payload.user_id, role.name)


bot = KoPBot()


@bot.tree.command(name="rank", description="Check your or anyone rank and XP ammount")
@app_commands.describe(user="Choose username")
async def rank(interaction: discord.Interaction, user: discord.Member | None = None) -> None:
    member = user or interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("This command can only be used in the server.", ephemeral=True)
        return

    if is_debug():
        discord_user = get_user(member.id, readonly=True)
        if discord_user is None:
            await interaction.response.send_message("No user data found for that member.", ephemeral=True)
            return
    else:
        discord_user = get_or_create_user(member.id, avatar_key(member), discriminator(member), display_name(member))
        if update_profile(
            discord_user,
            username=display_name(member),
            avatar=avatar_key(member),
            discriminator=discriminator(member),
        ):
            update_user(discord_user)

    await interaction.response.send_message(embed=player_card(discord_user, get_rank(discord_user, readonly=is_debug())))


@bot.tree.command(name="top", description="Get TOP3 discord chatters")
async def top(interaction: discord.Interaction) -> None:
    users = top_users(limit=3, readonly=is_debug())
    if not users:
        await interaction.response.send_message("No users in the database yet.")
        return

    if interaction.guild is not None and not is_debug():
        for user in users:
            member = interaction.guild.get_member(int(user.discord_id))
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(user.discord_id))
                except discord.HTTPException:
                    logger.exception("Failed to refresh top user from Discord; using cached DB row for %s", user.discord_id)
                    continue

            if update_profile(user, username=display_name(member), avatar=avatar_key(member), discriminator=discriminator(member)):
                update_user(user)

    embeds = [player_card(user, get_rank(user, readonly=is_debug())) for user in users]
    await interaction.response.send_message(embeds=embeds)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is required")

    logger.info("Starting bot")
    bot.run(TOKEN)
