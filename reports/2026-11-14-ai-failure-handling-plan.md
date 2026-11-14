# 2026-11-14 local model error handling — plan

## Finding

`AIService._completions()` converts `OpenAIError` failures from the OpenAI-compatible endpoint into empty text. `analyze_question()` turns this text into a default Council result; `/questions/{id}/analyze` can save that result and write the `[Distractor Trap]` tag. This makes an unavailable endpoint, incorrect model name, authorization problem, or multimodal support issue look like a real diagnosis.

## Change

- Propagate provider errors through `_completions()`.
- Convert the error to a 502 API response in the analyze route; show it through the UI's existing error surface.
- Verify that the existing analysis and `hamartia_tag` remain unchanged after a failed call.
- Manually verify the existing `Review with Local AI` action on another computer, first with a text-only question and then with an image question; do not add a new probe endpoint.

## Limits and acceptance

- The automated test exercises a provider error using a fake `OpenAIError`; it does not call a real local model or endpoint.
- The test/benchmark does not measure the prompt, model output, quality, inference latency, or resource usage.
- Successful-call behavior, the Council schema, and image payload are unchanged.
- For a fake provider error, the API returns 502; the saved question/tag stays the same; the local model remains outside the test and benchmark.
