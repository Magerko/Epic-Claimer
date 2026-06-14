"""Epic Games sign-in: reuse a cached session when present, otherwise log in and
solve the hCaptcha challenge."""

import asyncio
import time
from contextlib import suppress

from hcaptcha_challenger.agent import AgentV
from loguru import logger
from playwright.async_api import expect, Page, Response

from settings import SCREENSHOTS_DIR, settings, EpicAccount

URL_CLAIM = "https://store.epicgames.com/en-US/free-games"


class EpicAuthorization:

    def __init__(self, page: Page, account: EpicAccount):
        self.page = page
        self.account = account

        self._is_login_success_signal = asyncio.Queue()
        self._is_refresh_csrf_signal = asyncio.Queue()

    async def _on_response_anything(self, r: Response):
        if r.request.method != "POST" or "talon" in r.url:
            return

        with suppress(Exception):
            result = await r.json()
            if "/id/api/login" in r.url and result.get("errorCode"):
                logger.error(f"Login error: {result.get('errorCode')}")
            elif "/id/api/analytics" in r.url and result.get("accountId"):
                self._is_login_success_signal.put_nowait(result)
            elif "/account/v2/refresh-csrf" in r.url and result.get("success") is True:
                self._is_refresh_csrf_signal.put_nowait(result)

    async def _dismiss_post_login_prompts(self):
        """Click through the optional prompts Epic shows right after sign-in (the
        security check, the "set up 2FA" offer, etc.) until the account page settles.

        #login-reminder-prompt-setup-tfa-skip is the button that declines the 2FA setup.
        """
        await self.page.goto("https://www.epicgames.com/account/personal", wait_until="networkidle")

        buttons = ["#link-success", "#login-reminder-prompt-setup-tfa-skip", "#yes"]
        while self._is_refresh_csrf_signal.empty() and buttons:
            await self.page.wait_for_timeout(500)
            for selector in buttons.copy():
                with suppress(Exception):
                    button = self.page.locator(selector)
                    await expect(button).to_be_visible(timeout=1000)
                    await button.click(timeout=1000)
                    buttons.remove(selector)

    async def _login(self) -> bool | None:
        agent = AgentV(page=self.page, agent_config=settings)
        logger.debug("Login with Email")

        try:
            point_url = (
                "https://www.epicgames.com/account/personal"
                "?lang=en-US&productName=egs&sessionInvalidated=true"
            )
            await self.page.goto(point_url, wait_until="domcontentloaded")

            email_input = self.page.locator("#email")
            await email_input.clear()
            await email_input.type(self.account.email)
            await self.page.click("#continue")

            password_input = self.page.locator("#password")
            await password_input.clear()
            await password_input.type(self.account.password.get_secret_value())

            # Submitting arms the hCaptcha listener, which the agent then solves
            await self.page.click("#sign-in")
            await agent.wait_for_challenge()

            await asyncio.wait_for(self._is_login_success_signal.get(), timeout=60)
            logger.success("Login success")

            await asyncio.wait_for(self._dismiss_post_login_prompts(), timeout=60)
            return True
        except Exception as err:
            logger.warning(f"{err}")
            sr = SCREENSHOTS_DIR.joinpath("authorization")
            sr.mkdir(parents=True, exist_ok=True)
            await self.page.screenshot(path=sr.joinpath(f"login-{int(time.time())}.png"))
            return None

    async def invoke(self):
        self.page.on("response", self._on_response_anything)

        for _ in range(3):
            await self.page.goto(URL_CLAIM, wait_until="domcontentloaded")
            if "true" == await self.page.locator("//egs-navigation").get_attribute("isloggedin"):
                logger.success("Epic Games is already logged in")
                return True
            if await self._login():
                return
