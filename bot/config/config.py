from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str


    REF_LINK: str = "https://t.me/BybitCoinsweeper_Bot?start=referredBy=6624523270"
    GAME_PLAY_EACH_ROUND: list[int] = [2, 4]
    TIME_PLAY_EACH_GAME: list[int] = [130, 180]

    DELAY_EACH_ACCOUNT: list[int] = [20, 30]

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()

