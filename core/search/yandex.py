"""
Yandex OSINT Search — web search, reverse image, email/username lookup, geolocation.
No API key required. All free.
"""

import requests
import re
import json
import os
import sys
from typing import List, Dict, Optional


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


class YandexSearch:
    """Yandex OSINT tools for DeepDive."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    @property
    def name(self):
        return "Yandex"

    # ── Web Search ──

    def search(self, query, max_results=10) -> List[Dict]:
        """Search Yandex web. Scrapes results directly."""
        try:
            url = 'https://yandex.com/search/'
            params = {'text': query, 'lr': 84}  # lr=84 = USA region
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []

            results = []
            # Parse search results from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')

            # Yandex organic results
            for item in soup.select('.serp-item'):
                link_el = item.select_one('a.OrganicTitle-Link, a[href]')
                title_el = item.select_one('.OrganicTitle-LinkText, h2')
                snippet_el = item.select_one('.OrganicTextContentSpan, .TextContainer')

                if link_el and title_el:
                    href = link_el.get('href', '')
                    # Skip yandex internal links
                    if 'yandex.' in href and '/search' in href:
                        continue
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': href,
                        'body': snippet_el.get_text(strip=True) if snippet_el else '',
                        'source': 'Yandex',
                    })
                    if len(results) >= max_results:
                        break

            return results
        except Exception as e:
            print(f"[Yandex] Search error: {e}")
            return []

    def search_news(self, query, max_results=10) -> List[Dict]:
        """Search Yandex News."""
        try:
            url = 'https://newssearch.yandex.com/news/search'
            params = {'text': query}
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []

            results = []
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')

            for item in soup.select('.news-search-item, .search-item'):
                title_el = item.select_one('a.mg-snippet__title, .news-search-item__title a, a')
                snippet_el = item.select_one('.mg-snippet__text, .news-search-item__snippet')

                if title_el:
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': title_el.get('href', ''),
                        'body': snippet_el.get_text(strip=True) if snippet_el else '',
                        'source': 'Yandex News',
                    })
                    if len(results) >= max_results:
                        break

            return results
        except Exception as e:
            print(f"[Yandex] News search error: {e}")
            return []

    # ── Reverse Image Search ──

    def reverse_image_search(self, image_url=None, image_path=None, max_results=10) -> List[Dict]:
        """Yandex reverse image search. Pass either a URL or a local file path."""
        try:
            if image_url:
                url = 'https://yandex.com/images/search'
                params = {'rpt': 'imageview', 'url': image_url}
                r = self.session.get(url, params=params, timeout=self.timeout)
            elif image_path:
                url = 'https://yandex.com/images/search'
                with open(image_path, 'rb') as f:
                    files = {'upfile': f}
                    r = self.session.post(url, files=files, data={'rpt': 'imageview'},
                                          timeout=self.timeout)
            else:
                return []

            if not r.ok:
                return []

            results = []
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')

            # Extract similar image results
            for item in soup.select('.CbirSites-Item, .other-sites__item'):
                title_el = item.select_one('.CbirSites-ItemTitle a, a')
                desc_el = item.select_one('.CbirSites-ItemDescription, .other-sites__snippet')

                if title_el:
                    results.append({
                        'title': title_el.get_text(strip=True),
                        'url': title_el.get('href', ''),
                        'body': desc_el.get_text(strip=True) if desc_el else '',
                        'source': 'Yandex Images',
                    })
                    if len(results) >= max_results:
                        break

            return results
        except Exception as e:
            print(f"[Yandex] Image search error: {e}")
            return []

    # ── Email/Username Lookup (via YaSeeker) ──

    def lookup_email(self, email) -> Optional[Dict]:
        """Look up a Yandex account by email using YaSeeker."""
        return self._yaseeker_lookup(email, 'email')

    def lookup_username(self, username) -> Optional[Dict]:
        """Look up a Yandex account by username."""
        return self._yaseeker_lookup(username, 'login')

    def _yaseeker_lookup(self, identifier, id_type) -> Optional[Dict]:
        """Run YaSeeker lookup."""
        try:
            tools_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'yaseeker')
            sys.path.insert(0, tools_dir)
            from ya_seeker import YandexIdAggregator

            aggregator = YandexIdAggregator(identifier, cookies={})
            aggregator.run()

            result = {
                'identifier': identifier,
                'type': id_type,
                'source': 'YaSeeker',
                'services': {},
            }

            for service_name, service_data in aggregator.sites_results.items():
                if service_data:
                    result['services'][service_name] = service_data

            if aggregator.info:
                result['profile'] = dict(aggregator.info)

            return result if result.get('services') or result.get('profile') else None
        except Exception as e:
            print(f"[Yandex] YaSeeker error: {e}")
            return None

    # ── Phone Number Lookup ──

    def search_phone(self, phone_number) -> List[Dict]:
        """Search Yandex for phone number information."""
        # Yandex web search with phone number — often reveals business listings,
        # spam databases, and directory entries
        results = self.search(f'"{phone_number}"', max_results=10)
        # Also check with formatted variants
        clean = re.sub(r'[^\d+]', '', phone_number)
        if clean != phone_number:
            results.extend(self.search(f'"{clean}"', max_results=5))
        return results

    # ── Geolocation ──

    def search_location(self, query) -> List[Dict]:
        """Search Yandex Maps for location data."""
        try:
            url = 'https://yandex.com/maps/api/search'
            params = {'text': query, 'lang': 'en_US', 'results': 10}
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.ok:
                try:
                    data = r.json()
                    results = []
                    for feature in data.get('features', []):
                        props = feature.get('properties', {})
                        geo = feature.get('geometry', {})
                        results.append({
                            'name': props.get('name', ''),
                            'description': props.get('description', ''),
                            'address': props.get('address', ''),
                            'coordinates': geo.get('coordinates', []),
                            'source': 'Yandex Maps',
                        })
                    return results
                except:
                    pass
            # Fallback: regular search with location terms
            return self.search(f'{query} address location', max_results=5)
        except Exception as e:
            print(f"[Yandex] Location search error: {e}")
            return []

    # ── Multi-angle OSINT Search ──

    def deep_search(self, subject) -> tuple:
        """Run comprehensive Yandex OSINT search on a subject."""
        all_results = {}
        all_text = ""

        # Web search
        web = self.search(subject, max_results=10)
        all_results['yandex_web'] = web
        for r in web:
            all_text += r.get('body', '') + "\n" + r.get('title', '') + "\n"

        # News
        news = self.search_news(subject, max_results=5)
        all_results['yandex_news'] = news
        for r in news:
            all_text += r.get('body', '') + "\n" + r.get('title', '') + "\n"

        # If it looks like a phone number
        if re.match(r'^[\d\+\-\(\)\s]{7,}$', subject.strip()):
            phone_results = self.search_phone(subject)
            all_results['yandex_phone'] = phone_results

        # If it looks like an email
        if '@' in subject:
            email_result = self.lookup_email(subject)
            if email_result:
                all_results['yandex_email'] = [email_result]

        return all_results, all_text
