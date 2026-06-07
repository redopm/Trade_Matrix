"""
Database Migration for Phase 4: Fibonacci Retracement
This script adds the new Fibonacci columns to the screener_signals table
without dropping the existing data.
"""
import asyncio
from sqlalchemy import text
from app.database import engine
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def migrate():
    logger.info("Starting Fibonacci Phase 4 migration...")
    
    async with engine.begin() as conn:
        # SQLite uses ALTER TABLE ... ADD COLUMN ...
        # Add Fibonacci fields to screener_signals
        columns = [
            "fib_swing_high FLOAT",
            "fib_swing_low FLOAT",
            "fib_level_0 FLOAT",
            "fib_level_236 FLOAT",
            "fib_level_382 FLOAT",
            "fib_level_500 FLOAT",
            "fib_level_618 FLOAT",
            "fib_level_786 FLOAT",
            "fib_level_100 FLOAT",
            "fib_nearest_level VARCHAR(10)",
            "fib_nearest_price FLOAT",
            "fib_confluence BOOLEAN",
            "fib_confluence_score FLOAT"
        ]
        
        for col in columns:
            col_name = col.split()[0]
            try:
                await conn.execute(text(f"ALTER TABLE screener_signals ADD COLUMN {col}"))
                logger.info(f"Added column {col_name}")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    logger.info(f"Column {col_name} already exists. Skipping.")
                else:
                    logger.warning(f"Failed to add column {col_name}: {e}")

    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
