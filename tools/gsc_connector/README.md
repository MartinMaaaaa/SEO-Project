# GSC Connector

This connector gives AI agents a controlled way to access Google Search Console data through `tools/gsc_cli.py`.

## Design

- Credentials stay in `.env`, which is ignored by git.
- Default OAuth scope is read-only: `https://www.googleapis.com/auth/webmasters.readonly`.
- AI agents should call the CLI or read exported cache files. They should not copy or expose secrets.
- Private exports are written under `data/gsc/` and ignored by git.

## Common Commands

```powershell
python tools/gsc_cli.py check-env
python tools/gsc_cli.py auth-url
python tools/gsc_cli.py exchange-code --code "PASTE_CODE_HERE" --write-env
python tools/gsc_cli.py token
python tools/gsc_cli.py sites
python tools/gsc_cli.py performance --start 2026-06-01 --end 2026-06-30 --dimensions query page --save
python tools/gsc_cli.py inspect --url "https://www.example.com/page/"
```

## Notes

- Search Analytics data is usually delayed. The CLI defaults to ending 3 days before today.
- Single requests are capped at 25,000 rows.
- URL Inspection API reports Google's indexed version, not a live page test.
- Use `--filter dimension:operator:expression` for filters, for example `--filter page:contains:/blog/`.
