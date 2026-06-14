"""Entry point: claim the current free Epic games once, then optionally keep
running on a schedule."""

import asyncio
import json
import signal
from contextlib import suppress
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from browserforge.fingerprints import Screen
from camoufox import AsyncCamoufox
from loguru import logger
from pytz import timezone

from notify import notify
from services.epic_authorization_service import EpicAuthorization
from services.epic_games_service import EpicAgent
from settings import LOG_DIR
from settings import settings, EpicAccount
from utils import init_log

init_log(
    runtime=LOG_DIR.joinpath("runtime.log"),
    error=LOG_DIR.joinpath("error.log"),
    serialize=LOG_DIR.joinpath("serialize.log"),
)

try:
    TIMEZONE = timezone(settings.SCHEDULE_TIMEZONE)
except Exception:
    TIMEZONE = timezone("UTC")


async def execute_browser_tasks(account: EpicAccount, headless: bool = True):
    """Authenticate one account and claim its available free games."""
    logger.debug(f"Processing {account.email}")

    proxy = settings.proxy_for(account)
    if proxy:
        logger.debug(f"Routing {account.email} through proxy {proxy['server']}")

    async with AsyncCamoufox(
        persistent_context=True,
        user_data_dir=settings.user_data_dir_for(account.email),
        proxy=proxy,
        geoip=bool(proxy),
        screen=Screen(max_width=1920, max_height=1080, min_height=1080, min_width=1920),
        humanize=0.2,
        headless=headless,
    ) as browser:
        page = browser.pages[0] if browser.pages else await browser.new_page()

        if not await EpicAuthorization(page, account).invoke():
            logger.error(f"Login failed for {account.email}")
            await notify(f"❌ Epic-Claimer: не удалось войти ({account.email})")
            return

        game_page = await browser.new_page()
        await EpicAgent(game_page).collect_epic_games()

        with suppress(Exception):
            for p in browser.pages:
                await p.close()
        with suppress(Exception):
            await browser.close()


async def run_all_accounts(headless: bool = True):
    """Process every configured account in turn; a failure on one never blocks the rest."""
    accounts = settings.accounts
    if not accounts:
        logger.error("No Epic account configured. Set EPIC_EMAIL/EPIC_PASSWORD or EPIC_ACCOUNTS.")
        return

    total = len(accounts)
    for idx, account in enumerate(accounts, start=1):
        logger.debug(f"[{idx}/{total}] {account.email}")
        try:
            await execute_browser_tasks(account, headless=headless)
        except Exception as e:
            logger.exception(f"Account {account.email} failed: {e}")
            await notify(f"❌ Epic-Claimer: аккаунт {account.email} — ошибка: {e}")


async def deploy():
    headless = True

    sj = settings.model_dump(mode="json")
    sj["headless"] = headless
    logger.debug(f"Configuration:\n{json.dumps(sj, indent=2, ensure_ascii=False)}")

    if not settings.accounts:
        logger.error("No Epic account configured. Set EPIC_EMAIL/EPIC_PASSWORD or EPIC_ACCOUNTS.")
        return
    logger.debug(f"Loaded {len(settings.accounts)} account(s)")

    await run_all_accounts(headless=headless)

    if not settings.ENABLE_APSCHEDULER:
        logger.debug("Scheduler disabled, done")
        return

    try:
        trigger = CronTrigger.from_crontab(
            settings.CRON_SCHEDULE, timezone=settings.SCHEDULE_TIMEZONE
        )
    except Exception as e:
        logger.error(f"Invalid CRON_SCHEDULE {settings.CRON_SCHEDULE!r}: {e}")
        return

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_all_accounts,
        trigger=trigger,
        id="epic_games_task",
        name="epic_games_task",
        args=[headless],
        replace_existing=False,
        max_instances=1,
    )

    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.debug(f"Received {signal.Signals(signum).name}, shutting down")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    scheduler.start()
    logger.success("Scheduler started")
    logger.debug(f"Now: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    for j in scheduler.get_jobs():
        if next_run := j.next_run_time:
            logger.debug(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} ({j.id})")

    try:
        await shutdown_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=True)
        logger.success("Scheduler stopped")


if __name__ == '__main__':
    asyncio.run(deploy())
