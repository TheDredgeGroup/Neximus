"""
GitHub Parser for Neximus
Natural language GitHub repo browsing with session state.
Mirrors plc_parser pattern: is_github_request() + process_message().

Session state tracks current path so "open agent" and "read core.py"
resolve correctly without requiring full paths each time.

Session is activated on first GitHub command and stays active until
explicitly cleared or a non-GitHub conversation takes over.
"""

import logging
import re
from agent import github_tools

logger = logging.getLogger(__name__)


class GitHubParser:
    """
    Natural language GitHub repo browser.
    Maintains session state for path-aware navigation.
    """

    def __init__(self, agent):
        self.agent = agent

        # Session state
        self.session_active = False       # True after first GitHub command this session
        self.current_path = ""            # Current directory path in repo (empty = root)
        self.last_listing = []            # Last directory listing returned (list of item dicts)

        # ---------------------------------------------------------------
        # Trigger phrases - checked by is_github_request()
        # ---------------------------------------------------------------

        # Entry triggers - always fire regardless of session state
        self.entry_triggers = [
            "go to the github repo",
            "go to github repo",
            "open the github repo",
            "open github repo",
            "check the github repo",
            "check github repo",
            "show the github repo",
            "show github repo",
            "list the repo",
            "list repo",
            "browse the repo",
            "browse github",
            "repo info",
            "github repo info",
        ]

        # Navigation triggers - only fire when session is active
        self.nav_triggers = [
            r"open (.+)",
            r"go into (.+)",
            r"go in (.+)",
            r"enter (.+)",
            r"navigate to (.+)",
            r"cd (.+)",
            r"back",
            r"go back",
            r"go up",
            r"root",
            r"go to root",
        ]

        # File read triggers - only fire when session is active
        self.read_triggers = [
            r"read (.+)",
            r"analyze (.+)",
            r"show me (.+)",
            r"open (.+)",
        ]

        # Info triggers - fire regardless of session state
        self.info_triggers = [
            "show commits",
            "recent commits",
            "show recent commits",
            "github commits",
            "show issues",
            "open issues",
            "github issues",
            "list issues",
        ]

    # ------------------------------------------------------------------
    # Public API - matches plc_parser interface
    # ------------------------------------------------------------------

    def is_github_request(self, message: str) -> bool:
        """
        Returns True if this message should be handled by the GitHub parser.
        Checks entry triggers, info triggers, and (if session active)
        navigation and file read triggers.
        """
        # Long messages are documents or briefings, not commands
        if len(message) > 300:
            return False

        msg = message.lower().strip()

        # Entry triggers - always checked
        for trigger in self.entry_triggers:
            if trigger in msg:
                return True

        # Info triggers - always checked
        for trigger in self.info_triggers:
            if trigger in msg:
                return True

        # Session-gated triggers
        if self.session_active:
            # Navigation
            for pattern in self.nav_triggers:
                if re.search(pattern, msg):
                    return True

            # File read - only if target looks like a file (has extension) or
            # matches a name from the last listing
            for pattern in self.read_triggers:
                m = re.search(pattern, msg)
                if m:
                    target = m.group(1).strip()
                    if self._looks_like_file(target) or self._in_last_listing(target):
                        return True

        return False

    def process_message(self, message: str, agent) -> tuple:
        """
        Processes a GitHub-related message.
        Returns (True, response_string) on success.
        Returns (False, None) if not handled.
        Mirrors plc_parser.process_message() signature.
        """
        msg = message.lower().strip()

        try:
            # --- Repo info / entry ---
            if self._matches_any(msg, self.entry_triggers):
                return self._handle_list_contents("")

            # --- Info triggers ---
            if any(t in msg for t in ["commit"]):
                return self._handle_commits()

            if any(t in msg for t in ["issue"]):
                return self._handle_issues()

            # --- Session navigation (only if session active) ---
            if self.session_active:

                # Back / up
                if re.search(r"\b(back|go back|go up|root|go to root)\b", msg):
                    return self._handle_navigate_up()

                # Open / navigate into folder
                for pattern in [r"(?:go into|go in|enter|navigate to|cd|open) (.+)"]:
                    m = re.search(pattern, msg)
                    if m:
                        target = m.group(1).strip()
                        # Is it a folder in the current listing?
                        folder = self._find_in_listing(target, type_filter="dir")
                        if folder:
                            new_path = folder["path"]
                            return self._handle_list_contents(new_path)
                        # Is it a file?
                        file_item = self._find_in_listing(target, type_filter="file")
                        if file_item:
                            return self._handle_read_file(file_item["path"], agent)
                        # Fall through to read triggers below

                # Read / analyze file
                for pattern in [r"(?:read|analyze|show me) (.+)"]:
                    m = re.search(pattern, msg)
                    if m:
                        target = m.group(1).strip()
                        # Look in current listing first
                        file_item = self._find_in_listing(target, type_filter="file")
                        if file_item:
                            return self._handle_read_file(file_item["path"], agent)
                        # Try target as a bare filename in current path
                        path = f"{self.current_path}/{target}".strip("/")
                        return self._handle_read_file(path, agent)

        except Exception as e:
            logger.error(f"GitHubParser.process_message error: {e}")
            return (True, f"GitHub parser error: {e}")

        return (False, None)

    def clear_session(self):
        """Reset session state. Call when user starts a new topic."""
        self.session_active = False
        self.current_path = ""
        self.last_listing = []

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_list_contents(self, path: str) -> tuple:
        """Fetch and format a directory listing."""
        result = github_tools.list_contents(path)

        if not result["success"]:
            return (True, f"⚠️ GitHub error: {result['error']}")

        items = result["data"]
        display_path = path or "/"

        # Update session state
        self.session_active = True
        self.current_path = path
        self.last_listing = items

        if not items:
            return (True, f"📁 `{display_path}` is empty.")

        # Build listing string
        lines = [f"📂 **{display_path}**\n"]
        for item in items:
            icon = "📁" if item["type"] == "dir" else "📄"
            size_str = f"  ({item['size']:,} bytes)" if item["type"] == "file" and item["size"] else ""
            lines.append(f"  {icon} {item['name']}{size_str}")

        lines.append("\nSay **'read [filename]'** or **'open [folder]'** to continue.")
        return (True, "\n".join(lines))

    def _handle_navigate_up(self) -> tuple:
        """Navigate one level up from current path."""
        if not self.current_path or self.current_path == "/":
            return (True, "Already at repo root.")

        parts = self.current_path.strip("/").split("/")
        parent = "/".join(parts[:-1])
        return self._handle_list_contents(parent)

    def _handle_read_file(self, path: str, agent) -> tuple:
        """Fetch a file and summarize it via Claude simple_chat."""
        result = github_tools.read_file(path)

        if not result["success"]:
            return (True, f"⚠️ GitHub error: {result['error']}")

        filename = result["name"]
        content = result["content"]
        size = result["size"]

        # Send to Claude for summarization
        try:
            prompt = (
                f"You are reviewing the file '{filename}' from the Neximus GitHub repository. "
                f"File size: {size:,} bytes.\n\n"
                f"Here is the full file content:\n\n"
                f"{content}\n\n"
                f"Please provide a clear, concise summary of what this file does, "
                f"its key components, and anything notable about its implementation."
            )
            summary = agent.grok.simple_chat(prompt)
            response = f"📄 **{filename}** ({size:,} bytes)\n\n{summary}"
        except Exception as e:
            logger.error(f"GitHub summarization error: {e}")
            # Fallback: return raw content truncated
            preview = content[:2000] + ("..." if len(content) > 2000 else "")
            response = f"📄 **{filename}** ({size:,} bytes)\n\n(Summary failed, showing raw preview)\n\n{preview}"

        return (True, response)

    def _handle_commits(self) -> tuple:
        """Fetch and format recent commits."""
        result = github_tools.get_commits(per_page=10)

        if not result["success"]:
            return (True, f"⚠️ GitHub error: {result['error']}")

        commits = result["data"]
        if not commits:
            return (True, "No commits found.")

        self.session_active = True

        lines = ["🔀 **Recent Commits**\n"]
        for c in commits:
            date = c["date"][:10] if c["date"] else "?"
            lines.append(f"  `{c['sha']}` {date} — {c['author']}: {c['message']}")

        return (True, "\n".join(lines))

    def _handle_issues(self) -> tuple:
        """Fetch and format open issues."""
        result = github_tools.get_issues(state="open", per_page=10)

        if not result["success"]:
            return (True, f"⚠️ GitHub error: {result['error']}")

        issues = result["data"]
        self.session_active = True

        if not issues:
            return (True, "✅ No open issues.")

        lines = [f"🐛 **Open Issues** ({len(issues)})\n"]
        for iss in issues:
            labels = f" [{', '.join(iss['labels'])}]" if iss["labels"] else ""
            date = iss["created_at"][:10] if iss["created_at"] else "?"
            lines.append(f"  #{iss['number']} {iss['title']}{labels} — {iss['user']} ({date})")

        return (True, "\n".join(lines))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _matches_any(self, msg: str, triggers: list) -> bool:
        return any(t in msg for t in triggers)

    def _looks_like_file(self, name: str) -> bool:
        """True if name contains a dot suggesting a file extension."""
        return "." in name.split("/")[-1]

    def _in_last_listing(self, name: str) -> bool:
        """True if name matches any item in the last directory listing.
        Normalizes spaces, underscores, and hyphens for fuzzy matching."""
        def normalize(s):
            return s.lower().strip().replace('_', ' ').replace('-', ' ')
        name_norm = normalize(name)
        return any(normalize(item["name"]) == name_norm for item in self.last_listing)

    def _find_in_listing(self, name: str, type_filter: str = None):
        """
        Find an item by name in last_listing.
        type_filter: 'file' or 'dir' or None for any.
        Normalizes spaces, underscores, and hyphens so 'grok agent' matches 'grok_agent'.
        Returns item dict or None.
        """
        def normalize(s):
            return s.lower().strip().replace('_', ' ').replace('-', ' ')

        name_norm = normalize(name)
        for item in self.last_listing:
            if normalize(item["name"]) == name_norm:
                if type_filter is None or item["type"] == type_filter:
                    return item
        return None


def initialize_github_parser(agent):
    """Initialize and return a GitHubParser instance."""
    return GitHubParser(agent)