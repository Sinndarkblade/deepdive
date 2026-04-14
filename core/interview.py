#!/usr/bin/env python3
"""
DeepDive Interview System — Claude determines investigation scope through user interaction.
Builds an investigation config that drives the loop controller.
"""

import json
from typing import Dict, List, Optional


# Investigation focus categories with sub-options
FOCUS_CATEGORIES = {
    "people": {
        "label": "People",
        "options": [
            ("background", "Background & identity"),
            ("family", "Family & associates"),
            ("employment", "Employment history"),
            ("death_records", "Death records / obituaries"),
            ("voter_reg", "Voter registration"),
            ("driving", "Driving records / licenses"),
            ("criminal", "Criminal history"),
            ("sex_offender", "Sex offender registry"),
        ]
    },
    "financial": {
        "label": "Financial",
        "options": [
            ("net_worth", "Net worth & assets"),
            ("property", "Property records (real estate, mortgages, liens)"),
            ("business_filings", "Business ownership & filings"),
            ("investments", "Investments & funding"),
            ("bankruptcy", "Bankruptcy filings"),
            ("tax_liens", "Tax liens / judgments"),
            ("political_donations", "Political donations / lobbying"),
            ("crypto", "Cryptocurrency / blockchain"),
        ]
    },
    "legal": {
        "label": "Legal",
        "options": [
            ("civil_court", "Civil court records"),
            ("criminal_court", "Criminal court records"),
            ("sec_filings", "SEC / regulatory filings"),
            ("foia", "FOIA / government records"),
            ("patents", "Patent & trademark filings"),
            ("sanctions", "Sanctions / watchlists"),
        ]
    },
    "digital": {
        "label": "Digital",
        "options": [
            ("social_media", "Social media (all platforms)"),
            ("domain_whois", "Domain / website ownership"),
            ("wayback", "Archived/deleted content (Wayback Machine)"),
            ("email_username", "Email / username traces"),
            ("dark_web", "Dark web mentions"),
            ("dns_ip", "DNS / IP / SSL records"),
        ]
    },
    "corporate": {
        "label": "Corporate",
        "options": [
            ("corp_structure", "Corporate structure (subsidiaries)"),
            ("officers", "Officers & directors"),
            ("licenses", "Business licenses"),
            ("contracts", "Contracts & procurement"),
            ("gov_contracts", "Government contracts"),
            ("mergers", "Mergers & acquisitions"),
        ]
    },
    "general": {
        "label": "General",
        "options": [
            ("timeline", "Timeline (chronological events)"),
            ("news", "News & media coverage"),
            ("academic", "Academic publications"),
        ]
    },
}

DEPTH_LEVELS = {
    "quick": {"label": "Quick Scan", "passes": 1, "expand_per_pass": 0, "description": "~50 entities, fast overview"},
    "standard": {"label": "Standard", "passes": 3, "expand_per_pass": 3, "description": "~150 entities, good coverage"},
    "exhaustive": {"label": "Exhaustive", "passes": 0, "expand_per_pass": 5, "description": "Unlimited passes until dry"},
}


