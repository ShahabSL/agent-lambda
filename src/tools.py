from langchain_core.tools import tool
import yfinance as yf
from datetime import datetime, timedelta

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
        # 'regularMarketPrice' is a common field for the current price
        # 'info' can be slow; 'fast_info' is a quicker alternative
        price = ticker.fast_info.get('regularMarketPrice')
        currency = ticker.fast_info.get('currency', 'USD')
        
        if price:
            return f"The real-time stock price for {symbol} is {price} {currency}."
        else:
            # Fallback for different data structures
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                return f"The real-time stock price for {symbol} is {price} {currency}."
            return f"Could not retrieve real-time price for {symbol}. The symbol may be invalid."
            
    except Exception as e:
        return f"An error occurred while retrieving the price for {symbol}: {e}"


@tool
def retrieve_historical_stock_price(symbol: str, months_ago: int = 3) -> str:
    """
    Retrieves the historical stock prices for a given symbol for a specified number of months. 
    A common request like 'Q4 last year' should be interpreted as a period of 3 months.

    Args:
        symbol: The stock ticker symbol (e.g., 'AMZN' for Amazon).
        months_ago: The number of months of historical data to retrieve. Defaults to 3 for a quarter.

    Returns:
        A string containing the historical stock prices (Date, Open, High, Low, Close),
        or an error message if the data cannot be retrieved.
    """
    try:
        ticker = yf.Ticker(symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_ago * 30) # Approximate months
        
        hist = ticker.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        
        if hist.empty:
            return f"No historical data found for {symbol} for the past {months_ago} months."
            
        # Format the data for better readability by the LLM
        hist_str = "Historical Prices for " + symbol + ":\n"
        hist_str += hist[['Open', 'High', 'Low', 'Close']].to_string()
        
        return hist_str
        
    except Exception as e:
        return f"An error occurred while retrieving historical data for {symbol}: {e}" 