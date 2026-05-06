import datetime
import interactions
from constants import COLORS
    
def PLAYER_CARD(discord_user, rank):
    embed = interactions.Embed(color = COLORS.YELLOW)

    if discord_user.avatar == None:
        embed.set_thumbnail(url = f"https://cdn.discordapp.com/embed/avatars/{int(discord_user.discord_id) % 5}.png")
    else:
        embed.set_thumbnail(url = f"https://cdn.discordapp.com/avatars/{discord_user.discord_id}/{discord_user.avatar}.png")
    
    embed.add_field(
        name = f"Rank - #{rank}",
        value = f"**User: {discord_user.username}**\n**Level:  {discord_user.level}**",
        inline = False
    )

    max_xp = discord_user.max_xp
    if max_xp == 0:
        percentage = 0
    else:
        percentage = int(discord_user.xp_now / max_xp * 100)
    yellow_box = percentage / 10
    
    embed.add_field(
        name = f"XP - {percentage}%",
        value = "🟨" * int(yellow_box) + "⬜" * (10 - int(yellow_box)),
        inline = False
    )

    return embed

def SUBMISSION(type, ctx, description):
    if type == "bug":
        title = "New Bug"
    elif type == "suggestion":
        title = "New suggestion"
    else:
        title = "???"

    embed = interactions.Embed(
        title = title,
        description = description, 
        color = COLORS.BLUE,
        timestamp = datetime.datetime.utcnow()
    )

    embed.set_author(
        name = ctx.author.name + '#' + ctx.author.discriminator,
        icon_url = ctx.author.avatar_url
    )
    
    return embed

def WELCOME(member):
    embed = interactions.Embed(
        description= f'**:smile:  <@{member.id}>  joined the server**', 
        color = COLORS.GREEN, 
        timestamp = datetime.datetime.utcnow()
    )
    
    embed.set_author(
        name = member.name + '#' + member.discriminator, 
        icon_url = member.avatar_url
    )
    
    embed.set_thumbnail(url = member.avatar_url)

    return embed

def BYE(member):
    embed = interactions.Embed(
        description = f'**:disappointed_relieved:  <@{member.id}>  left the server**',
        color = COLORS.RED,
        timestamp = datetime.datetime.utcnow()
    )
    
    embed.set_author(
        name = member.name + '#' + member.discriminator,
        icon_url = member.avatar_url
    )
    embed.set_thumbnail(url = member.avatar_url)
    return embed