class InvestigationConfig:
    """Configuration built from the interview that drives the investigation."""

    def __init__(self):
        self.subject = ""
        self.focus_areas = []  # list of focus option keys
        self.depth = "standard"
        self.time_period = ""  # optional date range
        self.user_context = ""  # anything user already knows
        self.multi_agent = False
        self.raw_intent = ""  # the full user instruction
        self.enabled_feeds = []  # OSINT feed names to query during investigation

    def to_dict(self) -> Dict:
        return {
            "subject": self.subject,
            "focus_areas": self.focus_areas,
            "depth": self.depth,
            "time_period": self.time_period,
            "user_context": self.user_context,
            "multi_agent": self.multi_agent,
            "raw_intent": self.raw_intent,
            "enabled_feeds": self.enabled_feeds,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'InvestigationConfig':
        config = cls()
        config.subject = data.get("subject", "")
        config.focus_areas = data.get("focus_areas", [])
        config.depth = data.get("depth", "standard")
        config.time_period = data.get("time_period", "")
        config.user_context = data.get("user_context", "")
        config.multi_agent = data.get("multi_agent", False)
        config.raw_intent = data.get("raw_intent", "")
        config.enabled_feeds = data.get("enabled_feeds", [])
        return config

    def build_search_prompt(self) -> str:
        """Build the focused search prompt based on selected focus areas."""
        focus_instructions = []

        # Map focus keys to specific search instructions
        focus_map = {
            "background": "Search for background information, identity details, aliases, date of birth.",
            "family": "Identify all family members, spouses, children, known associates and their relationships.",
            "employment": "Trace complete employment history — every company, role, dates, reasons for leaving.",
            "death_records": "Check death records, obituaries, SSN death index.",
            "voter_reg": "Search voter registration records for address history and registration status.",
            "driving": "Search for driving records, license status, vehicle registrations.",
            "criminal": "Search criminal records — arrests, convictions, warrants, mugshots.",
            "sex_offender": "Check sex offender registries across all states.",
            "net_worth": "Estimate net worth — assets, income sources, known wealth.",
            "property": "Search property records — real estate owned, mortgages, liens, tax assessments, purchase prices and dates.",
            "business_filings": "Search business filings — incorporation records, registered agents, annual reports, DBA filings.",
            "investments": "Trace investments — venture capital, stock holdings, fund participation, angel investments.",
            "bankruptcy": "Search bankruptcy court filings — Chapter 7, 11, 13, discharge status.",
            "tax_liens": "Search for tax liens, IRS liens, state tax judgments.",
            "political_donations": "Search FEC records for political donations, lobbying disclosures, PAC contributions.",
            "crypto": "Search blockchain records, known crypto wallets, DeFi participation, exchange accounts.",
            "civil_court": "Search civil court records — lawsuits filed by and against, settlements, judgments.",
            "criminal_court": "Search criminal court records — charges, plea deals, sentencing, appeals.",
            "sec_filings": "Search SEC EDGAR filings, 10-K, 10-Q, proxy statements, insider trading reports.",
            "foia": "Search FOIA releases, declassified documents, government records.",
            "patents": "Search USPTO patent and trademark filings.",
            "sanctions": "Check OFAC sanctions list, Interpol notices, global watchlists.",
            "social_media": "Search ALL social media platforms — Twitter/X, LinkedIn, Facebook, Instagram, Reddit, TikTok, YouTube. Extract handles, key posts, connections.",
            "domain_whois": "Search WHOIS records for domain ownership, registration history, associated domains.",
            "wayback": "Use Wayback Machine (web.archive.org) to find archived and DELETED web pages. What was removed is often the most important.",
            "email_username": "Trace email addresses and usernames across platforms — Gravatar, HaveIBeenPwned, username searches.",
            "dark_web": "Search for mentions on dark web forums, leaked databases, paste sites.",
            "dns_ip": "Search DNS records, IP history, SSL certificate transparency logs, hosting history.",
            "corp_structure": "Map complete corporate structure — parent companies, subsidiaries, shell companies, offshore entities.",
            "officers": "Identify all officers, directors, board members, registered agents — current and historical.",
            "licenses": "Search business licenses, professional licenses, permits.",
            "contracts": "Search for contracts, procurement records, vendor relationships.",
            "gov_contracts": "Search USAspending.gov, SAM.gov, FPDS for government contracts and awards.",
            "mergers": "Trace mergers, acquisitions, divestitures, joint ventures.",
            "timeline": "Build a complete chronological timeline of all key events with dates.",
            "news": "Search news archives, press releases, media coverage across all outlets.",
            "academic": "Search academic publications, patents, conference papers, research citations.",
        }

        if not self.focus_areas or "all" in self.focus_areas:
            focus_instructions = list(focus_map.values())
        else:
            for area in self.focus_areas:
                if area in focus_map:
                    focus_instructions.append(focus_map[area])

        prompt_parts = [f'Subject: "{self.subject}"']

        if self.raw_intent:
            prompt_parts.append(f"User's intent: {self.raw_intent}")

        if self.time_period:
            prompt_parts.append(f"Time period: {self.time_period}")

        if self.user_context:
            prompt_parts.append(f"Known context: {self.user_context}")

        prompt_parts.append("\nFOCUS AREAS — search these specifically:")
        for i, instruction in enumerate(focus_instructions, 1):
            prompt_parts.append(f"{i}. {instruction}")

        return "\n".join(prompt_parts)

    def get_depth_config(self) -> Dict:
        """Get the depth configuration for the loop controller."""
        return DEPTH_LEVELS.get(self.depth, DEPTH_LEVELS["standard"])


def get_focus_categories() -> Dict:
    """Return all focus categories for the UI to render checkboxes."""
    return FOCUS_CATEGORIES


def get_depth_levels() -> Dict:
    """Return all depth levels for the UI to render radio buttons."""
    return DEPTH_LEVELS
