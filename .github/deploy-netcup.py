"""Publish the static site with explicit TLS and verify the public response."""

from contextlib import contextmanager
from hashlib import sha256
from ftplib import FTP_TLS, error_perm
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4
import os
import re
import ssl


PUBLIC_URL = "https://trainbetterbynico.de/"
ROOT = Path("website")
ADDRESS_TOKEN = "{{IMPRESSUM_STRASSE}}"
ADDRESS_PAGES = {"impressum.html", "datenschutz.html"}
ASSET_REF = re.compile(r"((?:assets/[\w.-]+|favicon\.png|apple-touch-icon\.png))(?=[\s\"])")


def collect_files():
    """All files below website/, with index.html last so the new page goes live only at the end."""
    files = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and (path.name == ".htaccess" or not any(part.startswith(".") for part in path.relative_to(ROOT).parts))
    )
    if "index.html" not in files:
        raise SystemExit("website/index.html fehlt.")
    files.remove("index.html")
    return files + ["index.html"]


def build_pages(street):
    pages = {}
    # Cache-busting: every HTML page references styles.css with a content hash,
    # so browsers and server caches never mix new pages with an old stylesheet.
    # Same for every image and icon: replaced photos keep their file name,
    # so the hash in the URL forces browsers to load the new version.
    def version(rel):
        return sha256((ROOT / rel).read_bytes()).hexdigest()[:10]

    def bust(match):
        rel = match.group(1)
        if rel.endswith(".woff2") or not (ROOT / rel).is_file():
            return rel  # Schrift wird per CSS ohne Version geladen, Preload muss identisch sein
        return f"{rel}?v={version(rel)}"

    css_version = version("styles.css")
    for name in collect_files():
        data = (ROOT / name).read_bytes()
        if name.endswith(".html"):
            source = data.decode("utf-8")
            if 'href="styles.css"' not in source:
                raise SystemExit(f"Stylesheet-Link fehlt in {name}.")
            source = source.replace('href="styles.css"', f'href="styles.css?v={css_version}"')
            source = ASSET_REF.sub(bust, source)
            data = source.encode("utf-8")
        if name in ADDRESS_PAGES and ADDRESS_TOKEN in data.decode("utf-8"):
            if not street:
                raise SystemExit(f"{name} nutzt {ADDRESS_TOKEN}, aber das Secret IMPRESSUM_STRASSE fehlt.")
            data = data.decode("utf-8").replace(ADDRESS_TOKEN, escape(street)).encode("utf-8")
        pages[name] = data
    return pages


def ensure_dirs(ftp, names):
    for folder in sorted({str(Path(n).parent) for n in names if "/" in n}, key=len):
        try:
            ftp.mkd(folder)
        except error_perm as error:
            if not str(error).startswith("550"):
                raise


def temp_name(name, batch):
    path = Path(name)
    return str(path.with_name(f".deploy-{batch}-{path.name}")) if path.parent != Path(".") else f".deploy-{batch}-{name}"


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
    keys = ("NETCUP_FTP_HOST", "NETCUP_FTP_USER", "NETCUP_FTP_PASSWORD")
    missing = [key for key in keys if not os.environ.get(key)]
    if missing:
        raise SystemExit("GitHub-Secrets fehlen: " + ", ".join(missing))
    host, user, password = (os.environ[key] for key in keys)
    street = os.environ.get("IMPRESSUM_STRASSE", "")
    pages = build_pages(street)
    tls = ssl.create_default_context()

    with urlopen(PUBLIC_URL, timeout=15, context=tls) as response:
        if not response.url.startswith(("https://trainbetterbynico.de/", "https://www.trainbetterbynico.de/")):
            raise SystemExit("Die Domain liefert noch keine eigene Seite über HTTPS.")

    batch = uuid4().hex
    with verified_ftp(host, tls) as ftp:
        ftp.login(user, password)
        ftp.prot_p()
        ensure_dirs(ftp, pages)
        for name, content in pages.items():
            ftp.storbinary(f"STOR {temp_name(name, batch)}", BytesIO(content))
        for name in pages:
            ftp.rename(temp_name(name, batch), name)

    for name, content in pages.items():
        if name == ".htaccess":
            continue  # wird vom Server nie ausgeliefert
        with urlopen(f"{PUBLIC_URL}{name}?deploy={batch}", timeout=15, context=tls) as response:
            body = response.read()
        if name.endswith(".php"):
            # PHP wird auf dem Server ausgeführt: der Quelltext darf nie öffentlich sichtbar sein.
            if b"<?php" in body:
                raise SystemExit(f"PHP wird nicht ausgeführt, Quelltext sichtbar: {name}")
        elif body != content:
            raise SystemExit(f"HTTPS-Prüfung fehlgeschlagen: {name}")
    print(f"Alle {len(pages)} Dateien wurden über HTTPS verifiziert.")


if __name__ == "__main__":
    deploy()
