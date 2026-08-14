# Wxxxyyyy Core-Agent Notes

## Contribution Focus

This note records my first contribution to the `Core-Agent` area of YYGlobal,
following the existing practice of keeping each pull request small, scoped to
this directory, and easy to review.

## Ideas

- Keep every Core-Agent contribution in a clearly named, contributor-specific
  file to avoid merge conflicts with other contributors.
- When adding an agent utility, document its expected input, output, and
  failure behavior, and prefer examples that run without external credentials.
- Run the scope check before opening a pull request to confirm that every
  changed file stays under `Core-Agent/`:

  ```bash
  python Core-Agent/check_pr_scope.py --base upstream/main
  ```

## Suggested Review Checklist

- The file is under `Core-Agent/`.
- The change does not modify unrelated app, service, or dependency files.
- The content is safe to publish and contains no secrets.
- The title and PR description explain the purpose of the contribution.
