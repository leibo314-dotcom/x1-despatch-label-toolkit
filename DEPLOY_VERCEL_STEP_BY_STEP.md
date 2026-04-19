# Deploy To Vercel: Step By Step

This guide assumes you want a public website link that other people can open.

## What You Already Have

Your deployable project folder is:

`F:\Open AI\Codex\FMI DELIVERY PDF 生成器\x1_despatch_label_toolkit`

Important files already prepared for you:

- `app.py`
- `web_app.py`
- `requirements.txt`
- `vercel.json`
- `.python-version`
- `templates/`
- `public/`
- `publish_to_github.ps1`

## Fastest Path Now

Because Git and GitHub CLI are now installed on this machine, the quickest route is:

1. Log into GitHub once
2. Set your Git name/email once
3. Run `publish_to_github.ps1`
4. Import the repo into Vercel

The detailed steps are below.

## Part 0: One-Time GitHub Login

### Command line option

1. Open PowerShell.
2. Run:
   `gh auth login`
3. Choose:
   - GitHub.com
   - HTTPS
   - Login with a web browser
4. Follow the browser login flow.
5. Return to PowerShell when it says login is complete.

### Set your Git identity

Still in PowerShell, run:

`git config --global user.name "Your Name"`

`git config --global user.email "your@email.com"`

Use the same email as your GitHub account if possible.

## Part 0.5: Auto-publish script

After login is done, you can publish this project with:

`powershell -ExecutionPolicy Bypass -File .\publish_to_github.ps1`

If you want the repo private:

`powershell -ExecutionPolicy Bypass -File .\publish_to_github.ps1 -Private`

## Part 1: Create A GitHub Repository

### Option A: If GitHub Desktop is already installed

1. Open GitHub Desktop.
2. Click `File`.
3. Click `Add Local Repository`.
4. Click `Choose...`.
5. Select this folder:
   `F:\Open AI\Codex\FMI DELIVERY PDF 生成器\x1_despatch_label_toolkit`
6. If GitHub Desktop says this is not a repository yet, click `create a repository`.
7. Use repository name:
   `x1-despatch-label-toolkit`
8. Keep it `Public` if you want easier Vercel hookup, or `Private` if you prefer.
9. Click `Create Repository`.
10. Click `Publish repository`.
11. Wait until upload finishes.

### Option B: If GitHub Desktop is not installed

1. Install GitHub Desktop from:
   [https://desktop.github.com/](https://desktop.github.com/)
2. Sign in to your GitHub account.
3. Then follow Option A.

### Option C: Use the prepared PowerShell script

1. Open PowerShell inside:
   `F:\Open AI\Codex\FMI DELIVERY PDF 生成器\x1_despatch_label_toolkit`
2. Run:
   `powershell -ExecutionPolicy Bypass -File .\publish_to_github.ps1`
3. Wait until the repo is created and pushed.

## Part 2: Deploy On Vercel

1. Open:
   [https://vercel.com/](https://vercel.com/)
2. Sign in.
3. Click `Add New...`
4. Click `Project`
5. If asked, connect GitHub.
6. Find repository:
   `x1-despatch-label-toolkit`
7. Click `Import`

## Part 3: Configure The Project In Vercel

When the import page opens, check these items carefully:

1. Framework Preset:
   Leave it as auto-detected or `Other`.
2. Root Directory:
   If Vercel asks for it, make sure it points to the actual app folder.
   If your repository contains only this project, leave root as default.
3. Build and Output Settings:
   Leave defaults unless Vercel asks you to edit them.

## Part 4: Add Environment Variable

Before clicking deploy, add this environment variable:

1. Find the `Environment Variables` section.
2. Add a variable named:
   `FLASK_SECRET_KEY`
3. For the value, paste any long random text.

Example:

`x1-label-secret-2026-keep-this-private`

If Vercel lets you choose environments, apply it to:

- Production
- Preview
- Development

## Part 5: Deploy

1. Click `Deploy`.
2. Wait for build and deploy to finish.
3. When deployment completes, Vercel will show a public URL.

It will look similar to:

`https://x1-despatch-label-toolkit.vercel.app`

That is the link you can send to other people.

## Part 6: Test The Live Site

After deployment:

1. Open the new Vercel URL.
2. Upload a sample PDF.
3. Click `Generate PDF`.
4. Confirm it reaches the result page.
5. Click `Download PDF`.
6. Check the output:
   - `TWT` is gone
   - `Size` text is gone
   - the address appears once at the top

## If The Import Fails

Check these things:

1. The GitHub repo upload finished completely.
2. Vercel imported the correct repository.
3. `FLASK_SECRET_KEY` was added.
4. The project root is correct.

## If The Site Loads But CSS Looks Missing

That usually means static files were not picked up correctly.

This project already includes `public/styles.css`, which is the Vercel-friendly location.

So if this still happens:

1. Open the deployed site.
2. Try opening:
   `/styles.css`
3. If it loads, refresh the page.
4. If not, redeploy once from Vercel.

## If PDF Generation Fails On Vercel

Possible causes:

1. The uploaded PDF layout differs from the expected X1 Quote Schedule pattern.
2. A Python dependency install failed during build.
3. The runtime environment behaves differently from local desktop.

In that case:

1. Open the project in Vercel.
2. Open the latest deployment.
3. Check `Build Logs`.
4. Then check `Runtime Logs`.
5. Copy the error message and send it to me.

## Fastest Path If You Want The Least Friction

Use this exact order:

1. Install GitHub Desktop
2. Publish this folder to GitHub
3. Import the repo into Vercel
4. Add `FLASK_SECRET_KEY`
5. Click Deploy
6. Send me any error screenshot or log text if it stops anywhere
