import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from models import Base, Tenant, TenantAuth, Message

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Ensure message table exists (Message model must be imported so it's in Base.metadata)
    Message.__table__.create(bind=engine, checkfirst=True)
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'message'"))
        if r.fetchone():
            logger.info("Message table exists")
        else:
            logger.warning("Message table missing after create_all; creating explicitly")
            Message.__table__.create(bind=engine, checkfirst=True)
    # Add missing columns and migrations (for existing databases)
    try:
        with engine.connect() as conn:
            # Check if last_error column exists
            result = conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='tenant_auth' AND column_name='last_error'
                """)
            )
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE tenant_auth ADD COLUMN last_error TEXT"))
                conn.commit()
            
            # Check if phone_code_hash column exists
            result = conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='tenant_auth' AND column_name='phone_code_hash'
                """)
            )
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE tenant_auth ADD COLUMN phone_code_hash VARCHAR(128)"))
                conn.commit()
            for col, spec in [
                ("code_requested_at", "TIMESTAMP WITH TIME ZONE"),
                ("code_timeout_seconds", "INTEGER"),
            ]:
                r = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name='tenant_auth' AND column_name=:c"
                    ),
                    {"c": col},
                )
                if r.fetchone() is None:
                    conn.execute(text(f"ALTER TABLE tenant_auth ADD COLUMN {col} {spec}"))
                    conn.commit()
            
            # Message table migrations
            # Check if message table exists
            result = conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name='message'
                """)
            )
            if result.fetchone() is not None:
                # Table exists, check for column migrations
                
                # Rename address to chat_id if address exists and chat_id doesn't
                result = conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='message' AND column_name='address'
                    """)
                )
                has_address = result.fetchone() is not None
                
                result = conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='message' AND column_name='chat_id'
                    """)
                )
                has_chat_id = result.fetchone() is not None
                
                if has_address and not has_chat_id:
                    conn.execute(text("ALTER TABLE message RENAME COLUMN address TO chat_id"))
                    conn.commit()
                
                # Add phone_number column if it doesn't exist
                result = conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='message' AND column_name='phone_number'
                    """)
                )
                if result.fetchone() is None:
                    conn.execute(text("ALTER TABLE message ADD COLUMN phone_number VARCHAR(32)"))
                    conn.commit()
                
                # Add username column if it doesn't exist
                result = conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='message' AND column_name='username'
                    """)
                )
                if result.fetchone() is None:
                    conn.execute(text("ALTER TABLE message ADD COLUMN username VARCHAR(255)"))
                    conn.commit()
                
                # Remove telegram_chat_id column if it exists (migrate to chat_id only)
                result = conn.execute(
                    text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='message' AND column_name='telegram_chat_id'
                    """)
                )
                if result.fetchone() is not None:
                    conn.execute(text("ALTER TABLE message DROP COLUMN telegram_chat_id"))
                    conn.commit()
    except Exception as e:
        logger.warning("Message/tenant_auth migration step failed (may be harmless): %s", e)


def get_session():
    with SessionLocal() as session:
        yield session
