```markdown
# Lean PRD — Bitget Futures Public Signal Scanner (Local)

## 1) Ringkasan

Sistem lokal yang memindai semua pair **USDT Perpetual Futures** di Bitget menggunakan **Public API (tanpa API key)**, memilih pair terbaik saat itu, lalu menghasilkan rencana trading **manual**: arah (LONG/SHORT), **entry**, **stop loss (SL)**, dan **take profit (TP1/TP2)**. Output ditampilkan dalam **dashboard Streamlit**.

## 2) Tujuan

- Membantu memilih **pair terbaik** untuk di-trade (likuid, spread kecil, gerak cukup, struktur jelas).
- Membantu menentukan **kapan entry**, dan level **SL/TP** secara konsisten.
- Semua berjalan **lokal** (tanpa hosting) dan **tanpa akses akun**.

## 3) Non-Goals (Tidak termasuk v1)

- Auto-trading / eksekusi order.
- Menggunakan API key / data akun / risk monitor liquidation.
- Model ML/AI kompleks (deep learning/RL). (Boleh di fase berikutnya.)
- Integrasi berita/sentimen/on-chain.

## 4) Pengguna & Alur Penggunaan

**Pengguna:** pribadi (manual trader).  
**Alur:**

1. Buka dashboard Streamlit.
2. Klik **Run Scan** atau jalankan auto-refresh.
3. Lihat **Top pairs** (rank + alasan) dan **Signal details** (entry/SL/TP).
4. Gunakan sinyal sebagai rencana manual di chart/exchange.

## 5) Scope v1 (Fitur Wajib)

### 5.1 Data Sources (Public Bitget)

- Contracts (universe symbol perpetual + status)
- All tickers (ranking awal semua pair)
- Candles: 15m, 1H, 4H (analisis teknikal)
- (Opsional v1): funding rate & open interest

### 5.2 Pair Scanner (Ranking)

Mekanisme 2 tahap:

- **Tahap A (Cepat):** contracts + tickers → ranking cepat → Top N kandidat.
- **Tahap B (Teknikal):** candles (15m/1H/4H) hanya Top N → skor teknikal → Top K final.

### 5.3 Regime Detection (4H)

Label per pair:

- `TREND_UP`, `TREND_DOWN`, `RANGE`, atau `NO_TRADE`
  Basis awal (v1):
- EMA50/EMA200 alignment + slope sederhana.

### 5.4 Signal Engine (Manual Entry/SL/TP)

Output per pair:

- Arah (LONG/SHORT) sesuai bias 4H
- Entry plan berbasis 15m
- SL (ATR-based atau swing-based)
- TP1/TP2 berbasis R-multiple
- Invalidation condition

### 5.5 Dashboard Streamlit

Tampilan minimal:

- Panel settings (timeframes, N kandidat, K output, threshold volume/spread).
- Tombol **Run Scan**
- Tabel “Top Pairs” dengan skor & alasan singkat
- Detail sinyal per pair (entry/SL/TP + level utama)

## 6) Output Format Sinyal (Standar)

Untuk tiap pair:

- Pair: `XXXUSDT PERP`
- Regime 4H: TREND_UP / TREND_DOWN / RANGE / NO_TRADE
- Direction: LONG / SHORT / NO TRADE
- Entry type: Break+Retest (default v1)
- Entry zone: `[low, high]`
- SL: `price` + alasan (ATR atau swing)
- TP1, TP2: `price` (1R & 2R)
- Invalidation: kondisi batal (mis. close 15m balik melewati level)

## 7) Definisi Sukses (Success Metrics)

- Dashboard bisa scan dan menghasilkan top K sinyal dengan durasi wajar (bergantung koneksi & N kandidat).
- Mayoritas sinyal muncul pada pair likuid (spread kecil) dan struktur jelas.
- Sinyal konsisten (aturan stabil), tidak “spam” di kondisi chop.

## 8) Risiko & Mitigasi

- **Rate limit / request berat:** pakai 2 tahap + caching lokal.
- **Data historis terbatas:** gunakan window cukup (200–500 candles).
- **Fakeout di market chop:** regime filter 4H + chop filter sederhana.
- **Overfitting parameter:** mulai rule-based, evaluasi, baru upgrade.

## 9) Tech Stack (Local)

- Python 3.12.3
- Streamlit (dashboard)
- httpx/requests (API call)
- pandas atau polars (olah data)
- indikator: manual (EMA/ATR) atau pandas-ta
- Storage cache: Parquet/CSV (opsional DuckDB di fase berikut)

---

# 10) Struktur Folder (Rapi & Scalable)

> Struktur ini memisahkan **UI**, **core logic**, dan **data/cache** supaya mudah di-maintain.
```

