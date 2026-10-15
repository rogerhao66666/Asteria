"""Multiplayer hardening: signed tokens, TLS, the exposure guard and the adapter allow-list."""

from __future__ import annotations

import shutil
import subprocess
import threading

import pytest

from asteria.multiplayer import MultiplayerClient, MultiplayerServer
from asteria.multiplayer.client import MultiplayerClientError
from asteria.multiplayer.examples import build_counter_adapter
from asteria.multiplayer.security import (
    AuthError,
    TlsSettings,
    TokenAuthenticator,
    check_exposure,
    client_context,
    is_loopback,
)
from asteria.multiplayer.server import _load_adapter

SECRET = "a-secret-of-at-least-16-bytes"


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_a_token_names_its_player_and_is_checked():
    clock = Clock()
    auth = TokenAuthenticator(SECRET, clock=clock)
    token = auth.issue("alice", ttl_seconds=60)
    assert auth.verify(token) == "alice" and auth.verify(token, "alice") == "alice"
    with pytest.raises(AuthError, match="different player"):
        auth.verify(token, "bob")
    clock.now += 61
    with pytest.raises(AuthError, match="expired"):
        auth.verify(token)


def test_forged_and_malformed_tokens_are_rejected():
    auth = TokenAuthenticator(SECRET)
    other = TokenAuthenticator("another-secret-of-16+bytes")
    token = other.issue("alice")
    with pytest.raises(AuthError, match="signature"):
        auth.verify(token)
    who, expires, signature = auth.issue("alice").split(".")
    with pytest.raises(AuthError, match="signature"):  # swapping the name breaks the signature
        auth.verify(f"bob.{expires}.{signature}")
    with pytest.raises(AuthError, match="signature"):  # so does stretching the expiry
        auth.verify(f"{who}.{int(expires) + 99999}.{signature}")
    for bad in ("", "a.b", "a.b.c.d", None, 12, "x" * 300):
        with pytest.raises(AuthError):
            auth.verify(bad)


def test_secrets_and_lifetimes_are_validated():
    with pytest.raises(ValueError):
        TokenAuthenticator("short")
    auth = TokenAuthenticator(SECRET)
    with pytest.raises(ValueError):
        auth.issue("alice", ttl_seconds=0)
    with pytest.raises(ValueError):
        auth.issue("bad name!")


@pytest.mark.parametrize(
    "host, expected", [("127.0.0.1", True), ("::1", True), ("localhost", True), ("0.0.0.0", False)]
)
def test_loopback_detection(host, expected):
    assert is_loopback(host) is expected


def test_listening_beyond_this_machine_needs_tls_and_tokens_unless_forced():
    check_exposure("127.0.0.1", tls=False, auth=False)
    with pytest.raises(ValueError, match="TLS and authentication"):
        check_exposure("0.0.0.0", tls=False, auth=False)
    with pytest.raises(ValueError, match="authentication"):
        check_exposure("192.168.1.5", tls=True, auth=False)
    check_exposure("0.0.0.0", tls=True, auth=True)
    check_exposure("0.0.0.0", tls=False, auth=False, allow_insecure=True)
    with pytest.raises(ValueError):
        MultiplayerServer(("0.0.0.0", 0), adapter=build_counter_adapter())


def test_the_adapter_allow_list_limits_what_a_server_will_import():
    adapter = _load_adapter(
        "asteria.multiplayer.examples:build_counter_adapter",
        allowed_prefixes=["asteria.multiplayer"],
    )
    assert hasattr(adapter, "handle_command")
    with pytest.raises(ValueError, match="allow-list"):
        _load_adapter("os:getcwd", allowed_prefixes=["asteria.multiplayer"])
    with pytest.raises(ValueError, match="allow-list"):
        _load_adapter("asteria.multiplayerevil:x", allowed_prefixes=["asteria.multiplayer"])
    assert _load_adapter("asteria.multiplayer.examples:build_counter_adapter") is not None


