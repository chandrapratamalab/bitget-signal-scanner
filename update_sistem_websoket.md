# PRD — Integrasi WebSocket Orderbook Bitget USDT-M Futures (Streamlit)

Tanggal: 2026-01-11  
Stack saat ini: Python + Streamlit (sudah berjalan)  
Target market: Bitget **USDT-M Futures** (`USDT-FUTURES`)

---

## 1) Latar Belakang

Sistem saat ini mengambil data market (kemungkinan via REST) sehingga:

- update depth/orderbook bersifat _polling_ (lebih lambat, beban request lebih besar),
- sulit mendapatkan perubahan orderbook yang cepat untuk logic (spread, slippage, imbalance, dll).

Bitget menyediakan WebSocket publik untuk market & depth yang lebih real-time. Domain WS publik: `wss://ws.bitget.com/v2/ws/public`. :contentReference[oaicite:0]{index=0}

---

## 2) Tujuan

1. Menambahkan **sumber data orderbook real-time** via WebSocket Bitget untuk **USDT-FUTURES**.
2. Menjaga **backward compatibility**: program lama tetap jalan tanpa perubahan perilaku default.
3. Menyediakan **fallback otomatis** ke REST bila WebSocket bermasalah.
4. Menyediakan _interface_ data orderbook yang seragam untuk modul logic lama.

---

## 3) Non-Goal

- Tidak mengubah logic sinyal inti yang sudah ada (hanya menambah input data).
- Tidak menambah trading/private WebSocket (order/position). Fokus hanya public orderbook.
- Tidak memaksa semua pair menggunakan WS; hanya jika user mengaktifkan.

---

## 4) Referensi Teknis (Bitget)

### 4.1 WebSocket domain & heartbeat

- WS publik: `wss://ws.bitget.com/v2/ws/public`. :contentReference[oaicite:1]{index=1}
- Agar stabil: kirim string `"ping"` tiap 30 detik dan harapkan `"pong"`. Jika tidak ada `"pong"`, reconnect. Server akan putuskan koneksi jika 2 menit tidak menerima `"ping"`. :contentReference[oaicite:2]{index=2}
- Batas: max 10 pesan/detik per koneksi; subscription limit & saran < 50 channel per koneksi. :contentReference[oaicite:3]{index=3}

### 4.2 Channel orderbook (Futures)

- Channel depth: `books`, `books1`, `books5`, `books15`. :contentReference[oaicite:4]{index=4}
- Untuk implementasi aman & simple, gunakan:
  - **`books5`** (5 level) → push **`snapshot` setiap update** (tidak perlu merge incremental). :contentReference[oaicite:5]{index=5}
- `instType` untuk target ini: **`USDT-FUTURES`**. :contentReference[oaicite:6]{index=6}

### 4.3 Fallback REST (opsional)

- Merge depth REST: `GET /api/v2/mix/market/merge-depth` dengan `productType=USDT-FUTURES&symbol=BTCUSDT`. :contentReference[oaicite:7]{index=7}

---

## 5) Prinsip “Tidak Merusak Program Lama”

### 5.1 Feature Flag (default OFF)

Tambahkan konfigurasi:

- `ENABLE_WS_ORDERBOOK=false` (default)
- `WS_ORDERBOOK_CHANNEL=books5` (default)
- `WS_INST_TYPE=USDT-FUTURES` (fixed untuk scope PRD)
- `WS_UI_REFRESH_MS=1000` (default aman)
- `WS_RECONNECT_BACKOFF_MS=1500` (default)
- `WS_STALE_TIMEOUT_SEC=3` (jika tidak ada data baru, fallback)
- `FALLBACK_TO_REST=true` (default)

**Default OFF** memastikan perilaku lama tetap sama.

### 5.2 Kontrak Data Seragam

Buat struktur data baru yang dipakai modul lama tanpa perlu tahu sumbernya (WS/REST):

