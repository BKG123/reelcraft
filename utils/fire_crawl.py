import os
import asyncio
from firecrawl import Firecrawl
from dotenv import load_dotenv

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")


class WebScrapingError(Exception):
    """Custom exception for web scraping failures."""
    pass


async def get_webpage_markdown(
    url: str,
) -> str:
    """
    Scrape a webpage and return its content in markdown format.

    Args:
        url: The URL of the webpage to scrape

    Returns:
        str: The webpage content formatted as markdown

    Raises:
        ValueError: If no API key is provided
        WebScrapingError: If scraping fails or returns invalid content
    """
    if not FIRECRAWL_API_KEY:
        raise ValueError(
            "API key must be provided or set in FIRECRAWL_API_KEY environment variable"
        )

    try:
        # Run the synchronous scraping in an executor to avoid blocking
        loop = asyncio.get_event_loop()
        firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

        # Scrape the URL and get markdown content
        doc = await loop.run_in_executor(
            None,
            lambda: firecrawl.scrape(url, formats=["markdown"])
        )

        if not doc or not hasattr(doc, 'markdown'):
            raise WebScrapingError(f"Failed to scrape content from {url}: Invalid response")

        markdown = doc.markdown

        # Validate the content - check for common error patterns
        if not markdown or len(markdown.strip()) < 100:
            raise WebScrapingError(f"Failed to scrape content from {url}: Content too short or empty")

        # Check for common error indicators in the content
        error_indicators = [
            "apologies, but something went wrong",
            "500 internal server error",
            "404 not found",
            "access denied",
            "forbidden",
            "recaptcha requires verification"
        ]

        markdown_lower = markdown.lower()
        for indicator in error_indicators:
            if indicator in markdown_lower:
                raise WebScrapingError(
                    f"Failed to scrape content from {url}: Page returned an error ({indicator})"
                )

        return markdown

    except WebScrapingError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # Wrap any other exceptions in our custom error
        raise WebScrapingError(f"Failed to scrape content from {url}: {str(e)}") from e


# Example usage
if __name__ == "__main__":
    # You can set your API key here or use environment variable
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-YOUR-API-KEY")

    # Test the function
    test_url = "https://medium.com/data-science-at-microsoft/how-large-language-models-work-91c362f5b78f"
    markdown_content = get_webpage_markdown(test_url)
    print(markdown_content)
