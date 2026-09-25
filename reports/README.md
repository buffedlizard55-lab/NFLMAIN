# Generated reports

`verification.md` in this directory is **generated** by `pipeline/build_site_data.py` on
every data refresh. Do not edit it by hand — the next run overwrites it.

It is the audit trail required by `PROJECT_PROMPT.md` rules R3 and R4:

* exactly which upstream URLs were fetched, with HTTP status, byte counts and SHA-256 digests
* the declared source registry, including the verification evidence behind each source
* coverage: seasons, games, plays, and the inferred current week
* the `api.nfl.com` cross-check outcome
* every irregularity flagged for human review, with the official links needed to check it
