import pytest
from unittest.mock import patch
from Tools.scraper_agent import extract_tables

@pytest.mark.asyncio
async def test_extract_tables_exception():
    with patch("Tools.scraper_agent._fetch", side_effect=Exception("Mocked fetch error")):
        result = await extract_tables("http://example.com")
        assert result == "Failed to extract tables: Mocked fetch error"
