"""HTML to Markdown converter with metadata extraction."""
import re
import unicodedata
from typing import Dict
from markdownify import markdownify
import yaml


def slugify(text: str) -> str:
    """Convert page title to safe filesystem name.
    
    Args:
        text: Page title
        
    Returns:
        Slugified filename (lowercase, hyphens, ASCII only, max 100 chars)
    """
    # Normalize Unicode to NFKD and encode to ASCII
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Lowercase
    text = text.lower()
    
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    # Remove leading/trailing hyphens
    text = text.strip('-')
    
    # Truncate to 100 chars max
    if len(text) > 100:
        text = text[:100].rstrip('-')
    
    # Fallback if empty
    if not text:
        text = 'untitled'
    
    return text


def extract_metadata(page: dict, base_url: str) -> dict:
    """Extract metadata from Confluence page object.
    
    Args:
        page: Confluence page object from API
        base_url: Base URL of Confluence instance
        
    Returns:
        Dictionary with frontmatter fields
    """
    metadata = {}
    
    # All fields use None for missing values (consistent handling)
    metadata['title'] = page.get('title') or None
    metadata['page_id'] = page.get('id') or None
    metadata['space_key'] = page.get('space', {}).get('key') or None
    
    # Author
    created_by = page.get('history', {}).get('createdBy', {})
    metadata['author'] = created_by.get('displayName') or None
    
    # Dates
    metadata['created'] = page.get('history', {}).get('createdDate') or None
    metadata['modified'] = page.get('version', {}).get('when') or None
    
    # URL (relative from API, prepend base URL)
    webui_link = page.get('_links', {}).get('webui')
    if webui_link:
        metadata['url'] = base_url + webui_link
    else:
        metadata['url'] = None
    
    # Parent ID (from ancestors array, use last one)
    ancestors = page.get('ancestors', [])
    if ancestors:
        metadata['parent_id'] = ancestors[-1].get('id') or None
    else:
        metadata['parent_id'] = None
    
    return metadata


def convert_to_markdown(html: str, metadata: dict) -> str:
    """Convert HTML to markdown with YAML frontmatter.
    
    Args:
        html: HTML content from Confluence
        metadata: Metadata dictionary for frontmatter
        
    Returns:
        Markdown with YAML frontmatter prepended
    """
    # Convert HTML to markdown
    markdown_body = markdownify(html, heading_style="ATX")
    
    # Generate YAML frontmatter (safe_dump prevents injection)
    yaml_str = yaml.safe_dump(metadata, default_flow_style=False, allow_unicode=True)
    
    # Remove trailing newline from YAML to control formatting
    yaml_str = yaml_str.rstrip('\n')
    
    # Format: ---\n{yaml}\n---\n\n{markdown}
    result = f"---\n{yaml_str}\n---\n\n{markdown_body}"
    
    return result
