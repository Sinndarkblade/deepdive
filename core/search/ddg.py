"""
DuckDuckGo Search — Zero setup, no API key, no account.
In practice no hard limit, but rate-limit yourself to avoid blocks.
"""

from ddgs import DDGS
import time


class DDGSearch:
    """DuckDuckGo search engine for DeepDive."""

    def __init__(self, delay=1.0):
        self.delay = delay  # seconds between searches to avoid rate limiting
        self.total_searches = 0

    @property
    def name(self):
        return "DuckDuckGo"

    def search(self, query, max_results=10):
        """
        Search DuckDuckGo. Returns list of {title, url, body}.
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            self.total_searches += 1
            time.sleep(self.delay)
            return results
        except Exception as e:
            print(f"[DDG] Search error: {e}")
            return []

    def search_news(self, query, max_results=10):
        """Search DuckDuckGo News."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
            self.total_searches += 1
            time.sleep(self.delay)
            return results
        except Exception as e:
            print(f"[DDG] News search error: {e}")
            return []

    def multi_angle_search(self, subject):
        """
        Run 5 search angles on a subject. Returns combined results.
        This is the OSINT search pattern.
        """
        angles = [
            f"{subject} connections associates background",
            f"{subject} funding money investors transactions payments",
            f"{subject} leadership employees partners associates",
            f"{subject} lawsuit scandal investigation controversy",
            f"{subject} location headquarters address offices properties",
        ]

        all_results = {}
        for i, query in enumerate(angles):
            angle_names = ["overview", "money", "people", "legal", "locations"]
            results = self.search(query, max_results=8)
            all_results[angle_names[i]] = results
            print(f"  [{angle_names[i]}] {len(results)} results")

        return all_results

    def deep_search(self, subject, follow_up_queries=None):
        """
        Deep search: initial multi-angle + follow-up queries.
        """
        results = self.multi_angle_search(subject)

        if follow_up_queries:
            for query in follow_up_queries:
                extra = self.search(query, max_results=5)
                results[f"followup_{query[:30]}"] = extra
                print(f"  [followup] {len(extra)} results for: {query[:50]}")

        # Combine all text for entity extraction
        all_text = ""
        for angle, hits in results.items():
            for hit in hits:
                all_text += hit.get('body', '') + "\n"
                all_text += hit.get('title', '') + "\n"

        return results, all_text
