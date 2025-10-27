"""Database setup and models using SQLAlchemy with SQLite."""

from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
import enum

DATABASE_URL = "sqlite+aiosqlite:///./reelcraft.db"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


class JobStatus(enum.Enum):
    """Job status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Background job model."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)  # UUID
    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    progress = Column(Integer, default=0)  # 0-100
    progress_message = Column(String, default="")
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationship to video
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    video = relationship("Video", back_populates="job")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "video_id": self.video_id,
        }


class Video(Base):
    """Video model."""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    source_url = Column(Text, nullable=False)
    file_path = Column(String, nullable=True)  # Relative path from project root

    duration = Column(Float, nullable=True)  # Duration in seconds
    size_mb = Column(Float, nullable=True)  # File size in MB

    script_json = Column(Text, nullable=True)  # JSON string of the script

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship to job
    job = relationship("Job", back_populates="video", uselist=False)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "file_path": self.file_path,
            "duration": self.duration,
            "size_mb": self.size_mb,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session
