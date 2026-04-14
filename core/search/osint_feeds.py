#!/usr/bin/env python3
"""
DeepDive OSINT Data Feeds — integrated from Horus, Crucix, ShadowBroker.
Pulls real-time open source intelligence from public APIs.
No API keys required for most feeds.
"""

import json
import time
import requests
from typing import Dict, List, Optional


class OSINTFeeds:
    """Aggregates OSINT data from multiple public sources."""

    def __init__(self, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        self.session.headers['Accept'] = 'application/json, text/html, */*'

    def _get(self, url, params=None):
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.ok:
                return r.json()
        except:
            pass
        return None

    # ── NEWS & GEOPOLITICS ──

    def fetch_news_rss(self, query=None) -> List[Dict]:
        """Fetch headlines from major news RSS feeds."""
        import xml.etree.ElementTree as ET

        feeds = {
            'BBC': 'http://feeds.bbci.co.uk/news/world/rss.xml',
            'NPR': 'https://feeds.npr.org/1004/rss.xml',
            'AlJazeera': 'https://www.aljazeera.com/xml/rss/all.xml',
            'GDACS': 'https://www.gdacs.org/xml/rss.xml',
        }

        articles = []
        for source, url in feeds.items():
            try:
                r = self.session.get(url, timeout=self.timeout)
                if not r.ok:
                    continue
                root = ET.fromstring(r.content)
                for item in root.iter('item'):
                    title = item.findtext('title', '')
                    desc = item.findtext('description', '')
                    link = item.findtext('link', '')
                    pub = item.findtext('pubDate', '')

                    if query and query.lower() not in (title + desc).lower():
                        continue

                    articles.append({
                        'source': source,
                        'title': title,
                        'description': desc[:300],
                        'url': link,
                        'date': pub,
                    })
            except:
                continue

        return articles[:50]

    def fetch_gdelt_events(self, query=None) -> List[Dict]:
        """Fetch recent events from GDELT — global event database."""
        import time, re
        url = 'https://api.gdeltproject.org/api/v2/doc/doc'
        # GDELT requires hyphened words to be quoted; sanitize query
        if query:
            # Quote any hyphenated multi-word names
            clean = re.sub(r'(\w+)-(\w+)', r'"\1-\2"', query)
        else:
            clean = 'investigation OR sanctions OR fraud'
        params = {
            'query': clean,
            'mode': 'artlist',
            'maxrecords': 20,
            'format': 'json',
            'timespan': '90d',
        }
        time.sleep(8)  # GDELT rate limit: 1 req per 5s
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.status_code == 429:
                time.sleep(15)
                r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []
            try:
                data = r.json()
            except Exception:
                return []
        except Exception:
            return []
        if not data or isinstance(data, str):
            return []
        return [
            {
                'title': a.get('title', ''),
                'url': a.get('url', ''),
                'source': a.get('domain', ''),
                'date': a.get('seendate', ''),
                'language': a.get('language', ''),
            }
            for a in data.get('articles', [])[:20]
        ]

    # ── FINANCIAL ──

    def fetch_stock_price(self, symbol) -> Optional[Dict]:
        """Fetch stock price from Yahoo Finance API."""
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        params = {'interval': '1d', 'range': '5d'}
        data = self._get(url, params)
        if not data:
            return None
        try:
            result = data['chart']['result'][0]
            meta = result['meta']
            return {
                'symbol': symbol,
                'price': meta.get('regularMarketPrice'),
                'previous_close': meta.get('previousClose'),
                'currency': meta.get('currency'),
                'exchange': meta.get('exchangeName'),
            }
        except:
            return None

    def fetch_fred_data(self, series_id='GDP', api_key=None) -> Optional[Dict]:
        """Fetch economic data from FRED (Federal Reserve)."""
        if not api_key:
            return None
        url = 'https://api.stlouisfed.org/fred/series/observations'
        params = {
            'series_id': series_id,
            'api_key': api_key,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 10,
        }
        data = self._get(url, params)
        if not data:
            return None
        return {
            'series': series_id,
            'observations': data.get('observations', [])[:5],
        }

    # ── GOVERNMENT & SANCTIONS ──

    def fetch_ofac_sanctions(self, query) -> List[Dict]:
        """Search OFAC sanctions list (Treasury SDN)."""
        url = 'https://sanctionssearch.ofac.treas.gov/api/search'
        params = {'query': query, 'limit': 10}
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if r.ok:
                return r.json().get('results', [])[:10]
        except:
            pass
        return []

    def fetch_usaspending(self, query) -> List[Dict]:
        """Search USAspending.gov for government contracts."""
        url = 'https://api.usaspending.gov/api/v2/search/spending_by_award/'
        try:
            r = self.session.post(url, json={
                'filters': {
                    'keywords': [query],
                    'time_period': [{'start_date': '2020-01-01', 'end_date': '2026-12-31'}],
                },
                'fields': ['Award ID', 'Recipient Name', 'Award Amount', 'Awarding Agency',
                           'Start Date', 'End Date', 'Award Type'],
                'limit': 10,
                'page': 1,
            }, timeout=self.timeout)
            if r.ok:
                return r.json().get('results', [])[:10]
        except:
            pass
        return []

    def fetch_sec_filings(self, query) -> List[Dict]:
        """Search SEC EDGAR for filings."""
        url = 'https://efts.sec.gov/LATEST/search-index'
        params = {'q': query, 'dateRange': 'custom', 'startdt': '2020-01-01', 'enddt': '2026-12-31'}
        headers = {'User-Agent': 'DeepDive OSINT research@deepdive.app'}
        try:
            r = self.session.get(
                f'https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt=2020-01-01',
                headers=headers, timeout=self.timeout)
            if r.ok:
                hits = r.json().get('hits', {}).get('hits', [])[:10]
                results = []
                for h in hits:
                    src = h.get('_source', h)
                    results.append({
                        'title': src.get('display_names', [src.get('entity_name', src.get('file_date', '?'))])[0] if isinstance(src.get('display_names'), list) else src.get('entity_name', src.get('file_date', h.get('_id', '?'))),
                        'source': 'SEC EDGAR',
                        'url': f"https://www.sec.gov/Archives/edgar/{src.get('file_path', '')}" if src.get('file_path') else '',
                        'date': src.get('period_of_report', src.get('file_date', '')),
                        'form_type': src.get('form_type', ''),
                    })
                return results
        except:
            pass
        return []

    # ── GEOSPATIAL ──

    def fetch_earthquakes(self, min_magnitude=4.0) -> List[Dict]:
        """Fetch recent earthquakes from USGS."""
        url = f'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{min_magnitude}_day.geojson'
        data = self._get(url)
        if not data:
            return []
        return [
            {
                'magnitude': f['properties'].get('mag'),
                'place': f['properties'].get('place'),
                'time': f['properties'].get('time'),
                'url': f['properties'].get('url'),
                'coordinates': f['geometry']['coordinates'] if 'geometry' in f else None,
            }
            for f in data.get('features', [])[:20]
        ]

    def fetch_flights(self, bounds=None) -> List[Dict]:
        """Fetch live flight data from ADS-B Exchange (free tier)."""
        url = 'https://api.adsb.lol/v2/mil'  # Military flights - no key needed
        data = self._get(url)
        if not data:
            return []
        return [
            {
                'callsign': a.get('flight', '').strip(),
                'hex': a.get('hex', ''),
                'type': a.get('t', ''),
                'altitude': a.get('alt_baro'),
                'speed': a.get('gs'),
                'lat': a.get('lat'),
                'lon': a.get('lon'),
                'country': a.get('dbFlags', ''),
            }
            for a in data.get('ac', [])[:50]
            if a.get('flight', '').strip()
        ]

    def fetch_satellites(self) -> List[Dict]:
        """Fetch satellite TLE data from CelesTrak."""
        url = 'https://celestrak.org/NORAD/elements/gp.php'
        params = {'GROUP': 'active', 'FORMAT': 'json'}
        data = self._get(url, params)
        if not data:
            return []
        return [
            {
                'name': s.get('OBJECT_NAME', ''),
                'norad_id': s.get('NORAD_CAT_ID', ''),
                'country': s.get('COUNTRY_CODE', ''),
                'launch_date': s.get('LAUNCH_DATE', ''),
                'period': s.get('PERIOD', ''),
            }
            for s in (data if isinstance(data, list) else [])[:30]
        ]

    # ── SOCIAL MEDIA ──

    def fetch_reddit_posts(self, subreddit='worldnews', query=None) -> List[Dict]:
        """Fetch posts from Reddit."""
        if query:
            url = f'https://www.reddit.com/r/{subreddit}/search.json'
            params = {'q': query, 'sort': 'new', 'limit': 15, 't': 'month'}
        else:
            url = f'https://www.reddit.com/r/{subreddit}/hot.json'
            params = {'limit': 15}
        data = self._get(url, params)
        if not data:
            return []
        return [
            {
                'title': p['data'].get('title', ''),
                'author': p['data'].get('author', ''),
                'score': p['data'].get('score', 0),
                'url': p['data'].get('url', ''),
                'created': p['data'].get('created_utc', 0),
                'subreddit': subreddit,
                'num_comments': p['data'].get('num_comments', 0),
            }
            for p in data.get('data', {}).get('children', [])[:15]
        ]

    # ── PATENTS ──

    def fetch_patents(self, query) -> List[Dict]:
        """Search USPTO patents."""
        url = 'https://developer.uspto.gov/ibd-api/v1/application/publications'
        params = {'searchText': query, 'start': 0, 'rows': 10}
        data = self._get(url, params)
        if not data:
            return []
        return [
            {
                'title': p.get('inventionTitle', ''),
                'patent_number': p.get('patentApplicationNumber', ''),
                'date': p.get('datePublished', ''),
                'inventors': p.get('inventorNameArrayText', ''),
                'assignee': p.get('assigneeEntityName', ''),
            }
            for p in data.get('results', [])[:10]
        ]

    # ── WAYBACK MACHINE ──

    def fetch_wayback_snapshots(self, url, limit=10) -> List[Dict]:
        """Get archived snapshots from the Wayback Machine."""
        api_url = 'https://web.archive.org/cdx/search/cdx'
        params = {
            'url': url,
            'output': 'json',
            'limit': limit,
            'fl': 'timestamp,original,statuscode,digest,length',
        }
        data = self._get(api_url, params)
        if not data or len(data) < 2:
            return []
        headers = data[0]
        return [
            {
                'timestamp': row[0],
                'url': row[1],
                'status': row[2],
                'archive_url': f'https://web.archive.org/web/{row[0]}/{row[1]}',
            }
            for row in data[1:]
        ]

    # ── ARMED CONFLICT (from Crucix/ACLED) ──

    def fetch_conflicts(self, query=None, country=None) -> List[Dict]:
        """Fetch recent armed conflict events from ACLED via GDELT fallback."""
        # Use GDELT conflict filter as free alternative to ACLED (which needs auth)
        url = 'https://api.gdeltproject.org/api/v2/doc/doc'
        search = query or 'armed conflict violence attack'
        if country:
            search += f' {country}'
        params = {
            'query': search,
            'mode': 'artlist',
            'maxrecords': 20,
            'format': 'json',
            'timespan': '14d',
        }
        data = self._get(url, params)
        if not data:
            return []
        return [
            {
                'title': a.get('title', ''),
                'url': a.get('url', ''),
                'source': a.get('domain', ''),
                'date': a.get('seendate', ''),
                'tone': a.get('tone', ''),
            }
            for a in data.get('articles', [])[:20]
        ]

    # ── NASA FIRES (from Crucix/FIRMS) ──

    def fetch_fires(self, country=None) -> List[Dict]:
        """Fetch active fire/thermal anomalies from NASA FIRMS.
        Detects wildfires, military strikes, industrial fires."""
        # FIRMS open CSV — last 24h, VIIRS
        url = 'https://firms.modaps.eosdis.nasa.gov/api/area/csv/OPEN_KEY/VIIRS_SNPP_NRT/world/1'
        try:
            r = self.session.get(url, timeout=self.timeout)
            if not r.ok:
                return []
            import csv, io
            reader = csv.DictReader(io.StringIO(r.text))
            fires = []
            for row in reader:
                if country and country.lower() not in row.get('country_id', '').lower():
                    continue
                fires.append({
                    'lat': row.get('latitude', ''),
                    'lon': row.get('longitude', ''),
                    'brightness': row.get('bright_ti4', ''),
                    'confidence': row.get('confidence', ''),
                    'date': row.get('acq_date', ''),
                    'time': row.get('acq_time', ''),
                    'source': 'NASA FIRMS',
                })
                if len(fires) >= 50:
                    break
            return fires
        except:
            return []

    # ── OPEN SANCTIONS (from Crucix) ──

    def fetch_sanctions(self, query) -> List[Dict]:
        """Search OpenSanctions — aggregated global sanctions & PEP data."""
        url = 'https://api.opensanctions.org/search/default'
        params = {'q': query, 'limit': 15}
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []
            data = r.json()
            return [
                {
                    'name': res.get('caption', ''),
                    'schema': res.get('schema', ''),
                    'datasets': ', '.join(res.get('datasets', [])[:3]),
                    'countries': ', '.join(res.get('properties', {}).get('country', [])[:3]),
                    'score': res.get('score', 0),
                    'source': 'OpenSanctions',
                }
                for res in data.get('results', [])[:15]
            ]
        except:
            return []

    # ── BLUESKY SOCIAL (from Crucix) ──

    def fetch_bluesky(self, query) -> List[Dict]:
        """Search Bluesky/AT Protocol for public posts."""
        url = 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts'
        params = {'q': query, 'limit': 20, 'sort': 'latest'}
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []
            data = r.json()
            return [
                {
                    'author': p.get('author', {}).get('handle', ''),
                    'text': p.get('record', {}).get('text', '')[:200],
                    'date': p.get('record', {}).get('createdAt', ''),
                    'likes': p.get('likeCount', 0),
                    'reposts': p.get('repostCount', 0),
                    'url': f"https://bsky.app/profile/{p.get('author', {}).get('handle', '')}/post/{p.get('uri', '').split('/')[-1]}",
                    'source': 'Bluesky',
                }
                for p in data.get('posts', [])[:20]
            ]
        except:
            return []

    # ── WHO DISEASE OUTBREAKS (from Crucix) ──

    def fetch_who_outbreaks(self, query=None) -> List[Dict]:
        """Fetch WHO disease outbreak news."""
        url = 'https://www.who.int/api/news/diseaseoutbreaknews'
        try:
            r = self.session.get(url, timeout=self.timeout)
            if not r.ok:
                return []
            data = r.json()
            items = data.get('value', [])[:20]
            results = []
            for item in items:
                title = item.get('Title', {}).get('Value', '') if isinstance(item.get('Title'), dict) else str(item.get('Title', ''))
                if query and query.lower() not in title.lower():
                    continue
                results.append({
                    'title': title,
                    'date': item.get('PublicationDate', ''),
                    'url': item.get('UrlName', ''),
                    'source': 'WHO',
                })
            return results[:15]
        except:
            return []

    # ── CISA KNOWN EXPLOITED VULNERABILITIES (from Crucix) ──

    def fetch_cisa_kev(self, query=None) -> List[Dict]:
        """Fetch CISA Known Exploited Vulnerabilities catalog."""
        url = 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json'
        data = self._get(url)
        if not data:
            return []
        vulns = data.get('vulnerabilities', [])
        if query:
            q = query.lower()
            vulns = [v for v in vulns if q in v.get('vendorProject', '').lower()
                     or q in v.get('product', '').lower()
                     or q in v.get('vulnerabilityName', '').lower()]
        return [
            {
                'cve': v.get('cveID', ''),
                'vendor': v.get('vendorProject', ''),
                'product': v.get('product', ''),
                'name': v.get('vulnerabilityName', ''),
                'date_added': v.get('dateAdded', ''),
                'due_date': v.get('dueDate', ''),
                'source': 'CISA KEV',
            }
            for v in vulns[:15]
        ]

    # ── RELIEF WEB / HUMANITARIAN (from Crucix) ──

    def fetch_humanitarian(self, query=None) -> List[Dict]:
        """Fetch humanitarian crisis reports from ReliefWeb."""
        url = 'https://api.reliefweb.int/v1/reports'
        params = {
            'appname': 'deepdive-osint',
            'limit': 15,
            'fields[include][]': ['title', 'url', 'date.created', 'source.name', 'country.name'],
        }
        if query:
            params['query[value]'] = query
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []
            data = r.json()
            return [
                {
                    'title': item.get('fields', {}).get('title', ''),
                    'date': item.get('fields', {}).get('date', {}).get('created', ''),
                    'source': ', '.join([s.get('name', '') for s in item.get('fields', {}).get('source', [])[:2]]) or 'ReliefWeb',
                    'countries': ', '.join([c.get('name', '') for c in item.get('fields', {}).get('country', [])[:3]]),
                    'url': item.get('fields', {}).get('url', ''),
                }
                for item in data.get('data', [])[:15]
            ]
        except:
            return []

    # ── SHIP TRACKING (from Crucix/ShadowBroker) ──

    def fetch_ships(self, query=None) -> List[Dict]:
        """Fetch vessel data — uses MarineTraffic-compatible public endpoint."""
        # Try the free Marine Traffic density endpoint
        # For actual vessel data, would need AIS feed
        url = 'https://services.marinetraffic.com/api/exportvessel/v:5'
        # This requires API key, so we use an alternative
        # Fall back to searching news about maritime activity
        return self.fetch_conflicts(query=f"vessel ship maritime {query}" if query else "vessel ship maritime sanctions")

    # ── NOAA SEVERE WEATHER (from Crucix) ──

    def fetch_weather_alerts(self) -> List[Dict]:
        """Fetch active severe weather alerts from NOAA."""
        url = 'https://api.weather.gov/alerts/active'
        params = {'status': 'actual', 'limit': 20}
        try:
            r = self.session.get(url, params=params, timeout=self.timeout,
                                 headers={'Accept': 'application/geo+json'})
            if not r.ok:
                return []
            data = r.json()
            return [
                {
                    'event': f.get('properties', {}).get('event', ''),
                    'headline': f.get('properties', {}).get('headline', ''),
                    'severity': f.get('properties', {}).get('severity', ''),
                    'area': f.get('properties', {}).get('areaDesc', '')[:100],
                    'effective': f.get('properties', {}).get('effective', ''),
                    'source': 'NOAA',
                }
                for f in data.get('features', [])[:20]
            ]
        except:
            return []

    # ── SPACE / SATELLITES (from Crucix) ──

    def fetch_recent_launches(self) -> List[Dict]:
        """Fetch recent and upcoming space launches."""
        url = 'https://ll.thespacedevs.com/2.3.0/launches/upcoming/'
        params = {'limit': 10, 'format': 'json'}
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            if not r.ok:
                return []
            data = r.json()
            return [
                {
                    'name': l.get('name', ''),
                    'date': l.get('net', ''),
                    'provider': l.get('launch_service_provider', {}).get('name', ''),
                    'pad': l.get('pad', {}).get('name', ''),
                    'status': l.get('status', {}).get('name', ''),
                    'source': 'Space Devs',
                }
                for l in data.get('results', [])[:10]
            ]
        except:
            return []

    # ── AGGREGATE SEARCH ──

    def search_all(self, query, feeds=None, include_new=True) -> Dict:
        """Run search across all applicable feeds for a query.
        include_new=True adds the new Crucix/ShadowBroker feeds too."""
        results = {}

        if not feeds or 'news' in feeds:
            results['news'] = self.fetch_news_rss(query)

        if not feeds or 'gdelt' in feeds:
            results['gdelt'] = self.fetch_gdelt_events(query)

        if not feeds or 'reddit' in feeds:
            results['reddit'] = self.fetch_reddit_posts('all', query)

        if not feeds or 'patents' in feeds:
            results['patents'] = self.fetch_patents(query)

        if not feeds or 'usaspending' in feeds:
            results['gov_contracts'] = self.fetch_usaspending(query)

        if include_new:
            if not feeds or 'sanctions' in feeds:
                results['sanctions'] = self.fetch_sanctions(query)

            if not feeds or 'bluesky' in feeds:
                results['bluesky'] = self.fetch_bluesky(query)

            if not feeds or 'conflicts' in feeds:
                results['conflicts'] = self.fetch_conflicts(query)

            if not feeds or 'cisa' in feeds:
                results['cisa'] = self.fetch_cisa_kev(query)

            if not feeds or 'sec' in feeds:
                results['sec'] = self.fetch_sec_filings(query)

        if not feeds or 'wayback' in feeds:
            # Try common domains
            for domain in [f'{query.lower().replace(" ", "")}.com', f'{query.lower().replace(" ", "")}.org']:
                wb = self.fetch_wayback_snapshots(domain)
                if wb:
                    results['wayback'] = wb
                    break

        return results

    def search_targeted(self, query, feed_name) -> List[Dict]:
        """Run a single targeted feed search."""
        feed_map = {
            'news': lambda q: self.fetch_news_rss(q),
            'gdelt': lambda q: self.fetch_gdelt_events(q),
            'reddit': lambda q: self.fetch_reddit_posts('all', q),
            'patents': lambda q: self.fetch_patents(q),
            'usaspending': lambda q: self.fetch_usaspending(q),
            'sec': lambda q: self.fetch_sec_filings(q),
            'sanctions': lambda q: self.fetch_sanctions(q),
            'ofac': lambda q: self.fetch_ofac_sanctions(q),
            'bluesky': lambda q: self.fetch_bluesky(q),
            'who': lambda q: self.fetch_who_outbreaks(q),
            'cisa': lambda q: self.fetch_cisa_kev(q),
            'humanitarian': lambda q: self.fetch_humanitarian(q),
            'conflicts': lambda q: self.fetch_conflicts(q),
            'flights': lambda _: self.fetch_flights(),
            'satellites': lambda _: self.fetch_satellites(),
            'earthquakes': lambda _: self.fetch_earthquakes(),
            'weather': lambda _: self.fetch_weather_alerts(),
            'fires': lambda _: self.fetch_fires(),
            'launches': lambda _: self.fetch_recent_launches(),
            'ships': lambda q: self.fetch_ships(q),
            'stock': lambda q: self.fetch_stock_price(q),
            'yandex': lambda q: self._yandex_search(q),
            'yandex_image': lambda q: self._yandex_image(q),
            'yandex_phone': lambda q: self._yandex_phone(q),
            'yandex_email': lambda q: self._yandex_email(q),
        }
        fn = feed_map.get(feed_name)
        if fn:
            try:
                return fn(query) or []
            except Exception as e:
                print(f"[OSINT] Feed {feed_name} error: {e}")
                return []
        return []

    def _yandex_search(self, query) -> List[Dict]:
        try:
            from search.yandex import YandexSearch
            y = YandexSearch(timeout=self.timeout)
            return y.search(query, max_results=10)
        except Exception as e:
            print(f"[Yandex] Search error: {e}")
            return []

    def _yandex_image(self, image_url) -> List[Dict]:
        try:
            from search.yandex import YandexSearch
            y = YandexSearch(timeout=self.timeout)
            return y.reverse_image_search(image_url=image_url)
        except Exception as e:
            print(f"[Yandex] Image search error: {e}")
            return []

    def _yandex_phone(self, phone) -> List[Dict]:
        try:
            from search.yandex import YandexSearch
            y = YandexSearch(timeout=self.timeout)
            return y.search_phone(phone)
        except Exception as e:
            print(f"[Yandex] Phone search error: {e}")
            return []

    def _yandex_email(self, email) -> List[Dict]:
        try:
            from search.yandex import YandexSearch
            y = YandexSearch(timeout=self.timeout)
            result = y.lookup_email(email)
            return [result] if result else []
        except Exception as e:
            print(f"[Yandex] Email lookup error: {e}")
            return []
        fn = feed_map.get(feed_name)
        if fn:
            result = fn(query)
            return result if isinstance(result, list) else [result] if result else []
        return []

    def format_for_context(self, results: Dict) -> str:
        """Format search results as context string for the AI."""
        parts = []
        for source, items in results.items():
            if not items:
                continue
            parts.append(f"\n--- {source.upper()} ({len(items)} results) ---")
            for item in items[:10]:
                if isinstance(item, dict):
                    line = ' | '.join(f'{k}: {str(v)[:100]}' for k, v in item.items() if v)
                    parts.append(line)
        return '\n'.join(parts)
