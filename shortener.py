import secrets
import string
import threading
from urllib.parse import urlparse

_ALPHABET = string.ascii_letters + string.digits
_CODE_LEN = 7

_lock = threading.Lock()
_store: dict[str, str] = {}   # code -> original url
_hits: dict[str, int] = {}    # code -> hit count


def _generate_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url!r}")


def shorten(url: str) -> str:
    _validate_url(url)
    with _lock:
        # Return existing code if this URL was already shortened.
        for code, stored in _store.items():
            if stored == url:
                return code
        while True:
            code = _generate_code()
            if code not in _store:
                break
        _store[code] = url
        _hits[code] = 0
        return code


def resolve(code: str) -> str | None:
    with _lock:
        url = _store.get(code)
        if url is not None:
            _hits[code] += 1
        return url


def stats() -> dict:
    with _lock:
        return dict(_hits)


if __name__ == "__main__":
    urls = [
        "https://www.example.com/some/long/path?query=1",
        "https://openai.com/research/gpt-4",
        "https://www.example.com/some/long/path?query=1",  # duplicate
    ]

    print("=== shorten ===")
    codes = []
    for url in urls:
        code = shorten(url)
        codes.append(code)
        print(f"  {url!r:55s} -> {code}")

    print("\n=== resolve ===")
    for code in dict.fromkeys(codes):  # unique codes
        original = resolve(code)
        print(f"  {code} -> {original!r}")

    # Resolve one code a second time to bump its hit count.
    resolve(codes[0])

    print("\n=== stats ===")
    for code, count in stats().items():
        print(f"  {code}: {count} hit(s)")

    print("\n=== invalid URL ===")
    try:
        shorten("not-a-url")
    except ValueError as exc:
        print(f"  Caught: {exc}")
