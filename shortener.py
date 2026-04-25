import string
import secrets
import threading

_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 6

_url_to_code: dict[str, str] = {}
_code_to_url: dict[str, str] = {}
_hits: dict[str, int] = {}
_lock = threading.Lock()


def _generate_code() -> str:
    # Called within shorten, so lock is already held.
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if code not in _code_to_url:
            return code


def shorten(url: str) -> str:
    if not url:
        raise ValueError("URL cannot be empty")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")

    with _lock:
        if url in _url_to_code:
            return _url_to_code[url]
        code = _generate_code()
        _url_to_code[url] = code
        _code_to_url[code] = url
        _hits[code] = 0
        return code


def resolve(code: str) -> str | None:
    with _lock:
        url = _code_to_url.get(code)
        if url is not None:
            _hits[code] += 1
        return url


def stats() -> dict:
    with _lock:
        return dict(_hits)


if __name__ == "__main__":
    try:
        code1 = shorten("https://example.com")
        code2 = shorten("https://anthropic.com")
        code3 = shorten("https://example.com")

        print(f"shorten('https://example.com')    -> {code1}")
        print(f"shorten('https://anthropic.com')  -> {code2}")
        print(f"shorten('https://example.com')    -> {code3} (same as first)")

        print(f"resolve({code1!r}) -> {resolve(code1)}")
        print(f"resolve({code2!r}) -> {resolve(code2)}")
        print(f"resolve({code1!r}) -> {resolve(code1)}")
        print(f"resolve('missing') -> {resolve('missing')}")

        print(f"stats() -> {stats()}")
    except ValueError as e:
        print(f"Error: {e}")
