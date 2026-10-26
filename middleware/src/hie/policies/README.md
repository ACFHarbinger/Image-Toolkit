# HIE Middleware Policies (`middleware/policies/`)

The `policies` package manages Reinforcement Learning (RL) agents and automated editing decision policies designed to assist digital artists in interactive editing workflows.

## Subsystem Components

- **Interactive Brush Assistant (`policies/brush_assistant.py`):** RL agent trained via Gymnasium environments to assist with local dodging, burning, edge sharpening, and localized tone adjustments based on stroke history.
- **Global Tone & Retouching Agent (`policies/tone_agent.py`):** Automated tone, exposure, and color-grading policy that balances dynamic range and color harmony across multi-layer composites.
- **Crop & Composition Optimizer (`policies/crop_agent.py`):** Reinforcement learning policy for visual weight distribution, rule-of-thirds alignment, and automated aspect-ratio cropping.

## Architecture & Feedback Loop

- Policies interact with Gym/Gymnasium environments defined in the middleware, taking observations from image feature embeddings and layer metrics.
- Supports real-time artist feedback (reward/penalty signals) to fine-tune policy behavior live during interactive editing sessions.
