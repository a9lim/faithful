"""Diagnostic checks for ``faithful doctor``."""
from __future__ import annotations

import asyncio

from .config import Config
from .wizard import validate_credentials


def check_discord_token(token: str) -> str | None:
    """Try to log in to Discord with the token. Returns error string or None."""
    import discord

    async def _try():
        client = discord.Client(intents=discord.Intents.default())
        try:
            await asyncio.wait_for(client.login(token), timeout=10)
        except discord.LoginFailure as e:
            return f"invalid token: {e}"
        except asyncio.TimeoutError:
            return "connection timed out after 10s"
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {e}"
        finally:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass
        return None

    return asyncio.run(_try())


def check_llm_provider(config: Config) -> str | None:
    """Reuse the wizard's per-backend validator."""
    return validate_credentials(
        config.backend.active,
        config.backend.api_key,
        config.backend.model,
        config.backend.base_url,
    )


def run_doctor(config: Config) -> int:
    """Run all checks and print a checklist. Returns exit code (0 = all pass)."""
    failed = 0

    print("Running diagnostics...\n")
    print(f"  ✓ config loaded ({config.backend.active})")
    if config.data_dir.is_dir():
        print(f"  ✓ data dir at {config.data_dir}")
    else:
        print(f"  ✗ data dir missing at {config.data_dir}")
        failed += 1

    err = check_discord_token(config.discord.token)
    if err is None:
        print("  ✓ Discord token valid")
    else:
        print(f"  ✗ Discord: {err}")
        failed += 1

    err = check_llm_provider(config)
    if err is None:
        print(f"  ✓ {config.backend.active}: {config.backend.model} OK")
    else:
        print(f"  ✗ {config.backend.active}: {err}")
        failed += 1

    if failed == 0:
        print("\nAll checks passed.")
        return 0
    print(f"\n{failed} check(s) failed.")
    return 1
