"""Async update checker with 24-hour cache."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error


# Cache duration in seconds (24 hours)
CACHE_DURATION_SECONDS = 24 * 60 * 60

# npm registry URL for version check
NPM_REGISTRY_URL = "https://registry.npmjs.org/confluence-md"

# Timeout for HTTP request (seconds)
REQUEST_TIMEOUT = 2


def _get_cache_dir() -> Path:
    """Get cross-platform cache directory."""
    return Path.home() / ".confluence-md"


def _get_cache_file() -> Path:
    """Get path to cache file."""
    return _get_cache_dir() / "last-update-check.json"


def _read_cache() -> Optional[dict]:
    """Read cached update check result."""
    cache_file = _get_cache_file()
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            checked_at = datetime.fromisoformat(data["checked_at"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_seconds = (now - checked_at).total_seconds()
            
            if age_seconds < CACHE_DURATION_SECONDS:
                return data
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        pass
    
    return None


def _write_cache(latest_version: str) -> None:
    """Write update check result to cache."""
    cache_dir = _get_cache_dir()
    cache_file = _get_cache_file()
    
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "latest_version": latest_version
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # Silent failure - cache is optional


def _fetch_latest_version() -> Optional[str]:
    """Fetch latest version from npm registry."""
    try:
        req = urllib.request.Request(
            NPM_REGISTRY_URL,
            headers={"Accept": "application/json", "User-Agent": "confluence-md"}
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("dist-tags", {}).get("latest")
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None


def _parse_version(version: str) -> tuple:
    """Parse version string into comparable tuple."""
    try:
        # Strip leading 'v' if present
        v = version.lstrip("v")
        parts = v.split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _is_newer(latest: str, current: str) -> bool:
    """Check if latest version is newer than current."""
    return _parse_version(latest) > _parse_version(current)


class UpdateChecker:
    """Non-blocking update checker that runs in background thread."""
    
    def __init__(self, current_version: str):
        self.current_version = current_version
        self._result: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start background update check."""
        self._thread = threading.Thread(target=self._check, daemon=True)
        self._thread.start()
    
    def _check(self) -> None:
        """Perform update check (runs in background thread)."""
        # Check cache first
        cached = _read_cache()
        if cached:
            latest = cached.get("latest_version")
            if latest and _is_newer(latest, self.current_version):
                self._result = latest
            return
        
        # Fetch from npm registry
        latest = _fetch_latest_version()
        if latest:
            _write_cache(latest)
            if _is_newer(latest, self.current_version):
                self._result = latest
    
    def get_result(self, timeout: float = 0.5) -> Optional[str]:
        """
        Get update check result.
        
        Returns the latest version if newer than current, else None.
        Waits up to `timeout` seconds for background check to complete.
        """
        if self._thread:
            self._thread.join(timeout=timeout)
        return self._result


def check_for_updates(current_version: str, no_check: bool = False) -> Optional[str]:
    """
    Synchronous wrapper for update check.
    
    Args:
        current_version: Current installed version
        no_check: If True, skip update check entirely
    
    Returns:
        Latest version string if update available, else None
    """
    if no_check:
        return None
    
    # Check environment variable opt-out
    if os.environ.get("CONFLUENCE_MD_NO_UPDATE_CHECK", "").lower() in ("1", "true", "yes"):
        return None
    
    # Check cache first (fast path)
    cached = _read_cache()
    if cached:
        latest = cached.get("latest_version")
        if latest and _is_newer(latest, current_version):
            return latest
        return None
    
    # Fetch from registry
    latest = _fetch_latest_version()
    if latest:
        _write_cache(latest)
        if _is_newer(latest, current_version):
            return latest
    
    return None


def format_update_message(latest_version: str) -> str:
    """
    Format update notification message.
    
    Detects install method and provides appropriate upgrade instructions.
    """
    # Simple heuristic: if running from npm global, suggest npm update
    # Otherwise, point to GitHub releases
    try:
        # Check if we're in an npm global installation path
        import sys
        exe_path = sys.executable or ""
        if "node_modules" in exe_path.lower() or "npm" in exe_path.lower():
            return f"ℹ A new version ({latest_version}) is available. Run 'npm update -g confluence-md' to upgrade."
    except Exception:
        pass
    
    return f"ℹ A new version ({latest_version}) is available. Visit https://github.com/bzoboki/Confluence.md/releases for upgrade options."
