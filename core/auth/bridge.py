#!/usr/bin/env python3
"""
DeepDive Bridge — Claude powers the investigation engine.
Uses claude CLI in print mode for synchronous calls from the server.
Uses Agent SDK for standalone usage.
"""

import subprocess
import json
import os


INVESTIGATOR_PROMPT = """You are a senior OSINT investigator powering DeepDive. You conduct exhaustive investigations using the same sources and methods a licensed private investigator would.

YOUR DATA SOURCES — search ALL applicable sources for every subject:

PEOPLE:
- Background, identity, aliases, DOB
- Family members, spouses, associates, known connections
- Employment history, education, professional licenses
- Voter registration, address history
- Criminal records (arrests, convictions, warrants)
- Death records, obituaries, SSN death index

FINANCIAL:
- Property records (real estate ownership, mortgages, liens, tax assessments)
- Business filings (incorporation, officers, registered agents, annual reports)
- Bankruptcy filings, tax liens, civil judgments
- SEC filings, investor records, stock transactions
- Political donations (FEC records), lobbying disclosures
- Net worth estimates, salary data, investment history
- Government contracts, procurement awards

LEGAL:
- Civil court records (lawsuits, disputes, settlements)
- Criminal court records (charges, convictions, sentencing)
- Regulatory actions (SEC, FTC, EPA, OSHA violations)
- Patent and trademark filings (USPTO)
- FOIA documents, declassified records
- Sanctions lists, OFAC, Interpol notices

DIGITAL:
- Social media (Twitter/X, LinkedIn, Facebook, Instagram, Reddit, TikTok)
- Domain WHOIS records, website ownership
- Wayback Machine (web.archive.org) — archived and DELETED pages
- DNS records, IP history, SSL certificates
- Email/username traces across platforms
- Dark web mentions (forums, marketplaces, leaks)
- GitHub, code repositories, technical footprint

CORPORATE:
- Corporate structure (parent companies, subsidiaries, shell companies)
- Officers, directors, board members
- Business licenses, DBA filings
- Mergers, acquisitions, divestitures
- Government contracts (USAspending.gov, SAM.gov)
- Supplier and customer relationships

MEDIA & PUBLICATIONS:
- News articles, press releases
- Academic publications, patents, research
- Book authorship, conference appearances
- Podcast/video appearances, interviews

YOUR METHODOLOGY:
1. Search broadly first, then deep-dive specific angles
2. Date EVERY connection and event
3. Cross-reference — when the same entity appears from multiple sources, that's a key finding
4. Flag contradictions — when sources disagree, note both versions
5. Flag deletions — anything removed from the web is worth noting
6. Follow the money — every financial connection traced to its end

OUTPUT FORMAT — for each entity/connection found, output on its own line:
ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE

Entity types: person, company, location, event, money, document, government
Confidence: high (confirmed/documented), medium (reported/likely), low (alleged/rumored)

RULES:
- Extract EVERY name, company, amount, date, and location.
- Do NOT summarize — output individual connections, one per line.
- 50+ connections minimum for a thorough investigation.
- Include source (e.g., "per SEC filing", "LinkedIn profile", "Wayback archived 2019").
- Flag anything deleted, hidden, contradicted, or suspicious."""


# Focused prompts for specific action buttons
TIMELINE_PROMPT = """List the complete chronological timeline of events for this subject.

RULES:
- Output ONLY lines in this exact format, nothing else
- No explanations, no headers, no prose, no preamble
- Format: EVENT_NAME | event | RELATIONSHIP | CONFIDENCE
- Include date in EVENT_NAME (e.g. "2019-03 FTX Founded", "2022-11 Bankruptcy Filing")
- CONFIDENCE must be: high, medium, or low
- Minimum 15 events

Example:
2019-03 FTX Exchange Founded | event | founded_by | high
2022-11-02 CoinDesk Leak Published | event | triggered_collapse | high
2022-11-11 FTX Files Bankruptcy | event | chapter_11 | high"""

