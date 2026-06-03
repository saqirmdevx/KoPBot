from __future__ import annotations

import random

from database import UserRecord


XP_COOLDOWN_SECONDS = 60


def xp_to_level_up(level: int) -> int:
    return 5 * (level * level) + (50 * level) + 100


def update_profile(user: UserRecord, *, username: str | None, avatar: str | None, discriminator: str | None) -> bool:
    changed = False

    if username is not None and user.username != username:
        user.username = username
        changed = True

    if user.avatar != avatar:
        user.avatar = avatar
        changed = True

    if user.discriminator != discriminator:
        user.discriminator = discriminator
        changed = True

    return changed


def add_xp(user: UserRecord) -> bool:
    xp_gain = random.randint(15, 25)
    user.xp_level += xp_gain
    user.total_xp += xp_gain
    user.xp_cap = xp_to_level_up(user.level)
    user.message_count += 1

    if user.xp_level > user.xp_cap:
        user.level += 1
        user.xp_level -= user.xp_cap
        user.xp_cap = xp_to_level_up(user.level)
        return True

    return False
