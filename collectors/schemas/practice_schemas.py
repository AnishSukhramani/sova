"""
Pydantic schemas for practice-data collectors.

Pydantic validates collector output BEFORE writing to the database. If a
collector produces a record that doesn't match the schema, the validation
raises immediately — preventing partial/corrupted writes downstream.
"""

from typing import Optional

from pydantic import BaseModel, Field


class NPPESRecordSchema(BaseModel):
    """One row from the NPPES dental-practice extract."""

    npi: str
    practice_name: str
    address_line1: str = ''
    city: str = ''
    state: str = ''
    zip_code: str = ''
    phone: str = ''
    taxonomy_code: str = ''
    entity_type_code: str = ''  # NPPES code: '1' = individual, '2' = organization


class GooglePlacesDataSchema(BaseModel):
    """One Google Places result for a practice."""

    practice_npi: str
    google_place_id: Optional[str] = None
    review_count: Optional[int] = None
    star_rating: Optional[float] = None
    review_velocity_30d: Optional[float] = None
    phone_friction_count: int = 0
    phone_friction_keywords: list[str] = Field(default_factory=list)
    opening_hours: Optional[dict] = None
    response_rate: Optional[float] = None
