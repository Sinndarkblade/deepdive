"""
Local File Search — search a downloaded document corpus.
No VOIS, no special engine. Just grep-like text search.
Anyone can use this — just point it at a folder of documents.
"""

import os
import re
from pathlib import Path


class LocalFileSearch:
    """Search local files by keyword matching. No dependencies."""

    def __init__(self, document_dir=None):
        self.document_dir = document_dir
        self.file_cache = {}  # path -> content
        self.indexed = False

    @property
    def name(self):
        return f"Local Files ({self.document_dir})"

    def index(self, document_dir=None):
        """Read all files into memory for fast searching."""
        if document_dir:
            self.document_dir = document_dir

        if not self.document_dir or not os.path.exists(self.document_dir):
            print(f"[LocalFiles] Directory not found: {self.document_dir}")
            return False

        extensions = {
            '.txt', '.md', '.csv', '.json', '.html', '.xml', '.log', '.tsv',
            '.py', '.js', '.ts', '.yml', '.yaml', '.toml', '.ini', '.cfg',
            '.sql', '.sh', '.bat', '.env', '.rst', '.tex',
        }
        # Also handle SQLite databases
        db_extensions = {'.db', '.sqlite', '.sqlite3'}
        count = 0

        for root, dirs, files in os.walk(self.document_dir):
            # Skip .git internals but index git commit messages if we find a repo
            if '.git' in dirs:
                git_content = self._index_git_repo(root)
                if git_content:
                    self.file_cache[os.path.join(root, '.git_history')] = git_content
                    count += 1
                dirs.remove('.git')

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in extensions:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', errors='ignore') as f:
                            content = f.read()
                        self.file_cache[fpath] = content
                        count += 1
                    except:
                        pass
                elif ext in db_extensions:
                    fpath = os.path.join(root, fname)
                    db_content = self._index_sqlite(fpath)
                    if db_content:
                        self.file_cache[fpath] = db_content
                        count += 1

        self.indexed = True
        print(f"[LocalFiles] Indexed {count} files from {self.document_dir}")
        return True

    def _index_sqlite(self, db_path):
        """Extract text content from SQLite database tables."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            parts = [f"DATABASE: {os.path.basename(db_path)}\nTables: {', '.join(tables)}\n"]
            for table in tables[:20]:  # Limit tables
                try:
                    c.execute(f"SELECT * FROM [{table}] LIMIT 200")
                    rows = c.fetchall()
                    cols = [d[0] for d in c.description] if c.description else []
                    parts.append(f"\n--- TABLE: {table} ({len(rows)} rows) ---")
                    parts.append(' | '.join(cols))
                    for row in rows:
                        parts.append(' | '.join(str(v)[:200] for v in row))
                except:
                    pass
            conn.close()
            content = '\n'.join(parts)
            if len(content) > 500000:
                content = content[:500000]
            return content
        except Exception as e:
            print(f"[LocalFiles] SQLite error {db_path}: {e}")
            return None

    def _index_git_repo(self, repo_path):
        """Extract git commit messages and file list from a repo."""
        import subprocess
        try:
            # Get last 200 commit messages
            result = subprocess.run(
                ['git', 'log', '--oneline', '-200', '--all'],
                capture_output=True, text=True, timeout=10, cwd=repo_path
            )
            commits = result.stdout.strip()

            # Get file list
            result2 = subprocess.run(
                ['git', 'ls-files'],
                capture_output=True, text=True, timeout=10, cwd=repo_path
            )
            files = result2.stdout.strip()

            content = f"GIT REPO: {os.path.basename(repo_path)}\n\n"
            content += f"--- RECENT COMMITS ---\n{commits}\n\n"
            content += f"--- FILES ---\n{files}\n"
            return content
        except Exception as e:
            print(f"[LocalFiles] Git error {repo_path}: {e}")
            return None

    def search(self, query, max_results=20):
        """Search all indexed files for query terms. Returns matching passages."""
        if not self.indexed:
            if not self.index():
                return []

        query_terms = query.lower().split()
        results = []

        for fpath, content in self.file_cache.items():
            content_lower = content.lower()
            
            # Score: how many query terms appear in this file
            score = sum(1 for term in query_terms if term in content_lower)
            if score == 0:
                continue

            # Find the best matching passage (context around first match)
            for term in query_terms:
                idx = content_lower.find(term)
                if idx >= 0:
                    start = max(0, idx - 200)
                    end = min(len(content), idx + 300)
                    passage = content[start:end].strip()
                    break
            else:
                passage = content[:500]

            results.append({
                'title': os.path.basename(fpath),
                'url': fpath,
                'body': passage,
                'score': score / len(query_terms),
                'file': fpath,
            })

        # Sort by relevance
        results.sort(key=lambda x: -x['score'])
        return results[:max_results]

    def multi_angle_search(self, subject):
        """Run multiple searches from different angles."""
        angles = {
            "overview": f"{subject}",
            "money": f"{subject} payment fund money transfer",
            "people": f"{subject} associate partner employee",
            "legal": f"{subject} lawsuit court case charge",
            "locations": f"{subject} address location property",
        }

        all_results = {}
        for angle_name, query in angles.items():
            results = self.search(query, max_results=10)
            all_results[angle_name] = results
            print(f"  [{angle_name}] {len(results)} results")

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

        return results, all_text
