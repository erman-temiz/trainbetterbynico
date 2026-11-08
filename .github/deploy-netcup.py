"""Publish the static site with explicit TLS and verify the public response."""

from contextlib import contextmanager
from ftplib import FTP_TLS
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4
import os
import ssl


PUBLIC_URL = "https://trainbetterbynico.de/"
FILES = ("styles.css", "impressum.html", "datenschutz.html", "index.html")
ADDRESS_TOKEN = "{{IMPRESSUM_STRASSE}}"


def build_pages(street):
    pages = {}
    for name in FILES:
        source = Path("website", name).read_text(encoding="utf-8")
        if name in {"impressum.html", "datenschutz.html"}:
            if source.count(ADDRESS_TOKEN) != 1:
                raise SystemExit(f"Adressplatzhalter fehlt oder ist doppelt in {name}.")
            source = source.replace(ADDRESS_TOKEN, escape(street))
        pages[name] = source.encode("utf-8")
    return pages


@contextmanager
def verified_ftp(host, tls):
    candidates = (host, "a981d.netcup.net", "a981d.webhosting.systems")
    original_ip = None

    for candidate in dict.fromkeys(candidates):
        ftp = FTP_TLS(context=tls, timeout=20)
        try:
            try:
                ftp.connect(candidate, 21)
            except OSError:
                if candidate == host:
                    raise
                continue
            peer_ip = ftp.sock.getpeername()[0]
            if original_ip is None:
                original_ip = peer_ip
            if peer_ip != original_ip:
                continue
            try:
                ftp.auth()
            except ssl.SSLCertVerificationError as error:
                print(f"FTPES-Zertifikat für {candidate}: {error.verify_message}")
                continue

            print("FTPES-Zertifikat erfolgreich geprüft.")
            yield ftp
            return
        finally:
            ftp.close()

    raise SystemExit("Für den Netcup-FTP-Endpunkt wurde kein gültiger Zertifikatsname gefunden.")


def deploy():
    keys = ("NETCUP_FTP_HOST", "NETCUP_FTP_USER", "NETCUP_FTP_PASSWORD", "IMPRESSUM_STRASSE")
    missing = [key for key in keys if not os.environ.get(key)]
    if missing:
        raise SystemExit("GitHub-Secrets fehlen: " + ", ".join(missing))
    host, user, password, street = (os.environ[key] for key in keys)
    pages = build_pages(street)
    tls = ssl.create_default_context()

    with urlopen(PUBLIC_URL, timeout=15, context=tls) as response:
        if not response.url.startswith(("https://trainbetterbynico.de/", "https://www.trainbetterbynico.de/")):
            raise SystemExit("Die Domain liefert noch keine eigene Seite über HTTPS.")

    batch = uuid4().hex
    with verified_ftp(host, tls) as ftp:
        ftp.login(user, password)
        ftp.prot_p()
        for name, content in pages.items():
            ftp.storbinary(f"STOR .deploy-{batch}-{name}", BytesIO(content))
        for name in FILES:
            ftp.rename(f".deploy-{batch}-{name}", name)

    for name, content in pages.items():
        with urlopen(f"{PUBLIC_URL}{name}?deploy={batch}", timeout=15, context=tls) as response:
            if response.read() != content:
                raise SystemExit(f"HTTPS-Prüfung fehlgeschlagen: {name}")
    print("Alle vier Dateien wurden über HTTPS verifiziert.")


if __name__ == "__main__":
    deploy()
