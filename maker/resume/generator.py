"""PDF generation for resume documents using reportlab.

Renders validated Resume models to formatted PDF documents with
configurable fonts and layout themes.
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
)

from maker.resume.models import Resume
from maker.resume.fonts import register_font


PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN_H = 0.75 * inch
MARGIN_V = 0.375 * inch
FONT_SIZE_NAME = 24
FONT_SIZE_SECTION = 14
FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 9


class ResumeGenerator:
    """Generates PDF resumes from validated Resume models."""

    def __init__(
        self,
        font_name: str = "Helvetica",
        download_fonts: bool = False,
        verbose: bool = False,
    ):
        self.verbose = verbose
        self.font_family = self._setup_font(font_name, download_fonts)
        self.styles = self._create_styles()

    def _setup_font(self, font_name: str, download: bool) -> str:
        """Register font and return the family name for reportlab."""
        if font_name.lower() in ("helvetica", "times", "courier"):
            return font_name

        try:
            return register_font(font_name, download=download)
        except Exception:
            if self.verbose:
                from maker.shared import echo, Color

                echo(f"Font '{font_name}' not available, using Helvetica", Color.WARNING)
            return "Helvetica"

    def _create_styles(self) -> dict[str, ParagraphStyle]:
        """Create paragraph styles for different resume elements."""
        base = getSampleStyleSheet()

        return {
            "name": ParagraphStyle(
                "Name",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_NAME,
                leading=FONT_SIZE_NAME * 1.2,
                alignment=TA_CENTER,
                spaceAfter=4,
            ),
            "label": ParagraphStyle(
                "Label",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_BODY + 2,
                leading=(FONT_SIZE_BODY + 2) * 1.2,
                alignment=TA_CENTER,
                spaceAfter=8,
            ),
            "contact": ParagraphStyle(
                "Contact",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_SMALL,
                leading=FONT_SIZE_SMALL * 1.4,
                alignment=TA_CENTER,
                spaceAfter=12,
            ),
            "section_header": ParagraphStyle(
                "SectionHeader",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_SECTION,
                leading=FONT_SIZE_SECTION * 1.2,
                spaceBefore=12,
                spaceAfter=6,
                borderWidth=0,
                borderPadding=0,
            ),
            "entry_title": ParagraphStyle(
                "EntryTitle",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_BODY + 1,
                leading=(FONT_SIZE_BODY + 1) * 1.2,
                spaceBefore=6,
                spaceAfter=2,
            ),
            "entry_subtitle": ParagraphStyle(
                "EntrySubtitle",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_SMALL,
                leading=FONT_SIZE_SMALL * 1.2,
                textColor="gray",
                spaceAfter=4,
            ),
            "body": ParagraphStyle(
                "Body",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_BODY,
                leading=FONT_SIZE_BODY * 1.4,
                alignment=TA_LEFT,
                spaceAfter=4,
            ),
            "bullet": ParagraphStyle(
                "Bullet",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_BODY,
                leading=FONT_SIZE_BODY * 1.3,
                leftIndent=6,
                spaceAfter=1,
            ),
            "skills_row": ParagraphStyle(
                "SkillsRow",
                parent=base["Normal"],
                fontName=self.font_family,
                fontSize=FONT_SIZE_BODY,
                leading=FONT_SIZE_BODY * 1.4,
                spaceAfter=4,
            ),
        }

    def generate(self, resume: Resume, output_path: Path) -> None:
        """Generate PDF from resume model."""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            leftMargin=MARGIN_H,
            rightMargin=MARGIN_H,
            topMargin=MARGIN_V,
            bottomMargin=MARGIN_V,
        )

        story = []

        self._add_basics(story, resume.basics)

        if resume.work:
            self._add_work(story, resume.work)

        if resume.education:
            self._add_education(story, resume.education)

        if resume.skills:
            self._add_skills(story, resume.skills)

        if resume.projects:
            self._add_projects(story, resume.projects)

        doc.build(story)

    def _build_contact_parts(self, basics) -> list[str]:
        """Build contact information parts from basics."""
        parts = []
        if basics.email:
            parts.append(str(basics.email))
        if basics.phone:
            parts.append(basics.phone)
        if basics.url:
            parts.append(str(basics.url))
        if basics.location:
            loc = basics.location
            loc_parts = [p for p in [loc.city, loc.region, loc.countryCode] if p]
            if loc_parts:
                parts.append(", ".join(loc_parts))
        return parts

    def _add_basics(self, story: list, basics) -> None:
        """Add header section with name, title, and contact info."""
        story.append(Paragraph(basics.name, self.styles["name"]))

        if basics.label:
            story.append(Paragraph(basics.label, self.styles["label"]))

        contact_parts = self._build_contact_parts(basics)
        if contact_parts:
            story.append(Paragraph(" | ".join(contact_parts), self.styles["contact"]))

        if basics.summary:
            story.append(Spacer(1, 8))
            story.append(Paragraph(basics.summary, self.styles["body"]))

    def _add_work(self, story: list, work_entries: list) -> None:
        """Add work experience section."""
        story.append(Paragraph("Experience", self.styles["section_header"]))

        for entry in work_entries:
            if not entry.name and not entry.position:
                continue

            title = f"<b>{entry.position}</b>" if entry.position else ""
            if entry.name:
                title += f" at {entry.name}" if title else f"<b>{entry.name}</b>"

            story.append(Paragraph(title, self.styles["entry_title"]))

            date_str = self._format_date_range(entry.startDate, entry.endDate)
            if date_str:
                story.append(Paragraph(date_str, self.styles["entry_subtitle"]))

            if entry.summary:
                story.append(Paragraph(entry.summary, self.styles["body"]))

            if entry.highlights:
                self._add_bullet_list(story, entry.highlights)

    def _add_education(self, story: list, education_entries: list) -> None:
        """Add education section."""
        story.append(Paragraph("Education", self.styles["section_header"]))

        for entry in education_entries:
            if not entry.institution:
                continue

            title_parts = []
            if entry.studyType:
                title_parts.append(entry.studyType)
            if entry.area:
                title_parts.append(entry.area)

            title = f"<b>{', '.join(title_parts)}</b>" if title_parts else ""
            if entry.institution:
                title += f" - {entry.institution}" if title else entry.institution

            story.append(Paragraph(title, self.styles["entry_title"]))

            subtitle_parts = []
            date_str = self._format_date_range(entry.startDate, entry.endDate)
            if date_str:
                subtitle_parts.append(date_str)
            if entry.score:
                subtitle_parts.append(f"Score: {entry.score}")

            if subtitle_parts:
                story.append(Paragraph(" | ".join(subtitle_parts), self.styles["entry_subtitle"]))

    def _add_skills(self, story: list, skills: list) -> None:
        """Add skills section."""
        story.append(Paragraph("Skills", self.styles["section_header"]))

        for skill in skills:
            if not skill.name:
                continue

            keywords_str = ", ".join(skill.keywords) if skill.keywords else ""
            text = f"<b>{skill.name}:</b> {keywords_str}" if keywords_str else skill.name

            story.append(Paragraph(text, self.styles["skills_row"]))

    def _add_projects(self, story: list, projects: list) -> None:
        """Add projects section."""
        story.append(Paragraph("Projects", self.styles["section_header"]))

        for project in projects:
            if not project.name:
                continue

            title = f"<b>{project.name}</b>"
            if project.url:
                title += f' (<a href="{project.url}">{project.url}</a>)'

            story.append(Paragraph(title, self.styles["entry_title"]))

            if project.description:
                story.append(Paragraph(project.description, self.styles["body"]))

            date_str = self._format_date_range(project.startDate, project.endDate)
            if date_str:
                story.append(Paragraph(date_str, self.styles["entry_subtitle"]))

            if project.highlights:
                self._add_bullet_list(story, project.highlights)

    def _add_bullet_list(self, story: list, items: list[str]) -> None:
        """Add a bulleted list to the story."""
        list_items = [ListItem(Paragraph(item, self.styles["bullet"])) for item in items]
        story.append(
            ListFlowable(
                list_items,
                bulletType="bullet",
                start="circle",
                leftIndent=6,
                bulletFontSize=6,
                bulletOffsetY=-2,
            )
        )

    def _format_date_range(self, start: str | None, end: str | None) -> str:
        """Format date range for display."""
        if not start and not end:
            return ""

        start_str = self._format_date(start) if start else ""
        end_str = self._format_date(end) if end else "Present"

        if start_str and end_str:
            return f"{start_str} - {end_str}"
        return start_str or end_str

    def _format_date(self, date_str: str) -> str:
        """Format ISO 8601 date for display."""
        if not date_str:
            return ""

        parts = date_str.split("-")
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            months = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            try:
                month_idx = int(parts[1]) - 1
                if 0 <= month_idx < 12:
                    return f"{months[month_idx]} {parts[0]}"
            except ValueError:
                pass
            return date_str
        else:
            return date_str
