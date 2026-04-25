"""AirPlay session detection via unicast mDNS probe."""
import asyncio
import struct

_MDNS_PORT = 5353
_RAOP_SERVICE = "_raop._tcp.local"
# Set while an AirPlay session is active; clear when idle.
_SF_SESSION_ACTIVE = 0x0800


def _encode_name(name: str) -> bytes:
    result = b""
    for label in name.rstrip(".").split("."):
        enc = label.encode()
        result += bytes([len(enc)]) + enc
    return result + b"\x00"


def _build_query(name: str) -> bytes:
    header = struct.pack(">HHHHHH", 0x0001, 0x0000, 1, 0, 0, 0)
    question = _encode_name(name) + struct.pack(">HH", 255, 1)  # ANY, class IN
    return header + question


def _parse_name(data: bytes, offset: int):
    labels = []
    visited = set()
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(data):
                break
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            if ptr in visited:
                break
            visited.add(ptr)
            name, _ = _parse_name(data, ptr)
            labels.append(name)
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset + length].decode(errors="replace"))
        offset += length
    return ".".join(labels), offset


def _parse_txt_record(rdata: bytes) -> dict:
    result = {}
    pos = 0
    while pos < len(rdata):
        length = rdata[pos]
        pos += 1
        if length == 0 or pos + length > len(rdata):
            break
        item = rdata[pos:pos + length]
        pos += length
        if b"=" in item:
            k, _, v = item.partition(b"=")
            result[k.decode(errors="replace")] = v.decode(errors="replace")
        else:
            result[item.decode(errors="replace")] = ""
    return result


def _parse_response(data: bytes) -> list:
    if len(data) < 12:
        return []
    _tid, _flags, qdcount, ancount, nscount, arcount = struct.unpack(">HHHHHH", data[:12])
    offset = 12
    for _ in range(qdcount):
        _, offset = _parse_name(data, offset)
        offset += 4
    records = []
    for _ in range(ancount + nscount + arcount):
        if offset >= len(data):
            break
        name, offset = _parse_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata_offset = offset
        rdata = data[offset:offset + rdlen]
        offset += rdlen
        rec = {"name": name, "type": rtype}
        if rtype == 12:  # PTR — rdata is an encoded name; parse from original packet for pointer support
            rec["ptr"], _ = _parse_name(data, rdata_offset)
        elif rtype == 16:  # TXT
            rec["txt"] = _parse_txt_record(rdata)
        records.append(rec)
    return records


class _RaopProtocol(asyncio.DatagramProtocol):
    def __init__(self, future: asyncio.Future) -> None:
        self._future = future

    def datagram_received(self, data: bytes, addr) -> None:
        if not self._future.done():
            self._future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc) -> None:
        if exc and not self._future.done():
            self._future.set_exception(exc)


async def _probe(loop, ip: str, query: bytes, timeout: float):
    """Send one UDP query to ip:5353 and return the first response packet, or None."""
    future = loop.create_future()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _RaopProtocol(future),
        remote_addr=(ip, _MDNS_PORT),
    )
    try:
        transport.sendto(query)
        return await asyncio.wait_for(future, timeout=timeout)
    except Exception:
        return None
    finally:
        transport.close()


async def is_airplay_active(ip: str, timeout: float = 1.0) -> bool:
    """Return True if an AirPlay session is active on the soundbar at *ip*."""
    try:
        loop = asyncio.get_running_loop()

        # Step 1: PTR query to discover the service instance name.
        ptr_data = await _probe(loop, ip, _build_query(_RAOP_SERVICE), timeout)
        if ptr_data is None:
            return False
        instance_names = [
            rec["ptr"] for rec in _parse_response(ptr_data)
            if rec["type"] == 12 and "_raop._tcp" in rec.get("ptr", "")
        ]
        if not instance_names:
            return False

        # Step 2: TXT query for the instance to read the session-active flag.
        txt_data = await _probe(loop, ip, _build_query(instance_names[0]), timeout)
        if txt_data is None:
            return False
        for rec in _parse_response(txt_data):
            if rec["type"] == 16 and "_raop._tcp" in rec.get("name", ""):
                sf_raw = rec.get("txt", {}).get("sf")
                if sf_raw is not None:
                    return bool(int(sf_raw, 16) & _SF_SESSION_ACTIVE)
        return False
    except Exception:
        return False
