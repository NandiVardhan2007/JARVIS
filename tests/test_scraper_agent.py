import pytest
from unittest.mock import patch, MagicMock
from Tools.scraper_agent import scrape_url

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <header><h1>Welcome</h1></header>
    <nav><ul><li><a href="/">Home</a></li></ul></nav>
    <main>
        <h2>Main Section</h2>
        <p>This is a test paragraph.</p>
        <blockquote>And a quote</blockquote>
        <script>console.log("ignore me");</script>
    </main>
    <footer><p>Footer stuff</p></footer>
</body>
</html>
"""

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_text_mode(mock_fetch):
    mock_fetch.return_value = SAMPLE_HTML
    result = await scrape_url("https://example.com", mode="text")

    # Expected behavior in text mode:
    # <title> should be extracted (via the URL logic if title is present, but actually scrape_url uses soup.title.string for the prefix)
    # <script>, <nav>, <footer>, <header> should be removed.
    # Text should just have the main content.
    assert "Content from 'Test Page':" in result
    assert "Main Section" in result
    assert "This is a test paragraph." in result
    assert "And a quote" in result
    assert "Welcome" not in result # because <header> is removed
    assert "Home" not in result # because <nav> is removed
    assert "ignore me" not in result # because <script> is removed
    assert "Footer stuff" not in result # because <footer> is removed

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_html_mode(mock_fetch):
    mock_fetch.return_value = SAMPLE_HTML
    result = await scrape_url("https://example.com", mode="html")

    assert "Content from 'Test Page':" in result
    assert "<!DOCTYPE html>" in result
    assert "<script>console.log(\"ignore me\");</script>" in result
    assert "<h2>Main Section</h2>" in result

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_markdown_mode(mock_fetch):
    mock_fetch.return_value = SAMPLE_HTML
    result = await scrape_url("https://example.com", mode="markdown")

    assert "Content from 'Test Page':" in result
    assert "## Main Section" in result
    assert "- Home" in result
    assert "> And a quote" in result
    # We expect h1 too
    assert "# Welcome" in result

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_truncation(mock_fetch):
    mock_fetch.return_value = "<p>" + "a" * 5000 + "</p>"
    result = await scrape_url("https://example.com", mode="text", max_length=100)

    assert "... (truncated)" in result
    # The result has header: "Content from '...':\n────────────────────────────────────────\n"
    # followed by the text truncated at 100 chars plus the suffix
    assert len(result) < 5000

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_error_handling(mock_fetch):
    mock_fetch.side_effect = Exception("Connection Refused")
    result = await scrape_url("https://example.com", mode="text")

    assert "Failed to scrape https://example.com: Connection Refused" in result

@pytest.mark.asyncio
@patch("Tools.scraper_agent._fetch")
async def test_scrape_url_no_content(mock_fetch):
    mock_fetch.return_value = "<html><body><script>var x = 1;</script></body></html>"
    result = await scrape_url("https://example.com", mode="text")

    assert "Page loaded but no readable content found at https://example.com." in result
