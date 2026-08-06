#!/bin/sh
python scripts/prepare_buggins_streamlit.py
exec streamlit run app.py --server.address 0.0.0.0 --server.port "$PORT" --server.headless true
