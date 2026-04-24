# Bug Report Template

Use this template when creating bug issues for the email assistant project.

---

## Title
[Component] Brief description of defect

Examples:
- "[API] Gmail auth token expires without refresh"
- "[Database] Draft replies not saving for thread IDs > 1000"
- "[AI] Reply generation fails on emails with HTML formatting"

## Labels
- `bug`
- `severity:critical` or `severity:high` or `severity:medium` or `severity:low`
- `priority:critical` or `priority:high` or `priority:medium` or `priority:low`
- `area:api` or `area:frontend` or `area:ai` or `area:database` or `area:cli`

## Body

```markdown
## Bug Summary

[1-2 sentence description. Be specific: "X returns Y when it should return Z"]

## Environment

| Field | Value |
|---|---|
| Version / Commit | [git SHA or branch name] |
| OS / Platform | [e.g., macOS 15.3, Ubuntu 24.04] |
| Python Version | [e.g., 3.11.6] |
| Deployment | [local / Docker] |

## Components Affected

- **Primary:** [`src/ai/analyzer.py`](src/ai/analyzer.py) - [what it does]
- **Secondary:** [`src/database/db.py`](src/database/db.py) - [how it's involved]

## Reproduction Steps

1. [Exact first step with commands/inputs]
2. [Next step]
3. [Step where bug manifests]

**Reproduction rate:** [Always / Intermittent / One-time]

## Expected Result

[What should happen. Include expected output, status code, or behavior]

## Actual Result

[What actually happens. Include exact error messages]

## Evidence

<details>
<summary>Error output / Stack trace</summary>

\`\`\`
[Paste error output here]
\`\`\`

</details>

## Root Cause Analysis

**Likely cause:** [File path and line number if known]

**What's been ruled out:** [Things checked that are NOT the cause]

## Acceptance Criteria (Definition of Fixed)

- [ ] [Condition that must be true when fixed]
- [ ] [Another condition]
- [ ] No regression in [related functionality]
- [ ] All existing tests still pass

## Regression Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| [Original bug] | [precondition] | [action that triggered bug] | [correct result] |
| [Boundary case] | [precondition] | [similar action] | [expected result] |

## Sub-Tasks

### Backend (BE)
- [ ] [Specific fix with file path]
- [ ] [Another fix]

### QA
- [ ] Add regression test for original bug
- [ ] Add test for boundary case
- [ ] Verify all existing tests pass
```

---

## Example Bug Report

```markdown
## Bug Summary

Gmail token refresh fails with 401 error after 1 hour, requiring manual re-authentication instead of automatic refresh.

## Environment

| Field | Value |
|---|---|
| Version / Commit | main branch, commit abc123 |
| OS / Platform | macOS 15.3 |
| Python Version | 3.11.6 |
| Deployment | local development |

## Components Affected

- **Primary:** [`src/auth/gmail_auth.py`](src/auth/gmail_auth.py) - OAuth token management
- **Secondary:** [`src/email/fetcher.py`](src/email/fetcher.py) - Email fetching that triggers auth

## Reproduction Steps

1. Authenticate with Gmail API using `python src/main.py`
2. Wait 60+ minutes (token expires)
3. Run `python src/main.py` again to fetch emails

**Reproduction rate:** Always (100% after token expiry)

## Expected Result

Token should refresh automatically using the refresh token from `token.pickle`, allowing seamless email fetching without user intervention.

## Actual Result

```
googleapiclient.errors.HttpError: <HttpError 401 when requesting ...>
Error: The credentials do not contain the necessary fields for OAuth 2.0 access token.
```

User must delete `token.pickle` and re-authenticate manually.

## Evidence

<details>
<summary>Error Stack Trace</summary>

\`\`\`python
Traceback (most recent call last):
  File "src/main.py", line 15, in main
    gmail = get_gmail_service()
  File "src/auth/gmail_auth.py", line 23, in get_gmail_service
    return build('gmail', 'v1', credentials=creds)
  File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/googleapiclient/discovery.py", line 130, in build
    resp, content = http.request(requested_url)
googleapiclient.errors.HttpError: <HttpError 401>
\`\`\`

</details>

## Root Cause Analysis

**Likely cause:** In `src/auth/gmail_auth.py` line 18-22, the token refresh logic uses `creds.refresh(Request())` but doesn't handle the case where refresh_token is missing or invalid. The credentials object may not be persisting the refresh_token properly.

**What's been ruled out:**
- Scope changes (SCOPES haven't changed)
- credentials.json file corruption (re-downloaded, same issue)
- Network connectivity (other API calls work fine)

## Acceptance Criteria (Definition of Fixed)

- [ ] Token automatically refreshes when expired
- [ ] No manual re-authentication required after 1+ hour
- [ ] token.pickle persists refresh_token correctly
- [ ] Existing email fetching functionality unchanged
- [ ] All auth tests pass

## Regression Test Scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| Expired token refresh | Valid refresh_token in token.pickle | Token is 61 minutes old, user fetches emails | Token refreshes automatically, emails fetched successfully |
| First-time auth | No token.pickle exists | User authenticates | token.pickle created with access_token AND refresh_token |
| Valid token | Recently authenticated (< 1 hour) | User fetches emails | Uses existing token, no refresh needed |

## Sub-Tasks

### Backend (BE)
- [ ] Fix `src/auth/gmail_auth.py` line 18-25 to ensure refresh_token is saved
- [ ] Add explicit check for `creds.refresh_token` before attempting refresh
- [ ] Add error handling for refresh failures with user-friendly message
- [ ] Verify token.pickle includes both access_token and refresh_token fields

### QA
- [ ] Add test `test_token_auto_refresh()` that simulates expired token
- [ ] Add test `test_missing_refresh_token_error()` for edge case
- [ ] Manual test: authenticate, wait 65 minutes, verify auto-refresh
- [ ] Verify all existing auth tests still pass
```
