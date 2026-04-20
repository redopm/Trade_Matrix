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


