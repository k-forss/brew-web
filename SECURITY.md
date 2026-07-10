# Security

## Test Secrets

CI test secrets (`DATABASE_URL`, `SECRET_KEY`) are configured for ephemeral local and CI test infrastructure only. These secrets:

- Are used exclusively in isolated test environments
- Are not persisted beyond test execution
- Are scoped to temporary Docker containers or in-memory databases
- Should never be used in production deployments

**Note:** No secrets or credentials were exposed in PR #3. All test configurations use ephemeral, non-production values.

## Production Security

For production deployments:

- Generate a strong, unique `SECRET_KEY` and store it securely in `.env`
- Keep the application behind a TLS proxy
- Never expose port 4452 directly to the internet
- Rotate secrets regularly
- Follow the security guidelines in `README.md`
