"""Domain model for a single influencer.

This module intentionally contains no Streamlit, API, persistence, or parsing
logic. It defines only the core business object used across the application
layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class Influencer:
    """Represent one influencer in the domain layer.

    Design decisions:
    - A dataclass keeps the model lightweight and explicit.
    - ``slots=True`` reduces memory overhead and discourages accidental dynamic
      attributes.
    - Validation lives in ``__post_init__`` so every instance is checked once
      at creation time, regardless of whether it was built directly or through
      ``from_dict``.
    - The model stores only domain data and stays independent from UI, API, and
      file parsing concerns.
    """

    name: str
    handle: str
    platform: str
    bio: str = ""
    recent_content: list[str] = field(default_factory=list)
    followers: int = 0
    language: str = ""

    def __post_init__(self) -> None:
        """Normalize and validate the influencer data.

        This method trims string fields, copies list-like content into a plain
        list, and enforces a few core invariants such as non-negative follower
        counts.
        """
        self.name = self._clean_text(self.name, "name", required=True)
        self.handle = self._clean_handle(self.handle)
        self.platform = self._clean_text(self.platform, "platform", required=True)
        self.bio = self._clean_text(self.bio, "bio", required=False)
        self.language = self._clean_text(self.language, "language", required=False)
        self.recent_content = self._normalize_recent_content(self.recent_content)
        self.followers = self._validate_followers(self.followers)

    @staticmethod
    def _clean_text(value: str, field_name: str, required: bool) -> str:
        """Return a trimmed string and validate required fields.

        Args:
            value: The raw string value to normalize.
            field_name: Field name used in error messages.
            required: Whether the field must contain non-empty text.

        Returns:
            The trimmed string value.

        Raises:
            TypeError: If the value is not a string.
            ValueError: If a required field is empty after trimming.
        """
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string")

        cleaned_value = value.strip()
        if required and not cleaned_value:
            raise ValueError(f"{field_name} cannot be empty")
        return cleaned_value

    @staticmethod
    def _clean_handle(value: str) -> str:
        """Normalize the influencer handle.

        Handles are stored without leading whitespace and with a single leading
        ``@`` removed when present. The method still requires a non-empty value.
        """
        cleaned_handle = Influencer._clean_text(value, "handle", required=True)
        return cleaned_handle[1:] if cleaned_handle.startswith("@") else cleaned_handle

    @staticmethod
    def _normalize_recent_content(value: list[str] | tuple[str, ...] | None) -> list[str]:
        """Normalize recent content into a list of trimmed strings.

        The domain model keeps this field flexible for future parsers while still
        enforcing a consistent in-memory representation.
        """
        if value is None:
            return []

        if not isinstance(value, (list, tuple)):
            raise TypeError("recent_content must be a list or tuple of strings")

        normalized_content: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("recent_content items must be strings")
            cleaned_item = item.strip()
            if cleaned_item:
                normalized_content.append(cleaned_item)
        return normalized_content

    @staticmethod
    def _validate_followers(value: int) -> int:
        """Validate the follower count.

        Followers are expected to be an integer and cannot be negative. The
        model does not guess or coerce string values because that belongs in the
        parsing layer.
        """
        if not isinstance(value, int):
            raise TypeError("followers must be an integer")
        if value < 0:
            raise ValueError("followers cannot be negative")
        return value

    def to_dict(self) -> dict[str, Any]:
        """Convert the influencer to a plain dictionary.

        This is useful when exporting data, writing tests, or passing the model
        across layers that prefer serializable structures.
        """
        return {
            "name": self.name,
            "handle": self.handle,
            "platform": self.platform,
            "bio": self.bio,
            "recent_content": list(self.recent_content),
            "followers": self.followers,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Influencer":
        """Create an influencer from a dictionary-like object.

        Args:
            data: Mapping containing influencer fields.

        Returns:
            A validated ``Influencer`` instance.

        Raises:
            KeyError: If a required key is missing.
            TypeError: If the value types are invalid.
            ValueError: If the values violate domain rules.
        """
        return cls(
            name=data["name"],
            handle=data["handle"],
            platform=data["platform"],
            bio=data.get("bio", ""),
            recent_content=data.get("recent_content", []),
            followers=data.get("followers", 0),
            language=data.get("language", ""),
        )
