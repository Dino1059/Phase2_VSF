import ipaddress
import socket
from urllib.parse import urlparse


FORBIDDEN_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_webhook_url(url: str, allow_http: bool = True) -> bool:
    """Validate webhook URL against SSRF attacks by checking scheme and resolving DNS

    to reject private, loopback, link-local, and cloud metadata IP address ranges.
    """
    if not url or not isinstance(url, str):
        return False

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
    except Exception:
        return False

    scheme = (parsed.scheme or "").lower()
    allowed_schemes = ("https", "http") if allow_http else ("https",)
    if scheme not in allowed_schemes:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Resolve IP addresses for hostname
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except Exception:
        return False

    if not addr_info:
        return False

    resolved_ips = set()
    for item in addr_info:
        sockaddr = item[4]
        if sockaddr and len(sockaddr) > 0:
            resolved_ips.add(sockaddr[0])

    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_unspecified:
            return False

        for net in FORBIDDEN_IP_NETWORKS:
            if ip_obj in net:
                return False

    return True
