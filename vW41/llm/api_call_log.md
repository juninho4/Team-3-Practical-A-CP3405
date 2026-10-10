# R8 API Call Log

- Sprint: vW41
- Run time: 2026-10-10T01:52:07+00:00
- Successful providers: 1/3
- Requested minimum successes: 0
- Failure policy: non-fatal; errors are logged and the pipeline continues

| Provider | Model | Status | Error Code | Detail | Output |
|---|---|---|---|---|---|
| Groq | openai/gpt-oss-120b | FAILED | HTTP_403 / 1010 | HTTP 403: error code: 1010 | - |
| Google Gemini | gemini-3.5-flash | FAILED | HTTP_429 / too_many_requests | HTTP 429: Your project has exceeded a quota. See https://ai.dev/rate-limit to manage your rate limits. (error code: too_many_requests) | - |
| OpenRouter | openrouter/free | OK | - | - | vW41/llm/synthesis_openrouter.txt |
