"""Entry point — run with `python -m faithy`."""

import logging

from .bot import Faithy
from .config import Config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s",
    )

    config = Config()
    bot = Faithy(config)
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
