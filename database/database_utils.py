# +++ new_file: database_utils.py
from contextlib import contextmanager
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)


@contextmanager
def db_session_scope():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {e}")
        raise
    finally:
        db.close()
