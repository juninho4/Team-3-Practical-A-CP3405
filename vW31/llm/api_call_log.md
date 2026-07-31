# R8 API Call Log

- Sprint: vW31
- Run time: 2026-07-31T23:36:15+00:00
- Successful providers: 1/3
- Requested minimum successes: 0
- Failure policy: non-fatal; errors are logged and the pipeline continues

| Provider | Model | Status | Error Code | Detail | Output |
|---|---|---|---|---|---|
| Groq | openai/gpt-oss-120b | FAILED | HTTP_403 / 1010 | HTTP 403: error code: 1010 | - |
| Google Gemini | gemini-3.5-flash | FAILED | HTTP_500 / api_error | HTTP 500: gemini-3.5-flash is currently experiencing high demand, spikes in demand are usually temporary. Please try again later. (error code: api_error) | - |
| OpenRouter | openrouter/free | OK | - | - | vW31/llm/synthesis_openrouter.txt |
