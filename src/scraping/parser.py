"""DOM parsing with BeautifulSoup."""

from typing import Any, Callable

from bs4 import BeautifulSoup, Tag

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class DOMParser:
    """DOM parser using BeautifulSoup."""

    def __init__(self, html: str, parser: str = "lxml") -> None:
        """Initialize parser with HTML content.

        Args:
            html: HTML content to parse
            parser: BeautifulSoup parser (lxml, html.parser, html5lib)
        """
        self.soup = BeautifulSoup(html, parser)
        self._parser = parser

    @classmethod
    def from_selenium(cls, driver) -> "DOMParser":
        """Create parser from Selenium driver.

        Args:
            driver: Selenium WebDriver

        Returns:
            DOMParser instance
        """
        return cls(driver.page_source)

    def select(self, selector: str) -> list[Tag]:
        """Select elements using CSS selector.

        Args:
            selector: CSS selector

        Returns:
            List of matching elements
        """
        try:
            return self.soup.select(selector)
        except Exception as e:
            logger.warning(f"CSS select failed: {selector} | {e}")
            return []

    def select_one(self, selector: str) -> Tag | None:
        """Select single element using CSS selector.

        Args:
            selector: CSS selector

        Returns:
            First matching element or None
        """
        try:
            return self.soup.select_one(selector)
        except Exception as e:
            logger.warning(f"CSS select_one failed: {selector} | {e}")
            return None

    def find(self, tag: str, attrs: dict[str, Any] | None = None, **kwargs) -> Tag | None:
        """Find single element by tag and attributes.

        Args:
            tag: HTML tag name
            attrs: Attribute dictionary
            **kwargs: Additional attributes

        Returns:
            First matching element or None
        """
        return self.soup.find(tag, attrs=attrs, **kwargs)

    def find_all(self, tag: str, attrs: dict[str, Any] | None = None, limit: int | None = None, **kwargs) -> list[Tag]:
        """Find all elements by tag and attributes.

        Args:
            tag: HTML tag name
            attrs: Attribute dictionary
            limit: Maximum number of results
            **kwargs: Additional attributes

        Returns:
            List of matching elements
        """
        return self.soup.find_all(tag, attrs=attrs, limit=limit, **kwargs)

    def xpath(self, expression: str) -> list[Tag]:
        """Select elements using XPath (requires lxml).

        Args:
            expression: XPath expression

        Returns:
            List of matching elements
        """
        try:
            from lxml import etree

            tree = etree.HTML(str(self.soup))
            elements = tree.xpath(expression)

            # Convert lxml elements back to BeautifulSoup tags
            results = []
            for el in elements:
                html_str = etree.tostring(el, encoding="unicode")
                soup = BeautifulSoup(html_str, self._parser)
                if soup.contents:
                    results.append(soup.contents[0])
            return results

        except ImportError:
            logger.error("lxml not installed, XPath not available")
            return []
        except Exception as e:
            logger.warning(f"XPath failed: {expression} | {e}")
            return []

    def get_text(self, element: Tag | str, strip: bool = True, separator: str = " ") -> str:
        """Extract text from element.

        Args:
            element: BeautifulSoup Tag or CSS selector
            strip: Strip whitespace
            separator: Text separator

        Returns:
            Element text content
        """
        if isinstance(element, str):
            element = self.select_one(element)

        if element is None:
            return ""

        text = element.get_text(separator=separator)
        return text.strip() if strip else text

    def get_attribute(self, element: Tag | str, attr: str) -> str | None:
        """Get element attribute value.

        Args:
            element: BeautifulSoup Tag or CSS selector
            attr: Attribute name

        Returns:
            Attribute value or None
        """
        if isinstance(element, str):
            element = self.select_one(element)

        if element is None:
            return None

        return element.get(attr)

    def get_href(self, element: Tag | str) -> str | None:
        """Get href attribute from element.

        Args:
            element: BeautifulSoup Tag or CSS selector

        Returns:
            Href value or None
        """
        return self.get_attribute(element, "href")

    def get_src(self, element: Tag | str) -> str | None:
        """Get src attribute from element.

        Args:
            element: BeautifulSoup Tag or CSS selector

        Returns:
            Src value or None
        """
        return self.get_attribute(element, "src")

    def extract_data(
        self,
        container_selector: str,
        field_map: dict[str, str | dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract structured data from repeating elements.

        Args:
            container_selector: CSS selector for item containers
            field_map: Dictionary mapping field names to selectors
                       Value can be string (CSS selector) or dict with:
                       - selector: CSS selector
                       - attribute: Attribute to extract (default: text)
                       - transform: Optional transform function

        Returns:
            List of extracted data dictionaries

        Example:
            >>> parser.extract_data(
            ...     ".product",
            ...     {
            ...         "title": "h3.title",
            ...         "price": {"selector": ".price", "transform": parse_price},
            ...         "image": {"selector": "img", "attribute": "src"},
            ...     }
            ... )
        """
        containers = self.select(container_selector)
        results = []

        for container in containers:
            item = {}
            for field_name, config in field_map.items():
                if isinstance(config, str):
                    # Simple selector - extract text
                    element = container.select_one(config)
                    item[field_name] = self.get_text(element) if element else None
                elif isinstance(config, dict):
                    selector = config.get("selector", "")
                    attribute = config.get("attribute", "text")
                    transform = config.get("transform")

                    element = container.select_one(selector)
                    if element:
                        if attribute == "text":
                            value = self.get_text(element)
                        else:
                            value = element.get(attribute)

                        if transform and callable(transform):
                            value = transform(value)

                        item[field_name] = value
                    else:
                        item[field_name] = None

            results.append(item)

        logger.debug(f"Extracted {len(results)} items from {container_selector}")
        return results

    def extract_table(
        self,
        table_selector: str = "table",
        header_row: int = 0,
        has_header: bool = True,
    ) -> list[dict[str, Any]]:
        """Extract data from HTML table.

        Args:
            table_selector: CSS selector for table
            header_row: Row index for headers
            has_header: Whether table has header row

        Returns:
            List of row dictionaries
        """
        table = self.select_one(table_selector)
        if not table:
            return []

        rows = table.select("tr")
        if not rows:
            return []

        # Extract headers
        headers = []
        if has_header and len(rows) > header_row:
            header_cells = rows[header_row].select("th, td")
            headers = [self.get_text(cell) for cell in header_cells]
            data_rows = rows[header_row + 1:]
        else:
            data_rows = rows

        # Extract data
        results = []
        for row in data_rows:
            cells = row.select("td")
            if not cells:
                continue

            if headers:
                row_data = {}
                for i, cell in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_data[key] = self.get_text(cell)
                results.append(row_data)
            else:
                results.append({f"col_{i}": self.get_text(cell) for i, cell in enumerate(cells)})

        return results

    def extract_links(
        self,
        selector: str = "a",
        base_url: str | None = None,
        filter_func: Callable[[str], bool] | None = None,
    ) -> list[dict[str, str]]:
        """Extract links from page.

        Args:
            selector: CSS selector for links
            base_url: Base URL for relative links
            filter_func: Optional filter function

        Returns:
            List of link dictionaries with href and text
        """
        links = self.select(selector)
        results = []

        for link in links:
            href = link.get("href", "")
            text = self.get_text(link)

            if not href:
                continue

            # Make absolute URL
            if base_url and not href.startswith(("http://", "https://", "//")):
                href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"

            # Apply filter
            if filter_func and not filter_func(href):
                continue

            results.append({"href": href, "text": text})

        return results

    def extract_images(
        self,
        selector: str = "img",
        base_url: str | None = None,
    ) -> list[dict[str, str]]:
        """Extract images from page.

        Args:
            selector: CSS selector for images
            base_url: Base URL for relative URLs

        Returns:
            List of image dictionaries with src and alt
        """
        images = self.select(selector)
        results = []

        for img in images:
            src = img.get("src", "") or img.get("data-src", "")
            alt = img.get("alt", "")

            if not src:
                continue

            # Make absolute URL
            if base_url and not src.startswith(("http://", "https://", "//", "data:")):
                src = f"{base_url.rstrip('/')}/{src.lstrip('/')}"

            results.append({"src": src, "alt": alt})

        return results

    def get_meta(self, name: str | None = None, property: str | None = None) -> str | None:
        """Get meta tag content.

        Args:
            name: Meta name attribute
            property: Meta property attribute (for Open Graph)

        Returns:
            Meta content or None
        """
        if name:
            meta = self.find("meta", attrs={"name": name})
        elif property:
            meta = self.find("meta", attrs={"property": property})
        else:
            return None

        return meta.get("content") if meta else None

    def get_title(self) -> str:
        """Get page title.

        Returns:
            Page title
        """
        title = self.find("title")
        return self.get_text(title) if title else ""

    def remove_elements(self, selector: str) -> int:
        """Remove elements matching selector.

        Args:
            selector: CSS selector

        Returns:
            Number of elements removed
        """
        elements = self.select(selector)
        for el in elements:
            el.decompose()
        return len(elements)

    def get_clean_text(self, selector: str | None = None) -> str:
        """Get clean text content (removes scripts, styles, etc).

        Args:
            selector: Optional CSS selector to limit scope

        Returns:
            Clean text content
        """
        # Make a copy to avoid modifying original
        if selector:
            element = self.select_one(selector)
            if not element:
                return ""
            soup = BeautifulSoup(str(element), self._parser)
        else:
            soup = BeautifulSoup(str(self.soup), self._parser)

        # Remove unwanted elements
        for tag in soup.select("script, style, noscript, header, footer, nav"):
            tag.decompose()

        return soup.get_text(separator=" ", strip=True)
