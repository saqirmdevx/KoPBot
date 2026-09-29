import asyncio
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

import database
import main
from constants import GUILDS
from users import add_xp


class DatabaseFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        original_connect = database.connect
        db_path = str(Path(self.temp.name) / 'test.db')
        self.connection_patch = patch.object(
            database, 'connect', side_effect=lambda **kw: original_connect(db_path, **kw)
        )
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        database.initialize_database()

    def user(self, discord_id=123):
        return database.get_or_create_user(discord_id, None, '0', 'Test User')


class DatabaseTests(DatabaseFixture, unittest.TestCase):
    def test_exact_threshold_levels_up(self):
        user = self.user()
        user.xp_level = user.total_xp = 80
        with patch('users.random.randint', return_value=20):
            self.assertTrue(add_xp(user))
        self.assertEqual((user.level, user.xp_level, user.total_xp), (1, 0, 100))

    def test_excess_xp_can_cross_multiple_levels(self):
        user = self.user()
        user.xp_level = user.total_xp = 250
        with patch('users.random.randint', return_value=20):
            self.assertTrue(add_xp(user))
        self.assertEqual((user.level, user.xp_level, user.total_xp), (2, 15, 270))

    def test_profile_refresh_preserves_newer_progress(self):
        stale = self.user()
        current = self.user()
        with patch('users.random.randint', return_value=20):
            add_xp(current)
        database.update_user(current)
        stale.username = 'Renamed'
        database.update_user_profile(stale)
        saved = self.user()
        self.assertEqual((saved.total_xp, saved.message_count, saved.username), (20, 1, 'Renamed'))

    def test_tied_users_share_first_rank(self):
        first = self.user(123)
        second = self.user(456)
        self.assertEqual(database.get_rank(first), 1)
        self.assertEqual(database.get_rank(second), 1)


class MessageTests(DatabaseFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = main.KoPBot()
        self.addAsyncCleanup(self.bot.close)
        self.member = Mock(spec=discord.Member)
        self.member.id = 123
        self.member.bot = False
        self.member.guild.id = GUILDS.LEAGUE_OF_PIXELS
        self.member.avatar = None
        self.member.discriminator = '0'
        self.member.display_name = 'Test User'
        self.member.mention = '<@123>'
        self.member.roles = []
        self.member.add_roles = AsyncMock()
        self.message = SimpleNamespace(author=self.member, channel=SimpleNamespace(send=AsyncMock()))
        for p in (patch.object(main, 'DEBUG', 0), patch('users.random.randint', return_value=20),
                  patch.object(main, 'logger')):
            p.start()
            self.addCleanup(p.stop)
        user = self.user()
        user.xp_level = user.total_xp = 90
        database.update_user(user)

    async def test_role_failure_does_not_repeat_level_up(self):
        self.member.add_roles.side_effect = discord.Forbidden(
            SimpleNamespace(status=403, reason='Forbidden'), 'Missing Permissions'
        )
        with patch('main.time.monotonic', return_value=1000):
            await self.bot.on_message(self.message)
        saved = self.user()
        self.assertEqual((saved.level, saved.total_xp, saved.message_count), (1, 110, 1))
        with patch('main.time.monotonic', return_value=1061):
            await self.bot.on_message(self.message)
        self.assertEqual(self.user().total_xp, 130)
        self.message.channel.send.assert_awaited_once()
        self.assertEqual(self.member.add_roles.await_count, 2)

    async def test_send_failure_still_saves_xp_and_assigns_role(self):
        self.message.channel.send.side_effect = discord.Forbidden(
            SimpleNamespace(status=403, reason='Forbidden'), 'Missing Permissions'
        )
        await self.bot.on_message(self.message)
        self.assertEqual(self.user().level, 1)
        self.member.add_roles.assert_awaited_once()
        self.assertIn(123, self.bot.last_xp_at)

    async def test_overlapping_messages_only_award_once(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def slow_send(*args, **kwargs):
            entered.set()
            await release.wait()

        self.message.channel.send.side_effect = slow_send
        first = asyncio.create_task(self.bot.on_message(self.message))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            await self.bot.on_message(self.message)
        finally:
            release.set()
            await first
        self.assertEqual(self.user().total_xp, 110)
        self.message.channel.send.assert_awaited_once()

    async def test_failed_database_save_does_not_announce_or_consume_cooldown(self):
        with patch.object(main, 'update_user', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                await self.bot.on_message(self.message)
        self.assertEqual(self.user().total_xp, 90)
        self.message.channel.send.assert_not_awaited()
        self.assertNotIn(123, self.bot.last_xp_at)

    async def test_other_guild_does_not_award_xp(self):
        self.member.guild.id = 999
        await self.bot.on_message(self.message)
        self.assertEqual(self.user().total_xp, 90)

    async def test_top_member_fetch_does_not_undo_concurrent_xp(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            guild=SimpleNamespace(get_member=Mock(return_value=None), fetch_member=AsyncMock()),
        )

        async def fetch_member(user_id):
            interaction.response.defer.assert_awaited_once()
            await self.bot.on_message(self.message)
            self.member.display_name = 'Renamed'
            return self.member

        interaction.guild.fetch_member.side_effect = fetch_member
        await main.top.callback(interaction)
        saved = self.user()
        self.assertEqual((saved.level, saved.total_xp, saved.username), (1, 110, 'Renamed'))
        interaction.followup.send.assert_awaited_once()

    async def test_top_missing_member_keeps_saved_profile(self):
        interaction = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            guild=SimpleNamespace(
                id=GUILDS.LEAGUE_OF_PIXELS,
                get_member=Mock(return_value=None),
                fetch_member=AsyncMock(side_effect=discord.NotFound(
                    SimpleNamespace(status=404, reason='Not Found'),
                    {'code': 10007, 'message': 'Unknown Member'},
                )),
            ),
        )
        await main.top.callback(interaction)
        interaction.followup.send.assert_awaited_once()
        embeds = interaction.followup.send.call_args.kwargs['embeds']
        self.assertEqual(len(embeds), 1)
        self.assertIn('Test User', embeds[0].fields[0].value)
        self.assertEqual(self.user().total_xp, 90)
        main.logger.exception.assert_not_called()

    async def test_debug_mode_does_not_write(self):
        with patch.object(main, 'DEBUG', 1):
            await self.bot.on_message(self.message)
        self.assertEqual(self.user().total_xp, 90)
        self.member.add_roles.assert_not_awaited()
        self.message.channel.send.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
