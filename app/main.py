import os
import re
import sys
import time

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config.settings import (
    SCAN_MODE_SCALP,
    SCAN_MODE_TREND,
    Settings,
    default_settings,
)
from core.data.bitget_client import BitgetClient
from core.data.orderbook_provider import OrderbookProvider
from core.scanner.pipeline import run_custom_scan, run_scan
from core.utils.io import build_signals_export_df
from core.utils.time import to_datetime_ms, to_wib_string


def _with_rank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df.insert(0, "No", range(1, len(df) + 1))
    return df


def _auto_refresh(interval_ms: int) -> None:
    if interval_ms <= 0:
        return
    time.sleep(interval_ms / 1000.0)
    try:
        st.experimental_rerun()
    except AttributeError:
        try:
            st.rerun()
        except AttributeError:
            return


def _sanitize_symbol(raw_symbol: str, fallback: str) -> str:
    symbol = (raw_symbol or "").strip().upper()
    if not symbol or symbol.lower() == "default":
        return fallback
    return symbol


def _parse_custom_symbols(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    symbols: list[str] = []
    seen: set[str] = set()
    for part in parts:
        symbol = (part or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _format_age(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 1:
        return f"{seconds:.2f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    return f"{minutes:.1f}m"


def _get_orderbook_provider(settings: Settings) -> OrderbookProvider:
    provider = st.session_state.get("orderbook_provider")
    if provider is None:
        provider = OrderbookProvider(
            BitgetClient(),
            enable_ws=settings.enable_ws_orderbook,
            channel=settings.ws_orderbook_channel,
            inst_type=settings.ws_inst_type,
            reconnect_backoff_ms=settings.ws_reconnect_backoff_ms,
            stale_timeout_sec=settings.ws_stale_timeout_sec,
            fallback_to_rest=settings.fallback_to_rest,
        )
        st.session_state.orderbook_provider = provider
    else:
        provider.update_settings(
            enable_ws=settings.enable_ws_orderbook,
            channel=settings.ws_orderbook_channel,
            inst_type=settings.ws_inst_type,
            reconnect_backoff_ms=settings.ws_reconnect_backoff_ms,
            stale_timeout_sec=settings.ws_stale_timeout_sec,
            fallback_to_rest=settings.fallback_to_rest,
        )
    return provider


def _render_orderbook_panel(settings: Settings, symbol_options: list[str]) -> None:
    if not settings.enable_ws_orderbook and not settings.fallback_to_rest:
        return

    st.subheader("Orderbook (Realtime)")
    fallback_symbol = "BTCUSDT"
    last_symbol = st.session_state.get("orderbook_symbol", fallback_symbol)
    if isinstance(last_symbol, str):
        last_symbol = last_symbol.strip().upper()
    else:
        last_symbol = fallback_symbol

    if symbol_options:
        if last_symbol not in symbol_options:
            last_symbol = symbol_options[0]
        symbol = st.selectbox(
            "Orderbook Symbol",
            symbol_options,
            index=symbol_options.index(last_symbol),
            key="orderbook_symbol_select",
        )
    else:
        symbol = st.text_input(
            "Orderbook Symbol",
            value=last_symbol,
            key="orderbook_symbol_input",
        )

    symbol = _sanitize_symbol(symbol, fallback_symbol)
    st.session_state.orderbook_symbol = symbol

    provider = _get_orderbook_provider(settings)
    snapshot, status = provider.get_orderbook(symbol)
    health = provider.get_health()

    st.caption(f"WS Status: {status}")
    if health.get("last_error"):
        st.caption(f"WS Error: {health['last_error']}")

    if snapshot is None:
        st.info("Orderbook belum tersedia.")
        return

    best_bid = snapshot.bids[0][0] if snapshot.bids else None
    best_ask = snapshot.asks[0][0] if snapshot.asks else None
    spread = None
    spread_pct = None
    if best_bid is not None and best_ask is not None:
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2 if (best_bid + best_ask) else None
        if mid:
            spread_pct = spread / mid

    ts_label = to_wib_string(to_datetime_ms(snapshot.ts_ms))
    st.caption(
        f"Source: {snapshot.source} | Last update: {ts_label or snapshot.ts_ms}"
    )
    if spread is not None:
        spread_text = f"{spread:.6f}"
        if spread_pct is not None:
            spread_text = f"{spread:.6f} ({spread_pct * 100:.3f}%)"
        st.caption(f"Best bid: {best_bid:.6f} | Best ask: {best_ask:.6f} | Spread: {spread_text}")

    bids_df = pd.DataFrame(snapshot.bids, columns=["bid_price", "bid_size"])
    asks_df = pd.DataFrame(snapshot.asks, columns=["ask_price", "ask_size"])
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Bids**")
        st.dataframe(bids_df, hide_index=True)
    with col2:
        st.markdown("**Asks**")
        st.dataframe(asks_df, hide_index=True)

    with st.expander("WS Health", expanded=False):
        last_pong_age = _format_age(health.get("last_pong_age"))
        last_message_age = _format_age(health.get("last_message_age"))
        reconnect_count = health.get("reconnect_count", 0)
        last_connect_ts = health.get("last_connect_ts")
        last_connect_label = (
            to_wib_string(to_datetime_ms(int(last_connect_ts * 1000)))
            if last_connect_ts
            else "-"
        )
        last_seq = snapshot.seq if snapshot else None
        st.markdown(
            f"""
- connected: `{health.get('connected')}`
- last_pong_age: `{last_pong_age}`
- last_message_age: `{last_message_age}`
- reconnect_count: `{reconnect_count}`
- last_connect_time: `{last_connect_label}`
- last_seq: `{last_seq if last_seq is not None else '-'}`
"""
        )

    if settings.enable_ws_orderbook:
        _auto_refresh(settings.ws_ui_refresh_ms)


def _build_settings() -> Settings:
    defaults = default_settings()
    with st.sidebar:
        st.header("Scanner Settings")
        scan_mode_label = st.selectbox(
            "Scan Mode",
            ["Trend Mode", "Scalp Mode"],
            index=0 if defaults.scan_mode == SCAN_MODE_TREND else 1,
        )
        scan_mode = SCAN_MODE_TREND if scan_mode_label == "Trend Mode" else SCAN_MODE_SCALP

        product_type = st.text_input("Product Type", value=defaults.product_type)
        if st.button("Apply Wide Net Preset", key="wide_net_preset"):
            st.session_state["top_n_candidates"] = 100
            st.session_state["top_k_output"] = 10
            st.session_state["min_quote_volume"] = 1_000_000.0
            st.session_state["max_spread"] = 0.003
        st.caption("Preset: Top N=100, Top K=10, Min quote volume=1,000,000, Max spread=0.003")
        top_n = st.number_input(
            "Top N candidates",
            min_value=10,
            max_value=200,
            value=defaults.top_n_candidates,
            key="top_n_candidates",
        )
        top_k = st.number_input(
            "Top K output",
            min_value=1,
            max_value=20,
            value=defaults.top_k,
            key="top_k_output",
        )
        min_volume = st.number_input(
            "Min quote volume",
            min_value=0.0,
            value=defaults.min_quote_volume,
            step=100000.0,
            key="min_quote_volume",
        )
        max_spread = st.number_input(
            "Max spread",
            min_value=0.0,
            max_value=0.01,
            value=defaults.max_spread,
            step=0.0001,
            format="%.4f",
            key="max_spread",
        )
        atr_mult = st.number_input(
            "ATR multiplier", min_value=0.5, max_value=5.0, value=defaults.atr_mult, step=0.1
        )
        swing_lookback = st.number_input(
            "Swing lookback", min_value=10, max_value=100, value=defaults.swing_lookback
        )

        trend_bias_tf = defaults.trend_bias_tf
        trend_confirm_tf = defaults.trend_confirm_tf
        trend_entry_tf = defaults.trend_entry_tf
        show_funding_oi = defaults.show_funding_oi
        strict_trend_alignment = defaults.strict_trend_alignment
        strict_filters = defaults.strict_filters

        scalp_bias_tf = defaults.scalp_bias_tf
        scalp_trigger_tf = defaults.scalp_trigger_tf
        use_funding_filter = defaults.use_funding_filter
        use_oi_confirmation = defaults.use_oi_confirmation
        use_overextension_filter = defaults.use_overextension_filter

        funding_extreme_threshold = defaults.funding_extreme_threshold
        min_oi_change_pct = defaults.min_oi_change_pct
        max_extension_pct = defaults.max_extension_pct
        squeeze_threshold = defaults.squeeze_threshold

        if scan_mode == SCAN_MODE_TREND:
            st.subheader("Trend Mode Options")
            trend_bias_tf = st.selectbox("Bias TF", ["4H"], index=0).lower()
            trend_confirm_tf = st.selectbox(
                "Confirm TF",
                ["1H", "30M"],
                index=0 if defaults.trend_confirm_tf == "1h" else 1,
            ).lower()
            trend_entry_tf = st.selectbox("Entry TF", ["15M"], index=0).lower()
            show_funding_oi = st.checkbox(
                "Show Funding & OI", value=defaults.show_funding_oi
            )
            strict_trend_alignment = st.checkbox(
                "Strict Trend Alignment", value=defaults.strict_trend_alignment
            )
            strict_filters = st.checkbox("Strict Filters", value=defaults.strict_filters)
        else:
            st.subheader("Scalp Mode Options")
            scalp_bias_tf = st.selectbox(
                "Bias TF",
                ["1H", "30M"],
                index=0 if defaults.scalp_bias_tf == "1h" else 1,
            ).lower()
            scalp_trigger_tf = st.selectbox(
                "Trigger TF",
                ["15M", "5M"],
                index=0 if defaults.scalp_trigger_tf == "15m" else 1,
            ).lower()
            use_funding_filter = st.checkbox(
                "Use Funding Filter", value=defaults.use_funding_filter
            )
            use_oi_confirmation = st.checkbox(
                "Use OI Confirmation", value=defaults.use_oi_confirmation
            )
            use_overextension_filter = st.checkbox(
                "Use Overextension Filter", value=defaults.use_overextension_filter
            )
            funding_extreme_threshold = st.number_input(
                "Funding extreme threshold",
                min_value=0.0,
                max_value=0.01,
                value=defaults.funding_extreme_threshold,
                step=0.0001,
                format="%.4f",
            )
            min_oi_change_pct = st.number_input(
                "Min OI% confirmation",
                min_value=0.0,
                max_value=1.0,
                value=defaults.min_oi_change_pct,
                step=0.01,
                format="%.2f",
            )
            max_extension_pct = st.number_input(
                "Max extension from EMA",
                min_value=0.0,
                max_value=1.0,
                value=defaults.max_extension_pct,
                step=0.01,
                format="%.2f",
            )
            squeeze_threshold = st.number_input(
                "Squeeze threshold (ATR ratio)",
                min_value=0.1,
                max_value=1.0,
                value=defaults.squeeze_threshold,
                step=0.05,
                format="%.2f",
            )

        st.subheader("Realtime Orderbook")
        enable_ws_orderbook = st.checkbox(
            "Enable Realtime Orderbook (WebSocket)",
            value=defaults.enable_ws_orderbook,
        )
        ws_orderbook_channel = st.selectbox(
            "WS Channel",
            ["books5", "books15"],
            index=0 if defaults.ws_orderbook_channel == "books5" else 1,
        )
        ws_ui_refresh_ms = st.slider(
            "UI refresh interval (ms)",
            min_value=500,
            max_value=2000,
            value=defaults.ws_ui_refresh_ms,
            step=100,
        )
        fallback_to_rest = st.checkbox(
            "Fallback to REST",
            value=defaults.fallback_to_rest,
        )

        with st.expander("Dokumentasi Istilah", expanded=False):
            st.markdown(
                """
**Sidebar Controls**
- Scan Mode: pilih TREND (default) atau SCALP; menentukan bias TF dan filter yang dipakai.
- Product Type: jenis kontrak Bitget (contoh `USDT-FUTURES`).
- Top N candidates: jumlah kandidat dari Stage 1 sebelum disaring lebih lanjut.
- Top K output: jumlah pasangan terbaik yang diteruskan ke pembuatan sinyal.
- Min quote volume: filter likuiditas minimum berdasarkan volume USDT.
- Max spread: batas rasio spread bid-ask terhadap harga (semakin kecil semakin likuid).
- ATR multiplier: pengali ATR untuk memperlebar SL dari swing/ATR.
- Swing lookback: jumlah candle untuk mencari swing high/low.

**Trend Mode Options**
- Bias TF: timeframe utama untuk regime/trend (default 4H).
- Confirm TF: timeframe konfirmasi arah; digunakan jika Strict Trend Alignment aktif.
- Entry TF: timeframe trigger entry zone (default 15M).
- Show Funding & OI: tampilkan funding rate dan open interest di output.
- Strict Trend Alignment: wajib searah antara Bias TF dan Confirm TF.
- Strict Filters: jika aktif, risk flags bisa menahan entry (WAIT/NO_TRADE).

**Scalp Mode Options**
- Bias TF: timeframe utama (1H atau 30M).
- Trigger TF: timeframe trigger entry (15M atau 5M).
- Use Funding Filter: menahan entry saat funding ekstrem (crowded).
- Use OI Confirmation: butuh kenaikan OI yang searah dengan arah trade.
- Use Overextension Filter: tahan entry jika harga terlalu jauh dari EMA.
- Funding extreme threshold: batas funding untuk flag crowded_long/short.
- Min OI% confirmation: minimal perubahan OI untuk validasi.
- Max extension from EMA: batas jarak harga dari EMA (overextended).
- Squeeze threshold (ATR ratio): ATR relatif kecil untuk mendeteksi squeeze.

**Realtime Orderbook**
- Enable Realtime Orderbook (WebSocket): aktifkan WS depth realtime (default OFF).
- WS Channel: level orderbook (books5/15); books5 disarankan.
- UI refresh interval: jeda rerun untuk update panel orderbook.
- Fallback to REST: pakai REST jika WS stale/error.
- WS Health: status koneksi, umur pesan/pong, dan jumlah reconnect.
"""
            )

    return Settings(
        product_type=product_type,
        top_n_candidates=int(top_n),
        top_k=int(top_k),
        min_quote_volume=min_volume,
        max_spread=max_spread,
        atr_mult=atr_mult,
        swing_lookback=int(swing_lookback),
        candles_limit=defaults.candles_limit,
        scan_mode=scan_mode,
        trend_bias_tf=trend_bias_tf,
        trend_confirm_tf=trend_confirm_tf,
        trend_entry_tf=trend_entry_tf,
        show_funding_oi=show_funding_oi,
        strict_trend_alignment=strict_trend_alignment,
        strict_filters=strict_filters,
        scalp_bias_tf=scalp_bias_tf,
        scalp_trigger_tf=scalp_trigger_tf,
        use_funding_filter=use_funding_filter,
        use_oi_confirmation=use_oi_confirmation,
        use_overextension_filter=use_overextension_filter,
        funding_extreme_threshold=funding_extreme_threshold,
        min_oi_change_pct=min_oi_change_pct,
        max_extension_pct=max_extension_pct,
        squeeze_threshold=squeeze_threshold,
        late_move_atr_mult=defaults.late_move_atr_mult,
        enable_ws_orderbook=enable_ws_orderbook,
        ws_orderbook_channel=ws_orderbook_channel,
        ws_inst_type=defaults.ws_inst_type,
        ws_ui_refresh_ms=ws_ui_refresh_ms,
        ws_reconnect_backoff_ms=defaults.ws_reconnect_backoff_ms,
        ws_stale_timeout_sec=defaults.ws_stale_timeout_sec,
        fallback_to_rest=fallback_to_rest,
    )


def main() -> None:
    st.set_page_config(page_title="Chloe Scan", layout="wide")
    st.title("Chloe Scan Market Futures Trade in Bitget")
    st.caption("Manual trade signals with entry, SL, and TP levels.")

    if "scan_results" not in st.session_state:
        st.session_state.scan_results = None
    if "signals_export_df" not in st.session_state:
        st.session_state.signals_export_df = None
    if "custom_scan_results" not in st.session_state:
        st.session_state.custom_scan_results = None
    if "custom_signals_export_df" not in st.session_state:
        st.session_state.custom_signals_export_df = None

    settings = _build_settings()
    run = st.button("Run Scan")

    if run:
        client = BitgetClient()
        try:
            with st.spinner("Scanning market data..."):
                results = run_scan(client, settings)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Scan failed: {exc}")
            return
        finally:
            client.close()

        st.session_state.scan_results = results
        st.session_state.signals_export_df = build_signals_export_df(results.get("signals", []))

    results = st.session_state.scan_results
    if results:
        stage2 = results.get("stage2", [])
        signals = results.get("signals", [])

        st.subheader("Top Pairs")
        if stage2:
            st.dataframe(_with_rank(pd.DataFrame(stage2)), hide_index=True)
        else:
            st.info("No pairs passed the filters.")

        st.subheader("Signals")
        st.caption(
            "entry_time = close time candle trigger terakhir yang dipakai untuk evaluasi entry "
            "(bukan waktu wajib entry)."
        )
        with st.expander("Dokumentasi Output Table", expanded=False):
            st.markdown(
                """
- symbol: kode kontrak.
- scan_mode: mode scan yang dipakai (TREND/SCALP).
- regime: hasil regime dari Bias TF (TREND_UP/TREND_DOWN/RANGE/NO_TRADE).
- direction: arah trade (LONG/SHORT).
- setup_type: A = continuation, B = crowd fade.
- entry_status: NOW (harga di entry zone), WAIT (belum), NO_TRADE (diblok).
- entry_time: waktu close candle trigger untuk evaluasi entry.
- entry_price: harga tengah entry zone.
- entry_zone: range harga untuk break + retest.
- sl: stop loss.
- tp1/tp2: target take profit berbasis R multiple.
- recommended_leverage_cap: rekomendasi batas leverage maksimum.
- confidence_score: skor 0-100, makin tinggi makin kuat konfirmasi.
- funding_rate: funding rate saat scan.
- open_interest: nilai OI terbaru.
- oi_change_pct: perubahan OI dari snapshot sebelumnya atau data OI terbaru.
- risk_flags: peringatan risiko aktif (contoh: crowded_long, oi_divergence, overextended,
  thin_liquidity, late_move, trend_misaligned).

**Arti Risk Flags**
- crowded_long: funding rate sangat positif, potensi crowding di sisi long.
- crowded_short: funding rate sangat negatif, potensi crowding di sisi short.
- oi_divergence: OI naik tapi harga stagnan/berlawanan arah, indikasi jebakan.
- overextended: harga terlalu jauh dari EMA, rawan pullback.
- thin_liquidity: spread mendekati batas maksimum atau volume rendah.
- late_move: pergerakan sudah terlalu besar dibanding ATR/range recent, entry terlambat.
- trend_misaligned: Bias TF tidak searah dengan Confirm TF (saat strict alignment aktif).

**Setup Reason (setup_reason)**
- ok: kondisi 1H sesuai arah dan harga tidak terlalu jauh dari EMA.
- trend_misaligned: arah 1H tidak sejalan dengan arah trade.
- not_near_value: harga terlalu jauh dari EMA (tidak berada di area value/pullback).
- 1h_spike: candle 1H terakhir spike terlalu besar dibanding rata-rata.
- no_1h_data: data 1H tidak cukup, setup dianggap netral.
"""
            )
        if signals:
            export_df = st.session_state.signals_export_df
            if export_df is None or export_df.empty:
                export_df = build_signals_export_df(signals)
                st.session_state.signals_export_df = export_df
            export_records = export_df.where(pd.notnull(export_df), None).to_dict(orient="records")
            download_csv = export_df.to_csv(index=False)
            st.download_button(
                "Download Signals (CSV)",
                download_csv,
                file_name="signals.csv",
                mime="text/csv",
            )
            st.caption("Download tidak menghapus hasil scan pada halaman ini.")
            st.dataframe(
                _with_rank(
                    export_df[
                        [
                            "symbol",
                            "scan_mode",
                            "regime",
                            "direction",
                            "setup_type",
                            "entry_status",
                            "entry_time",
                            "entry_price",
                            "entry_zone",
                            "sl",
                            "tp1",
                            "tp2",
                            "recommended_leverage_cap",
                            "confidence_score",
                            "funding_rate",
                            "open_interest",
                            "oi_change_pct",
                            "risk_flags",
                        ]
                    ]
                ),
                hide_index=True,
            )
            for signal in export_records:
                with st.expander(f"{signal['symbol']} ({signal['direction']})"):
                    st.json(signal)
        else:
            st.info("No valid trade signals generated.")

        symbol_options = []
        if signals:
            symbol_options = [signal["symbol"] for signal in signals]
        elif stage2:
            symbol_options = [item["symbol"] for item in stage2]
        _render_orderbook_panel(settings, symbol_options)
    else:
        st.info("Click Run Scan untuk memulai pemindaian pasar.")

        _render_orderbook_panel(settings, [])

    st.divider()
    st.subheader("Custom Pair Scan")
    st.caption(
        "Scan pair tertentu tanpa menunggu masuk Top Pairs. Format: BTCUSDT, ETHUSDT"
    )
    custom_raw = st.text_input(
        "Custom pairs",
        key="custom_pairs_input",
        placeholder="IPUSDT, BTCUSDT",
    )
    run_custom = st.button("Run Custom Scan", key="run_custom_scan")
    if run_custom:
        symbols = _parse_custom_symbols(custom_raw)
        if not symbols:
            st.warning("Isi minimal 1 pair untuk custom scan.")
        else:
            client = BitgetClient()
            try:
                with st.spinner("Scanning custom pairs..."):
                    results = run_custom_scan(client, settings, symbols)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Custom scan failed: {exc}")
                return
            finally:
                client.close()

            st.session_state.custom_scan_results = results
            st.session_state.custom_signals_export_df = build_signals_export_df(
                results.get("signals", [])
            )

    custom_results = st.session_state.custom_scan_results
    if custom_results:
        skipped = custom_results.get("skipped", [])
        if skipped:
            reason_map = {
                "not_in_contracts": "tidak ada di kontrak aktif",
                "ticker_not_found": "ticker tidak ditemukan",
                "insufficient_candles": "candle bias < 210",
            }
            skipped_text = "; ".join(
                f"{item['symbol']} ({reason_map.get(item['reason'], item['reason'])})"
                for item in skipped
            )
            st.warning(f"Skipped: {skipped_text}")

        stage1_custom = custom_results.get("stage1", [])
        stage2_custom = custom_results.get("stage2", [])
        signals_custom = custom_results.get("signals", [])

        st.markdown("**Custom Pair Snapshot**")
        if stage1_custom:
            st.dataframe(pd.DataFrame(stage1_custom), hide_index=True)
        else:
            st.info("Tidak ada data snapshot custom pair.")

        st.markdown("**Custom Pair Scores**")
        if stage2_custom:
            st.dataframe(_with_rank(pd.DataFrame(stage2_custom)), hide_index=True)
        else:
            st.info("Tidak ada pair yang lolos scoring (candle bias kurang).")

        st.markdown("**Custom Signals**")
        if signals_custom:
            export_df = st.session_state.custom_signals_export_df
            if export_df is None or export_df.empty:
                export_df = build_signals_export_df(signals_custom)
                st.session_state.custom_signals_export_df = export_df
            export_records = export_df.where(pd.notnull(export_df), None).to_dict(
                orient="records"
            )
            download_csv = export_df.to_csv(index=False)
            st.download_button(
                "Download Custom Signals (CSV)",
                download_csv,
                file_name="custom_signals.csv",
                mime="text/csv",
            )
            st.caption("Download tidak menghapus hasil custom scan pada halaman ini.")
            st.dataframe(
                _with_rank(
                    export_df[
                        [
                            "symbol",
                            "scan_mode",
                            "regime",
                            "direction",
                            "setup_type",
                            "entry_status",
                            "entry_time",
                            "entry_price",
                            "entry_zone",
                            "sl",
                            "tp1",
                            "tp2",
                            "recommended_leverage_cap",
                            "confidence_score",
                            "funding_rate",
                            "open_interest",
                            "oi_change_pct",
                            "risk_flags",
                        ]
                    ]
                ),
                hide_index=True,
            )
            for signal in export_records:
                with st.expander(f"{signal['symbol']} ({signal['direction']})"):
                    st.json(signal)
        else:
            st.info("No valid trade signals generated for custom scan.")


if __name__ == "__main__":
    main()
