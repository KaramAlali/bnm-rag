# Agent results on the golden set (generated)

`uv run python -m bnm_rag.agent.evaluate`, 2026-11-09, answers as of 2026-11-07. Models: deepseek/deepseek-v4.1-flash-1017 (44). Judge: z-ai/glm-5.3. Analysis: `docs/04-agent-results.md`.

| check | result |
|---|---|
| questions answered without error | 100% (44/44) |
| coverage as expected | 91% (40/44) |
| expected paragraphs cited (all questions with some) | 95% (83/87) |
| questions citing every expected paragraph | 90% (37/41) |
| draft questions saying "proposed" | 100% (3/3) |
| replies passing citation checks | 100% (44/44) |
| replies sent back at least once | 5% (2/44) |
| judge: required facts stated | 98% (99/101) |
| judge: forbidden claims made | 0% (0/28) |
| judge: faithful to cited paragraphs | 84% (37/44) |
| tool calls per question (mean) | 12.4 |
| seconds per question (mean) | 37 |

## Per question

| id | coverage (expected → got) | expected cited | must say | must not | faithful | tools | fixes |
|---|---|---|---|---|---|---:|---:|
| g01 | answered | 3/3 | 4/4 | 0 | yes | 17 | 0 |
| g02 | answered | 2/2 | 3/3 | 0 | yes | 11 | 0 |
| g03 | not_covered | - | 1/1 | 0 | yes | 6 | 0 |
| g04 | **not_covered → partial** | - | 2/2 | 0 | yes | 10 | 0 |
| g05 | answered | 3/4 | 4/4 | 0 | yes | 31 | 0 |
| g06 | answered | 3/3 | 4/4 | 0 | yes | 21 | 0 |
| g07 | answered | 2/2 | 2/2 | 0 | yes | 8 | 0 |
| g08 | answered | 2/2 | **2/3** | 0 | yes | 15 | 0 |
| g09 | answered | 2/2 | 3/3 | 0 | yes | 9 | 0 |
| g10 | answered | 2/2 | 3/3 | 0 | yes | 28 | 0 |
| g11 | **answered → partial** | 3/4 | 4/4 | 0 | yes | 29 | 0 |
| g12 | partial | 1/1 | 2/2 | 0 | yes | 10 | 1 |
| g13 | answered | 2/2 | 2/2 | 0 | **no** | 8 | 0 |
| g14 | answered | 1/1 | 1/1 | 0 | **no** | 9 | 1 |
| g15 | answered | 2/2 | 3/3 | 0 | yes | 6 | 0 |
| g16 | answered | 2/2 | 1/1 | 0 | yes | 7 | 0 |
| g17 | answered | 2/2 | 3/3 | 0 | yes | 10 | 0 |
| g18 | answered | 3/3 | **1/2** | 0 | **no** | 12 | 0 |
| g19 | answered | 3/3 | 3/3 | 0 | yes | 15 | 0 |
| g20 | answered | 2/2 | 3/3 | 0 | yes | 8 | 0 |
| g21 | answered | 3/3 | 2/2 | 0 | **no** | 8 | 0 |
| g22 | answered | 3/3 | 3/3 | 0 | yes | 24 | 0 |
| g23 | answered | 3/4 | 3/3 | 0 | yes | 10 | 0 |
| g24 | answered | 2/2 | 2/2 | 0 | yes | 9 | 0 |
| g25 | answered | 1/1 | 1/1 | 0 | yes | 8 | 0 |
| g26 | answered | 4/4 | 4/4 | 0 | yes | 7 | 0 |
| g27 | answered | 3/3 | 2/2 | 0 | yes | 6 | 0 |
| g28 | answered | 3/3 | 4/4 | 0 | **no** | 23 | 0 |
| g29 | answered | 1/1 | 2/2 | 0 | yes | 7 | 0 |
| g30 | answered | 1/2 | 2/2 | 0 | yes | 13 | 0 |
| g31 | answered | 3/3 | 3/3 | 0 | yes | 10 | 0 |
| g32 | answered | 1/1 | 1/1 | 0 | yes | 8 | 0 |
| g33 | **answered → partial** | 2/2 | 2/2 | 0 | yes | 5 | 0 |
| g34 | answered | 2/2 | 2/2 | 0 | **no** | 14 | 0 |
| g35 | **answered → partial** | 1/1 | 1/1 | 0 | yes | 22 | 0 |
| g36 | not_covered | - | 1/1 | 0 | yes | 6 | 0 |
| g37 | partial | 2/2 | 2/2 | 0 | yes | 39 | 0 |
| g38 | answered | 2/2 | 2/2 | 0 | yes | 8 | 0 |
| g39 | answered | 1/1 | 1/1 | 0 | yes | 4 | 0 |
| g40 | answered | 1/1 | 3/3 | 0 | yes | 7 | 0 |
| g41 | answered | 1/1 | 1/1 | 0 | yes | 14 | 0 |
| g42 | answered | 1/1 | 1/1 | 0 | yes | 6 | 0 |
| g43 | answered | 1/1 | 1/1 | 0 | yes | 8 | 0 |
| g44 | answered | 1/1 | 2/2 | 0 | **no** | 10 | 0 |
