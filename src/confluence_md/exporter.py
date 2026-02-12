"""Recursive page exporter with rate limiting and error handling."""
import logging
import time
from pathlib import Path
from typing import Tuple
from .client import ConfluenceClient
from .converter import slugify, extract_metadata, convert_to_markdown

logger = logging.getLogger(__name__)


class PageExporter:
    """Orchestrates recursive Confluence page export."""
    
    def __init__(self, client: ConfluenceClient, output_path: Path, delay_ms: int, base_url: str, skip_existing: bool = False, max_depth: int = 50):
        """Initialize exporter.
        
        Args:
            client: Configured ConfluenceClient
            output_path: Root output directory
            delay_ms: Delay in milliseconds between API calls
            base_url: Base URL for metadata URL construction
            skip_existing: Skip files that already exist (resume capability)
            max_depth: Maximum recursion depth to prevent infinite loops (default: 50)
        """
        self.client = client
        self.output_path = Path(output_path)
        self.delay_ms = delay_ms
        self.base_url = base_url
        self.skip_existing = skip_existing
        self.max_depth = max_depth
    
    def _generate_unique_filename(self, base_slug: str, directory: Path) -> str:
        """Generate unique filename handling slug collisions.
        
        Args:
            base_slug: Base slug from page title
            directory: Target directory
            
        Returns:
            Unique filename with .md extension
        """
        filename = f"{base_slug}.md"
        filepath = directory / filename
        
        # Check for collision
        if not filepath.exists():
            return filename
        
        # Append counter suffix (-2, -3, etc.)
        counter = 2
        while True:
            filename = f"{base_slug}-{counter}.md"
            filepath = directory / filename
            if not filepath.exists():
                return filename
            counter += 1
    
    def _apply_rate_limit(self):
        """Sleep for configured delay (rate limiting)."""
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)
    
    def _write_page_file(self, page: dict, parent_path: Path, base_url: str) -> str:
        """Write a single page to disk.
        
        Args:
            page: Confluence page object
            parent_path: Parent directory for the file
            base_url: Base URL for metadata
            
        Returns:
            Actual filename (without .md extension) for child directory creation
        """
        # Extract metadata and convert to markdown
        metadata = extract_metadata(page, base_url)
        html_body = page.get('body', {}).get('storage', {}).get('value', '')
        markdown = convert_to_markdown(html_body, metadata)
        
        # Generate slug and check for collision
        slug = slugify(page.get('title', 'untitled'))
        filename = self._generate_unique_filename(slug, parent_path)
        
        # Create directory if needed
        parent_path.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists and skip_existing is enabled
        filepath = parent_path / filename
        if self.skip_existing and filepath.exists():
            logger.info(f"Skipped (exists): {filepath}")
            # Return actual filename without extension for child directory
            return filename[:-3] if filename.endswith('.md') else filename
        
        # Write file
        filepath.write_text(markdown, encoding='utf-8')
        
        logger.info(f"Created: {filepath}")
        
        # Return actual filename without extension for child directory
        return filename[:-3] if filename.endswith('.md') else filename
    
    def export_tree(self, root_page_id: str, parent_directory: Path, depth: int = 0) -> Tuple[int, int]:
        """Recursively export page and all children.
        
        Args:
            root_page_id: Page ID to export
            parent_directory: Directory where this page's file will be created
            depth: Current recursion depth (internal, starts at 0)
            
        Returns:
            Tuple of (success_count, failure_count)
        """
        # Check recursion depth limit
        if depth >= self.max_depth:
            logger.error(f"Maximum recursion depth ({self.max_depth}) reached for page {root_page_id}")
            return (0, 1)
        
        try:
            # Fetch root page
            logger.info(f"Fetching page: {root_page_id}")
            page = self.client.get_page(root_page_id)
            self._apply_rate_limit()
            
            # Write root page to disk (returns actual filename used)
            actual_filename = self._write_page_file(page, parent_directory, self.base_url)
            
            # Initialize counters (root succeeded)
            success_count = 1
            failure_count = 0
            
            # Create child directory using actual filename (handles collision case)
            child_directory = parent_directory / actual_filename
            
            # Fetch children
            children = self.client.get_child_pages(root_page_id)
            self._apply_rate_limit()
            
            # Recursively export each child
            for child in children:
                child_id = child.get('id')
                if child_id:
                    child_success, child_failure = self.export_tree(child_id, child_directory, depth + 1)
                    success_count += child_success
                    failure_count += child_failure
            
            return (success_count, failure_count)
            
        except Exception as e:
            # Log error and count as failure
            logger.error(f"Failed to export page {root_page_id}: {e}")
            return (0, 1)