MONEY_FLOW_PROMPT = """List ALL financial connections and money flows for this subject.

RULES:
- Output ONLY lines in this exact format, nothing else
- No explanations, no headers, no prose
- Format: ENTITY_NAME | money | RELATIONSHIP | CONFIDENCE
- Include amounts and direction in RELATIONSHIP (e.g. paid_32B_to, received_from, invested_in)
- CONFIDENCE must be: high, medium, or low
- Minimum 15 entries

Example:
$8 billion customer funds | money | misappropriated_by_alameda | high
Sequoia Capital $215M | money | invested_in_ftx_2021 | high
Caroline Ellison | money | directed_alameda_transfers | high"""

SOCIAL_MEDIA_PROMPT = """List social media accounts, posts, and digital footprint for this subject.

RULES:
- Output ONLY lines in this exact format, nothing else
- No explanations, no headers, no prose
- Format: ENTITY_NAME | document | RELATIONSHIP | CONFIDENCE
- ENTITY_NAME = platform + handle or specific post
- CONFIDENCE must be: high, medium, or low
- Minimum 10 entries

Example:
Twitter @SBF_FTX | document | official_account | high
Reddit r/FTX_Official | document | community_run | medium
LinkedIn Sam Bankman-Fried | document | professional_profile | high"""

WAYBACK_PROMPT = """List archived, deleted, or modified web content related to this subject from the Wayback Machine and other archives.

RULES:
- Output ONLY lines in this exact format, nothing else
- No explanations, no headers, no prose
- Format: ENTITY_NAME | document | RELATIONSHIP | CONFIDENCE
- ENTITY_NAME = URL or page description with archive date
- Flag anything deleted or changed
- CONFIDENCE must be: high, medium, or low

Example:
ftx.com homepage archived 2022-11-01 | document | deleted_post_bankruptcy | high
alameda-research.com team page removed | document | scrubbed_executive_list | high
FTX Terms of Service changed 2022-09 | document | modified_before_collapse | medium"""


class UsageTracker:
    """Track API usage across all bridge calls."""

    def __init__(self):
        self.total_calls = 0
        self.total_time = 0
        self.calls = []  # list of {prompt_len, response_len, duration, timestamp}
        self.kill_flag = False  # set True to abort running investigations

    def record(self, prompt_len, response_len, duration):
        import time
        self.total_calls += 1
        self.total_time += duration
        self.calls.append({
            'prompt_len': prompt_len,
            'response_len': response_len,
            'duration': round(duration, 1),
            'timestamp': time.time(),
        })

    def get_stats(self):
        return {
            'total_calls': self.total_calls,
            'total_time': round(self.total_time, 1),
            'avg_time': round(self.total_time / max(1, self.total_calls), 1),
            'total_prompt_chars': sum(c['prompt_len'] for c in self.calls),
            'total_response_chars': sum(c['response_len'] for c in self.calls),
            'recent': self.calls[-5:] if self.calls else [],
            'killed': self.kill_flag,
        }

    def kill(self):
        self.kill_flag = True

    def reset_kill(self):
        self.kill_flag = False


USAGE = UsageTracker()




