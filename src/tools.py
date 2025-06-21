from langchain_core.tools import tool
import yfinance as yf
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

@tool
def retrieve_realtime_stock_price(symbol: str) -> str:
    """
    Retrieves the real-time stock price for a given symbol.

    Args:
        symbol: The stock ticker symbol (e.g., 'AMZN' for Amazon).

    Returns:
        A string containing the real-time stock price and currency, 
        or an error message if the symbol is not found or an error occurs.
    """
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get('last_price')
        currency = ticker.fast_info.get('currency', 'USD')
        
        if price:
            return f"The real-time stock price for {symbol} is ${price:.2f} {currency}."
        else:
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                return f"The real-time stock price for {symbol} is ${price:.2f} {currency}."
            return f"Could not retrieve real-time price for {symbol}. The symbol may be invalid."
            
    except Exception as e:
        return f"An error occurred while retrieving the price for {symbol}: {e}"

class HistoricalPriceInput(BaseModel):
    """Pydantic model for the input of retrieve_historical_stock_price tool."""
    symbol: str = Field(description="The stock ticker symbol (e.g., 'AMZN').")
    start_date: str = Field(description="The start date for the historical data in 'YYYY-MM-DD' format.")
    end_date: str = Field(description="The end date for the historical data in 'YYYY-MM-DD' format.")

@tool(args_schema=HistoricalPriceInput)
def retrieve_historical_stock_price(symbol: str, start_date: str, end_date: str) -> str:
    """
    Retrieves historical stock data (Open, High, Low, Close) for a symbol between two dates.
    It's crucial to use this tool for any queries about past stock performance.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end_date)
        
        if hist.empty:
            return f"No historical data found for {symbol} between {start_date} and {end_date}."
            
        # Provide a concise summary that is easy for the LLM to process and repeat.
        start_price = hist['Open'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        high_price = hist['High'].max()
        low_price = hist['Low'].min()

        summary = (
            f"For {symbol} between {start_date} and {end_date}: "
            f"the opening price was ${start_price:.2f}, the closing price was ${end_price:.2f}, "
            f"the highest price was ${high_price:.2f}, and the lowest price was ${low_price:.2f}."
        )
        return summary
        
    except Exception as e:
        return f"An error occurred while retrieving historical data for {symbol}: {e}" 