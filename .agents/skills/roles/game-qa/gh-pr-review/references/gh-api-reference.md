# GitHub API Reference

Quick reference for `gh` CLI commands used in PR reviews.

## Fetch PR Data

```bash
# PR metadata (title, body, files, commits)
gh pr view $PR --repo $REPO --json title,body,files,commits,baseRefName,headRefName

# List changed files only
gh pr view $PR --repo $REPO --json files --jq '.files[].path'

# Full diff
gh pr diff $PR --repo $REPO

# Latest commit SHA
COMMIT_ID=$(gh pr view $PR --repo $REPO --json commits --jq '.commits[-1].oid')
```



## Submit Review Decision

You should submit the review by passing a Markdown file containing the review to the `-F` parameter.

```bash
# Approve
gh pr review $PR --repo $REPO --approve -F /tmp/pr-review.md

# Request changes
gh pr review $PR --repo $REPO --request-changes -F /tmp/pr-review.md

# Comment only
gh pr review $PR --repo $REPO --comment -F /tmp/pr-review.md
```



## Troubleshooting

### TLS Handshake Timeout
Intermittent network issues or Go's HTTP/2 client handling can cause `net/http: TLS handshake timeout`.
- **Fix 1: Toggle HTTP/2** — Force HTTP/1.1 by prepending `GODEBUG=http2client=0` to the command:
  ```bash
  GODEBUG=http2client=0 gh api ...
  ```
- **Fix 2: Retry** — Often resolved by simply rerunning the command.
- **Fix 3: Flush DNS** — `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` (Mac).

### 422 Validation Failed
This error usually means the GitHub API rejected the request due to invalid data.
- **Common Cause**: You are trying to comment on a file that is NOT changed in this PR.
- **Fix**: Use `gh pr view $PR --json files --jq '.files[].path'` to check if the file is in scope.
- **Common Cause**: The `line` or `start_line` is outside the range of the diff hunk.
- **Common Cause**: The `side` or `start_side` is incorrect (use `"RIGHT"` for new code).

### 404 Not Found
- Verify `$COMMIT_ID` is the latest commit on the PR
- Verify `$REPO` format is `owner/repo`
- Verify `path` matches the file path in the diff exactly
