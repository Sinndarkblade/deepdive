"""
Search Engine Wrapper — picks the best available search backend.
Priority: SearXNG (unlimited) > DuckDuckGo (easy) > None
"""


def get_search_engine(prefer=None):
    """Get the best available search engine."""

    if prefer == "searxng":
        from .searxng import SearXNGSearch
        engine = SearXNGSearch(auto_start=True)
        if engine.running:
            return engine
        print("[Search] SearXNG not available, falling back to DuckDuckGo")

    if prefer == "ddg" or prefer is None:
        try:
            from .ddg import DDGSearch
            return DDGSearch()
        except ImportError:
            print("[Search] DuckDuckGo not installed: pip install duckduckgo-search")

    if prefer == "searxng":
        # Already tried, fall through
        pass

    # Try both in order
    try:
        from .ddg import DDGSearch
        return DDGSearch()
    except:
        pass

    try:
        from .searxng import SearXNGSearch
        engine = SearXNGSearch(auto_start=True)
        if engine.running:
            return engine
    except:
        pass

    print("[Search] No search engine available!")
    print("  Install: pip install duckduckgo-search")
    print("  Or: docker pull searxng/searxng")
    return None
