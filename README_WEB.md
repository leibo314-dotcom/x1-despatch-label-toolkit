# X1 Despatch Label Web App

## What Changed

- Removed the `TWT` field from each item.
- Removed the extra `Size` text field from each item.
- Added a one-time address line at the top of the generated PDF.
- Kept the existing diagram extraction and label generation logic.
- Added a browser-based upload and download flow.

## Run Locally

1. Install Python 3.
2. Run `Install_Dependencies.bat`.
3. Run `Launch_Web_App.bat`.
4. Open `http://localhost:5000`.
5. Upload an X1 Quote Schedule PDF and download the result.

## Deploy As A Shareable Link

This folder now includes `render.yaml`, `Procfile`, `runtime.txt`, `app.py`, `vercel.json`, `.python-version`, `templates/`, and `public/`, so it is ready for common Python hosting platforms.

### Render

1. Put this folder in a Git repository.
2. Push the repository to GitHub.
3. Create a new Web Service in Render from that repository.
4. Render will use `render.yaml` and install dependencies automatically.
5. After deployment, Render will give you a public URL that you can send to other people.

### Railway / Similar Platforms

1. Put this folder in a Git repository.
2. Push the repository to GitHub.
3. Create a new Python web app from that repository.
4. The platform can start the app with `gunicorn web_app:app`.
5. After deployment, you will get a public URL.

### Vercel

According to Vercel's Flask docs, Flask can be deployed with zero configuration as long as an `app` instance is exposed from a supported entrypoint such as `app.py`. Vercel also recommends serving static files from `public/`, and this project now does that.

1. Put this folder in a Git repository.
2. Push the repository to GitHub.
3. Import the repository into Vercel.
4. Keep the project root pointed at this folder.
5. Set `FLASK_SECRET_KEY` in the Vercel project environment variables.
6. Deploy, then use the generated `vercel.app` URL.

For a click-by-click walkthrough, use:

`DEPLOY_VERCEL_STEP_BY_STEP.md`

## Notes

- The address is extracted from the first line on page 1 that looks like a street address.
- This is still tuned for X1 Quote Schedule style PDFs.
- If the source PDF layout changes a lot, extraction rules may need another adjustment.
- For public deployment, set `FLASK_SECRET_KEY` in the hosting platform environment variables.
