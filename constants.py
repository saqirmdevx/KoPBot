from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Guilds:
    LEAGUE_OF_PIXELS: int = 459472853360967680


@dataclass(frozen=True)
class Messages:
    LOOKING_FOR_GAME: int = 884513845207515226


@dataclass(frozen=True)
class Roles:
    LOOKING_FOR_GAME: int = 748940295974027324
    USER: int = 884415788524654632
    MINION: int = 885140347070595102
    KNIGHT: int = 876152198642421831
    CHAMPION: int = 946143243710640138
    HERO: int = 965977110474801202


@dataclass(frozen=True)
class Channels:
    BOT: int = 650398918147964929
    SUBMIT: int = 643611016613199873
    SUGGESTIONS: int = 884549848836218911
    BUGS: int = 884549823053848596
    CONTEST: int = 895763764765393008


@dataclass(frozen=True)
class Users:
    SYSTEM: int = 1261287111701696575
    IGNISSO: int = 427135054888697869
    QTX: int = 490964640046514188
    PRIM: int = 782963903738019860


@dataclass(frozen=True)
class Colors:
    GREEN: int = 0x2AA519
    RED: int = 0xCF2121
    YELLOW: int = 0xFFDA16
    BLUE: int = 0x4287F5


GUILDS = Guilds()
MESSAGES = Messages()
ROLES = Roles()
CHANNELS = Channels()
USERS = Users()
COLORS = Colors()
