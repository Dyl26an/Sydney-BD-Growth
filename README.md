# Sydney Growth Intelligence Platform

Streamlit app for multi-month BD merchant analysis.

## Features
- Upload multiple monthly Excel reports, including password-protected files
- Automatic reporting month detection
- Merchant level, area, category, and BD filters
- Weighted funnel conversion rates
- Executive dashboard with visuals
- Alert Center for declining stores and rising stars
- Learn From Best board
- Merchant AI Coach: input a merchant name and find Top 5 comparable learning stores
- Monthly trend and merchant timeline
- Metric Dictionary explaining calculation methodology

## Deploy on Streamlit
Upload these files/folders to your GitHub repo:
- `app.py`
- `requirements.txt`
- `README.md`
- `core/`
- `.streamlit/`

Then deploy with main file path: `app.py`.


## v1.1 fix
- Fixed pandas compatibility error when filling fallback conversion rates.
- Improved blank BD/name handling.
- Smoke-tested against a 1,901-row, 174-column monthly report.
