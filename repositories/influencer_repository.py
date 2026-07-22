"""Repository for loading influencer data from tabular files.

This repository is responsible only for ingestion and validation. It converts
CSV and Excel rows into validated ``Influencer`` domain objects without knowing
anything about Streamlit, the UI, or downstream AI services.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, IO
from zipfile import BadZipFile

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from models import Influencer
from utils.exceptions import (
    EmptyFileError,
    InvalidFileFormatError,
    InvalidRowError,
    MissingColumnsError,
)


FileSource = str | Path | IO[Any]


@dataclass(slots=True)
class LoadResult:
    """Summary of a repository load operation.

    Design decision:
    - Returning a small result object keeps the repository API expressive while
      preserving the domain list as the primary output.
    - The UI can display counts without needing to inspect file internals.
    """

    influencers: list[Influencer]
    total_rows: int
    loaded_count: int
    duplicate_count: int
    invalid_count: int


class InfluencerRepository:
    """Load and validate influencer data from CSV or Excel files.

    Design decisions:
    - The repository is the boundary between raw tabular data and the domain
      model.
    - It depends on the ``Influencer`` model, but not on Streamlit or any AI
      logic.
    - Validation is explicit, row-level issues are collected, and catastrophic
      input problems still raise custom exceptions.
    - The public API is intentionally small: one method that returns a list of
      domain objects, plus a richer method for UI summaries.
    """

    REQUIRED_COLUMNS: tuple[str, ...] = (
        "name",
        "handle",
        "platform",
        "bio",
        "recent_content",
        "followers",
        "language",
    )

    def load(self, file_source: FileSource) -> list[Influencer]:
        """Load influencers from a CSV or Excel source.

        Args:
            file_source: A file path or file-like object containing CSV or XLSX
                data.

        Returns:
            A list of validated ``Influencer`` objects.

        Raises:
            InvalidFileFormatError: If the file cannot be read as CSV or Excel.
            EmptyFileError: If the file has no rows or no usable data.
            MissingColumnsError: If any required columns are absent.
        """
        return self.load_with_stats(file_source).influencers

    def load_with_stats(self, file_source: FileSource) -> LoadResult:
        """Load influencers and return summary statistics.

        The repository is intentionally tolerant of row-level data issues so the
        UI can show a useful preview for partial datasets.
        """
        dataframe = self._read_dataframe(file_source)
        dataframe = self._normalize_columns(dataframe)
        self._validate_required_columns(dataframe.columns)

        if dataframe.empty:
            raise EmptyFileError()

        influencers: list[Influencer] = []
        seen_keys: dict[tuple[str, str], int] = {}
        duplicate_count = 0
        invalid_count = 0

        for row_number, row in enumerate(dataframe.to_dict(orient="records"), start=2):
            try:
                influencer = self._row_to_influencer(row, row_number=row_number)
            except InvalidRowError:
                invalid_count += 1
                continue

            duplicate_key = self._duplicate_key(influencer.handle, influencer.platform)
            first_seen_row = seen_keys.get(duplicate_key)
            if first_seen_row is not None:
                duplicate_count += 1
                continue

            seen_keys[duplicate_key] = row_number
            influencers.append(influencer)

        return LoadResult(
            influencers=influencers,
            total_rows=len(dataframe.index),
            loaded_count=len(influencers),
            duplicate_count=duplicate_count,
            invalid_count=invalid_count,
        )

    def _read_dataframe(self, file_source: FileSource) -> pd.DataFrame:
        """Read the source into a pandas DataFrame.

        The method supports only CSV and XLSX input because those are the file
        types required by the project.
        """
        file_name = self._resolve_file_name(file_source)
        file_suffix = self._resolve_suffix(file_name)

        try:
            if file_suffix == ".csv":
                return pd.read_csv(file_source, dtype=object, keep_default_na=False)

            if file_suffix == ".xlsx":
                return pd.read_excel(
                    file_source,
                    engine="openpyxl",
                    dtype=object,
                )

            raise InvalidFileFormatError(file_name)
        except EmptyDataError as exc:
            raise EmptyFileError() from exc
        except (ParserError, ValueError, BadZipFile, OSError) as exc:
            raise InvalidFileFormatError(file_name) from exc

    def _normalize_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to a predictable canonical form."""
        rename_map = {
            column: self._normalize_column_name(column) for column in dataframe.columns
        }

        normalized_names = list(rename_map.values())
        if len(normalized_names) != len(set(normalized_names)):
            raise InvalidFileFormatError(
                None,
                "Column names collapse to duplicates after normalization",
            )

        return dataframe.rename(columns=rename_map)

    def _validate_required_columns(self, columns: Any) -> None:
        """Ensure that all required columns are present."""
        available_columns = set(columns)
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in available_columns
        ]
        if missing_columns:
            raise MissingColumnsError(missing_columns)

    def _row_to_influencer(self, row: dict[str, Any], row_number: int) -> Influencer:
        """Convert one dataframe row into an ``Influencer`` instance."""
        name = self._require_text(row.get("name"), row_number=row_number, field_name="name")
        handle = self._require_text(
            row.get("handle"), row_number=row_number, field_name="handle"
        )
        platform = self._require_text(
            row.get("platform"), row_number=row_number, field_name="platform"
        )
        bio = self._optional_text(row.get("bio"))
        recent_content = self._parse_recent_content(row.get("recent_content"), row_number)
        followers = self._parse_followers(row.get("followers"), row_number)
        language = self._optional_text(row.get("language"))

        try:
            return Influencer(
                name=name,
                handle=handle,
                platform=platform,
                bio=bio,
                recent_content=recent_content,
                followers=followers,
                language=language,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidRowError(row_number, "influencer", str(exc)) from exc

    def _require_text(self, value: Any, row_number: int, field_name: str) -> str:
        """Return a trimmed non-empty string or raise a row validation error."""
        if self._is_missing(value):
            raise InvalidRowError(row_number, field_name, "value is required")
        if not isinstance(value, str):
            value = str(value)

        cleaned_value = value.strip()
        if not cleaned_value:
            raise InvalidRowError(row_number, field_name, "value is required")
        return cleaned_value

    def _optional_text(self, value: Any) -> str:
        """Return a trimmed string for optional fields or an empty string."""
        if self._is_missing(value):
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.strip()

    def _parse_recent_content(self, value: Any, row_number: int) -> list[str]:
        """Parse the recent content field into a list of strings."""
        if self._is_missing(value):
            return []

        if isinstance(value, (list, tuple)):
            return self._normalize_text_items(value, row_number, "recent_content")

        if not isinstance(value, str):
            value = str(value)

        text = value.strip()
        if not text:
            return []

        if text.startswith(("[", "(")) and text.endswith(("]", ")")):
            try:
                parsed_value = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed_value = None
            else:
                if isinstance(parsed_value, (list, tuple)):
                    return self._normalize_text_items(
                        parsed_value,
                        row_number,
                        "recent_content",
                    )

        split_items = [part.strip() for part in re.split(r"\s*(?:\r?\n|;|\|)\s*", text)]
        cleaned_items = [item for item in split_items if item]
        if len(cleaned_items) > 1:
            return cleaned_items

        return [text]

    def _parse_followers(self, value: Any, row_number: int) -> int:
        """Parse the followers field into a non-negative integer."""
        if self._is_missing(value):
            return 0

        if isinstance(value, bool):
            raise InvalidRowError(row_number, "followers", "must be a number")

        if isinstance(value, int):
            if value < 0:
                raise InvalidRowError(row_number, "followers", "cannot be negative")
            return value

        if isinstance(value, float):
            if math.isnan(value):
                return 0
            if not value.is_integer():
                raise InvalidRowError(row_number, "followers", "must be a whole number")
            integer_value = int(value)
            if integer_value < 0:
                raise InvalidRowError(row_number, "followers", "cannot be negative")
            return integer_value

        text = str(value).strip().replace(",", "")
        if not text:
            return 0

        try:
            number = float(text) if "." in text else int(text)
        except ValueError as exc:
            raise InvalidRowError(row_number, "followers", "must be numeric") from exc

        if isinstance(number, float):
            if not number.is_integer():
                raise InvalidRowError(row_number, "followers", "must be a whole number")
            number = int(number)

        if number < 0:
            raise InvalidRowError(row_number, "followers", "cannot be negative")
        return int(number)

    def _normalize_text_items(
        self,
        items: list[str] | tuple[str, ...],
        row_number: int,
        field_name: str,
    ) -> list[str]:
        """Normalize a list or tuple of text values."""
        normalized_items: list[str] = []
        for item in items:
            if self._is_missing(item):
                continue
            if not isinstance(item, str):
                item = str(item)
            cleaned_item = item.strip()
            if cleaned_item:
                normalized_items.append(cleaned_item)

        if not normalized_items:
            raise InvalidRowError(row_number, field_name, "must contain at least one item")
        return normalized_items

    def _duplicate_key(self, handle: str, platform: str) -> tuple[str, str]:
        """Build a case-insensitive duplicate detection key."""
        normalized_handle = handle.lstrip("@").strip().casefold()
        normalized_platform = platform.strip().casefold()
        return normalized_handle, normalized_platform

    def _resolve_file_name(self, file_source: FileSource) -> str | None:
        """Resolve a human-readable file name for extension detection."""
        if isinstance(file_source, (str, Path)):
            return str(file_source)

        file_name = getattr(file_source, "name", None)
        return file_name if isinstance(file_name, str) and file_name else None

    def _resolve_suffix(self, file_name: str | None) -> str:
        """Return the lower-case file suffix used to choose a parser."""
        if not file_name:
            return ""
        return Path(file_name).suffix.lower()

    @staticmethod
    def _normalize_column_name(column: Any) -> str:
        """Normalize a raw column name into the expected canonical form."""
        normalized = str(column).strip().lower()
        normalized = re.sub(r"\s+", "_", normalized)
        return normalized

    @staticmethod
    def _is_missing(value: Any) -> bool:
        """Return ``True`` when a value is empty, null, or whitespace only."""
        if value is None:
            return True

        if isinstance(value, str):
            return not value.strip()

        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False
