import logging
import datetime
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

@function_tool
async def morning_briefing(location: str = "", stock_symbol: str = "AAPL") -> str:
    """
    Generates a daily morning digest.
    Aggregates weather, calendar events, recent unread emails, finance updates, and pending tasks.
    Returns a compiled summary to be read aloud or sent as a notification.
    
    Args:
        location: Optional location for weather.
        stock_symbol: Optional stock symbol to check for the briefing.
    """
    try:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        briefing = f"🌅 **Morning Briefing for {today}**\n\n"
        
        # Weather
        try:
            from Tools.weather import get_weather
            weather_info = await get_weather(location)
            briefing += f"🌤️ **Weather in {location}:**\n{weather_info}\n\n"
        except Exception as e:
            briefing += f"🌤️ **Weather:** Unavailable ({e})\n\n"
            
        # Calendar
        try:
            from Tools.calendar_agent import list_upcoming_events
            events = await list_upcoming_events(days=1)
            briefing += f"📅 **Today's Schedule:**\n{events}\n\n"
        except ImportError:
            pass
        except Exception as e:
            briefing += f"📅 **Today's Schedule:** Unavailable ({e})\n\n"
            
        # Emails
        try:
            from Tools.email_agent import read_inbox
            emails = await read_inbox(n=3)
            briefing += f"📧 **Recent Emails:**\n{emails}\n\n"
        except ImportError:
            pass
        except Exception as e:
            briefing += f"📧 **Recent Emails:** Unavailable ({e})\n\n"
            
        # Finance
        try:
            from Tools.finance_agent import get_stock_price
            price = await get_stock_price(symbol=stock_symbol)
            briefing += f"📈 **Finance Update ({stock_symbol}):**\n{price}\n\n"
        except ImportError:
            pass
        except Exception as e:
            briefing += f"📈 **Finance Update:** Unavailable ({e})\n\n"
            
        # Tasks / Reminders
        try:
            from Tools.scheduler import view_scheduled_tasks
            tasks = await view_scheduled_tasks()
            briefing += f"⏳ **Pending Scheduled Tasks:**\n{tasks}\n"
        except ImportError:
            pass
        except Exception as e:
            briefing += f"⏳ **Pending Tasks:** Unavailable ({e})\n"
            
        return briefing
    except Exception as e:
        logger.error(f"Failed to generate morning briefing: {e}")
        return f"Could not generate full briefing: {e}"