bitget-signal-scanner/
├─ README.md
├─ pyproject.toml # atau requirements.txt (pilih salah satu)
├─ .env.example # opsional (untuk setting lokal non-sensitif)
├─ .gitignore
│
├─ app/ # Streamlit UI
│ ├─ main.py # entrypoint: streamlit run app/main.py
│ ├─ pages/ # multi-page UI (opsional)
│ │ ├─ 1_Scanner.py
│ │ └─ 2_Signal_Detail.py
│ ├─ components/ # komponen UI reusable
│ │ ├─ tables.py
│ │ ├─ charts.py
│ │ └─ controls.py
│ └─ assets/ # logo, icon, dll (opsional)
│
├─ core/ # Logika utama (tanpa UI)
│ ├─ config/
│ │ ├─ settings.py # default parameter: N,K, thresholds, ATR mult, dll
│ │ └─ constants.py # productType, granularity mapping, dll
│ │
│ ├─ data/
│ │ ├─ bitget_client.py # wrapper HTTP: get_contracts/get_tickers/get_candles/...
│ │ ├─ schemas.py # typing/shape data (dict keys, dataclass) (opsional)
│ │ └─ cache.py # caching Parquet/CSV + load/save (opsional v1, wajib v2)
│ │
│ ├─ features/
│ │ ├─ indicators.py # EMA, ATR, returns, volatility, dll
│ │ ├─ swing.py # swing high/low detection (fractal sederhana)
│ │ └─ transforms.py # helper: resample, clean, normalize
│ │
│ ├─ scanner/
│ │ ├─ stage1_rank.py # ranking awal dari tickers (volume/spread/move)
│ │ ├─ stage2_score.py # skor teknikal dari candles (trend/vol/chop)
│ │ └─ pipeline.py # orchestration: universe -> candidates -> topK
│ │
│ ├─ signals/
│ │ ├─ regime.py # 4H regime detection
│ │ ├─ entry_rules.py # 15m trigger (break+retest)
│ │ ├─ risk.py # SL/TP (ATR/swing), R multiple
│ │ └─ generator.py # generate final signal object per symbol
│ │
│ ├─ utils/
│ │ ├─ time.py # candle time helpers, alignment
│ │ ├─ math.py # scoring normalization, safe div
│ │ ├─ logging.py # logger config
│ │ └─ io.py # export CSV/JSON
│ │
│ └─ backtest/ # opsional (v2/v3)
│ └─ simple_bt.py
│
├─ data/ # Data lokal (di-ignore git)
│ ├─ raw/ # responses mentah (opsional)
│ ├─ candles/ # cache per symbol/timeframe (parquet/csv)
│ ├─ outputs/ # signals.csv, signals.json
│ └─ logs/
│
└─ scripts/ # util CLI (opsional)
├─ run_scan.py # jalankan scan tanpa UI
└─ warm_cache.py # prefetch candles (opsional)

```

**Catatan penting:**
- `app/` hanya mengurus tampilan & interaksi.
- `core/` semua logika hitung/scanner/sinyal supaya bisa dipakai dari UI maupun CLI.
- `data/` di root untuk cache & output (masuk `.gitignore`).

---

# MVP Plan (v1) — Implementasi Bertahap

## MVP-0: Setup & Skeleton
- Buat struktur folder di atas.
- `app/main.py` menampilkan sidebar settings + placeholder.
- `core/data/bitget_client.py` punya fungsi dummy.

## MVP-1: Data Collector Public
- Implement:
  - `get_contracts(productType)`
  - `get_tickers(productType)`
  - `get_candles(symbol, granularity, limit, productType)`
- Tambah error handling + retry sederhana.

## MVP-2: Scanner 2 Tahap
- `stage1_rank.py`:
  - filter universe (perpetual + normal)
  - rank volume + spread
  - pilih Top N kandidat
- `stage2_score.py`:
  - ambil candles untuk kandidat
  - hitung trend/vol/chop
  - pilih Top K final
- Tampilkan tabel top pairs di Streamlit.

## MVP-3: Signal Engine Entry/SL/TP
- `signals/regime.py` (EMA50/EMA200)
- `signals/entry_rules.py` (break+retest swing 15m)
- `signals/risk.py` (SL ATR 1.2x, TP 1R/2R)
- `signals/generator.py` (gabung jadi objek sinyal)
- Tampilkan detail sinyal per pair.

## MVP-4: Dashboard Streamlit Final v1
- Sidebar: N kandidat, K output, thresholds, ATR multiplier
- Main: Top pairs table + Signal detail panel
- Export signals ke `data/outputs/signals.csv`

---

# Acceptance Criteria (v1)
- Jalan lokal: `streamlit run app/main.py`
- Tanpa API key.
- Scan semua USDT perp → keluarkan Top K pair + sinyal entry/SL/TP.
- Output jelas dan konsisten, siap untuk eksekusi manual.
```
