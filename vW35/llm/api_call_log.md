# R8 API Call Log

- Sprint: vW35
- Run time: 2026-08-29T03:48:56+00:00
- Successful providers: 2/3
- Requested minimum successes: 0
- Failure policy: non-fatal; errors are logged and the pipeline continues

| Provider | Model | Status | Error Code | Detail | Output |
|---|---|---|---|---|---|
| Groq | openai/gpt-oss-120b | FAILED | HTTP_403 / 1010 | HTTP 403: error code: 1010 | - |
| Google Gemini | gemini-3.5-flash | OK | - | - | vW35/llm/synthesis_gemini.txt |
| OpenRouter | openrouter/free | OK | - | - | vW35/llm/synthesis_openrouter.txt |
