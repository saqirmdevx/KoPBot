import random
from database import *
from constants import ASCII

ATTRIBUTES = ["id", "discord_id", "avatar", "discriminator", "username", "level", "xp_now", "max_xp", "total_xp", "messages"]
DISCORD_USER_ID = 1

def xpToLevelUp(level):
    return 5 * (level * level) + (50 * level) + 100

class discordUser:
    def __init__(self, discord_id, logger, avatar = None, discriminator = None, username = None):
        if type(discord_id) != type("string"):
            raise Exception(f"discordUser.discord_id does not have a correct type, provided '{type(discord_id)}'' expected: 'string'") 
        
        self.logger = logger
        db = create_connection(DATABASE)
        if db is None:
            raise Exception(f"Could not open database for discord_id = {discord_id}")
        try:
            querry = db.cursor().execute("""
                SELECT * 
                FROM Users
                WHERE discord_id = ?
                LIMIT 1;""", (discord_id,)
            )
            result = querry.fetchone()
        finally:
            db.close()

        if result == None:
            raise Exception(f"There is no such user with discord_id = {discord_id} in database")

        for i, attribute in enumerate(ATTRIBUTES):
            setattr(self, attribute, result[i])
        
    def __str__(self):
        value =  f"discordUser {ASCII.OPENING_BRACKET}\n"
        
        for attribute in dir(self):
            if attribute in ATTRIBUTES:
                value += f"    {ASCII.QUOTE}{attribute}{ASCII.QUOTE}: {ASCII.QUOTE}{getattr(self, attribute)}{ASCII.QUOTE}\n"
        
        value += f"{ASCII.CLOSING_BRACKET}"
        
        return value

    def updateData(self, discordUser):
        changes = False

        guild_nick = getattr(discordUser, "nick", None)
        if guild_nick is None:
            guild_nick = getattr(discordUser, "nickname", None)

        if guild_nick != None:
            if self.username != guild_nick:
                self.logger.debug(f'User {guild_nick} has changed username, previously: {self.username}, now {guild_nick}')
                self.username = guild_nick
                changes = True
        elif discordUser.username != None:
            if self.username != discordUser.username:
                self.logger.debug(f'User {discordUser.username} has changed username, previously: {self.username}, now {discordUser.username}')
                self.username = discordUser.username
                changes = True
        
        if self.avatar != discordUser.avatar:
            self.logger.debug(f'User {self.username} has changed avatar')
            self.avatar = discordUser.avatar
            changes = True
        
        if self.discriminator != discordUser.discriminator:
            self.discriminator = discordUser.discriminator
            changes = True

        if changes == True:
            self.commitChanges()

        
    def addXP(self):
        
        xp_gain = random.randint(15,25)
        self.logger.debug(f'User {self.username} just got {xp_gain}XP')
        self.xp_now += xp_gain
        self.total_xp += xp_gain
        self.max_xp = xpToLevelUp(self.level)
        self.messages += 1

        if self.xp_now > self.max_xp:
            self.level += 1
            self.xp_now -= self.max_xp
            self.max_xp = xpToLevelUp(self.level)
            return True

        return False

    def commitChanges(self):
        db = create_connection(DATABASE)
        if db is None:
            return
        try:
            db.cursor().execute("""
                UPDATE Users
                SET avatar = ?, discriminator = ?, username = ?, level = ?, xp_level = ?, xp_cap = ?, total_xp = ?, message_count = ?
                WHERE discord_id = ?
                ;""", (self.avatar, self.discriminator, self.username, self.level, self.xp_now, self.max_xp, self.total_xp, self.messages, self.discord_id)
            )
            db.commit()
        finally:
            db.close()

    def getRank(self):
        db = create_connection(DATABASE)
        if db is None:
            return 0
        try:
            querry = db.cursor().execute("""
                SELECT COUNT(*)
                FROM Users
                WHERE total_xp >= ?
                ORDER BY total_xp;""", (self.total_xp,)
            )
            result = querry.fetchone()
            return int(result[0])
        finally:
            db.close()