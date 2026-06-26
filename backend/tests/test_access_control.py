import pytest

from app.services import access_control
from app.services.access_control import access_decision, client_ip_from_headers, is_local_address


def test_local_only_allows_private_and_blocks_public_addresses():
    settings = {"local_only_enabled": True, "block_ans_network_enabled": True}

    assert access_decision("192.168.1.50", settings)[0] is True
    assert access_decision("10.0.0.8", settings)[0] is True

    allowed, reason = access_decision("8.8.8.8", settings)
    assert allowed is False
    assert "Internet access is disabled" in reason


def test_ans_network_block_detects_known_ans_ranges():
    settings = {"local_only_enabled": False, "block_ans_network_enabled": True}

    allowed, reason = access_decision("81.201.139.20", settings)
    assert allowed is False
    assert "ANS/UKFast" in reason

    allowed, reason = access_decision("176.124.53.12", settings)
    assert allowed is False
    assert "ANS/UKFast" in reason


def test_ans_network_block_can_be_disabled():
    settings = {"local_only_enabled": False, "block_ans_network_enabled": False}

    assert access_decision("81.201.139.20", settings)[0] is True


def test_x_forwarded_for_uses_rightmost_public_address():
    headers = {"x-forwarded-for": "8.8.8.8, 81.201.139.20, 172.18.0.2"}

    assert client_ip_from_headers(headers, "172.18.0.3") == "81.201.139.20"


def test_reverse_dns_ukfast_detection(monkeypatch):
    monkeypatch.setattr(access_control, "ANS_KNOWN_NETWORKS", tuple())
    monkeypatch.setattr(access_control.socket, "gethostbyaddr", lambda ip: ("8.8.8.8.srvlist.ukfast.net", [], [ip]))
    monkeypatch.setattr(access_control, "_cymru_asn_org", lambda ip: (None, None))

    blocked, reason = access_control._detect_ans_network("8.8.8.8")
    assert blocked is True
    assert "srvlist.ukfast.net" in reason