@pytest.fixture
def start():
    started = []

    def run(**options):
        server = MultiplayerServer(("127.0.0.1", 0), adapter=build_counter_adapter(), **options)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append((server, thread))
        return server

    yield run
    for server, thread in started:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _join(server, **kwargs):
    client = MultiplayerClient()
    try:
        return client, client.connect(*server.server_address[:2], "Ann", **kwargs)
    except Exception:
        client.close()
        raise


def test_a_server_with_a_secret_only_admits_holders_of_a_valid_token(start):
    auth = TokenAuthenticator(SECRET)
    server = start(authenticator=auth)
    with pytest.raises(MultiplayerClientError, match="authentication failed"):
        _join(server)
    with pytest.raises(MultiplayerClientError, match="authentication failed"):
        _join(server, guest_id="alice", token="alice.1.forged")
    with pytest.raises(MultiplayerClientError, match="different player"):
        _join(server, guest_id="bob", token=auth.issue("alice"))
    client, welcome = _join(server, token=auth.issue("alice"))  # the token names the player
    try:
        assert welcome["player_id"] == "alice"
    finally:
        client.close()
    assert server.metrics_snapshot()["rejected"]["auth"] == 3


def test_a_claimed_guest_id_cannot_be_hijacked_once_a_secret_is_required(start):
    auth = TokenAuthenticator(SECRET)
    server = start(authenticator=auth)
    owner, _ = _join(server, guest_id="alice", token=auth.issue("alice"))
    try:
        with pytest.raises(MultiplayerClientError):
            _join(server, guest_id="alice", token=auth.issue("mallory"))
    finally:
        owner.close()


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    if shutil.which("openssl") is None:
        pytest.skip("the openssl command is not available")
    folder = tmp_path_factory.mktemp("tls")
    cert, key = folder / "cert.pem", folder / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return TlsSettings(str(cert), str(key))


def test_tls_encrypts_the_session_and_clients_verify_the_server(start, certificate):
    server = start(tls=certificate)
    client, welcome = _join(server, tls=True, cafile=certificate.certfile)
    try:
        assert welcome["type"] == "welcome"
        client.send_command("increment", {"amount": 2})
        assert client.connected
    finally:
        client.close()


def test_a_client_that_does_not_trust_the_certificate_cannot_connect(start, certificate):
    server = start(tls=certificate)
    with pytest.raises(MultiplayerClientError):
        _join(server, tls=True)  # the default trust store does not know this certificate
    insecure = client_context(verify=False)  # explicit opt-out, for throw-away certificates only
    client, welcome = _join(server, tls=insecure)
    client.close()
    assert welcome["type"] == "welcome"


def test_a_plaintext_client_gets_nowhere_on_a_tls_server(start, certificate):
    server = start(tls=certificate)
    with pytest.raises(MultiplayerClientError):
        _join(server, timeout=1.0)
    assert server.metrics_snapshot()["peak_players"] == 0


def test_tls_and_tokens_work_together(start, certificate):
    auth = TokenAuthenticator(SECRET)
    server = start(tls=certificate, authenticator=auth)
    client, welcome = _join(
        server, tls=True, cafile=certificate.certfile, token=auth.issue("carol")
    )
    client.close()
    assert welcome["player_id"] == "carol"


def test_the_issue_command_prints_a_token_the_server_accepts(tmp_path, capsys):
    from asteria.multiplayer.security import main

    secret = tmp_path / "secret"
    secret.write_text(SECRET + "\n")
    assert main(["issue", "--secret-file", str(secret), "--player", "dana", "--hours", "1"]) == 0
    token = capsys.readouterr().out.strip()
    assert TokenAuthenticator(SECRET).verify(token, "dana") == "dana"
    assert main(["issue", "--secret-file", str(tmp_path / "missing"), "--player", "dana"]) == 2
    short = tmp_path / "short"
    short.write_text("tiny")
    assert main(["issue", "--secret-file", str(short), "--player", "dana"]) == 2
