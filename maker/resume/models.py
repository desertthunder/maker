"""Pydantic models for JSON Resume schema validation.

Implements a subset of jsonresume.org v1.0.0 schema covering:
basics, work, education, skills, and projects sections.
"""

from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional


class Location(BaseModel):
    """Geographic location information."""

    city: Optional[str] = None
    region: Optional[str] = None
    countryCode: Optional[str] = None


class Profile(BaseModel):
    """Social or professional profile link."""

    network: Optional[str] = None
    username: Optional[str] = None
    url: Optional[HttpUrl] = None


class Basics(BaseModel):
    """Core biographical information."""

    name: str
    label: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    url: Optional[HttpUrl] = None
    summary: Optional[str] = None
    location: Optional[Location] = None
    profiles: list[Profile] = []


class Work(BaseModel):
    """Work experience entry."""

    name: Optional[str] = None
    position: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    summary: Optional[str] = None
    highlights: list[str] = []


class Education(BaseModel):
    """Education entry."""

    institution: Optional[str] = None
    studyType: Optional[str] = None
    area: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    score: Optional[str] = None


class Skill(BaseModel):
    """Skill category with keywords."""

    name: Optional[str] = None
    level: Optional[str] = None
    keywords: list[str] = []


class Project(BaseModel):
    """Personal or professional project."""

    name: Optional[str] = None
    description: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    url: Optional[HttpUrl] = None
    highlights: list[str] = []


class Resume(BaseModel):
    """Root resume model following JSON Resume schema subset."""

    basics: Basics
    work: list[Work] = []
    education: list[Education] = []
    skills: list[Skill] = []
    projects: list[Project] = []

    class Config:
        extra = "ignore"
