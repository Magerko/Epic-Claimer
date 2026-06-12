# -*- coding: utf-8 -*-
"""
@Time    : 2025/7/16 21:15
@Author  : QIN2DIM
@GitHub  : https://github.com/QIN2DIM
@Desc    :
"""
from pathlib import Path
from typing import List

from hcaptcha_challenger.agent import AgentConfig
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent
VOLUMES_DIR = PROJECT_ROOT.joinpath("volumes")

LOG_DIR = VOLUMES_DIR.joinpath("logs")
USER_DATA_DIR = VOLUMES_DIR.joinpath("user_data")

RUNTIME_DIR = VOLUMES_DIR.joinpath("runtime")
SCREENSHOTS_DIR = VOLUMES_DIR.joinpath("screenshots")
RECORD_DIR = VOLUMES_DIR.joinpath("record")
HCAPTCHA_DIR = VOLUMES_DIR.joinpath("hcaptcha")


class EpicAccount(BaseModel):
    email: str
    password: SecretStr


class EpicSettings(AgentConfig):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    EPIC_EMAIL: str | None = Field(default=None, description="Epic 游戏账号，需要关闭多步验证")

    EPIC_PASSWORD: SecretStr | None = Field(default=None, description="Epic 游戏密码，需要关闭多步验证")

    EPIC_ACCOUNTS: List[EpicAccount] = Field(
        default_factory=list,
        description="多账号列表，JSON 数组。设置后优先于 EPIC_EMAIL/EPIC_PASSWORD",
    )

    DISABLE_BEZIER_TRAJECTORY: bool = Field(
        default=True, description="是否关闭贝塞尔曲线轨迹模拟，默认关闭，直接使用 Camoufox 的特性"
    )

    cache_dir: Path = HCAPTCHA_DIR.joinpath(".cache")
    challenge_dir: Path = HCAPTCHA_DIR.joinpath(".challenge")
    captcha_response_dir: Path = HCAPTCHA_DIR.joinpath(".captcha")

    ENABLE_APSCHEDULER: bool = Field(default=True, description="是否启用定时任务，默认启用")

    TASK_TIMEOUT_SECONDS: int = Field(
        default=900,
        description="Maximum execution time for browser tasks before force termination",
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


settings = EpicSettings()
settings.ignore_request_questions = ["Please drag the crossing to complete the lines"]
