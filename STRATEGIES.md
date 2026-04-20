### 2. The Trading Logic (``)

```markdown
# Trading Strategies & Logic Playbook

This document contains the plain-English rules for every algorithm running inside TradeMatrix. If the code deviates from these rules, the code is wrong.

---

## Strategy 1: The Alpha Screener (Phase 1)
**Objective:** Identify fundamentally strong companies that are currently experiencing a short-term technical pullback (Buy the dip in a strong asset).

### Parameters
* **Universe:** Nifty 500 (or Top 200 Liquid Stocks)
* **Timeframe:** Daily (End of Day Data)
* **Position Type:** Swing Trading / Short-to-Medium Term/Long term

### Filter Rules (Entry Conditions)
**A. Fundamental Filters:**
1. `ROCE > 15%` (Capital is being used efficiently).
2. `Debt-to-Equity < 1.0` (Low bankruptcy/leverage risk).

**B. Technical Filters:**
1. `Current Price > 200 DMA` (The long-term macro trend must be UP).
2. `RSI (14) < 30` (The stock is currently oversold or in a short-term correction).

### Paper Trading / Execution Logic
* **Entry:** Buy at the market open on the day *after* the signal is generated.
* **Stop Loss (SL):** 5% below the entry price (Strict cut-off).
* **Target / Exit:** - *Condition 1:* RSI (14) crosses above 70 (Overbought).
  - *Condition 2:* Fixed trailing target of 12% profit.

### **3** **1. Trend Indicators (Direction)**
Ye kyun use hote hain? Ye batate hain ki market ya stock ka overall rasta (trend) kahan hai—upar (bullish), neeche (bearish), ya side mein (sideways). Inko dekh kar pata chalta hai ki flow ke against trade toh nahi le rahe.

SMA (Simple Moving Average) / EMA (Exponential Moving Average): 50 aur 200 days ka average. Basic trend check karne ke liye.

MACD (Moving Average Convergence Divergence): Do moving averages ke beech ka gap. Trend change detect karne ke liye.

Supertrend: Chart par seedha Buy/Sell signal deta hai trend ke hisaab se.

ADX (Average Directional Index): Ye nahi batata ki trend up hai ya down, ye batata hai ki trend mein dum kitna hai. Agar ADX > 25 hai, toh trend strong hai.

### **2. Momentum Indicators / Oscillators (Speed & Reversals)**
Ye kyun use hote hain? Ye trend ki 'speed' batate hain. Agar gaadi (stock) bohot tez chal rahi hai, toh shayad over-heating (Overbought) ho gayi hai aur ab break lagega. Ye reversal pakadne (buy the dip) ke kaam aate hain.

RSI (Relative Strength Index): 0 se 100 ke beech ghoomta hai. < 30 matlab sasta (Oversold), > 70 matlab mehanga (Overbought).

Stochastic Oscillator: RSI jaisa hi hai, par thoda fast signal deta hai.

CCI (Commodity Channel Index): Naye trend ki shuruwat ya extreme conditions pakadne ke liye.

#### **3. Volatility Indicators (Risk & Stop-Loss)**
Ye kyun use hote hain? Ye batate hain ki stock din mein kitna utar-chadav karta hai. Algo-trading mein inka sabse bada use Stop-Loss (SL) aur Target set karne ke liye hota hai, taaki normal utar-chadav mein tumhara SL hit na ho jaye.

ATR (Average True Range): Ye batata hai ki stock average din mein kitne rupey ghoomta hai. Agar ATR 10 hai, toh kam se kam 10-15 point door SL lagana chahiye. (Pro traders ka secret tool).

Bollinger Bands: Price ke aas-paas ek rubber band bana deta hai. Jab price band ko todkar bahar nikalta hai, toh bada move aata hai.

#### **4. Volume Indicators (Confirmation)**
Ye kyun use hote hain? Price jhooth bol sakta hai, par Volume nahi. Agar price upar ja raha hai lekin volume nahi hai, toh wo "Fake Move" ya trap ho sakta hai. Ye batate hain ki kya bade players (Institutions) paisa daal rahe hain?

VWAP (Volume Weighted Average Price): Intraday trading ka king. Ye batata hai ki din bhar mein volume ke hisaab se average price kya raha.

OBV (On-Balance Volume): Total volume ko add/subtract karta hai price movement ke hisaab se. Agar price sideways hai par OBV upar ja raha hai, matlab chupke se buying ho rahi hai (Accumulation).

### **5. Price Levels / Support & Resistance (Advanced)**
Ye kyun use hote hain? Algo tool ko samajh nahi aata ki chart par line kahan kheenchni hai. Ye indicators mathematically support aur resistance nikal kar dete hain, jahan se price ghoomne ke chances sabse zyada hote hain.

Pivot Points (Standard/Fibonacci): Pichle din/hafte ke hisaab se aaj ka support aur resistance automatically nikal kar dete hain.

Donchian Channels: Pichle X dino ka highest high aur lowest low batata hai. Breakout trading ke liye best hai.

## **6. Market Breadth / Sentiment (The Master Filter)**
Ye kyun use hote hain? Ye kisi ek stock ke liye nahi, balki poori market ki health check karne ke liye hote hain. Agar poori market gir rahi hai, toh individual stock mein buy karna risky hota hai.

# **VIX (India VIX)**: Darr ka index (Fear Index). Agar VIX bohot high hai, toh options khareedna risk hota hai kyunki premium mehenge hote hain.

Advance/Decline Ratio: Kitne stocks upar hain vs kitne neeche hain.

Summary for your Notes:

Kharidna hai ya nahi? -> Trend + Momentum dekho.
Stop-Loss kahan lagana hai? -> Volatility (ATR) dekho.
Asli move hai ya trap? -> Volume dekho.


### **Fundamentals ko 4 Core Categories + 1 Event Category** mein document kar lete hain. Ise bhi apne notes mein save kar lo:

### **1. Valuation Metrics (Stock Sasta Hai Ya Mehanga?)**
Kyun dekhna hai? Taaki hum overhyped stocks ko top par kharidne se bach sakein.

P/E Ratio (Price-to-Earnings): Industry average se kam hona chahiye. (Agar sector ka P/E 30 hai, aur stock 15 par mil raha hai, toh sasta hai).

PEG Ratio (P/E to Growth): P/E ko uski growth se compare karta hai. PEG < 1 ko generally undervalued maana jata hai.

Price to Book (P/B): Banking aur Financial stocks ke liye sabse important.

### *2. Profitability Metrics (Business Kaisa Chal Raha Hai?)**
Kyun dekhna hai? Sasta stock 'Kachra' bhi ho sakta hai. Ye metrics batate hain ki company actual mein profit kama rahi hai ya nahi.

ROCE (Return on Capital Employed): Tumhara favourite! Company apne total capital par kitna return nikal rahi hai. ROCE > 15% is excellent.

ROE (Return on Equity): Shareholder ke paise par kitna return ban raha hai.

Operating Profit Margin (OPM): Dhandhe mein actual margin kitna hai? Agar margin har saal badh raha hai, toh stock fundamentally strong hai.

### *3. Financial Health & Solvency (Kahin Company Doob Toh Nahi Jayegi?)**
Kyun dekhna hai? Algo mein hume default hone wali companies se door rehna hai, chahe unka chart kitna bhi sundar ho.

Debt-to-Equity Ratio: Company par karza kitna hai. D/E < 1 best hota hai. Banking stocks mein ise ignore karte hain.

Free Cash Flow (FCF): Sab kharche nikalne ke baad company ke haath mein kitna actual cash bacha. Positive FCF matlab company king hai.

### *4. Shareholding Pattern (Bade Players Ka Bharosa)**
Kyun dekhna hai? Agar Promoters (owners) hi apne share bech rahe hain, toh hum kyun kharidein?

Promoter Holding: Minimum 50% honi chahiye.

FII / DII Increasing Stake: Agar Foreign Investors ya Mutual Funds apna paisa badha rahe hain, toh wo ek bohot strong fundamental trigger hota hai.

### *5. Fundamental Momentum / Growth Metrics (Company Ki Speed Kya Hai?)**
Kyun dekhna hai? Sasti aur profitable company agar grow nahi kar rahi (stagnant hai), toh uska stock price bhi nahi badhega. Algo ko trend ke saath 'Growth' bhi chahiye.

QoQ / YoY EPS Growth: Pichle quarter ya pichle saal ke mukable Earnings Per Share (EPS) kitna badha. Algo filter lagata hai: EPS_Growth > 15%.

Revenue/Sales Growth: Sirf kharche kam karke profit badhana acchi baat nahi hai, actual sales bhi badhni chahiye.

### *6. Quant Scoring Models (Algo Traders Ka Brahmastra! ⚡)**
Kyun dekhna hai? Algo coding mein har baar 10 alag-alag metrics (ROCE, P/E, Debt) check karna complex ho jata hai. Isliye math experts ne kuch aise 'Scores' banaye hain jo ek single number mein company ki poori kundali nikal dete hain. Algos inko sabse zyada use karte hain.

Piotroski F-Score (0 to 9): Ye 9 alag-alag accounting criteria check karta hai. Agar score 7, 8, ya 9 hai, toh company financially ekdum solid hai. Algo rule bohot simple ho jata hai: If F-Score >= 7, Pass.

Altman Z-Score: Ye mathematically predict karta hai ki aane wale 2 saal mein company ke bankrupcy (doobne) ke kitne chance hain. Agar score < 1.8 hai, toh algo us stock ko reject kar dega.

### *7. Sector-Specific Exceptions (Zaroori Logic)**
Kyun dekhna hai? Tumhara algo poore Nifty 500 par ek hi rule nahi laga sakta. Jo rule IT company par chalega, wo Bank par fail ho jayega. Banks karza (Debt) lekar hi dhandha karte hain, toh unka Debt-to-Equity hamesha high hoga.

Banks / NBFCs ke liye: Yahan P/E ya Debt nahi dekhte. Yahan algo filter karega NPA (Non-Performing Assets) (Kam hona chahiye) aur NIM (Net Interest Margin) (Zyada hona chahiye).

Capital Intensive (Jaise Power/Steel): Yahan P/B (Price to Book) zyada important hota hai.

Algo Logic: If Sector == "Banking", apply Bank_Rules; Else apply Standard_Rules.

## **8. Event-Driven Filters (Tumhara Master Idea! 🎯)**
Kyun dekhna hai? Risk ko manage karne aur high-volatility se bachne (ya uska fayda uthane) ke liye.

Next Earnings Date (Quarterly Results): Humara algo check karega: Kya aane wale 3 din mein result hai? Agar haan, toh trade mat lo (Block Entry).

Earnings Surprise: Result aane ke baad check karna ki actual profit estimate se kitna zyada tha.

Dividend Yield: Long-term portfolio banane ke liye.

The Documentation Add-on
Apni STRATEGIES.md file mein "Fundamental Filters" ke section mein is line ko zaroor add kar lena:

Event Risk Filter (Crucial): The algorithm must fetch the Next_Earnings_Date. If Current_Date is within ±3 days of the Next_Earnings_Date, the system will IGNORE all technical buy/sell signals to avoid gap-up/gap-down risk.


### **Technical part for Trade Matrix**
## 1. Trend Identification (Market Ka Flow Kahan Hai?)
Kyun dekhna hai? Algo ka sabse pehla rule: "Trend is your friend." Agar market upar ja raha hai, toh algo sirf Buy ka signal dhoondhega, Short sell ka nahi.

Moving Averages (SMA/EMA): 200 EMA long-term trend batata hai, aur 50 EMA short-term trend.

Algo Logic: If Current_Price > 200 EMA -> Trend is Bullish (Only allow BUY signals).

ADX (Average Directional Index): Ye batata hai ki trend mein "dum" kitna hai. Agar ADX > 25 hai, matlab trend strong hai, chalo trade lein. Agar < 20 hai, matlab market sideways hai, algo shant baithega.

### 2. Momentum & Mean Reversion (Entry Timing)
Kyun dekhna hai? Trend bullish hai iska matlab ye nahi ki abhi kharid lo. Hume saste mein (dip par) kharidna hai.

RSI (Relative Strength Index): Oversold (sasta) aur Overbought (mehanga) zone batata hai.

Algo Logic: If Trend == Bullish AND RSI(14) < 30 -> Executing BUY order (Matlab strong stock thoda gira hai, utha lo).

MACD (Moving Average Convergence Divergence): Jab MACD line signal line ko neeche se kaat-ti hai, toh wo ek naye momentum ka start hota hai.

### 3. Volatility & Dynamic Risk Management (The Pro Secret)
Kyun dekhna hai? Retail trader hamesha fixed 5% ya 10 rupees ka Stop-Loss (SL) lagata hai aur wo jaldi hit ho jata hai. Algo trader hamesha Dynamic Stop-Loss lagata hai market ke mood ke hisaab se.

ATR (Average True Range): Ye batata hai ki stock 1 din mein kitna utaar-chadav karta hai.

Algo Logic: Agar stock ka ATR ₹15 hai, toh algo Stop-Loss entry price se 2 x ATR (yani ₹30) neeche lagayega. Isse market ke normal noise mein SL hit nahi hota.

Bollinger Bands: Jab bands sikudne (squeeze) lagte hain, algo samajh jata hai ki ek bada blast (breakout) aane wala hai.

### 4. Volume & Liquidity (Asliyat Check)
Kyun dekhna hai? Chart par price upar ja raha hai, par kya bade khiladi (Institutions) actual mein paisa daal rahe hain? Agar volume nahi hai, toh wo ek "Trap" (dhoka) hai.

Volume SMA: Algo hamesha check karta hai ki breakout ke din ka volume pichle 20 din ke average volume se zyada hona chahiye.

VWAP (Volume Weighted Average Price): Intraday algo traders ka bhagwan. Ye batata hai ki volume ke hisaab se din ka average price kya hai. If Price > VWAP -> Buy.

Liquidity Filter: Algo pehle hi check kar leta hai ki stock mein roz minimum ₹10 Crore ka trade hota hai ya nahi. Warna order execute karne mein 'Slippage' (price difference) bohot aayega.

### 5. Mathematical Price Levels (Support/Resistance)
Kyun dekhna hai? Algo ko support/resistance khud draw karna nahi aata, isliye wo math ka use karta hai automatically levels nikalne ke liye.

Pivot Points (Standard/Fibonacci): Pichle din/hafte ke high, low aur close ke basis par math formula se aaj ke liye R1, R2 (Resistance) aur S1, S2 (Support) nikal deta hai.

Algo Logic: If Price touches S1 AND RSI indicates Oversold -> BUY.

Donchian Channels: Pichle X dino ka highest aur lowest point track karta hai (Jaise 52-week high breakout).

### 6. Multi-Timeframe Analysis (MTF - The Holy Grail)
Kyun dekhna hai? Koi bhi pro algo system sirf ek time-frame par trade nahi leta.

Algo Logic: Algo pehle Daily Chart (1D) check karega trend ke liye (e.g., Bullish). Phir wo 15-Min Chart (15m) par aayega aur RSI oversold hone ka wait karega.

Bada Timeframe = Direction.

Chota Timeframe = Precision Entry.

### Robust System Ka Blueprint:
Ek perfect technical algo wo nahi jisme 50 indicators hon. Ek perfect algo wo hai jisme:
Ek Trend indicator ho (SMA)
Ek Timing indicator ho (RSI)
Ek Risk/SL indicator ho (ATR)
Ek Confirmation indicator ho (Volume)


### Chart Pattern Recognition: Iski Poori ABCD
Ab aate hain sabse heavy aur mazedar part par. Pattern recognition (Double Top, Head & Shoulders, Flags) ek computer ke liye aasan nahi hota kyunki computer numbers dekhta hai, shapes nahi. Isko banane ke liye hume Computer Vision ka use karna hoga.

Isko banane ka step-by-step blueprint ye raha:

Step 1: Data Image Generation (The Raw Material)
Tumhara Python script NSE/BSE ke pichle 5 saal ke OHLCV (Open, High, Low, Close, Volume) data ko download karega aur library (jaise mplfinance) ka use karke un numbers ko actual candlestick charts ki images (.png) mein convert karega.

Step 2: Data Labeling (The Smart AI Use)
In hazaron images ko manual tag karna possible nahi hai. Yahan humara purana plan kaam aayega: Hum in images ko ek advanced Vision AI (jaise Gemini 1.5 Pro) API ko bhejenge aur usse bolenge: "Is chart mein Head & Shoulders kahan hai, uske coordinates batao aur is image ko label karo." Ye humara training data ban jayega.

Step 3: Training the Local Model (The Brain)
Ab hum in labeled images par ek lightweight CNN (Convolutional Neural Network) model train karenge (TensorFlow ya PyTorch use karke). Kyunki tumhe pehle se hi backtesting aur model training ka thoda idea hai, ye part tumhare liye bohot interesting hoga. Ye local model sirf ek cheez seekhega: Patterns ko pehchanna.

Step 4: Live Integration (The Eye)
Jab model ready ho jayega, toh live market mein humara system har 15 minute mein current chart ki image banayega, apne local CNN model me daalega, aur model millisecond mein batayega ki: "Confidence 85%: Double Bottom pattern detected." Iske baad humara pehle wala filter (ROCE, RSI) check karega ki trade lena hai ya nahi.

## Phase 3: The Paper Trading & Confluence Engine

**Objective:** To seamlessly bridge Phase 1 (Data Screener) and Phase 2 (Vision AI), and to execute/track simulated trades locally in real-time. This phase acts as a risk-free testing ground with zero-latency execution logic.

### 1. The Confluence Logic (Filter -> Trigger -> Execute)
The system uses a sequential pipeline to save compute power and maximize accuracy.
* **Step 1 (The Filter - Phase 1):** The screener runs on the Nifty 500 universe. Output: A highly filtered shortlist of 10-15 stocks meeting fundamental (e.g., ROCE > 15) and technical (e.g., RSI < 30) criteria.
* **Step 2 (The Trigger - Phase 2):** The local CNN model scans the charts of ONLY these 10-15 shortlisted stocks. If a bullish setup (e.g., Double Bottom) is detected with >80% confidence, it generates a `TRADE_TRIGGER`.
* **Step 3 (The Execution):** The trigger is sent to the Paper Broker to initiate a simulated Buy order.

### 2. Paper Broker Architecture
A custom Python engine (`PaperBroker`) manages virtual capital, executes orders, and tracks P&L using a local SQLite database.

**Core Mechanics:**
* **Virtual Capital:** Initialized at ₹10,00,000.
* **Position Sizing:** Auto-calculated based on a fixed risk model (e.g., risking only 2% of total capital per trade).
* **The WebSocket Watchdog:** Instead of REST API polling (which causes slippage and rate limits), the engine connects to a WebSocket stream (e.g., Yahoo Finance or Broker API) for Live Traded Price (LTP).
* **Zero-Latency Exit Logic:** The WebSocket event listener constantly checks:
  `IF LTP <= Stop_Loss OR LTP >= Target -> IMMEDIATELY EXECUTE SELL ORDER`

### 3. Database Schema (SQLite)
The local database (`tradematrix_local.db`) acts as the memory of the paper trading system.

**Table 1: `account_balance`**
* `id` (INT, Primary Key)
* `total_capital` (FLOAT) - Starting balance
* `available_margin` (FLOAT) - Capital free to trade
* `used_margin` (FLOAT) - Capital currently locked in active trades

**Table 2: `active_positions`**
* `trade_id` (TEXT, Primary Key)
* `symbol` (TEXT) - e.g., 'RELIANCE.NS'
* `entry_price` (FLOAT)
* `quantity` (INT)
* `stop_loss` (FLOAT)
* `target` (FLOAT)
* `entry_time` (DATETIME)
* `strategy_used` (TEXT) - e.g., 'Alpha_Screener_v1'

**Table 3: `trade_history` (The Ledger)**
* `trade_id` (TEXT, Primary Key)
* `symbol` (TEXT)
* `buy_price` (FLOAT)
* `sell_price` (FLOAT)
* `pnl_amount` (FLOAT)
* `pnl_percentage` (FLOAT)
* `exit_reason` (TEXT) - e.g., 'SL_HIT', 'TARGET_HIT', 'MANUAL_EXIT'
* `exit_time` (DATETIME)

### Phase 4 documnetation
. F&O Clearance Blueprint (Kaunsa Hathiyar Kab Use Karna Hai)
# A. Futures Trading (The Linear Game)

Fundament: Future ekdum cash stock ki tarah chalta hai. Isme time decay (Theta) ya Volatility (Vega) ka koi asar nahi hota.

Kya Dekhna Hai: Yahan Greeks ko bhool jao. Sirf apna Phase 1 aur Phase 2 (Price Action, Trend, aur Volume) dekho.

Algo Logic: Breakout aaya -> Future Buy karo -> Strict Stop Loss lagao. Pura khel leverage (kam paise mein zyada quantity) ka hai.

# B. Option Buying (The Speed Game - Naked Buy)

Fundament: Option buying mein sabse bada dushman hai Time (Theta). Agar market tumhari disha mein gaya, par dheere-dheere gaya, tab bhi tumhara loss hoga.

Kya Dekhna Hai:

Delta: Algo hamesha 0.50 se 0.60 (At-The-Money ya slight In-The-Money) wala strike chuega. OTM (Out of The Money) kabhi nahi buy karna hai.

Gamma: Expiry ke din (Zero-Hero ke liye) high Gamma wale strikes uthane hain kyunki wo price ko rocket banate hain.

Momentum: Algo sirf tab buy karega jab Phase 1 mein "Strong Momentum" (jaise ADX > 25) detect ho.

# C. Option Selling (The Time Game - Naked Sell)

Fundament: Yahan Theta tumhara best friend hai. Agar market tumhari disha mein na jaakar wahi khada bhi raha (sideways), toh bhi tum profit kamaoge.

Kya Dekhna Hai:

Delta (The Enemy): Algo OTM strikes select karega jinka Delta < 0.20 ho. Iska matlab us strike ke In-The-Money hone ke chances sirf 20% hain (Yani tumhari jeetne ki probability 80% hai).

Theta: Jis strike mein sabse zyada theta decay bacha ho, use sell karna.

# D. Hedging / Spreads (The Professional Game)

Fundament: Jab tum ek option buy aur dusra sell ek sath karte ho (Jaise Bull Call Spread), toh tum apne Greeks ko "Neutral" kar dete ho.

Kya Dekhna Hai: Yahan individual Greeks nahi dekhte. Algo Net Premium, Max Profit, aur Max Loss calculate karega. Hedging ka main target Vega (Volatility) aur Theta (Decay) ke risk ko aapas mein kaatna (cancel out) hota hai.

# 2. Open Interest (OI) Kahan Fit Hota Hai?
Greeks batate hain ki Option ka premium kaise move hoga, par OI batata hai ki Market/Index khud kahan jayega. OI option pricing ka hissa nahi hai, wo market ki Map/GPS hai.

Highest Call OI: Ye market ka Resistance hai. (Yahan call sellers baithe hain, wo market ko iske upar nahi jaane denge).

Highest Put OI: Ye market ka Support hai.

Algo Logic: Agar Nifty 22000 par hai aur highest Call OI 22200 par hai, toh algo ko pata hai ki upside sirf 200 point ki bachi hai. Wo 22300 ka target kabhi set nahi karega.

# 3. Kya Pro Algo Traders Itna Hi Dekhte Hain? (The Missing Secret)
Nahi bhai, pro quants aur institutions iske alawa 3 Advanced Metrics ko apna master filter maante hain. Inke bina F&O ka system adhoora hai:

Implied Volatility (IV) & IV Percentile (IVP): Ye sabse critical factor hai. IV batata hai ki options abhi "saste" hain ya "mehenge".

Rule: Agar IVP > 80 (Options bohot mehenge hain), algo kabhi Option Buy nahi karega, wo Option Sell/Hedge karega. Agar IVP < 20 (Options saste hain), tabhi algo Naked Buy karega.

Put-Call Ratio (PCR): Ye pure market ka sentiment batata hai.

Rule: PCR > 1.5 matlab market Overbought hai (reversal aa sakta hai). PCR < 0.6 matlab Oversold hai (bounce aa sakta hai). Algo Phase 1 ke signals ko PCR se cross-verify karta hai.

Max Pain Theory: Expiry wale din, market us strike price ke aas-paas close hone ki koshish karta hai jahan option buyers ko sabse zyada loss ho (aur sellers ko max profit). Algo is point ko calculate karke expiry day ki strategy banata hai.
