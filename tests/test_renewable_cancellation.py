import asyncio

import pytest
from nebius.aio.token.options import OPTION_REPORT_ERROR
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.static import Bearer as StaticBearer
from nebius.aio.token.token import Receiver, Token


@pytest.mark.asyncio()
@pytest.mark.parametrize("report_error", [False, True])
@pytest.mark.parametrize("abandon", ["cancel", "timeout"])
async def test_renewal_survives_waiter_abandonment(report_error: bool, abandon: str) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class BlockingReceiver(Receiver):
        async def _fetch(self, timeout=None, options=None) -> Token:
            nonlocal calls
            calls += 1
            started.set()
            await asyncio.wait_for(release.wait(), timeout)
            return Token("token")

        def can_retry(self, err, options=None) -> bool:
            return False

    class BlockingBearer(StaticBearer):
        def receiver(self) -> Receiver:
            return BlockingReceiver()

    bearer = RenewableBearer(BlockingBearer("unused"))
    options = {OPTION_REPORT_ERROR: "1"} if report_error else None
    leader = asyncio.create_task(bearer.fetch(timeout=0.05 if abandon == "timeout" else 1, options=options))
    follower = None
    other = None
    try:
        await asyncio.wait_for(started.wait(), 1)
        follower = asyncio.create_task(bearer.fetch(timeout=1, options=options))
        await asyncio.sleep(0)  # Let the follower join the pending renewal.
        other = asyncio.create_task(bearer.fetch(timeout=1, options=options))
        await asyncio.sleep(0)
        if abandon == "cancel":
            leader.cancel()
            with pytest.raises(asyncio.CancelledError):
                await leader
        else:
            with pytest.raises(asyncio.TimeoutError):
                await leader
        release.set()
        assert (await follower).token == "token"
        assert (await other).token == "token"
        assert (await bearer.fetch()).token == "token"
        assert calls == 1
    finally:
        release.set()
        leader.cancel()
        if follower is not None:
            follower.cancel()
        if other is not None:
            other.cancel()
        await asyncio.gather(*(task for task in (leader, follower, other) if task is not None), return_exceptions=True)
        await bearer.close()
