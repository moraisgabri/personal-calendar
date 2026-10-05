# 06: Backup command (test-first)

**What to build:** A command with two operations. `backup` turns a whole Calendar into one encrypted, timestamped Backup. `restore` verifies a Backup and writes it into an empty location. Built test-first with `/tdd` against small sample Calendars, never the real one. This is the Owner's first AI-assisted coding project, so keep it small and readable. Spec: `.scratch/personal-calendar/spec.md`, Seam 2.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `backup` produces one encrypted Backup file, named by when it was taken
- [ ] Encryption uses an `age` keypair; `backup` needs only the public key
- [ ] backup → restore yields exactly the same events
- [ ] An empty Calendar round-trips
- [ ] Restoring without the right key fails clearly
- [ ] A truncated or tampered Backup is rejected and nothing is written
- [ ] Restore into a non-empty location is refused unless explicitly forced
- [ ] Tests only exercise the command's inputs and outputs, not its internals
- [ ] No keys are committed to the repo; test keys are generated during the tests