- `OrderBookSnapshot`
  - `symbol: str`
  - `bids: list[[price, size]]`
  - `asks: list[[price, size]]`
  - `ts_ms: int` (timestamp)
  - `source: "ws"|"rest"`
  - `seq: optional` (kalau tersedia)

---

## 6) Desain Solusi

### 6.1 Arsitektur High-Level

Komponen baru:

1. **WS Client Service (public)**

   - Mengelola koneksi WS + subscribe depth.
   - Mengirim heartbeat `"ping"` tiap 30 detik. :contentReference[oaicite:8]{index=8}
   - Menghasilkan `OrderBookSnapshot` terbaru ke “store”.

2. **Orderbook Store (per session)**

   - Menyimpan snapshot terbaru untuk UI & logic.
   - Disarankan **per-session** memakai `st.session_state` agar tidak bentrok antar user.
   - Catatan: `st.cache_resource` berbagi object lintas user/rerun dan harus thread-safe. :contentReference[oaicite:9]{index=9}

3. **Provider Layer**
   - `get_orderbook(symbol) -> OrderBookSnapshot`
   - Jika WS enabled & sehat → pakai snapshot WS terbaru.
   - Jika WS stale/error → fallback REST `merge-depth`. :contentReference[oaicite:10]{index=10}

### 6.2 Flow Data

1. User mengaktifkan “Realtime Orderbook (WS)” di UI.
2. App membuat (atau reuse) WS connection → subscribe `books5` untuk symbol yang dipilih.
3. Listener thread menerima message → parse → update snapshot di store.
4. UI melakukan refresh periodik (rerun) dan membaca snapshot terbaru.
5. Logic lama membaca orderbook via provider (tidak berubah di sisi pemakai).

---

## 7) UI/UX Perubahan (Minimal & Aman)

Tambahkan di panel pengaturan:

- Toggle: **Enable Realtime Orderbook (WebSocket)**
- Dropdown: Channel (default `books5`; opsional `books15`)
- Slider: UI refresh interval (500–2000ms; default 1000ms)
- Status badge:
  - `WS: Connected / Reconnecting / Stale / Fallback REST`
- Debug kecil (opsional): last update time, last seq, last pong age.

Catatan: Streamlit tidak push UI secara native; gunakan mekanisme rerun berkala (autorefresh) atau timer UI yang sudah ada pada program lama.

---

## 8) Spesifikasi Teknis Implementasi

### 8.1 Folder & File Baru (tidak mengganggu struktur lama)

Contoh struktur (sesuaikan dengan repo saat ini):

- `services/bitget_ws_client.py`
  - `connect()`, `subscribe_depth(symbol)`, `run_listener()`, `close()`
- `services/orderbook_provider.py`
  - `get_orderbook(symbol)` (WS → fallback REST)
- `models/orderbook.py`
  - `OrderBookSnapshot`
- `utils/retry.py`
  - exponential/backoff helper (opsional)
- `config.py` atau `.env` loader
  - variabel fitur flag & parameter WS

### 8.2 Aturan Subscribe (USDT-FUTURES)

Request subscribe mengikuti format Bitget futures depth channel:

- `instType: "USDT-FUTURES"`
- `channel: "books5"`
- `instId: "<SYMBOL>"` (contoh `"BTCUSDT"`) :contentReference[oaicite:11]{index=11}

### 8.3 Heartbeat & Rate Control

Wajib:

- Timer 30 detik kirim `"ping"` dan validasi `"pong"`. :contentReference[oaicite:12]{index=12}
- Jangan mengirim > 10 pesan/detik di satu koneksi. :contentReference[oaicite:13]{index=13}
- Batasi channel per koneksi (saran < 50). :contentReference[oaicite:14]{index=14}

### 8.4 Reconnect Strategy

- Jika:
  - tidak menerima `"pong"` setelah ping,
  - tidak ada message depth baru selama `WS_STALE_TIMEOUT_SEC`,
  - terjadi exception socket,
    → lakukan reconnect dengan backoff.
