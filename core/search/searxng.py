"""
SearXNG Search — Self-hosted, NO limits, NO tracking.
Searches multiple engines simultaneously (Google, Bing, DuckDuckGo, etc).
Runs in Docker on localhost.
"""

import json
import subprocess
import time
import requests


class SearXNGSearch:
    """SearXNG self-hosted metasearch engine."""

    def __init__(self, base_url="http://localhost:8888", auto_start=True):
        self.base_url = base_url
        self.running = False
        self.total_searches = 0

        if auto_start:
            self.ensure_running()

    @property
    def name(self):
        return "SearXNG (self-hosted)"

    def ensure_running(self):
        """Start SearXNG Docker container if not running."""
        try:
            r = requests.get(f"{self.base_url}/healthz", timeout=3)
            if r.status_code == 200:
                self.running = True
                return True
        except:
            pass

        # Try to start it
        print("[SearXNG] Starting Docker container...")
        try:
            # Check if container exists but stopped
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=deepdive-searxng", "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=10
            )

            if "Exited" in result.stdout:
                subprocess.run(["docker", "start", "deepdive-searxng"],
                               capture_output=True, timeout=30)
            elif not result.stdout.strip():
                # Create new container
                subprocess.run([
                    "docker", "run", "-d",
                    "--name", "deepdive-searxng",
                    "-p", "8888:8080",
                    "-e", "SEARXNG_BASE_URL=http://localhost:8888",
                    "searxng/searxng:latest"
                ], capture_output=True, timeout=60)

            # Wait for it to be ready
            for i in range(30):
                try:
                    r = requests.get(f"{self.base_url}/healthz", timeout=2)
                    if r.status_code == 200:
                        self.running = True
                        print("[SearXNG] Ready")
                        return True
                except:
                    time.sleep(1)

        except Exception as e:
            print(f"[SearXNG] Failed to start: {e}")

        return False

    def search(self, query, max_results=10, categories="general"):
        """Search via SearXNG API."""
        if not self.running:
            if not self.ensure_running():
                return []

        try:
            params = {
                "q": query,
                "format": "json",
                "categories": categories,
                "pageno": 1,
            }
            r = requests.get(f"{self.base_url}/search", params=params, timeout=30)
            data = r.json()
            results = data.get("results", [])[:max_results]
            self.total_searches += 1

            # Normalize to same format as DDG
            normalized = []
            for item in results:
                normalized.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "body": item.get("content", ""),
                    "engine": item.get("engine", ""),
                })
            return normalized
        except Exception as e:
            print(f"[SearXNG] Search error: {e}")
            return []

    def search_news(self, query, max_results=10):
        """Search news category."""
        return self.search(query, max_results, categories="news")

    def multi_angle_search(self, subject):
        """Same 5-angle OSINT pattern as DDG."""
        angles = [
            f"{subject} connections associates background",
            f"{subject} funding money investors transactions payments",
            f"{subject} leadership employees partners associates",
            f"{subject} lawsuit scandal investigation controversy",
            f"{subject} location headquarters address offices properties",
        ]

        all_results = {}
        angle_names = ["overview", "money", "people", "legal", "locations"]
        for i, query in enumerate(angles):
            results = self.search(query, max_results=10)
            all_results[angle_names[i]] = results
            print(f"  [{angle_names[i]}] {len(results)} results")

        return all_results

    def deep_search(self, subject, follow_up_queries=None):
        """Deep search with follow-ups."""
        results = self.multi_angle_search(subject)

        if follow_up_queries:
            for query in follow_up_queries:
                extra = self.search(query, max_results=5)
                results[f"followup_{query[:30]}"] = extra

        all_text = ""
        for angle, hits in results.items():
            for hit in hits:
                all_text += hit.get('body', '') + "\n"
                all_text += hit.get('title', '') + "\n"

        return results, all_text

    def stop(self):
        """Stop the Docker container."""
        subprocess.run(["docker", "stop", "deepdive-searxng"], capture_output=True)
        self.running = False
