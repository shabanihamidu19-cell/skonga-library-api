"""
SKONGA Library API — Database Models
=======================================
SQLAlchemy ORM models. These must always stay in sync with the Alembic
migration files in app/db/migrations/. Never alter the production
database schema by hand — always go through Alembic.
"""
from datetime import date
from typing import Optional

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True)         # e.g. "biology"
    name_en = Column(String, nullable=False)
    name_sw = Column(String, nullable=False)
    icon = Column(String, nullable=True)
    schema_version = Column(Integer, nullable=False, default=1)
    last_updated = Column(Date, nullable=False)

    # relationships
    subject_forms = relationship("SubjectForm", back_populates="subject")
    topics = relationship("Topic", back_populates="subject")

    def __repr__(self) -> str:
        return f"<Subject id={self.id} name_en={self.name_en}>"


class Form(Base):
    __tablename__ = "forms"
    __table_args__ = (
        CheckConstraint("id BETWEEN 1 AND 6", name="forms_id_range"),
    )

    id = Column(SmallInteger, primary_key=True)   # 1–6

    subject_forms = relationship("SubjectForm", back_populates="form")
    topics = relationship("Topic", back_populates="form")


class SubjectForm(Base):
    """Many-to-many: which forms each subject is taught in."""
    __tablename__ = "subject_forms"

    subject_id = Column(String, ForeignKey("subjects.id"), primary_key=True)
    form_id = Column(SmallInteger, ForeignKey("forms.id"), primary_key=True)

    subject = relationship("Subject", back_populates="subject_forms")
    form = relationship("Form", back_populates="subject_forms")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('foundational', 'intermediate', 'advanced')",
            name="topics_difficulty_values",
        ),
        CheckConstraint(
            "status IN ('skeleton', 'draft', 'reviewed', 'published')",
            name="topics_status_values",
        ),
        Index("idx_topics_subject_form", "subject_id", "form_id"),
    )

    id = Column(String, primary_key=True)         # e.g. "bio-f1-t04-photosynthesis"
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    form_id = Column(SmallInteger, ForeignKey("forms.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    title_en = Column(Text, nullable=False)
    title_sw = Column(Text, nullable=False)
    competency_mkuu = Column(Text, nullable=True)
    tags = Column(ARRAY(String), nullable=True, default=list)
    related_topics = Column(ARRAY(String), nullable=True, default=list)
    difficulty = Column(String, nullable=True)
    status = Column(String, nullable=False, default="skeleton")
    content_version = Column(Integer, nullable=False, default=1)
    last_updated = Column(Date, nullable=False)

    # Phase 2: content text stored on Topic itself for Phase 1 full-text
    content_md = Column(Text, nullable=True)

    subject = relationship("Subject", back_populates="topics")
    form = relationship("Form", back_populates="topics")

    def __repr__(self) -> str:
        return f"<Topic id={self.id}>"
