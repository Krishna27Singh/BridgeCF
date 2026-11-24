# BridgeCF Roadmap

This roadmap describes possible directions, not release commitments. Ideas and implementation proposals are welcome.

## Phase 1: Deeper Codeforces Mastery

- Add contest-safe auto-lock during live rounds.
- Use wrong-answer and time-limit-exceeded submissions to tailor debugging hints.
- Visualize the interactive prerequisite DAG.
- Refresh the indexed Codeforces catalog automatically each week with GitHub Actions.

## Phase 2: Multi-Platform Expansion — AtCoder & CodeChef

- Introduce a platform-agnostic `ProblemProvider` adapter.
- Integrate the Kenkoooo AtCoder Problems API and parse bilingual AtCoder task DOM content.
- Parse CodeChef problem pages and normalize ratings across platforms.
- Support a unified user profile with multiple platform handles.

## Phase 3: Distribution & Community

- Publish to Edge Add-ons, Firefox AMO, and the Chrome Web Store.
- Add a BYOK model selector for catalogs above 1,900 problems.
- Use hint-quality feedback to improve and extend `evals/`.

## Phase 4: Scale & Reliability

- Add multi-provider LLM failover for rate limits and service errors (429/503).
- Move distributed user-history caching to Redis.
- Offer always-warm hosting for lower-latency requests.

## How to Claim a Roadmap Item

Before starting a large roadmap change, open an issue to discuss the scope and approach. Once maintainers and contributors agree on the direction, link the issue from your pull request.
