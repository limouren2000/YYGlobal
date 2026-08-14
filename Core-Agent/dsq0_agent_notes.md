# dsq0 Core-Agent Notes

## Contribution Focus

This note collects a few lightweight ideas for the `Core-Agent` area of YYGlobal.
The goal is to keep future agent improvements easy to review, test, and merge without touching shared project files.

## Ideas

- Keep Core-Agent contributions scoped to one small capability or note per pull request.
- Put contributor-specific experiments in clearly named files to reduce merge conflicts.
- When adding an agent utility, include the expected input, output, and failure behavior.
- Prefer simple examples that can be checked without external credentials or private data.

## Suggested Review Checklist

- The file is under `Core-Agent/`.
- The change does not modify unrelated app, service, or dependency files.
- The content is safe to publish and contains no secrets.
- The title and PR description explain the purpose of the contribution.
