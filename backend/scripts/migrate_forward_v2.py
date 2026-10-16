"""
Idempotent Database Migration for Forward Validation Protocol v2.1
Applies schema updates to database/tradematrix.db safely.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path("database/tradematrix.db")

def migrate():
    print(f"Connecting to database at {DB_PATH.resolve()}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Update paper_trades columns safely
    cursor.execute("PRAGMA table_info(paper_trades)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    print(f"Existing paper_trades columns: {len(existing_cols)}")

    new_cols = [
        ("batch_id", "VARCHAR(50)"),
        ("experiment_arm", "VARCHAR(30) DEFAULT 'TOOL_TOP10'"),
        ("regime_tag", "VARCHAR(30) DEFAULT 'DEFENSIVE'"),
        ("nifty_entry_price", "FLOAT"),
        ("nifty_exit_price", "FLOAT"),
        ("friction_cost", "FLOAT DEFAULT 0.00385"),
    ]

    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}' to paper_trades...")
            cursor.execute(f"ALTER TABLE paper_trades ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column '{col_name}' already exists in paper_trades.")

    # 2. Tag legacy trades as LEGACY_PRE_V2
    cursor.execute("UPDATE paper_trades SET experiment_arm = 'LEGACY_PRE_V2' WHERE batch_id IS NULL AND (experiment_arm IS NULL OR experiment_arm != 'LEGACY_PRE_V2')")
    affected = cursor.rowcount
    if affected > 0:
        print(f"Tagged {affected} existing paper trades as 'LEGACY_PRE_V2'.")

    # 3. Create forward_batches table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forward_batches (
        batch_id VARCHAR(50) PRIMARY KEY,
        created_at VARCHAR(30) NOT NULL,
        cohort_type VARCHAR(20) NOT NULL,
        status VARCHAR(20) DEFAULT 'ACTIVE',
        regime VARCHAR(20) NOT NULL,
        nifty_base_price FLOAT NOT NULL,
        scoring_git_hash VARCHAR(50) NOT NULL,
        scoring_formula_version VARCHAR(50) NOT NULL,
        random_seed INT NOT NULL,
        eligible_universe_count INT NOT NULL,
        tool_stock_count INT DEFAULT 10,
        control_basket_count INT DEFAULT 1000,
        slot_capital_inr FLOAT DEFAULT 25000.0,
        total_allocated_inr FLOAT DEFAULT 250000.0,
        tool_avg_return_pct FLOAT DEFAULT 0.0,
        control_mean_return_pct FLOAT DEFAULT 0.0,
        delta_excess_return_pct FLOAT DEFAULT 0.0,
        nifty_return_pct FLOAT DEFAULT 0.0,
        spearman_rho FLOAT DEFAULT 0.0,
        monte_carlo_percentile FLOAT DEFAULT 0.0,
        completed_at VARCHAR(30)
    )
    """)
    print("Table 'forward_batches' verified.")

    # 4. Create universe_score_snapshots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS universe_score_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id VARCHAR(50) NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        company_name VARCHAR(200),
        sector VARCHAR(100),
        composite_score FLOAT NOT NULL,
        is_top10 BOOLEAN DEFAULT 0,
        entry_price FLOAT NOT NULL,
        day90_price FLOAT,
        day90_return_pct FLOAT,
        day90_net_return_pct FLOAT,
        notes TEXT,
        FOREIGN KEY(batch_id) REFERENCES forward_batches(batch_id)
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_snapshot_batch_symbol ON universe_score_snapshots(batch_id, symbol)")
    print("Table 'universe_score_snapshots' verified.")

    conn.commit()
    conn.close()
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
