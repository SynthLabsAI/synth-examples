# Review the permission change

Review /app/change.diff against the export-access policy in /app/POLICY.md.
The current implementation and caller are in /app/permissions.py.
Report a consequential bug introduced by the change.

Write /logs/artifacts/review.json with this structure:

```json
{
  "findings": [
    {
      "path": "permissions.py",
      "title": "Short description",
      "explanation": "Connect the changed code to the failing input and consequence.",
      "counterexample": {
        "is_admin": true,
        "user_org_id": "example-org",
        "export_org_id": "example-org"
      }
    }
  ]
}
```

The object above illustrates the format, not a failing input. Your
counterexample must be a real input that the changed implementation allows
but the stated policy forbids. Use JSON booleans, not strings. Report the root
cause once; do not duplicate it for several inputs. If you find no supported
issue, write an empty findings array.

Do not modify the implementation. You may read it and execute small checks.
The verifier checks the counterexample against the code and policy; it cannot
fully assess the quality of your explanation. This is a small teaching example,
not an exhaustive test of code-review ability.
