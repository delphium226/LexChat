from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    research_mode: Mapped[str] = mapped_column(String(50), default="legislation_only")
    chat_mode: Mapped[str] = mapped_column(String(50), default="research")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chats: Mapped[list["Chat"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    matters: Mapped[list["Matter"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    matter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("matters.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="chats")
    matter: Mapped["Matter | None"] = relationship(back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_chats_user_created', 'user_id', 'created_at'),
        Index('idx_chats_created_at', 'created_at'),
        Index('idx_chats_matter', 'matter_id'),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chat: Mapped["Chat"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="valid_rating"),
        Index('idx_messages_chat_created', 'chat_id', 'created_at'),
        Index('idx_messages_created_at', 'created_at'),
        Index('idx_messages_rated', 'chat_id', 'created_at', postgresql_where=text("rating IS NOT NULL")),
        Index('idx_messages_content_fts', text("to_tsvector('english', content)"), postgresql_using='gin'),
    )

class RequestTiming(Base):
    __tablename__ = "request_timings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    queue_wait_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    learning_db_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_ttft_first_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lex_api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lex_api_total_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # --- Algorithmic-efficiency metrics (Manager→Worker loop behaviour) ---
    manager_delegations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peer_consults: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    react_turns_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_turns_halted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase1_search_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase2_retrieval_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_legislation_ids_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_legislation_ids_retrieved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redundant_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summarisation_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summarisation_chars_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summarisation_chars_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summarisation_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncation_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_extracted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_kept: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_filter_fallback: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Parliamentary search-budget wall hits (model looped on discovery search).
    search_budget_blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Effective per-request research mode (future-proofs per-mode filtering).
    research_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_request_timings_created_at', 'created_at'),
    )


class ProductFeedback(Base):
    __tablename__ = "product_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_saved_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_without_aila_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    research_success: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class ServiceHealthStatus(Base):
    __tablename__ = "service_health_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_health_service_checked', 'service_name', 'checked_at'),
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_activity_log_created_at', 'created_at'),
    )


class Matter(Base):
    __tablename__ = "matters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legislation_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="matters")
    chats: Mapped[list["Chat"]] = relationship(back_populates="matter")
    notes: Mapped[list["MatterNote"]] = relationship(
        back_populates="matter", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_matters_user_created', 'user_id', 'created_at'),
    )


class MatterNote(Base):
    __tablename__ = "matter_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matters.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    matter: Mapped["Matter"] = relationship(back_populates="notes")

    __table_args__ = (
        Index('idx_matter_notes_matter', 'matter_id', 'created_at'),
    )


class PeerBot(Base):
    __tablename__ = "peer_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    peer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpCommitteeItem(Base):
    __tablename__ = "sp_committee_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    iob_id: Mapped[str] = mapped_column(String(32), nullable=False)
    committee_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    committee_name: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    meeting_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    agenda_item_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    speeches: Mapped[list | None] = mapped_column(JSON, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("meeting_id", "iob_id", name="uq_sp_meeting_iob"),
    )


class SpPlenaryItem(Base):
    __tablename__ = "sp_plenary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    iob_id: Mapped[str] = mapped_column(String(32), nullable=False)
    committee_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    committee_name: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    meeting_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    agenda_item_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    speeches: Mapped[list | None] = mapped_column(JSON, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("meeting_id", "iob_id", name="uq_sp_plenary_meeting_iob"),
    )


class SpVideoCaption(Base):
    """One row per Scottish Parliament TV event (i.e. per plenary meeting).

    Stores the cached caption transcript + a char-offset → wall-clock index so a
    plenary citation can be enriched with a `?clip_start=…` video deep link.
    Keyed to plenary meetings by `meeting_id` (the Official Report `?meeting=` id).
    See docs/parliament/VIDEO_DEEPLINK_PLAN.md §4.
    """
    __tablename__ = "sp_video_captions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Committee SP TV slugs embed the full debate title and can exceed 128 chars
    # (e.g. "standards-...-committee-debate-shaping-parliamentary-...-2021"), so this
    # is unbounded Text. It builds the deep-link URL and must not be truncated.
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    start_time_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_youtube: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [[char_offset, wall_clock_ms], …] — monotonic, for offset→time lookup
    offset_index: Mapped[list | None] = mapped_column(JSON, nullable=True)
    caption_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_documents_chat', 'chat_id'),
    )
