from __future__ import annotations

import datetime

import discord

from constants import COLORS
from database import UserRecord


YELLOW_SQUARE = "\U0001F7E8"
WHITE_LARGE_SQUARE = "\u2B1C"


def player_card(user: UserRecord, rank: int) -> discord.Embed:
    embed = discord.Embed(color=COLORS.YELLOW)

    if user.avatar is None:
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/embed/avatars/{int(user.discord_id) % 5}.png")
    else:
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/avatars/{user.discord_id}/{user.avatar}.png")

    embed.add_field(
        name=f"Rank - #{rank}",
        value=f"**User: {user.username}**\n**Level:  {user.level}**",
        inline=False,
    )

    percentage = 0 if user.xp_cap == 0 else int(user.xp_level / user.xp_cap * 100)
    filled_boxes = int(percentage / 10)
    embed.add_field(
        name=f"XP - {percentage}%",
        value=YELLOW_SQUARE * filled_boxes + WHITE_LARGE_SQUARE * (10 - filled_boxes),
        inline=False,
    )

    return embed


def welcome(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        description=f"**:smile:  <@{member.id}>  joined the server**",
        color=COLORS.GREEN,
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


def goodbye(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        description=f"**:disappointed_relieved:  <@{member.id}>  left the server**",
        color=COLORS.RED,
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed
