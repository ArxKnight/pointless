import ipaddress
import socket
import struct
import time
from functools import lru_cache

from app.runtime_config import access_settings

ANS_ASN = "61323"
ANS_ORG_MARKERS = ("ANS ACADEMY LIMITED", "UKFAST")
ANS_REVERSE_DNS_MARKERS = ("srvlist.ukfast.net", "ukfast.net")
ANS_KNOWN_NETWORKS = tuple(ipaddress.ip_network(n) for n in ("81.201.128.0/20", "176.124.52.0/22"))
CACHE_SECONDS = 3600
_ip_cache: dict[str, tuple[float, bool, str]] = {}


def client_ip_from_headers(headers: dict, fallback: str | None = None) -> str | None:
    # Cloudflare terminates TLS in front of the app and connects onward from a
    # Cloudflare edge IP. nginx then overwrites X-Forwarded-For with that edge
    # IP, so the only reliable end-user address available at the app boundary is
    # CF-Connecting-IP (or True-Client-IP on some Cloudflare plans).
    cloudflare_ip = headers.get("cf-connecting-ip") or headers.get("CF-Connecting-IP")
    if parse_ip(cloudflare_ip) is not None:
        return cloudflare_ip
    true_client_ip = headers.get("true-client-ip") or headers.get("True-Client-IP")
    if parse_ip(true_client_ip) is not None:
        return true_client_ip

    forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if forwarded:
        # Prefer the right-most public address: nginx/proxies append to the chain,
        # so this avoids trusting a client-supplied spoofed first value while still
        # skipping local Docker/proxy hops.
        valid: list[str] = []
        for part in [p.strip() for p in forwarded.split(",") if p.strip()]:
            if parse_ip(part) is not None:
                valid.append(part)
        public = [part for part in valid if not is_local_address(part)]
        if public:
            return public[-1]
        if valid:
            return valid[-1]
    return headers.get("x-real-ip") or headers.get("X-Real-IP") or fallback


def parse_ip(value: str | None):
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.split(":")[0] if value.count(":") == 1 else value)
    except ValueError:
        return None


def is_local_address(value: str | None) -> bool:
    ip = parse_ip(value)
    if ip is None:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def _dns_query_txt(name: str, server: str = "1.1.1.1", timeout: float = 1.0) -> list[str]:
    labels = name.rstrip(".").split(".")
    query_id = int(time.time() * 1000) & 0xFFFF
    packet = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    for label in labels:
        encoded = label.encode("ascii")
        packet += bytes([len(encoded)]) + encoded
    packet += b"\0" + struct.pack("!HH", 16, 1)  # TXT, IN
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (server, 53))
        data, _ = sock.recvfrom(2048)
    if len(data) < 12:
        return []
    _, _, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", data[:12])
    offset = 12

    def skip_name(pos: int) -> int:
        while pos < len(data):
            length = data[pos]
            if length & 0xC0 == 0xC0:
                return pos + 2
            if length == 0:
                return pos + 1
            pos += 1 + length
        return pos

    for _ in range(qdcount):
        offset = skip_name(offset) + 4
    results: list[str] = []
    for _ in range(ancount):
        offset = skip_name(offset)
        if offset + 10 > len(data):
            break
        rtype, _, _, rdlength = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlength]
        offset += rdlength
        if rtype == 16 and rdata:
            pos = 0
            chunks: list[str] = []
            while pos < len(rdata):
                size = rdata[pos]
                pos += 1
                chunks.append(rdata[pos:pos + size].decode("utf-8", "ignore"))
                pos += size
            results.append("".join(chunks))
    return results


def _cymru_asn_org(ip: ipaddress._BaseAddress) -> tuple[str | None, str | None]:
    if ip.version != 4:
        return None, None
    reversed_ip = ".".join(reversed(str(ip).split(".")))
    try:
        origin = _dns_query_txt(f"{reversed_ip}.origin.asn.cymru.com")
        if not origin:
            return None, None
        asn = origin[0].split("|")[0].strip()
        org_rows = _dns_query_txt(f"AS{asn}.asn.cymru.com")
        org = org_rows[0].split("|", 4)[-1].strip() if org_rows else None
        return asn, org
    except Exception:
        return None, None


def _detect_ans_network(ip_text: str) -> tuple[bool, str]:
    ip = parse_ip(ip_text)
    if ip is None or is_local_address(ip_text):
        return False, "local-or-invalid"
    if any(ip in network for network in ANS_KNOWN_NETWORKS):
        return True, "known ANS/UKFAST netblock"
    try:
        host = socket.gethostbyaddr(str(ip))[0].lower().rstrip(".")
        if any(marker in host for marker in ANS_REVERSE_DNS_MARKERS):
            return True, f"reverse DNS {host}"
    except Exception:
        pass
    asn, org = _cymru_asn_org(ip)
    if asn == ANS_ASN or (org and any(marker in org.upper() for marker in ANS_ORG_MARKERS)):
        return True, f"ASN {asn} {org or ''}".strip()
    return False, "not ANS/UKFAST"


def is_ans_network(ip_text: str | None) -> tuple[bool, str]:
    if not ip_text:
        return False, "missing client IP"
    now = time.time()
    cached = _ip_cache.get(ip_text)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1], cached[2]
    blocked, reason = _detect_ans_network(ip_text)
    _ip_cache[ip_text] = (now, blocked, reason)
    return blocked, reason


def access_decision(client_ip: str | None, settings: dict | None = None) -> tuple[bool, str]:
    cfg = settings or access_settings()
    if cfg.get("local_only_enabled") and not is_local_address(client_ip):
        return False, "Not Found"
    if cfg.get("block_ans_network_enabled", True):
        blocked, reason = is_ans_network(client_ip)
        if blocked:
            return False, "Not Found"
    return True, "ok"
