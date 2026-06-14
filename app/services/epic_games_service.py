"""Epic store automation: discover the current free games and claim them."""

import asyncio
import json
import time
from contextlib import suppress
from json import JSONDecodeError
from typing import List

import httpx
from hcaptcha_challenger.agent import AgentV
from loguru import logger
from playwright.async_api import Page
from playwright.async_api import TimeoutError

from models import OrderItem, Order
from models import PromotionGame
from settings import settings, RUNTIME_DIR, SCREENSHOTS_DIR

URL_CLAIM = "https://store.epicgames.com/en-US/free-games"
URL_PROMOTIONS = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
URL_PRODUCT_PAGE = "https://store.epicgames.com/en-US/p/"
URL_PRODUCT_BUNDLES = "https://store.epicgames.com/en-US/bundles/"


def get_promotions() -> List[PromotionGame]:
    """Return this week's fully-free games from Epic's promotions endpoint."""

    def is_free(prot: dict) -> bool | None:
        with suppress(KeyError, IndexError, TypeError):
            offers = prot["promotions"]["promotionalOffers"][0]["promotionalOffers"]
            for offer in offers:
                if offer["discountSetting"]["discountPercentage"] == 0:
                    return True

    resp = httpx.get(URL_PROMOTIONS, params={"local": "zh-CN"})
    try:
        data = resp.json()
    except JSONDecodeError as err:
        logger.error("Failed to get promotions", err=err)
        return []

    with suppress(Exception):
        cache = RUNTIME_DIR.joinpath("promotions.json")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    promotions: List[PromotionGame] = []
    for e in data["data"]["Catalog"]["searchStore"]["elements"]:
        if not is_free(e):
            continue
        try:
            e["url"] = f"{URL_PRODUCT_PAGE.rstrip('/')}/{e['offerMappings'][0]['pageSlug']}"
        except (KeyError, IndexError):
            if e.get("productSlug"):
                e["url"] = f"{URL_PRODUCT_BUNDLES.rstrip('/')}/{e['productSlug']}"
            else:
                logger.info(f"Failed to get URL: {e}")
                continue
        logger.info(e["url"])
        promotions.append(PromotionGame(**e))

    return promotions


class EpicAgent:

    def __init__(self, page: Page):
        self.page = page
        self.epic_games = EpicGames(self.page)

        self._promotions: List[PromotionGame] = []
        self._ctx_cookies_is_available: bool = False
        self._orders: List[OrderItem] = []
        self._namespaces: List[str] = []

    async def _sync_order_history(self):
        if self._orders:
            return

        completed_orders: List[OrderItem] = []
        try:
            await self.page.goto("https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory")
            data = json.loads(await self.page.text_content("//pre"))
            for _order in data["orders"]:
                order = Order(**_order)
                if order.orderType != "PURCHASE":
                    continue
                for item in order.items:
                    if item.namespace and len(item.namespace) == 32:
                        completed_orders.append(item)
        except Exception as err:
            logger.warning(err)

        self._orders = completed_orders

    async def _check_orders(self):
        await self._sync_order_history()
        self._namespaces = self._namespaces or [order.namespace for order in self._orders]
        # Keep only the promotions the account does not already own
        self._promotions = [p for p in get_promotions() if p.namespace not in self._namespaces]

    async def _should_ignore_task(self) -> bool:
        self._ctx_cookies_is_available = False
        await self.page.goto(URL_CLAIM, wait_until="domcontentloaded")

        if await self.page.locator("//egs-navigation").get_attribute("isloggedin") == "false":
            logger.error("❌ context cookies is not available")
            return False

        self._ctx_cookies_is_available = True
        await self._check_orders()
        return not self._promotions

    async def collect_epic_games(self):
        if await self._should_ignore_task():
            logger.success("All week-free games are already in the library")
            return

        if not self._ctx_cookies_is_available:
            return

        if not self._promotions:
            await self._check_orders()
        if not self._promotions:
            logger.success("All week-free games are already in the library")
            return

        games = []
        for p in self._promotions:
            logger.debug(f"Discover promotion: {p.title} - {p.url}")
            if "/bundles/" in p.url:
                logger.debug(f"Skip bundle: {p.url}")
            else:
                games.append(p)

        if games:
            try:
                await self.epic_games.collect_weekly_games(games)
            except Exception as e:
                logger.exception(e)


class EpicGames:

    def __init__(self, page: Page):
        self.page = page

    @staticmethod
    async def _agree_license(page: Page):
        with suppress(TimeoutError):
            await page.click("//label[@for='agree']", timeout=4000)
            accept = page.locator("//button//span[text()='Accept']")
            if await accept.is_enabled():
                await accept.click()

    @staticmethod
    async def _confirm_free_order(page: Page) -> bool:
        """Click "Add to library" in Epic's purchase modal. It can live in the main
        document or inside the purchase iframe, so scan every frame for it."""
        confirm_xpath = (
            "//button[contains(normalize-space(.), 'Add to library') "
            "or contains(normalize-space(.), 'Add To Library') "
            "or contains(normalize-space(.), 'Place Order')]"
        )
        for _ in range(20):
            for frame in page.frames:
                with suppress(Exception):
                    button = frame.locator(confirm_xpath).first
                    if await button.count() > 0 and await button.is_enabled(timeout=1000):
                        await button.click()
                        return True
            await page.wait_for_timeout(1000)
        return False

    @staticmethod
    async def _screenshot(page: Page, url: str, tag: str):
        with suppress(Exception):
            sr = SCREENSHOTS_DIR.joinpath("claim")
            sr.mkdir(parents=True, exist_ok=True)
            slug = url.rstrip("/").split("/")[-1]
            await page.screenshot(path=str(sr.joinpath(f"{slug}-{tag}-{int(time.time())}.png")))

    async def _claim_one(self, url: str, agent: AgentV) -> None:
        page = self.page
        logger.debug(f"Claiming {url}")
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(3000)

        cta = page.locator("//button[@data-testid='purchase-cta-button']")
        try:
            status = (await cta.text_content(timeout=15000) or "").strip()
        except TimeoutError:
            logger.warning(f"No purchase button found - {url}")
            return

        if any(s in status for s in ("In Library", "Owned", "Manage", "Launch")):
            logger.success(f"Already in the library - {url}")
            return
        if "Get" not in status:
            logger.warning(f"Not a free 'Get' offer ({status!r}) - {url}")
            return

        # Click "Get" to open the purchase modal, then confirm — no cart involved
        await cta.click()
        await page.wait_for_timeout(2000)
        await self._agree_license(page)

        if not await self._confirm_free_order(page):
            await self._screenshot(page, url, "no-confirm")
            logger.warning(f"'Add to library' button not found - {url}")
            return

        # Confirming may trigger an hCaptcha challenge
        with suppress(Exception):
            await asyncio.wait_for(agent.wait_for_challenge(), timeout=180)
        await page.wait_for_timeout(5000)

        with suppress(TimeoutError):
            status = (await cta.text_content(timeout=8000) or "").strip()
            if any(s in status for s in ("In Library", "Owned", "Manage")):
                logger.success(f"🎉 Claimed - {url}")
                return

        await self._screenshot(page, url, "unconfirmed")
        logger.warning(f"Claim not confirmed - {url}")

    async def collect_weekly_games(self, promotions: List[PromotionGame]):
        agent = AgentV(page=self.page, agent_config=settings)
        for p in promotions:
            try:
                await self._claim_one(p.url, agent)
            except Exception as err:
                logger.warning(f"Failed to claim {p.url} - {err}")
