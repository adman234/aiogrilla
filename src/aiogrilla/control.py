# src/aiogrilla/control.py
"""Remote-control helpers: setpoint command payloads and the PowerDown REST call."""

from __future__ import annotations

from typing import Any

import aiohttp

from . import const
from .exceptions import GrillaAuthError, GrillaConnectionError


def grill_target_command(temp_f: float) -> dict[str, Any]:
    """Build the grill setpoint command, rounded to the app's 5 °F step.

    Raises ValueError when the rounded value is outside the app's 180-500 °F range."""
    step = const.GRILL_TARGET_STEP_F
    value = int(round(temp_f / step) * step)
    if not const.GRILL_TARGET_MIN_F <= value <= const.GRILL_TARGET_MAX_F:
        raise ValueError(
            f"grill target {temp_f} °F is outside "
            f"{const.GRILL_TARGET_MIN_F}-{const.GRILL_TARGET_MAX_F} °F"
        )
    return {"cmd": const.CMD_TARGET_TEMP, "data": value}


def probe_target_command(temp_f: float, probe: int = 1) -> dict[str, Any]:
    """Build a food-probe setpoint command (probe 1 or 2), rounded to whole °F.

    Raises ValueError for an unknown probe or a value outside the app's 100-225 °F range."""
    cmd = const.CMD_PROBE_TARGET_TEMP.get(probe)
    if cmd is None:
        raise ValueError(f"unknown probe {probe}; expected 1 or 2")
    value = int(round(temp_f))
    if not const.PROBE_TARGET_MIN_F <= value <= const.PROBE_TARGET_MAX_F:
        raise ValueError(
            f"probe target {temp_f} °F is outside "
            f"{const.PROBE_TARGET_MIN_F}-{const.PROBE_TARGET_MAX_F} °F"
        )
    return {"cmd": cmd, "data": value}


async def async_power_down(session: aiohttp.ClientSession, *, id_token: str, grill_id: str) -> None:
    """POST the vendor's PowerDown call for one grill.

    401/403 -> GrillaAuthError; other HTTP errors or network failures -> GrillaConnectionError.
    """
    headers = {"Authorization": f"Bearer {id_token}"}
    try:
        async with session.post(
            f"{const.API_POWER_DOWN}/",
            headers=headers,
            json={"grill_id": grill_id},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status in (401, 403):
                raise GrillaAuthError(f"power-down unauthorized ({resp.status})")
            if resp.status >= 400:
                raise GrillaConnectionError(f"power-down returned {resp.status}")
    except aiohttp.ClientError as err:
        raise GrillaConnectionError("power-down request failed") from err
