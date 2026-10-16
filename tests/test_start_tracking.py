"""/start stores where the user came from (needs a real PostgreSQL, see test_admin_api.py)."""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="needs a real PostgreSQL")

TG_BASE = 9_100_000_000


@pytest_asyncio.fixture
async def maker():
    from database.engine import async_session_maker, engine
    from database.models import User
    yield async_session_maker
    async with async_session_maker() as s:
        await s.execute(delete(User).where(User.telegram_id >= TG_BASE, User.telegram_id < TG_BASE + 1000))
        await s.commit()
    await engine.dispose()


def _msg(tg_id):
    return SimpleNamespace(from_user=SimpleNamespace(id=tg_id, full_name=f"U{tg_id}", username=f"u{tg_id}"), answer=AsyncMock())


async def _start(tg_id, args):
    from bot.handlers.start import cmd_start
    state = SimpleNamespace(clear=AsyncMock())
    await cmd_start(_msg(tg_id), state, SimpleNamespace(args=args))


async def _get(maker, tg_id):
    from database.models import User
    async with maker() as s:
        return (await s.execute(select(User).where(User.telegram_id == tg_id))).scalar_one()


async def test_new_users_get_their_source(maker):
    inviter = TG_BASE + 1
    await _start(inviter, None)
    await _start(TG_BASE + 2, f"ref_{inviter}")
    await _start(TG_BASE + 3, "src_Instagram")
    await _start(TG_BASE + 4, "weird")
    await _start(TG_BASE + 5, "ref_999999999999")      # inviter does not exist

    inv = await _get(maker, inviter)
    assert inv.acquisition_source == "direct" and inv.start_payload is None
    ref = await _get(maker, TG_BASE + 2)
    assert (ref.acquisition_source, ref.referred_by, ref.start_payload) == ("referral", inv.id, f"ref_{inviter}")
    camp = await _get(maker, TG_BASE + 3)
    assert (camp.acquisition_source, camp.referred_by) == ("src:instagram", None)
    assert (await _get(maker, TG_BASE + 4)).acquisition_source == "other"
    ghost = await _get(maker, TG_BASE + 5)
    assert (ghost.acquisition_source, ghost.referred_by) == ("direct", None)


async def test_first_touch_wins_and_self_referral_is_ignored(maker):
    await _start(TG_BASE + 11, "src_flyer")
    await _start(TG_BASE + 11, "src_other_campaign")          # already known: the source does not change
    assert (await _get(maker, TG_BASE + 11)).acquisition_source == "src:flyer"

    await _start(TG_BASE + 12, f"ref_{TG_BASE + 12}")          # own link
    me = await _get(maker, TG_BASE + 12)
    assert me.referred_by is None and me.acquisition_source == "direct"


async def test_existing_user_without_inviter_can_still_be_invited(maker):
    inviter, guest = TG_BASE + 21, TG_BASE + 22
    await _start(inviter, None)
    await _start(guest, None)                                  # came on their own first
    await _start(guest, f"ref_{inviter}")                      # then opened an invitation: the inviter earns the bonus
    g = await _get(maker, guest)
    assert g.referred_by == (await _get(maker, inviter)).id and g.acquisition_source == "referral"