- Setelah reconnect, lakukan re-subscribe symbol yang aktif.

### 8.5 Fallback Strategy (Agar sistem lama tetap jalan)

Jika WS tidak aktif / error / stale:

- Gunakan REST `GET /api/v2/mix/market/merge-depth` dengan `productType=USDT-FUTURES&symbol=<SYMBOL>`. :contentReference[oaicite:15]{index=15}
- Provider selalu mengembalikan `OrderBookSnapshot` sehingga logic lama tidak perlu diubah selain mengganti sumber orderbook ke provider.

---

## 9) Dampak ke Modul Lama & Cara Integrasi

### 9.1 Integrasi Minimal (Disarankan)

- Identifikasi titik sistem lama yang membaca orderbook/depth (atau yang butuh best bid/ask).
- Ganti pemanggilan langsung REST menjadi:
  - `orderbook_provider.get_orderbook(symbol)`
- Semua perhitungan lama (spread/slippage estimator/imbalance) tetap sama karena format data diseragamkan.

### 9.2 Mode Operasi

- Mode lama (default): REST/polling seperti sekarang.
- Mode baru: WS realtime + fallback REST.

---

## 10) Observability & Logging

Tambahkan log yang ringkas:

- connect/disconnect reason
- reconnect count & last error
- last message timestamp (ts_ms)
- fallback triggered (yes/no)
- ping/pong age

Opsional: tampilkan di UI “WS Health”.

---

## 11) Pengujian

### 11.1 Unit Test

- Parser message WS → `OrderBookSnapshot`
- Provider memilih WS vs REST sesuai kondisi (connected/stale/error)
- Backoff/reconnect logic (mock socket)

### 11.2 Integration Test (Manual)

- 1 symbol (BTCUSDT) dengan `books5`:
  - status connected
  - update bids/asks berubah
- Matikan koneksi internet / block WS:
  - sistem masuk fallback REST
  - UI tetap berjalan
- Uji beban:
  - refresh UI 1000ms, pastikan tidak lag & tidak spam reconnect

---

## 12) Kriteria Penerimaan (Acceptance Criteria)

1. Dengan `ENABLE_WS_ORDERBOOK=false`, aplikasi berjalan **identik** seperti sebelumnya.
2. Dengan `ENABLE_WS_ORDERBOOK=true`, orderbook update real-time via WS untuk USDT-FUTURES.
3. Jika WS putus/stale, sistem otomatis fallback REST tanpa crash.
4. Tidak ada spam pesan > 10 msg/s; ping tiap 30 detik; reconnect stabil sesuai aturan Bitget. :contentReference[oaicite:16]{index=16}
5. Logic lama tetap kompatibel (menggunakan `OrderBookSnapshot` provider).

---

## 13) Rollout Plan (Aman)

1. Implementasi provider + fallback REST (tanpa WS) → pastikan tidak mengubah hasil.
2. Tambahkan WS client, tetapi flag OFF secara default.
3. Uji internal (1–3 simbol) di environment dev.
4. Aktifkan WS untuk beberapa user (jika multi-user) via config.
5. Jika terjadi masalah, rollback cukup dengan set `ENABLE_WS_ORDERBOOK=false`.

---

## 14) Risiko & Mitigasi

- **Streamlit rerun model**: UI bukan push realtime → gunakan refresh interval yang masuk akal (≥500ms) untuk stabilitas.
- **Thread safety**: Hindari menyimpan WS client sebagai global shared yang bisa dipakai banyak session; gunakan `st.session_state` atau pastikan thread-safe jika memakai cache_resource. :contentReference[oaicite:17]{index=17}
- **Disconnect karena heartbeat/rate**: pastikan ping 30s, batasi pesan, batasi channel per koneksi. :contentReference[oaicite:18]{index=18}

---
