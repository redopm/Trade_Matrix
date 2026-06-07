import pandas as pd
import datetime

df = pd.read_csv('https://public.fyers.in/sym_details/NSE_FO.csv', header=None)
opts = df[(df[13]=='NIFTY') & df[16].isin(['CE','PE'])]
opts_sorted = opts.sort_values(by=8)
future = opts_sorted[opts_sorted[8] >= datetime.datetime.now().timestamp()]
print('Total NIFTY opts:', len(opts), 'Future:', len(future))
if not future.empty:
    exp = future.iloc[0][8]
    chain = future[future[8]==exp]
    print('Nearest exp epoch:', exp, 'Chain size:', len(chain))
    print('Sample:')
    print(chain[9].head(5).tolist())
    
    # test filter
    atm = 23400
    filtered = []
    import re
    for sym in chain[9].tolist():
        match = re.search(r'(\d+)(CE|PE)$', sym)
        if match:
            strike = int(match.group(1))
            if abs(strike - atm)/atm <= 0.15:
                filtered.append(sym)
    print("Filtered around 23400:", len(filtered))
