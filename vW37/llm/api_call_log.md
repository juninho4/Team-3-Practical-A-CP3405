# R8 API Call Log

- Sprint: vW37
- Run time: 2026-09-12T00:27:35+00:00
- Successful providers: 1/3
- Requested minimum successes: 0
- Failure policy: non-fatal; errors are logged and the pipeline continues

| Provider | Model | Status | Error Code | Detail | Output |
|---|---|---|---|---|---|
| Groq | openai/gpt-oss-120b | FAILED | HTTP_403 / 1010 | HTTP 403: error code: 1010 | - |
| Google Gemini | gemini-3.5-flash | OK | - | - | vW37/llm/synthesis_gemini.txt |
| OpenRouter | openrouter/free | FAILED | EMPTY_RESPONSE | API response did not contain answer text | - |
