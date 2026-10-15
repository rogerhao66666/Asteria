"""Authentication tokens, TLS contexts and the "do not expose this to the internet by accident"
guard for the multiplayer server.

A token is ``<player id>.<expiry unix time>.<signature>`` where the signature is an HMAC-SHA256 of
the first two parts under a secret only the server operator holds. A server with a secret refuses
a ``hello`` whose token is missing, expired, forged or issued for another player id - so a guest id
can no longer be claimed by someone who merely knows it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import ssl
import time
from dataclasses import dataclass

from .protocol import clean_guest_id

MAX_TTL = 365 * 24 * 3600


class AuthError(ValueError):
    pass


def _sign(secret: bytes, body: str) -> str:
    digest = hmac.new(secret, body.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class TokenAuthenticator:
    """Issues and checks signed player tokens."""

    def __init__(self, secret, *, clock=time.time):
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        if not isinstance(secret, bytes | bytearray) or len(secret) < 16:
            raise ValueError("the auth secret must be at least 16 bytes")
        self._secret = bytes(secret)
        self._clock = clock

    def issue(self, player_id, ttl_seconds=24 * 3600):
        player_id = clean_guest_id(player_id)
        ttl = int(ttl_seconds)
        if not 1 <= ttl <= MAX_TTL:
            raise ValueError("ttl_seconds must be between 1 second and one year")
        expires = int(self._clock()) + ttl
        body = f"{player_id}.{expires}"
        return f"{body}.{_sign(self._secret, body)}"

    def verify(self, token, player_id=None):
        """The player id the token belongs to; raises ``AuthError`` if it cannot be trusted."""
        if not isinstance(token, str) or token.count(".") != 2 or len(token) > 256:
            raise AuthError("malformed token")
        who, expires, signature = token.split(".")
        expected = _sign(self._secret, f"{who}.{expires}")
        if not hmac.compare_digest(signature, expected):
            raise AuthError("invalid token signature")
        if not expires.isdigit() or int(expires) < self._clock():
            raise AuthError("token has expired")
        try:
            who = clean_guest_id(who)
        except ValueError as exc:
            raise AuthError("token names an invalid player") from exc
        if player_id is not None and who != player_id:
            raise AuthError("token was issued for a different player")
        return who


def load_secret(path):
    """Read an auth secret from a file (surrounding whitespace is ignored)."""
    with open(path, "rb") as handle:
        return handle.read().strip()


@dataclass(frozen=True, slots=True)
class TlsSettings:
    certfile: str
    keyfile: str

    def server_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.certfile, self.keyfile)
        return context


def client_context(cafile=None, *, verify=True):
    """A TLS client context that verifies the server (``cafile`` for a private certificate)."""
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if not verify:  # for tests against a throw-away certificate only
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def is_loopback(host):
    host = str(host)
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_exposure(host, *, tls, auth, allow_insecure=False):
    """Refuse to listen beyond this machine without encryption and authentication.

    Binding to ``127.0.0.1`` is always fine. Any other address needs TLS and a token secret, unless
    the operator passes ``allow_insecure`` (a trusted LAN) - the choice is explicit, never default.
    """
    if is_loopback(host) or allow_insecure:
        return
    missing = [name for name, on in (("TLS", tls), ("authentication", auth)) if not on]
    if missing:
        raise ValueError(
            f"refusing to listen on {host} without {' and '.join(missing)} "
            "(use 127.0.0.1, enable them, or pass --insecure-lan for a trusted network)"
        )


def main(argv=None):
    """``python -m asteria.multiplayer.security issue --secret-file F --player ID [--hours N]``
    prints a token the player puts in their connection profile."""
    import argparse

    parser = argparse.ArgumentParser(description="Issue a multiplayer player token")
    parser.add_argument("command", choices=("issue",))
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--hours", type=float, default=24.0)
    args = parser.parse_args(argv)
    try:
        auth = TokenAuthenticator(load_secret(args.secret_file))
        print(auth.issue(args.player, ttl_seconds=int(args.hours * 3600)))
    except (OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
