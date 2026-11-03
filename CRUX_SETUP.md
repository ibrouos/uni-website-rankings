# Setting up the CrUX API key

`crux.py` needs a Google API key for the Chrome UX Report API. The API is free: Google limits it to
150 requests a minute, and there is no paid tier. A daily run makes roughly 270 requests, spaced out to stay
under the limit.

## 1. Create the key

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project or pick an existing one.
2. Enable the **Chrome UX Report API**:
   [console.cloud.google.com/apis/library/chromeuxreport.googleapis.com](https://console.cloud.google.com/apis/library/chromeuxreport.googleapis.com).
   It only appears in the key's restriction list once it's enabled.
3. Under **APIs & Services → Credentials**, create an API key.
4. Edit the key:
   - **API restrictions**: restrict it to **Chrome UX Report API** only.
   - **Application restrictions**: none. Requests come from GitHub's servers, which have no fixed address.

To be certain of never being charged, leave the project without a billing account
(**Billing → Linked account** should say the project has none). CrUX works without one.

## 2. Give it to GitHub Actions

Repository **Settings → Secrets and variables → Actions → New repository secret**:

- Name: `CRUX_API_KEY`
- Secret: the key

Never commit the key: this repository is public.

## 3. Running it locally (optional)

```powershell
$env:CRUX_API_KEY = "your-key"   # this terminal session only
python crux.py
```

## Troubleshooting

- **HTTP 403** on the first request: the API isn't enabled for the key's project, or the key is restricted to
  other APIs. Key changes can take a few minutes to apply. The script stops after the first failure so a bad key
  doesn't make hundreds of failing requests.
- **No data for a university**: Chrome only reports sites with enough real traffic. The script tries the
  homepage, then the whole site; if neither has data, the dashboard shows "–".
