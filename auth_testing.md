# Auth Testing — PMOS • WMEU

## Bearer token flow

1. **Login admin**
   ```
   curl -X POST $BACKEND/api/auth/login -H 'Content-Type: application/json' \
        -d '{"email":"patrick@buckleylabs.io","password":"WMEU-2026-Admin!"}'
   ```
   → response: `{ "token": "...", "user": {...,"role":"admin"} }`

2. **Use token**
   ```
   curl $BACKEND/api/auth/me -H "Authorization: Bearer <TOKEN>"
   ```

3. **Register member**
   ```
   curl -X POST $BACKEND/api/auth/register -H 'Content-Type: application/json' \
        -d '{"email":"tester@wmeu.io","password":"Tester-2026!","name":"Tester"}'
   ```

4. **Vote (member, requires token)**
   ```
   curl -X POST $BACKEND/api/governance/vote -H "Authorization: Bearer <TOKEN>" \
        -H 'Content-Type: application/json' \
        -d '{"proposal_id":"<id>","choice":"yes"}'
   ```

5. **Approve canon (admin only)**
   ```
   curl -X POST $BACKEND/api/meme-assets/<asset_id>/approve -H "Authorization: Bearer <ADMIN_TOKEN>"
   ```

Errors:
- 401 if no/invalid token, 403 if member tries admin route.
