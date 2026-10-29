### 20-question question set (strict score, 95% Wilson interval)

| Model | Setting | Correct | Interval | vs none: only none right (b) | only setting right (c) | exact McNemar p |
|---|---|---|---|---|---|---|
| qwen3.5:4b | none | 13/20 | 43%-82% | | | |
| qwen3.5:4b | validate | 13/20 | 43%-82% | 0 | 0 | 1.000 |
| qwen3.5:4b | readonly | 13/20 | 43%-82% | 0 | 0 | 1.000 |
| qwen3.5:4b | schema_filter | 11/20 | 34%-74% | 3 | 1 | 0.625 |
| qwen3.5:4b | all_three | 11/20 | 34%-74% | 3 | 1 | 0.625 |
| qwen3.5:4b | label_rule | 12/20 | 39%-78% | 3 | 2 | 1.000 |
| qwen3.5:4b | fewshot | 16/20 | 58%-92% | 2 | 5 | 0.453 |
| qwen3.5:9b | none | 17/20 | 64%-95% | | | |
| qwen3.5:9b | validate | 17/20 | 64%-95% | 0 | 0 | 1.000 |
| qwen3.5:9b | readonly | 17/20 | 64%-95% | 0 | 0 | 1.000 |
| qwen3.5:9b | schema_filter | 15/20 | 53%-89% | 2 | 0 | 0.500 |
| qwen3.5:9b | all_three | 15/20 | 53%-89% | 2 | 0 | 0.500 |
| qwen3.5:9b | label_rule | 16/20 | 58%-92% | 2 | 1 | 1.000 |
| qwen3.5:9b | fewshot | 17/20 | 64%-95% | 2 | 2 | 1.000 |
| gemma3:4b | none | 13/20 | 43%-82% | | | |
| gemma3:4b | validate | 13/20 | 43%-82% | 0 | 0 | 1.000 |
| gemma3:4b | readonly | 13/20 | 43%-82% | 0 | 0 | 1.000 |
| gemma3:4b | schema_filter | 13/20 | 43%-82% | 2 | 2 | 1.000 |
| gemma3:4b | all_three | 13/20 | 43%-82% | 2 | 2 | 1.000 |
| gemma3:4b | label_rule | 10/20 | 30%-70% | 3 | 0 | 0.250 |
| gemma3:4b | fewshot | 18/20 | 70%-97% | 0 | 5 | 0.062 |
| gemma4:e4b | none | 16/20 | 58%-92% | | | |
| gemma4:e4b | validate | 16/20 | 58%-92% | 0 | 0 | 1.000 |
| gemma4:e4b | readonly | 16/20 | 58%-92% | 0 | 0 | 1.000 |
| gemma4:e4b | schema_filter | 16/20 | 58%-92% | 0 | 0 | 1.000 |
| gemma4:e4b | all_three | 16/20 | 58%-92% | 0 | 0 | 1.000 |
| gemma4:e4b | label_rule | 16/20 | 58%-92% | 0 | 0 | 1.000 |
| gemma4:e4b | fewshot | 17/20 | 64%-95% | 0 | 1 | 1.000 |

24 paired comparisons against 'none'; 0 with p < 0.05 (uncorrected). With n = 20 questions per cell, a difference of one or two questions cannot be told from noise.

### held-out (13 questions) question set (strict score, 95% Wilson interval)

| Model | Setting | Correct | Interval | vs none: only none right (b) | only setting right (c) | exact McNemar p |
|---|---|---|---|---|---|---|
| qwen3.5:4b | none | 8/13 | 36%-82% | | | |
| qwen3.5:4b | label_rule | 9/13 | 42%-87% | 1 | 2 | 1.000 |
| qwen3.5:4b | fewshot | 10/13 | 50%-92% | 1 | 3 | 0.625 |
| qwen3.5:9b | none | 11/13 | 58%-96% | | | |
| qwen3.5:9b | label_rule | 11/13 | 58%-96% | 1 | 1 | 1.000 |
| qwen3.5:9b | fewshot | 11/13 | 58%-96% | 2 | 2 | 1.000 |
| gemma3:4b | none | 8/13 | 36%-82% | | | |
| gemma3:4b | label_rule | 7/13 | 29%-77% | 1 | 0 | 1.000 |
| gemma3:4b | fewshot | 9/13 | 42%-87% | 2 | 3 | 1.000 |
| gemma4:e4b | none | 11/13 | 58%-96% | | | |
| gemma4:e4b | label_rule | 10/13 | 50%-92% | 1 | 0 | 1.000 |
| gemma4:e4b | fewshot | 11/13 | 58%-96% | 0 | 0 | 1.000 |

8 paired comparisons against 'none'; 0 with p < 0.05 (uncorrected). With n = 13 questions per cell, a difference of one or two questions cannot be told from noise.