class DeepDiveBridge:
    """Bridge to AI providers for DeepDive investigations."""

    def __init__(self):
        self._claude_bin = self._find_claude()

    def _find_claude(self) -> str:
        result = subprocess.run(['which', 'claude'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        for path in ['/usr/local/bin/claude', os.path.expanduser('~/.local/bin/claude')]:
            if os.path.exists(path):
                return path
        return 'claude'

    def _get_settings(self):
        """Load current provider settings."""
        settings_file = os.path.expanduser('~/.deepdive/settings.json')
        if os.path.exists(settings_file):
            try:
                with open(settings_file) as f:
                    return json.load(f)
            except:
                pass
        return {'provider': 'claude', 'api_keys': {}}

    def is_available(self) -> bool:
        settings = self._get_settings()
        provider = settings.get('provider', 'claude')

        if provider == 'claude':
            try:
                result = subprocess.run([self._claude_bin, '--version'],
                    capture_output=True, text=True, timeout=5)
                return result.returncode == 0
            except:
                return False
        elif provider == 'claude_api':
            return bool(settings.get('api_keys', {}).get('claude_api', ''))
        elif provider == 'ollama':
            try:
                import requests
                r = requests.get(settings.get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=3)
                return r.status_code == 200
            except:
                return False
        elif provider == 'openai':
            return bool(settings.get('api_keys', {}).get('openai', ''))
        return False

    def _call(self, prompt: str, timeout: int = 300) -> str:
        """Route to the configured provider."""
        settings = self._get_settings()
        provider = settings.get('provider', 'claude')

        if provider == 'claude_api':
            return self._call_anthropic_api(prompt, settings, timeout)
        elif provider == 'ollama':
            return self._call_ollama(prompt, settings, timeout)
        elif provider == 'openai':
            return self._call_openai_compat(prompt, settings, timeout)
        return self._call_claude_cli(prompt, timeout)

    def _web_search_for_prompt(self, prompt: str) -> str:
        """Extract a search query from the prompt and run DDG + Yandex search.
        Returns formatted search results to inject into the prompt."""
        import re, sys
        # Ensure duckduckgo_search is importable regardless of working directory
        _ddg_paths = [
            '/usr/lib/python3/dist-packages',
            '/home/joe/.local/share/pipx/venvs/duckduckgo-search/lib/python3.12/site-packages',
        ]
        for _p in _ddg_paths:
            if _p not in sys.path:
                sys.path.insert(0, _p)
        try:
            # Skip search for very short prompts (confirmations, yes/no)
            # These are conversational, not investigation queries
            words = [w for w in prompt.split() if len(w) > 2]
            if len(words) < 5:
                return ""

            # Extract entity/subject from common prompt patterns
            search_terms = []
            for pattern in [
                r'Research "([^"]+)"',
                r'Subject: "([^"]+)"',
                r'investigate (.+?)[\.\n]',
                r'dive (?:deeper )?into (.+?)[\.\n]',
                r'trace .+ for (.+?)[\.\n]',
                r'expand(?:ing)? (.+?)[\.\n]',
            ]:
                m = re.search(pattern, prompt, re.I)
                if m:
                    search_terms.append(m.group(1).strip())
                    break

            if not search_terms:
                # Fall back: grab first quoted string or capitalized proper noun
                quoted = re.findall(r'"([^"]+)"', prompt)
                if quoted:
                    search_terms.append(quoted[0])

            if not search_terms:
                return ""

            from concurrent.futures import ThreadPoolExecutor, as_completed
            from search.ddg import DDGSearch
            from search.yandex import YandexSearch

            query = search_terms[0]
            ddg = DDGSearch(delay=0.3)
            yandex = YandexSearch(timeout=10)

            # Run multiple search angles simultaneously for maximum coverage
            text = ""
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {
                    pool.submit(ddg.search, query, 10): 'web',
                    pool.submit(ddg.search_news, query, 8): 'news',
                    pool.submit(ddg.search, f"{query} connections associates", 8): 'connections',
                    pool.submit(ddg.search, f"{query} funding money financial", 6): 'financial',
                    pool.submit(ddg.search, f"{query} lawsuit court legal", 6): 'legal',
                }

                # Yandex as supplemental (may get captcha'd but worth trying)
                try:
                    futures[pool.submit(yandex.search, query, 6)] = 'yandex'
                except:
                    pass

                results_by_type = {}
                for future in as_completed(futures, timeout=15):
                    key = futures[future]
                    try:
                        results_by_type[key] = future.result()
                    except:
                        results_by_type[key] = []

            # Format all results
            web = results_by_type.get('web', [])
            news = results_by_type.get('news', [])
            connections = results_by_type.get('connections', [])
            financial = results_by_type.get('financial', [])
            legal = results_by_type.get('legal', [])
            y_web = results_by_type.get('yandex', [])

            if web:
                text += f"\n\nWEB RESULTS for '{query}':\n"
                for r in web[:10]:
                    text += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"
            if news:
                text += f"\nRECENT NEWS:\n"
                for n in news[:8]:
                    text += f"- [{n.get('date', '')}] {n.get('title', '')}: {n.get('body', '')[:150]}\n"
            if connections:
                text += f"\nCONNECTIONS & ASSOCIATES:\n"
                for r in connections[:6]:
                    text += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"
            if financial:
                text += f"\nFINANCIAL:\n"
                for r in financial[:5]:
                    text += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"
            if legal:
                text += f"\nLEGAL:\n"
                for r in legal[:5]:
                    text += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"
            if y_web:
                text += f"\nYANDEX RESULTS:\n"
                for r in y_web[:6]:
                    text += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"

            if not text.strip():
                return ""

            return text[:4000]
        except Exception as e:
            print(f"[Bridge] Web search error: {e}")
            return ""

    def _call_ollama(self, prompt: str, settings: dict, timeout: int = 300) -> str:
        """Call a local Ollama model with web search augmentation."""
        import time, requests

        if USAGE.kill_flag:
            return "Error: Investigation killed by user"

        model = settings.get('ollama_model', 'gemma4')
        base_url = settings.get('ollama_url', 'http://localhost:11434')

        # Augment prompt with web search results
        web_results = self._web_search_for_prompt(prompt)
        augmented_prompt = prompt + web_results if web_results else prompt

        start = time.time()
        try:
            # Use streaming to collect response — non-streaming returns empty for some models (gemma4)
            collected = []
            with requests.post(
                f'{base_url}/api/generate',
                json={
                    'model': model,
                    'prompt': augmented_prompt,
                    'stream': True,
                    'options': {
                        'num_ctx': 16384,
                        'num_predict': 2048,
                        'temperature': 0.5,
                    },
                },
                stream=True,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    USAGE.record(len(prompt), 0, time.time() - start)
                    return f"Error: Ollama returned {response.status_code}"

                import json as _json
                for line in response.iter_lines():
                    if USAGE.kill_flag:
                        return "Error: Investigation killed by user"
                    if line:
                        try:
                            chunk = _json.loads(line)
                            tok = chunk.get('response', '')
                            if tok:
                                collected.append(tok)
                            if chunk.get('done'):
                                break
                        except:
                            pass

            duration = time.time() - start
            text = ''.join(collected)
            USAGE.record(len(prompt), len(text), duration)
            return text.strip()

        except requests.Timeout:
            USAGE.record(len(prompt), 0, time.time() - start)
            return "Error: Request timed out"
        except requests.ConnectionError:
            return "Error: Cannot connect to Ollama. Is it running? (ollama serve)"
        except Exception as e:
            USAGE.record(len(prompt), 0, time.time() - start)
            return f"Error: {e}"

    def _call_openai_compat(self, prompt: str, settings: dict, timeout: int = 300) -> str:
        """Call any OpenAI-compatible API (OpenAI, Grok, DeepSeek, etc.)."""
        import time, requests

        if USAGE.kill_flag:
            return "Error: Investigation killed by user"

        api_key = settings.get('api_keys', {}).get('openai', '')
        base_url = settings.get('openai_base_url', 'https://api.openai.com/v1')
        model = settings.get('openai_model', 'gpt-4o-mini')

        if not api_key:
            return "Error: No API key set for this provider. Go to Settings."

        start = time.time()
        try:
            response = requests.post(
                f'{base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 4096,
                },
                timeout=timeout,
            )
            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content']
                USAGE.record(len(prompt), len(text), duration)
                return text.strip()
            else:
                USAGE.record(len(prompt), 0, duration)
                return f"Error: API returned {response.status_code}: {response.text[:200]}"

        except Exception as e:
            USAGE.record(len(prompt), 0, time.time() - start)
            return f"Error: {e}"

    def _call_claude_cli(self, prompt: str, timeout: int = 300) -> str:
        """Call Claude via CLI."""
        import time

        if USAGE.kill_flag:
            return "Error: Investigation killed by user"

        start = time.time()
        try:
            proc = subprocess.Popen(
                [
                    self._claude_bin, '-p', prompt,
                    '--permission-mode', 'bypassPermissions',
                    '--tools', 'WebSearch,WebFetch',
                    '--no-session-persistence',
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={**os.environ, 'BROWSER': '', 'DISPLAY': ''}
            )

            while proc.poll() is None:
                if USAGE.kill_flag:
                    proc.kill()
                    return "Error: Investigation killed by user"
                time.sleep(0.5)
                if time.time() - start > timeout:
                    proc.kill()
                    USAGE.record(len(prompt), 0, time.time() - start)
                    return "Error: Request timed out"

            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
            duration = time.time() - start

            if proc.returncode == 0:
                USAGE.record(len(prompt), len(stdout), duration)
                return stdout.strip()
            else:
                USAGE.record(len(prompt), 0, duration)
                return f"Error: {stderr.strip()}"

        except Exception as e:
            USAGE.record(len(prompt), 0, time.time() - start)
            return f"Error: {e}"

    def _call_anthropic_api(self, prompt: str, settings: dict, timeout: int = 300) -> str:
        """Call Anthropic API directly with API key."""
        import time, requests

        if USAGE.kill_flag:
            return "Error: Investigation killed by user"

        api_key = settings.get('api_keys', {}).get('claude_api', '')
        if not api_key:
            return "Error: No Anthropic API key set. Go to Settings."

        start = time.time()
        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': 'claude-sonnet-4-5-20250929',
                    'max_tokens': 8192,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'tools': [
                        {'type': 'web_search_20260209', 'name': 'web_search'},
                    ],
                },
                timeout=timeout
            )
            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                text = ''.join(b['text'] for b in data.get('content', []) if b.get('type') == 'text')
                USAGE.record(len(prompt), len(text), duration)
                return text
            else:
                USAGE.record(len(prompt), 0, duration)
                return f"Error: API returned {response.status_code}: {response.text[:200]}"

        except Exception as e:
            USAGE.record(len(prompt), 0, time.time() - start)
            return f"Error: {e}"


    def _gather_osint(self, entity_name: str, enabled_feeds: list = None):
        """Gather OSINT data from enabled feeds to supplement AI search.
        Returns (context_string, raw_results_dict) so caller can display results."""
        raw_results = {}
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from search.osint_feeds import OSINTFeeds
            feeds = OSINTFeeds()

            if enabled_feeds:
                for feed_name in enabled_feeds:
                    try:
                        items = feeds.search_targeted(entity_name, feed_name)
                        if items:
                            raw_results[feed_name] = items
                    except:
                        pass
            else:
                raw_results = feeds.search_all(entity_name, include_new=False)

            context = feeds.format_for_context(raw_results)
            if context.strip():
                feed_list = ', '.join(raw_results.keys())
                return f"\n\nOSINT FEED DATA (sources: {feed_list}):\n{context[:6000]}\n", raw_results
        except:
            pass
        return "", raw_results

    def research(self, entity_name: str, entity_type: str, context: str = "",
                 enabled_feeds: list = None):
        """Research an entity using AI + OSINT feeds.
        Returns (response_text, feed_results_dict)."""
        osint_data, feed_results = self._gather_osint(entity_name, enabled_feeds)

        settings = self._get_settings()
        provider = settings.get('provider', 'claude')

        if provider == 'ollama':
            # Include investigation context so the model knows scope
            inv_name = ""
            if hasattr(self, '_current_investigation'):
                inv_name = self._current_investigation
            else:
                try:
                    import server.state as srv_state
                    if srv_state.GRAPH:
                        inv_name = srv_state.GRAPH.name
                except:
                    pass

            inv_line = f"\nThis is part of an investigation into: {inv_name}\n" if inv_name else ""

            prompt = f"""You are an OSINT investigator building a complete entity map for "{entity_name}".{inv_line}
IMPORTANT: Only output connections directly related to "{entity_name}". Do not include entities from other unrelated subjects.

STEP 1 — From your training knowledge, list ALL known connections for "{entity_name}" specifically:
- Every named person (co-founders, employees, family, associates, attorneys, prosecutors, victims)
- Every company (employers, subsidiaries, shell companies, investors, counterparties)
- Every government body (regulators, courts, agencies, law enforcement)
- Every financial amount ($X in funds, investments, losses, fines)
- Every location (headquarters, residences, incorporation jurisdictions)
- Every major event (founding dates, arrests, trials, bankruptcies, deals)

STEP 2 — From the web/OSINT data below, extract any ADDITIONAL entities not covered above.
{context}
{osint_data}

OUTPUT RULES — strictly follow these:
- Output ONLY pipe-separated lines. No prose. No headers. No explanations.
- Each line: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE
- ENTITY_TYPE: person, company, location, event, money, document, government
- CONFIDENCE: high, medium, low
- Minimum 40 lines. Prefer specificity: "Gary Wang" over "co-founder", "$8 billion customer funds" over "large amount"

ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE
[Person Name] | person | [role] | high
[Company Name] | company | [relationship] | high
[Location] | location | [hq/residence/jurisdiction] | high
[$Amount] | money | [flow_direction] | high
[Event Name Date] | event | [what_happened] | high"""
        else:
            prompt = INVESTIGATOR_PROMPT + f"""

Research "{entity_name}" ({entity_type}) and find ALL connections.

{context}
{osint_data}

Output each connection as:
ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE (high/medium/low)

Be thorough. Follow every thread."""

        return self._call(prompt), feed_results

    def analyze_gap(self, entity_a: str, entity_c: str, bridge: str, investigation: str) -> str:
        """Research a gap between two entities."""
        prompt = INVESTIGATOR_PROMPT + f"""

GAP ANALYSIS for "{investigation}":

{entity_a} and {entity_c} both connect to {bridge} but have NO direct connection.

Search for ANY link between {entity_a} and {entity_c}.
Output connections as: ENTITY_NAME | ENTITY_TYPE | RELATIONSHIP | CONFIDENCE
If none found, say NO CONNECTION FOUND and explain why."""

        return self._call(prompt)

    def generate_report(self, entity_name: str, connections: list, findings: list, investigation: str) -> str:
        """Generate a detailed intelligence report."""
        conn_text = "\n".join(
            f"- {c['name']} ({c['type']}) — {c['relationship']} ({int(c['confidence']*100)}%)"
            for c in connections
        )

        prompt = f"""Write a detailed intelligence report for "{entity_name}".

Investigation: {investigation}
Connections ({len(connections)}):
{conn_text}

Findings:
{chr(10).join(f for f in findings if entity_name.lower() in f.lower())}

Format as markdown with [[wikilinks]]. Include: summary, connections by type,
why each matters, suspicious patterns, gaps, next steps."""

        return self._call(prompt, timeout=300)

    def trace_timeline(self, entity_name: str, context: str = "") -> str:
        """Trace chronological timeline for an entity."""
        prompt = TIMELINE_PROMPT + f'\n\nSubject: "{entity_name}"\n{context}'
        return self._call(prompt)

    def trace_money(self, entity_name: str, context: str = "") -> str:
        """Trace all financial connections."""
        prompt = MONEY_FLOW_PROMPT + f'\n\nSubject: "{entity_name}"\n{context}'
        return self._call(prompt)

    def scan_social_media(self, entity_name: str, context: str = "") -> str:
        """Search social media for posts about an entity."""
        prompt = SOCIAL_MEDIA_PROMPT + f'\n\nSubject: "{entity_name}"\n{context}'
        return self._call(prompt)

    def check_wayback(self, entity_name: str, context: str = "") -> str:
        """Check Wayback Machine for archived/deleted content."""
        prompt = WAYBACK_PROMPT + f'\n\nSubject: "{entity_name}"\n{context}'
        return self._call(prompt)
