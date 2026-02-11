import logging

from .bot import Faithful
from .config import Config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
    )

    config = Config()
    bot = Faithful(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
