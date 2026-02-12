"""Click-based CLI for Confluence.md."""
import os
import sys
import logging
from pathlib import Path
import click
from dotenv import load_dotenv
from . import __version__
from .client import ConfluenceClient, ConfluenceAuthError, ConfluenceNotFoundError, ConfluenceConnectionError
from .exporter import PageExporter
from .update_checker import UpdateChecker, format_update_message


@click.command()
@click.version_option(version=__version__, prog_name='confluence-md')
@click.option('--page-id', required=True, help='Confluence page ID to export')
@click.option('--output-path', required=True, type=click.Path(), help='Output directory path')
@click.option('--url', help='Confluence base URL (or set CONFLUENCE_URL env var)')
@click.option('--user', help='Username/email for Cloud, omit for Server PAT (or set CONFLUENCE_USER)')
@click.option('--token', help='API token (Cloud) or Personal Access Token (Server) (or set CONFLUENCE_TOKEN)')
@click.option('--delay-ms', default=100, type=int, help='Delay between API calls in milliseconds (default: 100)')
@click.option('--timeout', default=30, type=int, help='HTTP request timeout in seconds (default: 30)')
@click.option('--skip-existing', is_flag=True, help='Skip files that already exist (resume capability)')
@click.option('--max-depth', default=50, type=int, help='Maximum recursion depth (default: 50)')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
@click.option('--no-update-check', is_flag=True, help='Disable update check')
def main(page_id, output_path, url, user, token, delay_ms, timeout, skip_existing, max_depth, verbose, no_update_check):
    """Export Confluence pages to Markdown files recursively."""
        # Start background update check (non-blocking)
    update_checker = None
    should_check_updates = not no_update_check and not os.environ.get("CONFLUENCE_MD_NO_UPDATE_CHECK", "").lower() in ("1", "true", "yes")
    if should_check_updates:
        update_checker = UpdateChecker(__version__)
        update_checker.start()
        # Load environment variables from .env file
    load_dotenv()
    
    # Setup logging
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s'
        )
    
    # Resolve credentials independently (CLI args > system env var > .env file)
    confluence_url = url or os.getenv('CONFLUENCE_URL')
    confluence_user = user or os.getenv('CONFLUENCE_USER') or None  # User is optional for Server PAT
    confluence_token = token or os.getenv('CONFLUENCE_TOKEN')
    
    # Validate required credentials
    if not confluence_url:
        click.echo("Error: CONFLUENCE_URL not provided (use --url or set environment variable)", err=True)
        sys.exit(2)
    if not confluence_token:
        click.echo("Error: CONFLUENCE_TOKEN not provided (use --token or set environment variable)", err=True)
        sys.exit(2)
    
    # Log authentication method
    if confluence_user:
        click.echo(f"Using Cloud authentication (username + token) for {confluence_url}")
    else:
        click.echo(f"Using Server authentication (Bearer token only) for {confluence_url}")
    
    # Validate output directory is writable
    output_dir = Path(output_path)
    if output_dir.exists() and not os.access(output_dir, os.W_OK):
        click.echo(f"Error: Output directory '{output_path}' is not writable", err=True)
        sys.exit(2)
    
    # Instantiate Confluence client (user is optional for Server PAT)
    client = ConfluenceClient(confluence_url, confluence_token, user=confluence_user, timeout=timeout)
    
    # Instantiate exporter
    exporter = PageExporter(
        client=client,
        output_path=Path(output_path),
        delay_ms=delay_ms,
        base_url=confluence_url,
        skip_existing=skip_existing,
        max_depth=max_depth
    )
    
    # Execute export with progress reporting
    mode_msg = " (resuming, skipping existing files)" if skip_existing else ""
    click.echo(f"Exporting page {page_id} to {output_path}{mode_msg}...")
    click.echo(f"Settings: timeout={timeout}s, delay={delay_ms}ms, max_depth={max_depth}")
    success_count, failure_count = exporter.export_tree(page_id, Path(output_path))
    
    # Report results and exit with appropriate code
    exit_code = 0
    if failure_count == 0:
        click.echo(f"✓ All pages exported successfully ({success_count} pages)")
        exit_code = 0
    elif success_count > 0:
        click.echo(f"⚠ Partial success: {success_count} succeeded, {failure_count} failed", err=True)
        exit_code = 1
    else:
        click.echo("✗ Export failed", err=True)
        exit_code = 1
    
    # Check for updates (print after main output)
    if update_checker:
        latest = update_checker.get_result(timeout=0.5)
        if latest:
            click.echo(format_update_message(latest))
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
