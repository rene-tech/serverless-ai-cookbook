# Sync results from your existing bucket

Scientific AI exports results to the bucket already bound to your authenticated
owner. You do not need another storage integration. `GET /v1/storage` describes
that binding; `POST /v1/storage/credentials` returns its existing S3 credentials
to the authenticated owner. It does not create a bucket or mint a key. A
`not_configured`, disabled or unavailable binding is an operator handoff gap;
never substitute a shared/admin credential.

Use trusted local code or a secret manager for this response, never an MCP
tool result destined for the language model. The following Python snippet runs
from the portable client's environment and transfers credentials directly to
an `aws s3 sync` child environment without printing them or writing a key file.
Install the AWS CLI separately using its normal installation method.

Set `RESULT_PREFIX` to the **exact own-bucket output prefix** returned by your
completed operation's `customer_storage`/manifest receipt, not another user's
prefix. The example downloads only; it does not delete or upload remote files.

```bash
export RESULT_PREFIX='the/exact/prefix/from/your-result/'
export RESULT_DIRECTORY='./downloaded-results'
.venv/bin/python - <<'PY'
import os
import subprocess
from urllib.parse import urlsplit

import httpx

endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
parsed = urlsplit(endpoint)
if parsed.scheme != 'https' or parsed.path.rstrip('/') != '/mcp' or parsed.query or parsed.fragment:
    raise SystemExit('Use the issued HTTPS /mcp endpoint.')
origin = f'{parsed.scheme}://{parsed.netloc}'
with httpx.Client(headers={'Authorization': 'Bearer ' + os.environ['SCIENTIFIC_MODELS_API_KEY']},
                  follow_redirects=False, trust_env=False, timeout=60) as http:
    view_response = http.get(origin + '/v1/storage')
    view_response.raise_for_status()
    view = view_response.json()
    if view['state'] != 'ready':
        raise SystemExit('Your existing storage binding is not ready.')
    response = http.post(origin + '/v1/storage/credentials')
    response.raise_for_status()
    credentials = response.json()
    for field in ('bucket_name', 'endpoint', 'region', 'access_key_id'):
        if credentials[field] != view[field]:
            raise SystemExit('Storage binding changed; inspect it before copying.')

prefix = os.environ['RESULT_PREFIX']
if not prefix or prefix.startswith('/') or '..' in prefix.split('/') or not prefix.endswith('/'):
    raise SystemExit('Use the exact returned result prefix ending with /.')
env = {key: value for key, value in os.environ.items()
       if not key.startswith('AWS_') and key != 'SCIENTIFIC_MODELS_API_KEY'}
env.update(AWS_ACCESS_KEY_ID=credentials['access_key_id'],
           AWS_SECRET_ACCESS_KEY=credentials['secret_access_key'],
           AWS_DEFAULT_REGION=credentials['region'])
subprocess.run(['aws', '--endpoint-url', credentials['endpoint'], 's3', 'sync',
                's3://' + credentials['bucket_name'] + '/' + prefix,
                os.environ['RESULT_DIRECTORY'], '--only-show-errors'], env=env, check=True)
PY
```

Preserve and verify the returned result manifest's SHA-256/size entries after
sync; S3 ETags are not generally SHA-256. The portable batch client already
performs this verification when using its normal download/recovery path.
Your own S3 permission scope is determined by the bound credential, not this
example. Never forward that credential to another tenant or paste it into chat.

`GET /v1/me/usage` provides the platform's available usage view. Missing costs
are unknown, not free; this view is not a guarantee of complete provider billing
or charges for every failed/cancelled attempt.
