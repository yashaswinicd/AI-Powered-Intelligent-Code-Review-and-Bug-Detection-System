# API

All endpoints return JSON unless noted. Errors look like
`{"success": false, "error": "message"}`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/analyze` | Find problems only |
| POST | `/debug` | Find, fix, verify, return corrected code |
| POST | `/upload-debug` | Same as `/debug` for an uploaded file (`multipart/form-data`: `file`, optional `language`, `stdin_input`) |
| GET | `/report/<result_id>/<txt\|json\|pdf>` | Download a report (results are kept in memory for the last 50 runs) |
| GET | `/api/languages` | Supported languages and installed compilers |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/benchmark` | Benchmark and ML metrics |
| GET | `/api/health` | Health check |

## Request body for `/analyze` and `/debug`

```json
{"code": "...", "language": "auto", "filename": "optional.c", "stdin_input": ""}
```

`language` is `auto` or one of: python, java, c, cpp, csharp, javascript,
typescript, go, php, rust, kotlin, swift.

## Main fields of the response

| Field | Meaning |
|-------|---------|
| `language`, `language_name`, `engines` | What was detected and which analysers ran |
| `original_issues[]` | `type, line, column, severity, category, message, suggestion, status` |
| `status` | `fixed`, `needs manual fix`, `suggestion` or `found` (analysis only) |
| `fixed_code`, `diff`, `fixes[]` | Corrected source, unified diff, log of repairs |
| `original_score`, `fixed_score` | Quality score 0-100 with grade |
| `execution` | Python run result, or compile check for other languages |
| `verification` | `verified` flag and message |
| `result_id` | Use with `/report/...` |
