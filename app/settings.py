"""Settings and per-account configuration loaded from the environment / .env."""

from pathlib import Path
from typing import List
from urllib.parse import urlparse

from hcaptcha_challenger.agent import AgentConfig
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent
VOLUMES_DIR = PROJECT_ROOT.joinpath("volumes")

LOG_DIR = VOLUMES_DIR.joinpath("logs")
USER_DATA_DIR = VOLUMES_DIR.joinpath("user_data")

RUNTIME_DIR = VOLUMES_DIR.joinpath("runtime")
SCREENSHOTS_DIR = VOLUMES_DIR.joinpath("screenshots")
HCAPTCHA_DIR = VOLUMES_DIR.joinpath("hcaptcha")


class EpicAccount(BaseModel):
    email: str
    password: SecretStr
    proxy: str | None = None


def _parse_proxy(raw: str | None) -> dict | None:
    if not raw:
        return None

    parsed = urlparse(raw)
    if not parsed.hostname:
        return None

    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server = f"{server}:{parsed.port}"

    proxy = {"server": server}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


class EpicSettings(AgentConfig):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    EPIC_EMAIL: str | None = Field(
        default=None, description="Epic account email, 2FA must be disabled"
    )

    EPIC_PASSWORD: SecretStr | None = Field(
        default=None, description="Epic account password, 2FA must be disabled"
    )

    EPIC_ACCOUNTS: List[EpicAccount] = Field(
        default_factory=list,
        description="Multiple accounts as a JSON array. Takes precedence over EPIC_EMAIL/EPIC_PASSWORD",
    )

    EPIC_PROXY: str | None = Field(
        default=None,
        description="Default proxy (e.g. http://user:pass@host:port) for accounts without their own proxy",
    )

    DISABLE_BEZIER_TRAJECTORY: bool = Field(
        default=True,
        description="Disable bezier-curve trajectory simulation and rely on Camoufox's native behaviour",
    )

    cache_dir: Path = HCAPTCHA_DIR.joinpath(".cache")
    challenge_dir: Path = HCAPTCHA_DIR.joinpath(".challenge")
    captcha_response_dir: Path = HCAPTCHA_DIR.joinpath(".captcha")

    ENABLE_APSCHEDULER: bool = Field(
        default=True, description="Keep running as a scheduler after the immediate run"
    )

    CRON_SCHEDULE: str = Field(
        default="30 12 * * *",
        description="Cron expression for recurring runs when ENABLE_APSCHEDULER is true",
    )

    SCHEDULE_TIMEZONE: str = Field(
        default="UTC", description="Timezone for the cron schedule and log timestamps"
    )

    TELEGRAM_BOT_TOKEN: str | None = Field(
        default=None, description="Telegram bot token for notifications (optional)"
    )

    TELEGRAM_CHAT_ID: str | None = Field(
        default=None, description="Telegram chat id to notify (optional)"
    )

    TASK_TIMEOUT_SECONDS: int = Field(
        default=900, description="Maximum execution time for browser tasks before force termination"
    )

    @property
    def accounts(self) -> List[EpicAccount]:
        if self.EPIC_ACCOUNTS:
            return self.EPIC_ACCOUNTS
        if self.EPIC_EMAIL and self.EPIC_PASSWORD:
            return [EpicAccount(email=self.EPIC_EMAIL, password=self.EPIC_PASSWORD)]
        return []

    def user_data_dir_for(self, email: str) -> Path:
        target_ = USER_DATA_DIR.joinpath(email)
        if not target_.is_dir():
            target_.mkdir(parents=True, exist_ok=True)
        return target_

    def proxy_for(self, account: EpicAccount) -> dict | None:
        return _parse_proxy(account.proxy or self.EPIC_PROXY)


settings = EpicSettings()
settings.ignore_request_questions = ["Please drag the crossing to complete the lines"]
