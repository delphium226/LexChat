import logging
from typing import AsyncGenerator

from passlib.hash import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import AppSetting, Base, User

logger = logging.getLogger("app")

# Use asyncpg driver
DB_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_size=settings.db_max_connections,
    max_overflow=5,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    """Create tables and seed default admin user."""
    logger.info("[Database] Initialising...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Migrate existing tables — add columns that may not exist yet
        # matters/matter_notes tables must be created before matter_id FK is added to chats.
        # For fresh installs, create_all handles table creation in dependency order.
        # For existing databases, we create the new tables explicitly first.
        migration_statements = [
            # New tables (safe to run on existing DBs via IF NOT EXISTS)
            """CREATE TABLE IF NOT EXISTS matters (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'open',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS matter_notes (
                id SERIAL PRIMARY KEY,
                matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            # Existing table column additions
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS matter_id INTEGER REFERENCES matters(id) ON DELETE SET NULL",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS model VARCHAR(255)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS cost_usd FLOAT",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS total_cost_usd FLOAT NOT NULL DEFAULT 0.0",
            # Algorithmic-efficiency metrics (Manager→Worker loop behaviour)
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS manager_delegations INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS peer_consults INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS worker_tool_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS react_turns_max INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS max_turns_halted INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS phase1_search_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS phase2_retrieval_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS distinct_legislation_ids_seen INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS distinct_legislation_ids_retrieved INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS redundant_tool_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS summarisation_calls INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS summarisation_chars_in INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS summarisation_chars_out INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS summarisation_chunks INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS truncation_events INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS sources_extracted INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS sources_kept INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS source_filter_fallback INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS search_budget_blocked INTEGER NOT NULL DEFAULT 0",
            # Token-cost caching (D5, additive): memo hits + provider prompt-cache stats
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS memo_hits INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS cached_prompt_tokens INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS cache_discount_usd FLOAT NOT NULL DEFAULT 0.0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS research_mode VARCHAR(50)",
            # Deep Research (additive): per-request chat mode + approved-plan audit column
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS chat_mode VARCHAR(50)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS research_plan JSONB",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS research_mode VARCHAR(50) NOT NULL DEFAULT 'legislation_only'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_mode VARCHAR(50) NOT NULL DEFAULT 'research'",
            "ALTER TABLE matters ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(100)",
            "ALTER TABLE matters ADD COLUMN IF NOT EXISTS legislation_type VARCHAR(100)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources JSONB",
            """CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                content_text TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE product_feedback ALTER COLUMN message DROP NOT NULL",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS time_saved_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS time_without_aila_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS research_success VARCHAR(50)",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS confidence INTEGER",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS verification_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS usability INTEGER",
            """CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(20) NOT NULL,
                username VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS peer_bots (
                id SERIAL PRIMARY KEY,
                peer_id VARCHAR(64) NOT NULL UNIQUE,
                name VARCHAR(128) NOT NULL,
                base_url VARCHAR(256) NOT NULL,
                api_key VARCHAR(256),
                description TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE peer_bots ADD COLUMN IF NOT EXISTS name VARCHAR(128) NOT NULL DEFAULT ''",
            # lexchat_parliament DB was created when this column was called is_enabled.
            # Rename it to match the model; no-op if enabled already exists.
            """DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='peer_bots' AND column_name='is_enabled'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='peer_bots' AND column_name='enabled'
                ) THEN
                    ALTER TABLE peer_bots RENAME COLUMN is_enabled TO enabled;
                END IF;
            END $$""",
            # lexchat_parliament DB was built from a more evolved schema and has extra
            # NOT NULL columns (display_name, timeout_s, ...) not in the current model.
            # Drop NOT NULL from every column that isn't one of the core required fields
            # so INSERTs that omit them don't fail. Safe on all DBs — the loop is a no-op
            # for any columns that don't exist.
            """DO $$
            DECLARE col TEXT;
            BEGIN
                FOR col IN
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'peer_bots'
                      AND is_nullable = 'NO'
                      AND column_name NOT IN ('id','peer_id','name','base_url','description','enabled','created_at')
                LOOP
                    EXECUTE format('ALTER TABLE peer_bots ALTER COLUMN %I DROP NOT NULL', col);
                END LOOP;
            END $$""",
            """CREATE TABLE IF NOT EXISTS sp_committee_items (
                id SERIAL PRIMARY KEY,
                meeting_id VARCHAR(32) NOT NULL,
                slug VARCHAR(128) NOT NULL,
                iob_id VARCHAR(32) NOT NULL,
                committee_code VARCHAR(64),
                committee_name VARCHAR(256),
                meeting_date DATE,
                agenda_item_title VARCHAR(512),
                url VARCHAR(512) UNIQUE,
                speeches JSONB,
                full_text TEXT,
                fetched_at TIMESTAMP,
                CONSTRAINT uq_sp_meeting_iob UNIQUE (meeting_id, iob_id)
            )""",
            """CREATE TABLE IF NOT EXISTS sp_plenary_items (
                id SERIAL PRIMARY KEY,
                meeting_id VARCHAR(32) NOT NULL,
                slug VARCHAR(128) NOT NULL,
                iob_id VARCHAR(32) NOT NULL,
                committee_code VARCHAR(64),
                committee_name VARCHAR(256),
                meeting_date DATE,
                agenda_item_title VARCHAR(512),
                url VARCHAR(512) UNIQUE,
                speeches JSONB,
                full_text TEXT,
                fetched_at TIMESTAMP,
                CONSTRAINT uq_sp_plenary_meeting_iob UNIQUE (meeting_id, iob_id)
            )""",
            """CREATE TABLE IF NOT EXISTS sp_video_captions (
                id SERIAL PRIMARY KEY,
                meeting_id VARCHAR(32) NOT NULL,
                event_id VARCHAR(64) NOT NULL UNIQUE,
                slug TEXT,
                meeting_date DATE,
                start_time_utc TIMESTAMP,
                is_youtube BOOLEAN NOT NULL DEFAULT FALSE,
                youtube_url VARCHAR(512),
                transcript TEXT,
                offset_index JSONB,
                caption_ok BOOLEAN NOT NULL DEFAULT FALSE,
                fetched_at TIMESTAMP
            )""",
            # Local prompt cache (D7, additive): cross-user summary cache + per-request hit metrics
            """CREATE TABLE IF NOT EXISTS local_prompt_cache (
                id SERIAL PRIMARY KEY,
                content_hash VARCHAR(64) NOT NULL,
                query_hash VARCHAR(64) NOT NULL,
                query_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                summarise_model VARCHAR(255),
                doc_name VARCHAR(512),
                chars_in INTEGER,
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_hit_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_local_prompt_cache_key UNIQUE (content_hash, query_hash)
            )""",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS local_cache_hits INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS local_cache_chars_saved INTEGER NOT NULL DEFAULT 0",
            # Committee SP TV slugs can exceed 128 chars (they embed the full debate
            # title), so widen slug from the original VARCHAR(128) to TEXT on existing
            # DBs. Guarded so it only runs while the column is still varchar.
            """DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='sp_video_captions' AND column_name='slug'
                      AND data_type='character varying'
                ) THEN
                    ALTER TABLE sp_video_captions ALTER COLUMN slug TYPE TEXT;
                END IF;
            END $$""",
        ]
        async with engine.begin() as conn:
            for stmt in migration_statements:
                await conn.execute(text(stmt))
        logger.info("[Database] Column migrations applied.")

        # Apply indexes to existing tables (create_all only indexes new tables)
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_chats_user_created ON chats (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chats_matter ON chats (matter_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages (chat_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_rated ON messages (chat_id, created_at) WHERE rating IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON messages USING GIN (to_tsvector('english', content))",
            "CREATE INDEX IF NOT EXISTS idx_health_service_checked ON service_health_logs (service_name, checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_request_timings_created_at ON request_timings (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_matters_user_created ON matters (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_matter_notes_matter ON matter_notes (matter_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_documents_chat ON documents (chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_sp_items_meeting_id ON sp_committee_items (meeting_id)",
            "CREATE INDEX IF NOT EXISTS idx_sp_items_committee_code ON sp_committee_items (committee_code)",
            "CREATE INDEX IF NOT EXISTS idx_sp_items_committee_name ON sp_committee_items (committee_name)",
            "CREATE INDEX IF NOT EXISTS idx_sp_items_meeting_date ON sp_committee_items (meeting_date)",
            "CREATE INDEX IF NOT EXISTS idx_sp_items_full_text ON sp_committee_items USING GIN (to_tsvector('english', coalesce(full_text,'')))",
            "CREATE INDEX IF NOT EXISTS idx_sp_plenary_meeting_id ON sp_plenary_items (meeting_id)",
            "CREATE INDEX IF NOT EXISTS idx_sp_plenary_committee_code ON sp_plenary_items (committee_code)",
            "CREATE INDEX IF NOT EXISTS idx_sp_plenary_committee_name ON sp_plenary_items (committee_name)",
            "CREATE INDEX IF NOT EXISTS idx_sp_plenary_meeting_date ON sp_plenary_items (meeting_date)",
            "CREATE INDEX IF NOT EXISTS idx_sp_plenary_full_text ON sp_plenary_items USING GIN (to_tsvector('english', coalesce(full_text,'')))",
            "CREATE INDEX IF NOT EXISTS idx_sp_video_captions_meeting_id ON sp_video_captions (meeting_id)",
            "CREATE INDEX IF NOT EXISTS idx_sp_video_captions_meeting_date ON sp_video_captions (meeting_date)",
            "CREATE INDEX IF NOT EXISTS ix_local_prompt_cache_content_hash ON local_prompt_cache (content_hash)",
        ]
        async with engine.begin() as conn:
            for stmt in index_statements:
                await conn.execute(text(stmt))
        logger.info("[Database] Indexes applied.")

        # Seed default admin user
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin = result.scalar_one_or_none()

            if admin is None:
                hashed = bcrypt.using(rounds=10).hash("admin")
                admin_user = User(
                    username="admin",
                    password_hash=hashed,
                    role="admin",
                )
                session.add(admin_user)
                await session.commit()
                logger.info("[Database] Default admin user created.")
            else:
                logger.info("[Database] Admin user already exists.")

        # Seed default active_provider setting
        async with async_session_maker() as session:
            result = await session.execute(
                select(AppSetting).where(AppSetting.key == "active_provider")
            )
            if result.scalar_one_or_none() is None:
                session.add(AppSetting(key="active_provider", value="ollama"))
                await session.commit()
                logger.info("[Database] Default active_provider seeded.")

        logger.info("[Database] Initialised successfully.")
    except Exception as e:
        logger.error(f"[Database] Initialisation failed: {e}. The server will start, but database-dependent features will fail.")
