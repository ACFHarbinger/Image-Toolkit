"""Search operator injection for reverse/text-fallback search URLs.

Translates user-facing domain toggles (e.g. "restrict to Reddit",
"only r/specific_subreddit") into the search-operator syntax each backend
engine expects. Kept separate from the engines themselves so new domain
toggles don't require touching engine code.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote_plus


@dataclass
class DomainScope:
    """One user-configurable scraping restriction.

    Attributes:
        domain: Bare domain, e.g. "reddit.com".
        path_prefix: Optional path restriction, e.g. "/r/specific_subreddit".
        exclude: If True, this becomes a "-site:" exclusion instead of an
            inclusion. Useful for e.g. "search everywhere except Pinterest".
    """
    domain: str
    path_prefix: Optional[str] = None
    exclude: bool = False

    def as_operator(self) -> str:
        target = self.domain + (self.path_prefix or "")
        return f'{"-" if self.exclude else ""}site:{target}'


@dataclass
class SearchOperatorBuilder:
    """Builds engine-appropriate query strings from a list of DomainScopes.

    Args:
        scopes: Domain restrictions/exclusions to apply.
        base_terms: Free-text terms (e.g. tags from an interrogator model)
            to combine with the site operators.
    """
    scopes: List[DomainScope] = field(default_factory=list)
    base_terms: List[str] = field(default_factory=list)

    def build_query_string(self) -> str:
        """Return a plain query string, e.g. '"1girl" "sword" site:reddit.com/r/x'."""
        parts = [f'"{t}"' if " " in t else t for t in self.base_terms]
        parts.extend(scope.as_operator() for scope in self.scopes)
        return " ".join(parts).strip()

    def build_url(self, base_search_url: str, query_param: str = "q") -> str:
        """Build a full search URL for engines that accept a simple GET query param.

        Args:
            base_search_url: e.g. "https://www.google.com/search".
            query_param: Name of the query param, e.g. "q" (Google/Bing) or
                "text" (some engines).
        """
        query = self.build_query_string()
        sep = "&" if "?" in base_search_url else "?"
        return f"{base_search_url}{sep}{query_param}={quote_plus(query)}"

    def add_subreddit(self, subreddit: str, exclude: bool = False) -> "SearchOperatorBuilder":
        """Convenience: restrict to a specific subreddit's image posts."""
        self.scopes.append(
            DomainScope(domain="reddit.com", path_prefix=f"/r/{subreddit}", exclude=exclude)
        )
        return self
