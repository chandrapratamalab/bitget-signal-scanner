import os
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config.settings import Settings, default_settings
from core.data.bitget_client import BitgetClient
from core.scanner.pipeline import run_scan
from core.utils.io import build_signals_export_df


def _with_rank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df.insert(0, "No", range(1, len(df) + 1))
    return df


def _build_settings() -> Settings:
    defaults = default_settings()
    with st.sidebar:
        st.header("Scanner Settings")
        product_type = st.text_input("Product Type", value=defaults.product_type)
        top_n = st.number_input("Top N candidates", min_value=10, max_value=200, value=defaults.top_n_candidates)
        top_k = st.number_input("Top K output", min_value=1, max_value=20, value=defaults.top_k)
        min_volume = st.number_input(
            "Min quote volume", min_value=0.0, value=defaults.min_quote_volume, step=100000.0
        )
        max_spread = st.number_input(
            "Max spread", min_value=0.0, max_value=0.01, value=defaults.max_spread, step=0.0001, format="%.4f"
        )
        atr_mult = st.number_input(
            "ATR multiplier", min_value=0.5, max_value=5.0, value=defaults.atr_mult, step=0.1
        )
        swing_lookback = st.number_input(
            "Swing lookback", min_value=10, max_value=100, value=defaults.swing_lookback
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
    )


def main() -> None:
    st.set_page_config(page_title="Chloe Scan", layout="wide")
    st.title("Chloe Scan Signal Futures Trade in Bitget")
    st.caption("Manual trade signals with entry, SL, and TP levels.")

    if "scan_results" not in st.session_state:
        st.session_state.scan_results = None
    if "signals_export_df" not in st.session_state:
        st.session_state.signals_export_df = None

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
            "entry_time = close time candle 15m terakhir yang dipakai untuk evaluasi entry "
            "(bukan waktu wajib entry)."
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
                            "direction",
                            "entry_time",
                            "entry_price",
                            "sl",
                            "tp1",
                            "tp2",
                            "recommended_leverage_cap",
                            "entry_status",
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
    else:
        st.info("Click Run Scan untuk memulai pemindaian pasar.")


if __name__ == "__main__":
    main()
