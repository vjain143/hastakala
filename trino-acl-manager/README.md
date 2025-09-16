# Trino ACL Manager (Streamlit)

Streamlit app to author and evaluate Trino file-based ACL JSON.

## Quickstart
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501

## Docker
```bash
docker build -t trino-acl-streamlit:0.1 .
docker run --rm -p 8501:8501 trino-acl-streamlit:0.1
```

Load `sample_acl.json` from the sidebar to try it out.
