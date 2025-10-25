import os
from firecrawl import Firecrawl
from dotenv import load_dotenv
from mocks.mock import MOCK_FIRECRAWL_RESPONSE

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")


def get_webpage_markdown(
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
        Exception: If scraping fails
    """
    # if not FIRECRAWL_API_KEY:
    #     raise ValueError(
    #         "API key must be provided or set in FIRECRAWL_API_KEY environment variable"
    #     )

    # firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

    # # Scrape the URL and get markdown content
    # doc = firecrawl.scrape(url, formats=["markdown"])

    # return doc.markdown
    return MOCK_FIRECRAWL_RESPONSE


# Example usage
if __name__ == "__main__":
    # You can set your API key here or use environment variable
    api_key = os.getenv("FIRECRAWL_API_KEY", "fc-YOUR-API-KEY")

    # Test the function
    test_url = "https://medium.com/data-science-at-microsoft/how-large-language-models-work-91c362f5b78f"
    markdown_content = get_webpage_markdown(test_url)
    print(markdown_content)
