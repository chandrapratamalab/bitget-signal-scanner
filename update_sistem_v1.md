# Professional Futures Trade Logic (Entry, SL, TP, Leverage)

## 0) Prinsip Inti (yang dipakai trader profesional)

1. **Risk-first**: tentukan berapa % equity yang siap hilang jika SL kena (risk per trade).
2. **SL ditentukan oleh market structure/volatility**, bukan oleh leverage.
3. **Position size diturunkan dari risk & SL distance**.
4. **Leverage hanya alat** untuk membuka notional yang dibutuhkan; leverage dipilih agar:
   - margin usage tidak berlebihan,
   - jarak ke liquidation aman,
   - tidak “overexposed” terhadap noise/volatility.

> Kesimpulan: Profesional tidak “main 20x” karena ingin cepat kaya.
> Mereka memilih leverage _setelah_ tahu SL% dan position sizing.

---

## 1) Apa yang Dilihat Profesional untuk Entry

### 1.1 Context / Regime (Higher TF: 4H)

Tujuan: trade searah arus dominan dan menghindari chop.

- Trend up/down (mis. EMA alignment, HH/HL vs LL/LH)
- Volatility regime (ATR%, apakah terlalu liar atau terlalu sepi)
- Range vs trend (chop filter)

Output:

- `bias = LONG / SHORT / NO_TRADE`

### 1.2 Setup Quality (Middle TF: 1H)

Tujuan: memastikan ide entry masuk akal, bukan noise 15m.

- Pullback “sehat” ke area value (mis. EMA20-50 / previous support-resistance)
- Struktur belum rusak (untuk long: HL masih valid, untuk short: LH masih valid)
- Hindari entry pas setelah spike 1H yang abnormal

Output:

- `setup_ok = true/false`
- `key_level` (support/resistance / breakout line)

### 1.3 Trigger (Lower TF: 15m)

Tujuan: timing entry dengan konfirmasi yang jelas.
Contoh trigger profesional yang umum:

- **Break + Retest** (lebih aman)
- Break + hold (agresif)
- Pullback entry ke level + rejection candle

Output:

- `entry_condition` (kapan order boleh diambil)
- `entry_zone` (range entry yang realistis)

---

## 2) Cara Profesional Menentukan Stop Loss (SL)

### 2.1 Rule utama: SL harus masuk akal secara struktur

Pilihan umum:

- Di bawah swing low (long) / di atas swing high (short)
- Di luar level yang membatalkan thesis (invalidation)

### 2.2 Volatility buffer (ATR)

Agar SL tidak mudah tersapu wick:

- `SL = structure_level ± (ATR * buffer)`
  Buffer umum:
- 0.2–0.7 ATR tergantung volatilitas & timeframe
- Alternatif sederhana: `SL distance >= 1.0–1.5 × ATR(15m)` untuk entry 15m

Output:

- `sl_price`
- `sl_reason = swing / structure / atr`

---

## 3) Cara Profesional Menentukan Take Profit (TP)

### 3.1 Target berbasis Market Structure

- TP pada resistance/support berikutnya (swing level HTF)
- Area supply/demand, atau previous high/low

### 3.2 R-multiple (risk-reward) sebagai kontrol kualitas

- `R = |entry - SL|`
- Minimal profesional biasanya menargetkan **>= 1.5R** pada setup yang bagus
- Skema umum:
  - TP1 = 1R (ambil partial, reduce risk)
  - TP2 = 2R (biarkan runner)
  - Trailing stop untuk trend kuat (EMA/ATR trail)

Output:

- `tp1`, `tp2` (+ optional `trail_rule`)

---

## 4) Cara Profesional Memutuskan Leverage (yang benar)

### 4.1 Parameter yang perlu (ideal)

Untuk benar-benar profesional, leverage harus menghitung:

- `equity` (modal)
- `risk_per_trade_pct` (mis. 0.25%–1%)
- `entry_price`, `sl_price`
- `max_margin_usage_pct` (mis. 10%–30% dari equity)
- constraints exchange: max leverage, min order size, etc.

> Karena sistem kamu public-only, equity tidak diketahui.
> Jadi output yang realistis adalah:
>
> - **risk-based position sizing formula** (butuh equity input)
> - atau **leverage cap recommendation** berdasarkan SL% & volatility (tanpa equity)

### 4.2 Rumus inti: posisi ditentukan oleh risk, bukan leverage

1. Hitung jarak SL dalam %:

- `sl_distance_pct = abs(entry - sl) / entry`

2. Jika user input:

- `equity`
- `risk_pct`
  maka position size (notional) yang benar:
- `risk_amount = equity * risk_pct`
- `position_notional = risk_amount / sl_distance_pct`

3. Margin usage pada leverage L:

- `required_margin = position_notional / L`
  Profesional memilih L agar:
- `required_margin <= equity * max_margin_usage_pct`

Sehingga leverage minimum yang dibutuhkan:

- `L_min = position_notional / (equity * max_margin_usage_pct)`
  Profesional lalu memilih:
- `L = ceil_to_allowed(L_min)` tapi tetap dalam batas aman (cap).

### 4.3 Tanpa equity (public-only): leverage cap yang profesional

Jika equity tidak ada, sistem mengeluarkan **batas leverage maksimum yang masuk akal** berdasarkan SL%:

- `leverage_cap = 1 / (sl_distance_pct * safety_factor)`

Default profesional yang konservatif:

- `safety_factor = 2.0` (buffer wick/slippage/volatility)

Contoh:

- SL 5% → cap ≈ 10x
- SL 10% → cap ≈ 5x
- SL 14% → cap ≈ 3.5x

### 4.4 Guard tambahan yang umum dipakai profesional

- **ATR guard:** jika SL < ~1×ATR(15m), kurangi leverage cap (noise risk).
- **Regime guard:** jika RANGE/chop, leverage cap turun.
- **Liquidity/spread guard:** spread besar → leverage cap turun.
- **Hard caps by asset class (umum):**
  - BTC/ETH: cap 10x (untuk manual trader konservatif)
  - Alt mid: cap 5x
  - Alt micro/liquiditas kecil: cap 2–3x

Output:

- `recommended_leverage_cap` (bukan “harus segini”)
- `reason`

---

## 5) Output Fields yang Disarankan (untuk sistem kamu)

Tambahkan ke JSON signal:

- `sl_distance_pct`
- `atr_15m`, `atr_pct`
- `recommended_leverage_cap`
- `recommended_leverage_cap_reason`

Opsional (kalau kamu mau input manual equity di dashboard):

- `risk_pct` (dropdown)
- `equity_input`
- `position_notional`
- `required_margin_at_L` (untuk beberapa L: 2x/3x/5x)

---

## 6) Pseudocode (Profesional, dua mode)

### Mode A — Public-only (tanpa equity)

```python
sl_dist_pct = abs(entry - sl) / entry
cap = 1 / (sl_dist_pct * 2.0)  # safety_factor=2.0

# guards
atr_pct = atr_15m / entry
if sl_dist_pct < atr_pct * 1.0:
    cap *= 0.7
if regime == "RANGE":
    cap *= 0.7
if spread_pct > 0.0015:
    cap *= 0.8

cap = clamp(cap, 1.0, asset_class_cap(symbol))  # BTC/ETH vs alt cap
cap = round_to([1,2,3,5,7,10], cap)

return cap
```
