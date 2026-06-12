import pytest
from Tools.whatsapp import _resolve_contact

@pytest.mark.asyncio
async def test_resolve_contact_invalid_extraction():
    """
    Test that passing a string with no numbers and no letters
    correctly raises a ValueError for invalid phone extraction.
    We avoid letters to bypass the Google Contacts lookup block.
    """
    with pytest.raises(ValueError, match="Could not extract a valid phone number from the contact provided."):
        await _resolve_contact("!@#$%")

@pytest.mark.asyncio
async def test_resolve_contact_valid_string():
    """
    Test that a valid numeric string correctly resolves.
    """
    result = await _resolve_contact("1234567890")
    assert result == "1234567890"
