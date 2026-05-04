# LLM DOE Pipeline

A Python project for running a factorial design over LLM-based analyses using a CSV dataset and Together AI as the live backend.

## What it does

- Builds summarized artifacts from `data.csv` so the full raw file does not need to be sent to the model on every run.
- Generates a factorial design matrix with randomization and replications.
- Executes each run against Together AI or a `mock` backend.
- Stores prompts, responses, execution times, and token counts reported by the inference backend.
- Exports results in a format ready for downstream analysis in a Design of Experiments course project.

## Structure

- `doe.py`: simple CLI entry point.
- `configs/`: ready-to-use experiment configurations.
- `prompts/`: prompt templates.
- `src/llm_doe/`: pipeline logic.
- `artifacts/data/`: derived summaries from the CSV.
- `outputs/`: design matrix, rendered prompts, responses, and metrics.

## Recommended workflow

Install the runtime dependency first:

```bash
python3 -m pip install -r requirements.txt
```

1. Test the pipeline first without a live Together AI call:

```bash
python3 doe.py build-data --config configs/pilot_experiment.json
python3 doe.py build-design --config configs/pilot_experiment.json
python3 doe.py run --config configs/pilot_experiment.json
python3 doe.py summarize-results --config configs/pilot_experiment.json
```

2. When you want to use real Together AI models:

```bash
export TOGETHER_API_KEY=your-api-key
python3 doe.py run --config configs/full_factorial.json --rebuild-data --rebuild-design
```

3. When you want a one-run smoke test against Together AI:

```bash
export TOGETHER_API_KEY=your-api-key
python3 doe.py run --config configs/together_smoke.json --clean --rebuild-data --rebuild-design
python3 doe.py summarize-results --config configs/together_smoke.json
```

If your API key is stored in `.env`, `doe.py` now loads it automatically.

If you want a fresh run log instead of appending to previous outputs:

```bash
python3 doe.py run --config configs/full_factorial.json --clean
```

## What to edit before running with Together AI

- Set `TOGETHER_API_KEY` in your shell before running the live config.
- In `configs/full_factorial.json`, verify that the model strings you want are available on Together AI.
- The current live config uses `deepseek-ai/DeepSeek-V3.1`, `moonshotai/Kimi-K2.5`, and `Qwen/Qwen3.5-9B`.
- Reasoning is explicitly disabled in the live configs to keep outputs cheaper and more comparable across the three models.
- `configs/together_smoke.json` runs a single Together AI request with `deepseek-ai/DeepSeek-V3.1`.
- Adjust the number of factor levels if 405 runs are too many for an initial pass.
- Replications are configured to reuse the same treatment combinations three times.

## Included factors

- `model`
- `temperature`
- `prompt_template`
- `data_view`

## Captured output variables

- `wall_clock_seconds`
- `input_token_count`
- `output_token_count`
- `total_token_count`
- `total_duration_seconds`
- `load_duration_seconds`
- `prompt_eval_duration_seconds`
- `eval_duration_seconds`
- JSON validity of the response
- `response_schema_completeness`

## DOE suggestions for the project

- Experimental unit: one LLM analysis run on a fixed view of the dataset.
- Main factors: model, temperature, prompt, and data view.
- Replication: the configs run three replications per treatment combination.
- Possible blocking factor: execution day, machine, or batch if Ollama latency changes over time.
- A natural next factor if you want to enrich the DOE: `num_predict`, `top_p`, or prompt language.

## Tests

```bash
python3 -m unittest discover -s tests
```
