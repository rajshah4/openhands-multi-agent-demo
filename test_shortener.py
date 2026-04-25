import pytest
import concurrent.futures
import shortener
from shortener import shorten, resolve, stats

@pytest.fixture(autouse=True)
def reset_state():
    """Reset the module-level state before each test to ensure isolation."""
    shortener._url_to_code.clear()
    shortener._code_to_url.clear()
    shortener._hits.clear()
    yield

def test_shorten_happy_path():
    url = "https://example.com"
    code = shorten(url)
    assert isinstance(code, str)
    assert len(code) == 6
    assert resolve(code) == url

def test_shorten_same_url_returns_same_code():
    url = "https://example.com"
    code1 = shorten(url)
    code2 = shorten(url)
    assert code1 == code2

def test_shorten_invalid_urls():
    with pytest.raises(ValueError, match="URL cannot be empty"):
        shorten("")
    
    with pytest.raises(ValueError, match="URL must start with http:// or https://"):
        shorten("ftp://example.com")
        
    with pytest.raises(ValueError, match="URL must start with http:// or https://"):
        shorten("example.com")

def test_resolve_missing_code():
    assert resolve("nonexistent") is None

def test_stats_tracking():
    url1 = "https://example.com"
    url2 = "https://anthropic.com"
    
    code1 = shorten(url1)
    code2 = shorten(url2)
    
    resolve(code1)
    resolve(code1)
    resolve(code2)
    
    s = stats()
    assert s[code1] == 2
    assert s[code2] == 1

def test_thread_safety_concurrent_shorten():
    """Verify that concurrent calls to shorten work safely and generate unique codes."""
    num_threads = 50
    urls = [f"https://example.com/{i}" for i in range(num_threads)]
    
    def worker(url):
        return shorten(url)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(worker, url): url for url in urls}
        codes = [future.result() for future in concurrent.futures.as_completed(futures)]
        
    assert len(codes) == num_threads
    assert len(set(codes)) == num_threads
    
    for url, code in zip(urls, codes):
        # Note: the order might be different, but we can check if each code resolves correctly
        pass
    
    # Check all are in stats
    s = stats()
    assert len(s) == num_threads
