"""Database models and operations for user profiles."""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from logger import db_logger, error_logger

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gradient_mcp.db")

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Profile(Base):
    """User profile with Twitter data."""
    __tablename__ = "profiles"

    stytch_user_id = Column(String, primary_key=True, index=True)
    twitter_id = Column(String, nullable=True, index=True)
    twitter_handle = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Profile(stytch_user_id={self.stytch_user_id}, twitter_handle=@{self.twitter_handle})>"


def init_db():
    """Initialize database tables."""
    try:
        db_logger.info("🗄️ Initializing database")
        db_logger.info(f"Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL.split('://')[0]}")
        Base.metadata.create_all(bind=engine)
        db_logger.info("✅ Database tables created/verified")
    except Exception as e:
        db_logger.error(f"❌ Database initialization failed: {str(e)}")
        error_logger.exception("Database init error", exc_info=e)
        raise


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db_logger.error(f"❌ Failed to create database session: {str(e)}")
        error_logger.exception("Database session error", exc_info=e)
        raise


def get_or_create_profile(db: Session, twitter_profile: dict) -> Optional[Profile]:
    """
    Get existing profile or create new one from Twitter data.

    Args:
        db: Database session
        twitter_profile: Dict with keys: stytch_user_id, twitter_id, twitter_handle, display_name, avatar_url

    Returns:
        Profile: User profile object
    """
    stytch_user_id = twitter_profile.get('stytch_user_id')

    if not stytch_user_id:
        db_logger.error("❌ No stytch_user_id provided")
        return None

    db_logger.info(f"🗄️ Fetching profile for user: {stytch_user_id}")

    try:
        # Try to find existing profile
        profile = db.query(Profile).filter_by(stytch_user_id=stytch_user_id).first()

        if profile:
            db_logger.info(f"✅ Existing profile found: @{profile.twitter_handle}")

            # Update if Twitter data changed
            needs_update = False
            if profile.twitter_handle != twitter_profile.get('twitter_handle'):
                db_logger.info(f"📝 Updating Twitter handle: {profile.twitter_handle} → {twitter_profile.get('twitter_handle')}")
                profile.twitter_handle = twitter_profile.get('twitter_handle')
                needs_update = True

            if profile.display_name != twitter_profile.get('display_name'):
                db_logger.info(f"📝 Updating display name: {profile.display_name} → {twitter_profile.get('display_name')}")
                profile.display_name = twitter_profile.get('display_name')
                needs_update = True

            if profile.avatar_url != twitter_profile.get('avatar_url'):
                db_logger.info(f"📝 Updating avatar URL")
                profile.avatar_url = twitter_profile.get('avatar_url')
                needs_update = True

            if needs_update:
                profile.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(profile)
                db_logger.info("✅ Profile updated")

        else:
            db_logger.info(f"➕ Creating new profile for @{twitter_profile.get('twitter_handle')}")
            profile = Profile(
                stytch_user_id=stytch_user_id,
                twitter_id=twitter_profile.get('twitter_id'),
                twitter_handle=twitter_profile.get('twitter_handle'),
                display_name=twitter_profile.get('display_name'),
                avatar_url=twitter_profile.get('avatar_url')
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            db_logger.info(f"✅ Profile created: {profile.stytch_user_id}")

        return profile

    except Exception as e:
        db_logger.error(f"❌ Database operation failed: {str(e)}")
        error_logger.exception("Profile get/create error", exc_info=e)
        db.rollback()
        return None


def get_profile_by_user_id(db: Session, stytch_user_id: str) -> Optional[Profile]:
    """Get profile by Stytch user ID."""
    try:
        db_logger.debug(f"Fetching profile: {stytch_user_id}")
        return db.query(Profile).filter_by(stytch_user_id=stytch_user_id).first()
    except Exception as e:
        db_logger.error(f"❌ Error fetching profile: {str(e)}")
        error_logger.exception("Profile fetch error", exc_info=e)
        return None


__all__ = ['Profile', 'init_db', 'get_db', 'get_or_create_profile', 'get_profile_by_user_id']