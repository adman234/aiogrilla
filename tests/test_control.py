# tests/test_control.py
import aiohttp
import pytest

from aiogrilla import const
from aiogrilla.control import async_power_down, grill_target_command, probe_target_command
from aiogrilla.exceptions import GrillaAuthError, GrillaConnectionError


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self) -> "_FakeResp":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, resp: _FakeResp | None = None, exc: Exception | None = None) -> None:
        self._resp = resp
        self._exc = exc
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs: object) -> _FakeResp:
        self.calls.append((url, kwargs))
        if self._exc is not None:
            raise self._exc
        assert self._resp is not None
        return self._resp


@pytest.mark.parametrize(
    ("temp", "sent"), [(225, 225), (227, 225), (228, 230), (180, 180), (500, 500), (181.5, 180)]
)
def test_grill_target_rounds_to_five(temp, sent):
    assert grill_target_command(temp) == {"cmd": "desired_temp", "data": sent}


@pytest.mark.parametrize("temp", [175, 177, 503, 600, -10])
def test_grill_target_out_of_range(temp):
    with pytest.raises(ValueError):
        grill_target_command(temp)


def test_probe_targets_use_per_probe_commands():
    assert probe_target_command(165) == {"cmd": "desired_probe_temp", "data": 165}
    assert probe_target_command(203.4, 2) == {"cmd": "desired_probe2_temp", "data": 203}


@pytest.mark.parametrize("temp", [99, 226, 300])
def test_probe_target_out_of_range(temp):
    with pytest.raises(ValueError):
        probe_target_command(temp)


def test_probe_target_unknown_probe():
    with pytest.raises(ValueError):
        probe_target_command(150, 3)


async def test_power_down_posts_grill_id_with_bearer_token():
    session = _FakeSession(_FakeResp(200))
    await async_power_down(session, id_token="ID", grill_id="sx1")  # type: ignore[arg-type]
    [(url, kwargs)] = session.calls
    assert url == f"{const.API_POWER_DOWN}/"
    assert kwargs["headers"] == {"Authorization": "Bearer ID"}
    assert kwargs["json"] == {"grill_id": "sx1"}


@pytest.mark.parametrize("status", [401, 403])
async def test_power_down_unauthorized_is_auth_error(status):
    session = _FakeSession(_FakeResp(status))
    with pytest.raises(GrillaAuthError):
        await async_power_down(session, id_token="ID", grill_id="sx1")  # type: ignore[arg-type]


async def test_power_down_server_error_is_connection_error():
    session = _FakeSession(_FakeResp(502))
    with pytest.raises(GrillaConnectionError):
        await async_power_down(session, id_token="ID", grill_id="sx1")  # type: ignore[arg-type]


async def test_power_down_network_error_is_connection_error():
    session = _FakeSession(exc=aiohttp.ClientConnectionError("down"))
    with pytest.raises(GrillaConnectionError):
        await async_power_down(session, id_token="ID", grill_id="sx1")  # type: ignore[arg-type]
