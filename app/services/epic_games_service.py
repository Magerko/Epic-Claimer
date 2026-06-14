# -*- coding: utf-8 -*-
# Time       : 2022/1/16 0:25
# Author     : QIN2DIM
# GitHub     : https://github.com/QIN2DIM
# Description: Game store control handle

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
    """
    Fetch weekly free game data

    <upcoming> promotion["promotions"]["upcomingPromotionalOffers"]
    <this week free> promotion["promotions"]["promotionalOffers"]
    :return: {"pageLink1": "pageTitle1", "pageLink2": "pageTitle2", ...}
    """

    def is_discount_game(prot: dict) -> bool | None:
        with suppress(KeyError, IndexError, TypeError):
            offers = prot["promotions"]["promotionalOffers"][0]["promotionalOffers"]
            for i, offer in enumerate(offers):
                if offer["discountSetting"]["discountPercentage"] == 0:
                    return True

    promotions: List[PromotionGame] = []

    resp = httpx.get(URL_PROMOTIONS, params={"local": "zh-CN"})

    try:
        data = resp.json()
    except JSONDecodeError as err:
        logger.error("Failed to get promotions", err=err)
        return []

    with suppress(Exception):
        cache_key = RUNTIME_DIR.joinpath("promotions.json")
        cache_key.parent.mkdir(parents=True, exist_ok=True)
        cache_key.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Get store promotion data and <this week free> games
    for e in data["data"]["Catalog"]["searchStore"]["elements"]:

        # Remove items that are discounted but not free.
        if not is_discount_game(e):
            continue

        # package free games
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

        self._cookies = None

    async def _sync_order_history(self):
        """Fetch the most recent order history"""
        if self._orders:
            return

        completed_orders: List[OrderItem] = []

        try:
            await self.page.goto("https://www.epicgames.com/account/v2/payment/ajaxGetOrderHistory")
            text_content = await self.page.text_content("//pre")
            data = json.loads(text_content)
            for _order in data["orders"]:
                order = Order(**_order)
                if order.orderType != "PURCHASE":
                    continue
                for item in order.items:
                    if not item.namespace or len(item.namespace) != 32:
                        continue
                    completed_orders.append(item)
        except Exception as err:
            logger.warning(err)

        self._orders = completed_orders

    async def _check_orders(self):
        # Fetch the player's historical purchase orders
        # Account credentials must be valid before running this
        await self._sync_order_history()

        self._namespaces = self._namespaces or [order.namespace for order in self._orders]

        # Fetch this week's promotion data
        # Diff against owned items to keep only promotions not yet collected
        self._promotions = [p for p in get_promotions() if p.namespace not in self._namespaces]

    async def _should_ignore_task(self) -> bool:
        self._ctx_cookies_is_available = False

        # Check whether the browser already cached the account token
        await self.page.goto(URL_CLAIM, wait_until="domcontentloaded")

        # == token expired == #
        status = await self.page.locator("//egs-navigation").get_attribute("isloggedin")
        if status == "false":
            logger.error("❌ context cookies is not available")
            return False

        # == token valid == #

        # Browser identity is still valid
        self._ctx_cookies_is_available = True

        # Load the not-yet-collected promotions
        await self._check_orders()

        # Empty promotions list means all free games are collected, task done
        if not self._promotions:
            return True

        # Account is valid but some free games are still unclaimed
        return False

    async def collect_epic_games(self):
        if await self._should_ignore_task():
            logger.success("All week-free games are already in the library")
            return

        # Refresh browser identity
        if not self._ctx_cookies_is_available:
            return

        # Load the not-yet-collected promotions
        if not self._promotions:
            await self._check_orders()

        if not self._promotions:
            logger.success("All week-free games are already in the library")
            return

        game_promotions = []
        bundle_promotions = []
        for p in self._promotions:
            pj = json.dumps({"title": p.title, "url": p.url}, indent=2, ensure_ascii=False)
            logger.debug(f"Discover promotion \n{pj}")
            if "/bundles/" in p.url:
                bundle_promotions.append(p)
            else:
                game_promotions.append(p)

        # Collect promotional games
        if game_promotions:
            try:
                await self.epic_games.collect_weekly_games(game_promotions)
            except Exception as e:
                logger.exception(e)

        # Collect game bundle content
        if bundle_promotions:
            logger.debug("Skip the game bundled content")

        logger.debug("All tasks in the workflow have been completed")


class EpicGames:

    def __init__(self, page: Page):
        self.page = page

        self._promotions: List[PromotionGame] = []

    @staticmethod
    async def _agree_license(page: Page):
        logger.debug("Agree license")
        with suppress(TimeoutError):
            await page.click("//label[@for='agree']", timeout=4000)
            accept = page.locator("//button//span[text()='Accept']")
            if await accept.is_enabled():
                await accept.click()

    @staticmethod
    async def _confirm_free_order(page: Page) -> bool:
        """Click the 'Add to library' confirm button in Epic's purchase modal.

        The modal may live in the main document or inside a purchase iframe, so we
        scan every frame for the button.
        """
        confirm_xpath = (
            "//button[contains(normalize-space(.), 'Add to library') "
            "or contains(normalize-space(.), 'Add To Library') "
            "or contains(normalize-space(.), 'Place Order')]"
        )
        for _ in range(20):
            for frame in page.frames:
                with suppress(Exception):
                    btn = frame.locator(confirm_xpath).first
                    if await btn.count() > 0 and await btn.is_enabled(timeout=1000):
                        logger.debug(f"Confirm order in frame: {frame.url[:70]}")
                        await btn.click()
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

    async def _claim_via_get(self, url: str, agent: AgentV) -> None:
        page = self.page
        logger.debug(f"Claiming {url}")
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(3000)

        cta = page.locator("//button[@data-testid='purchase-cta-button']")
        try:
            status = (await cta.text_content(timeout=15000) or "").strip()
        except TimeoutError:
            logger.warning(f"No purchase CTA found - {url}")
            return

        logger.debug(f"CTA text={status!r} - {url}")
        if any(s in status for s in ("In Library", "Owned", "Manage", "Launch")):
            logger.success(f"Already in the library - {url}")
            return
        if "Get" not in status:
            logger.warning(f"Not a free 'Get' offer (cta={status!r}) - {url}")
            return

        # --> Click "Get" to open the purchase confirmation modal (no cart needed)
        await cta.click()
        await page.wait_for_timeout(2000)
        await self._agree_license(page)

        if not await self._confirm_free_order(page):
            await self._screenshot(page, url, "no-confirm")
            logger.warning(f"'Add to library' confirm button not found - {url}")
            return

        # A hCaptcha challenge may appear after confirming the order
        with suppress(Exception):
            await asyncio.wait_for(agent.wait_for_challenge(), timeout=180)

        await page.wait_for_timeout(5000)

        with suppress(TimeoutError):
            new_status = (await cta.text_content(timeout=8000) or "").strip()
            if any(s in new_status for s in ("In Library", "Owned", "Manage")):
                logger.success(f"🎉 Claimed - {url}")
                return

        await self._screenshot(page, url, "unconfirmed")
        logger.warning(f"Claim not confirmed - {url}")

    async def collect_weekly_games(self, promotions: List[PromotionGame]):
        agent = AgentV(page=self.page, agent_config=settings)
        for p in promotions:
            try:
                await self._claim_via_get(p.url, agent)
            except Exception as err:
                logger.warning(f"Failed to claim {p.url} - {err}")
