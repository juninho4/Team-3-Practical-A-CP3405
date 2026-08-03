# Market Intelligence Dashboard

The integrated pipeline writes the current week to:

`docs/data/latest_prediction.json`

The webpage reads that file through `docs/script.js`.

Local test from the repository root:

```bash
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`.

For GitHub Pages, select **Deploy from a branch**, use the default branch, and choose the `/docs` folder.
