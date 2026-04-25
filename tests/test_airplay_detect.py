"""Tests for AirPlay detection via mDNS unicast probe."""
import asyncio
import struct

from unittest.mock import MagicMock, patch

from custom_components.samsung_soundbar.airplay_detect import is_airplay_active

_RAOP_SERVICE = "_raop._tcp.local"
_INSTANCE_NAME = "AABBCCDDEEFF@MySoundbar._raop._tcp.local"


# ---------------------------------------------------------------------------
# DNS packet helpers
# ---------------------------------------------------------------------------

def _encode_name(name: str) -> bytes:
    result = b""
    for label in name.rstrip(".").split("."):
        enc = label.encode()
        result += bytes([len(enc)]) + enc
    return result + b"\x00"


def _build_ptr_response(service: str, instance: str) -> bytes:
    """Build a minimal one-answer DNS PTR response packet."""
    encoded_service = _encode_name(service)
    encoded_instance = _encode_name(instance)
    header = struct.pack(">HHHHHH", 0x0001, 0x8400, 0, 1, 0, 0)
    answer = encoded_service + struct.pack(">HHIH", 12, 1, 4500, len(encoded_instance)) + encoded_instance
    return header + answer


def _build_txt_response(name: str, txt_fields: dict) -> bytes:
    """Build a minimal one-answer DNS TXT response packet."""
    rdata = b""
    for k, v in txt_fields.items():
        item = f"{k}={v}".encode()
        rdata += bytes([len(item)]) + item

    encoded_name = _encode_name(name)
    header = struct.pack(">HHHHHH", 0x0001, 0x8400, 0, 1, 0, 0)
    answer = encoded_name + struct.pack(">HHIH", 16, 1, 4500, len(rdata)) + rdata
    return header + answer


def _endpoint_mock(loop, *responses):
    """
    Return an async callable that mimics loop.create_datagram_endpoint.

    responses[i] is delivered to the protocol on the i-th call. If a call
    index exceeds the list, no data is delivered (simulates timeout).
    """
    responses = list(responses)
    calls = []

    async def fake(protocol_factory, *, remote_addr=None, **kwargs):
        idx = len(calls)
        calls.append(idx)
        response_data = responses[idx] if idx < len(responses) else None
        protocol = protocol_factory()
        transport = MagicMock()
        protocol.connection_made(transport)
        if response_data is not None:
            addr = (remote_addr[0] if remote_addr else "0.0.0.0", 5353)
            loop.call_soon(protocol.datagram_received, response_data, addr)
        return transport, protocol

    return fake


# ---------------------------------------------------------------------------
# Two-step happy path
# ---------------------------------------------------------------------------

async def test_airplay_active_sf_session_bit_set():
    """PTR → TXT with sf=0x0804 (bit 0x0800 set) → True."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    txt_resp = _build_txt_response(_INSTANCE_NAME, {"sf": "0x804"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp, txt_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is True


async def test_airplay_inactive_sf_session_bit_clear():
    """PTR → TXT with sf=0x0004 (bit 0x0800 clear) → False."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    txt_resp = _build_txt_response(_INSTANCE_NAME, {"sf": "0x4"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp, txt_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


# ---------------------------------------------------------------------------
# Step 1 (PTR) failures
# ---------------------------------------------------------------------------

async def test_step1_timeout_returns_false():
    """No response to PTR query → returns False without raising."""
    loop = asyncio.get_running_loop()
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop)):
        result = await is_airplay_active("192.168.1.100", timeout=0.05)
    assert result is False


async def test_step1_no_ptr_records_returns_false():
    """Step 1 response contains only TXT (wrong type) — no PTR → False."""
    loop = asyncio.get_running_loop()
    txt_only = _build_txt_response(_RAOP_SERVICE, {"sf": "0x804"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, txt_only)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


async def test_step1_ptr_wrong_service_returns_false():
    """PTR record in step 1 points to a non-RAOP service → False."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response("_airplay._tcp.local",
                                   "AABBCCDDEEFF@MySoundbar._airplay._tcp.local")
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


# ---------------------------------------------------------------------------
# Step 2 (TXT) failures
# ---------------------------------------------------------------------------

async def test_step2_timeout_returns_false():
    """PTR succeeds but TXT query times out → False."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    # Only one response supplied; second _probe call gets no data → timeout.
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp)):
        result = await is_airplay_active("192.168.1.100", timeout=0.1)
    assert result is False


async def test_step2_no_sf_field_returns_false():
    """Step 2 TXT record has no sf key → False."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    txt_resp = _build_txt_response(_INSTANCE_NAME, {"pk": "abcd1234"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp, txt_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


async def test_step2_sf_not_valid_hex_returns_false():
    """sf value that cannot be parsed as hex → False without raising."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    txt_resp = _build_txt_response(_INSTANCE_NAME, {"sf": "not-a-hex"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp, txt_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


async def test_step2_txt_wrong_service_returns_false():
    """Step 2 TXT record name does not contain _raop._tcp → False."""
    loop = asyncio.get_running_loop()
    ptr_resp = _build_ptr_response(_RAOP_SERVICE, _INSTANCE_NAME)
    txt_resp = _build_txt_response("_airplay._tcp.local", {"sf": "0x804"})
    with patch.object(loop, "create_datagram_endpoint",
                      side_effect=_endpoint_mock(loop, ptr_resp, txt_resp)):
        result = await is_airplay_active("192.168.1.100")
    assert result is False


# ---------------------------------------------------------------------------
# Transport / network errors
# ---------------------------------------------------------------------------

async def test_oserror_on_step1_returns_false():
    """OSError when opening the UDP socket → returns False without raising."""
    loop = asyncio.get_running_loop()

    async def raise_oserror(*args, **kwargs):
        raise OSError("Network unreachable")

    with patch.object(loop, "create_datagram_endpoint", side_effect=raise_oserror):
        result = await is_airplay_active("192.168.1.100")
    assert result is False
