"""Confluence API client wrapper with authentication and page fetching."""
import time
import logging
from typing import List, Dict
from atlassian import Confluence
import requests.exceptions

logger = logging.getLogger(__name__)


# Custom exceptions
class ConfluenceAuthError(Exception):
    """Raised when authentication fails (401/403)."""
    pass


class ConfluenceNotFoundError(Exception):
    """Raised when a page is not found (404)."""
    pass


class ConfluenceConnectionError(Exception):
    """Raised when connection fails."""
    pass


class ConfluenceAPIError(Exception):
    """Raised for other API errors."""
    pass


class ConfluenceClient:
    """Wrapper for Confluence API operations with retry logic."""
    
    def __init__(self, url: str, token: str, user: str = None, timeout: int = 30):
        """Initialize Confluence API client.
        
        Args:
            url: Base URL of Confluence instance
            token: Personal Access Token or API token
            user: Username/email (for Cloud with API token) or None (for Server with PAT)
            timeout: Request timeout in seconds (default: 30)
        """
        # Confluence Server (on-premise) uses token-only Bearer auth
        # Confluence Cloud uses username + API token as password
        if user:
            logger.info(f"Using username+token authentication for {url}")
            self.client = Confluence(url=url, username=user, password=token, timeout=timeout)
        else:
            logger.info(f"Using token-only (Bearer) authentication for {url}")
            self.client = Confluence(url=url, token=token, timeout=timeout)
        
        self.base_url = url
        self.timeout = timeout
    
    def _retry_with_backoff(self, func, *args, **kwargs) -> Dict:
        """Execute function with exponential backoff retry logic.
        
        Retries on 429 (rate limit) and 503 (service unavailable).
        Total attempts: 4 (1 initial + 3 retries)
        Delays: 1s, 2s, 4s
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Function result
            
        Raises:
            Original exception after all retries exhausted
        """
        delays = [1, 2, 4]
        attempt = 0
        last_exception = None
        
        while attempt < 4:  # 1 initial + 3 retries
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                last_exception = e
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    if status_code in (429, 503) and attempt < 4:
                        # Check for Retry-After header
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after and retry_after.isdigit():
                            delay = int(retry_after)
                            logger.warning(f"Rate limited (429/503), retrying in {delay}s (attempt {attempt + 1}/4)")
                        else:
                            delay = delays[min(attempt, len(delays) - 1)]
                            logger.warning(f"Rate limited (429/503), retrying in {delay}s (attempt {attempt + 1}/4)")
                        time.sleep(delay)
                        attempt += 1
                        continue
                # Not retryable or out of retries
                logger.error(f"HTTP error {status_code}: {e}")
                raise
            except Exception as e:
                # Other exceptions don't get retried
                raise
        
        # If we get here, all retries exhausted
        raise last_exception
    
    def get_page(self, page_id: str) -> dict:
        """Fetch single page with full metadata.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Full page object with HTML body, metadata, and hierarchy
            
        Raises:
            ConfluenceAuthError: Authentication failed (401/403)
            ConfluenceNotFoundError: Page not found (404)
            ConfluenceConnectionError: Connection failed
            ConfluenceAPIError: Other API errors
        """
        try:
            logger.debug(f"Fetching page {page_id}")
            result = self._retry_with_backoff(
                self.client.get_page_by_id,
                page_id=page_id,
                expand='body.storage,history,version,space,ancestors'
            )
            logger.debug(f"Successfully fetched page {page_id}")
            return result
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code in (401, 403):
                    raise ConfluenceAuthError(f"Authentication failed: {e}") from e
                elif status_code == 404:
                    raise ConfluenceNotFoundError(f"Page {page_id} not found") from e
                else:
                    raise ConfluenceAPIError(f"API error ({status_code}): {e}") from e
            raise ConfluenceAPIError(f"API error: {e}") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ConfluenceConnectionError(f"Connection failed: {e}") from e
    
    def get_child_pages(self, page_id: str) -> List[dict]:
        """Fetch all child pages with pagination handling.
        
        Args:
            page_id: Parent page ID
            
        Returns:
            List of child page objects (basic, not expanded)
            
        Raises:
            ConfluenceAuthError: Authentication failed
            ConfluenceConnectionError: Connection failed
            ConfluenceAPIError: Other API errors
        """
        all_children = []
        start = 0
        limit = 100
        
        try:
            logger.debug(f"Fetching child pages for {page_id}")
            while True:
                # Fetch page of results
                result = self._retry_with_backoff(
                    self.client.get_page_child_by_type,
                    page_id=page_id,
                    type='page',
                    start=start,
                    limit=limit
                )
                
                # Handle both response formats (dict with 'results' key, or list directly)
                if isinstance(result, list):
                    # Library returned list directly
                    batch_size = len(result)
                    all_children.extend(result)
                    logger.debug(f"Added {batch_size} children (total: {len(all_children)})")
                    # If we got less than limit, we're done
                    if batch_size < limit:
                        break
                    start += limit
                elif isinstance(result, dict):
                    # Library returned full response dict
                    logger.debug(f"API response keys: {result.keys()}")
                    
                    # Add results to accumulator
                    if 'results' in result:
                        batch_size = len(result['results'])
                        all_children.extend(result['results'])
                        logger.debug(f"Added {batch_size} children (total: {len(all_children)})")
                    else:
                        logger.warning(f"No 'results' key in API response for page {page_id}")
                    
                    # Check if there are more pages
                    if '_links' in result and 'next' in result['_links']:
                        start += limit
                        logger.debug(f"More pages available, continuing with start={start}")
                    else:
                        break
                else:
                    logger.error(f"Unexpected response type: {type(result)}")
                    break
            
            logger.info(f"Found {len(all_children)} child pages for page {page_id}")
            return all_children
            
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code in (401, 403):
                    raise ConfluenceAuthError(f"Authentication failed: {e}") from e
                elif status_code == 404:
                    raise ConfluenceNotFoundError(f"Page {page_id} not found") from e
                else:
                    raise ConfluenceAPIError(f"API error ({status_code}): {e}") from e
            raise ConfluenceAPIError(f"API error: {e}") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise ConfluenceConnectionError(f"Connection failed: {e}") from e
