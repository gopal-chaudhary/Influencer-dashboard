"""Custom exceptions for the data ingestion layer.

These exceptions keep repository concerns explicit and make it easy for UI or
service layers to react to different failure modes without depending on
Streamlit-specific behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


class IngestionError(Exception):
    """Base class for all ingestion-related errors.

    Design decision:
    - A shared base type allows callers to catch all repository failures when
      they do not need to distinguish between specific cases.
    """


class InvalidFileFormatError(IngestionError):
    """Raised when the input file is not a supported or readable format."""

    def __init__(self, file_name: str | None, message: str | None = None) -> None:
        self.file_name = file_name
        default_message = "Unsupported or unreadable file format"
        if file_name:
            default_message = f"{default_message}: {file_name}"
        super().__init__(message or default_message)


class EmptyFileError(IngestionError):
    """Raised when the file exists but contains no usable data."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "The uploaded file is empty")


class MissingColumnsError(IngestionError):
    """Raised when one or more required columns are absent from the file."""

    def __init__(self, missing_columns: list[str]) -> None:
        self.missing_columns = missing_columns
        columns_text = ", ".join(missing_columns)
        super().__init__(f"Missing required columns: {columns_text}")


@dataclass(slots=True)
class InvalidRowError(IngestionError):
    """Raised when a specific row cannot be converted into an influencer."""

    row_number: int
    field_name: str
    reason: str

    def __post_init__(self) -> None:
        super().__init__(
            f"Invalid row {self.row_number} in column '{self.field_name}': {self.reason}"
        )


class DuplicateInfluencerError(IngestionError):
    """Raised when the same handle and platform combination appears twice."""

    def __init__(
        self,
        handle: str,
        platform: str,
        row_number: int,
        first_row_number: int | None = None,
    ) -> None:
        self.handle = handle
        self.platform = platform
        self.row_number = row_number
        self.first_row_number = first_row_number
        detail = f"Duplicate influencer '{handle}' on '{platform}' found at row {row_number}"
        if first_row_number is not None:
            detail += f" (first seen at row {first_row_number})"
        super().__init__(detail)
