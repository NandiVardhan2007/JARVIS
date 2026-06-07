import pytest
from datetime import datetime
from unittest.mock import patch
from Tools.weather import get_time_info

@pytest.mark.asyncio
async def test_get_time_info():
    with patch('Tools.weather.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 10, 27, 14, 30)
        result = await get_time_info()
        assert result == "Today is Friday, 27 October 2023. The current time is 02:30 PM."
