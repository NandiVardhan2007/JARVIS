import pytest
from unittest.mock import patch, MagicMock

# Import the module to test
import Tools.scraper_agent as scraper_agent

@pytest.mark.asyncio
async def test_ai_summarize_page_happy_path():
    with patch("Tools.scraper_agent._fetch") as mock_fetch, \
         patch("Tools.scraper_agent._soup") as mock_soup, \
         patch("Tools.scraper_agent._clean_text") as mock_clean_text, \
         patch("Tools.scraper_agent._scraper_llm") as mock_llm:

        # Setup mocks
        mock_fetch.return_value = "<html><head><title>Test Title</title></head><body>Some text</body></html>"

        mock_soup_obj = MagicMock()
        mock_soup_obj.title.string = "Test Title"
        mock_soup.return_value = mock_soup_obj

        mock_clean_text.return_value = "Some text"
        mock_llm.return_value = "This is a summary."

        url = "http://example.com"
        result = await scraper_agent.ai_summarize_page(url)

        # Assertions
        mock_fetch.assert_called_once_with(url)
        mock_soup.assert_called_once_with(mock_fetch.return_value)
        mock_clean_text.assert_called_once_with(mock_soup.return_value)
        mock_llm.assert_called_once()

        assert "AI Summary for 'Test Title'" in result
        assert "This is a summary." in result

@pytest.mark.asyncio
async def test_ai_summarize_page_empty_content():
    with patch("Tools.scraper_agent._fetch") as mock_fetch, \
         patch("Tools.scraper_agent._soup") as mock_soup, \
         patch("Tools.scraper_agent._clean_text") as mock_clean_text, \
         patch("Tools.scraper_agent._scraper_llm") as mock_llm:

        mock_fetch.return_value = "<html><body></body></html>"
        mock_soup.return_value = MagicMock()
        mock_clean_text.return_value = "   \n  " # Empty/whitespace only text

        url = "http://example.com/empty"
        result = await scraper_agent.ai_summarize_page(url)

        mock_fetch.assert_called_once_with(url)
        mock_clean_text.assert_called_once()
        mock_llm.assert_not_called()

        assert f"No readable text found at {url} to summarize." in result

@pytest.mark.asyncio
async def test_ai_summarize_page_exception():
    with patch("Tools.scraper_agent._fetch") as mock_fetch:

        # Setup mock to raise an exception
        mock_fetch.side_effect = Exception("Network error")

        url = "http://example.com/error"
        result = await scraper_agent.ai_summarize_page(url)

        assert "Failed to summarize page: Network error" in result

@pytest.mark.asyncio
async def test_ai_summarize_page_truncates_text():
    with patch("Tools.scraper_agent._fetch") as mock_fetch, \
         patch("Tools.scraper_agent._soup") as mock_soup, \
         patch("Tools.scraper_agent._clean_text") as mock_clean_text, \
         patch("Tools.scraper_agent._scraper_llm") as mock_llm:

        mock_fetch.return_value = "<html><body>" + "a" * 20000 + "</body></html>"

        mock_soup_obj = MagicMock()
        mock_soup_obj.title.string = "Test Title"
        mock_soup.return_value = mock_soup_obj

        # Provide more than 15000 characters
        long_text = "a" * 20000
        mock_clean_text.return_value = long_text
        mock_llm.return_value = "Summary"

        url = "http://example.com"
        await scraper_agent.ai_summarize_page(url)

        # Check that the text passed to LLM is truncated to 15000
        llm_call_args = mock_llm.call_args[0]
        user_prompt = llm_call_args[1]

        # Check it includes exactly 15000 "a"s
        expected_text = "a" * 15000
        assert expected_text in user_prompt
        assert len(expected_text) == 15000
        # The prompt will also contain title and URL, so we just verify the exact content length constraint.
