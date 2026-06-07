import sqlite3

db_path = r'C:\Users\Omprakash Maury\Documents\project\Trade_matrix\database\tradematrix.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(screener_signals)")
cols = [row[1] for row in cur.fetchall()]
print('Existing columns:', cols)

needed = {
    'direction': 'VARCHAR(10) DEFAULT "LONG"',
    'market_regime': 'VARCHAR(20) DEFAULT "BULLISH"',
    'regime_confidence': 'FLOAT'
}

for col, typedef in needed.items():
    if col not in cols:
        print(f'Adding column: {col}')
        cur.execute(f'ALTER TABLE screener_signals ADD COLUMN {col} {typedef}')
    else:
        print(f'Column already exists: {col}')

conn.commit()
conn.close()
print('Migration done!')
