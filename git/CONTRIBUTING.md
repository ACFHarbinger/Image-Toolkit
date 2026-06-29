# Contributing to Image-Toolkit

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed%20by-uv-261230.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![MyPy](https://img.shields.io/badge/MyPy-checked-2f4f4f.svg)](https://mypy-lang.org/)
[![pytest](https://img.shields.io/badge/pytest-testing-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Coverage](https://img.shields.io/badge/coverage-60%25-green.svg)](https://coverage.readthedocs.io/)
[![CI](https://github.com/ACFHarbinger/Image-Toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ACFHarbinger/Image-Toolkit/actions/workflows/ci.yml)

> **Version**: 2.0
> **Last Updated**: January 2026

Thank you for your interest in contributing to Image-Toolkit! This document provides comprehensive guidelines for contributing to the project, from code style to the pull request process.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Development Setup](#2-development-setup)
3. [Code Style Guidelines](#3-code-style-guidelines)
4. [Git Workflow](#4-git-workflow)
5. [Pull Request Process](#5-pull-request-process)
6. [Testing Requirements](#6-testing-requirements)
7. [Documentation Standards](#7-documentation-standards)
8. [Architecture Guidelines](#8-architecture-guidelines)
9. [Adding New Features](#9-adding-new-features)
10. [Issue Reporting](#10-issue-reporting)
11. [Code Review Guidelines](#11-code-review-guidelines)
12. [Community Standards](#12-community-standards)

---

## 1. Getting Started

### 1.1 Prerequisites

Before contributing, ensure you have:

- Python 3.11 or higher
- Git
- Access to a CUDA-capable GPU (recommended for testing)
- Basic understanding of:
  - Deep Reinforcement Learning concepts
  - Vehicle Routing Problems
  - PyTorch and Graph Neural Networks

### 1.2 Finding Issues to Work On

1. **Good First Issues**: Look for issues labeled `good-first-issue`
2. **Help Wanted**: Issues labeled `help-wanted` need community support
3. **Bug Fixes**: Issues labeled `bug` are always appreciated
4. **Feature Requests**: Issues labeled `enhancement` for new features

### 1.3 Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

---

## 2. Development Setup

### 2.1 Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/ACFHarbinger/Image-Toolkit.git
cd Image-Toolkit

# Add upstream remote
git remote add upstream https://github.com/ACFPeacekeeper/Image-Toolkit.git
```

### 2.2 Environment Setup

We use `uv` for dependency management:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Verify installation
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### 2.3 Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually (optional)
pre-commit run --all-files
```

### 2.4 IDE Configuration

#### VS Code

Recommended extensions:

- Python (Microsoft)
- Pylance
- Ruff
- Git Lens

Recommended settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "ruff.lint.args": ["--config=pyproject.toml"]
}
```

#### PyCharm

1. Set interpreter to `.venv/bin/python`
2. Enable Ruff integration via plugin
3. Configure Black/Ruff as formatter

---

## 3. Code Style Guidelines

### 3.1 Python Style

We follow [PEP 8](https://pep8.org/) with the following specifics:

| Rule        | Specification                  |
| ----------- | ------------------------------ |
| Line length | 120 characters                 |
| Indentation | 4 spaces (no tabs)             |
| Quotes      | Double quotes for strings      |
| Imports     | Sorted with `isort` (via Ruff) |

### 3.2 Linting and Formatting

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type checking (non-blocking)
uv run mypy . || true
```

### 3.3 Import Organization

```python
# Standard library
import os
import sys
from typing import Dict, List, Optional, Tuple

# Third-party libraries
import numpy as np
import torch
import torch.nn as nn
from torch_geometric.nn import GATConv

# Local imports - absolute
from logic.src.models.modules import MultiHeadAttention
from logic.src.utils.configs.setup_utils import get_device

# Local imports - relative (within same package only)
from .encoder import GATEncoder
from ..modules import FeedForward
```

### 3.4 Type Hints

All public functions and methods **must** have type hints:

```python
# Good
def compute_route_cost(
    route: List[int],
    distance_matrix: np.ndarray,
    capacity: float = 100.0
) -> float:
    """Compute the total cost of a route."""
    total = 0.0
    for i in range(len(route) - 1):
        total += distance_matrix[route[i], route[i + 1]]
    return total

# Bad - missing type hints
def compute_route_cost(route, distance_matrix, capacity=100.0):
    ...
```

### 3.5 Docstrings

Use Google-style docstrings:

```python
def solve_vrpp(
    distances: np.ndarray,
    wastes: np.ndarray,
    capacity: float
) -> Tuple[List[List[int]], float, float]:
    """
    Solve the Vehicle Routing Problem with Profits.

    This function finds routes that maximize profit minus cost while
    respecting vehicle capacity constraints.

    Args:
        distances: Pairwise distance matrix of shape (n, n).
        wastes: Reward for visiting each node of shape (n,).
        capacity: Maximum vehicle capacity.

    Returns:
        A tuple containing:
            - routes: List of routes, each a list of node indices.
            - total_profit: Sum of collected wastes.
            - total_cost: Total distance traveled.

    Raises:
        ValueError: If distances matrix is not square.
        ValueError: If wastes has negative values.

    Example:
        >>> distances = np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]])
        >>> wastes = np.array([0, 10, 8])
        >>> routes, profit, cost = solve_vrpp(distances, wastes, 10)
    """
    ...
```

### 3.6 Naming Conventions

| Type      | Convention         | Example                            |
| --------- | ------------------ | ---------------------------------- |
| Classes   | PascalCase         | `AttentionModel`, `GATEncoder`     |
| Functions | snake_case         | `compute_route_cost`, `get_device` |
| Variables | snake_case         | `batch_size`, `learning_rate`      |
| Constants | UPPER_SNAKE_CASE   | `MAX_WASTE`, `DEFAULT_CAPACITY`    |
| Private   | Leading underscore | `_internal_method`, `_cache`       |
| Protected | Single underscore  | `_validate_input`                  |

---

## 4. Git Workflow

### 4.1 Branch Naming

```
<type>/<short-description>
```

| Type        | Purpose                  |
| ----------- | ------------------------ |
| `feature/`  | New features             |
| `fix/`      | Bug fixes                |
| `docs/`     | Documentation changes    |
| `refactor/` | Code refactoring         |
| `test/`     | Test additions/changes   |
| `ci/`       | CI/CD changes            |
| `perf/`     | Performance improvements |

Examples:

```
feature/add-pomo-baseline
fix/cuda-memory-leak
docs/update-architecture
refactor/simplify-decoder
```

### 4.2 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `perf`: Performance improvement
- `ci`: CI/CD changes
- `chore`: Maintenance

**Examples:**

```
feat(models): add POMO baseline support

- Implement POMO baseline in reinforce_baselines.py
- Add configuration options in train_parser.py
- Update documentation

Closes #123
```

```
fix(simulator): resolve memory leak in bins collection

The Bins.collect() method was not properly releasing
references to collected waste data.

Fixes #456
```

### 4.3 Keeping Branch Updated

```bash
# Fetch upstream changes
git fetch upstream

# Rebase your branch on main
git checkout your-branch
git rebase upstream/main

# Force push if needed (for PR branches only)
git push --force-with-lease origin your-branch
```

---

## 5. Pull Request Process

### 5.1 Before Opening a PR

1. **Ensure tests pass**:

   ```bash
   python main.py test_suite
   ```

2. **Check code style**:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```

3. **Update documentation** if needed

4. **Add/update tests** for new functionality

### 5.2 PR Template

When opening a PR, include:

```markdown
## Description

Brief description of the changes.

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring (no functional changes)

## Related Issues

Closes #<issue_number>

## Changes Made

- Change 1
- Change 2
- Change 3

## Testing

Describe the tests you ran:

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing performed

## Screenshots (if applicable)

Add screenshots for UI changes.

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code where necessary
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
```

### 5.3 PR Size Guidelines

| Size | Lines Changed | Description                 |
| ---- | ------------- | --------------------------- |
| XS   | < 50          | Typo fixes, small tweaks    |
| S    | 50-200        | Single feature, bug fix     |
| M    | 200-500       | Larger feature, refactoring |
| L    | 500-1000      | Major feature               |
| XL   | > 1000        | Split into smaller PRs      |

**Prefer smaller PRs** - they're easier to review and less likely to introduce bugs.

### 5.4 Review Process

1. **Automated checks** must pass (CI, linting, tests)
2. **At least one approval** required
3. **Address all comments** before merging
4. **Squash commits** if requested

---

## 6. Testing Requirements

### 6.1 Test Coverage

- **Minimum coverage**: 60%
- **Target coverage**: 80%
- **New code**: Must have tests

### 6.2 Running Tests

```bash
# All tests
python main.py test_suite

# Specific module
python main.py test_suite --module test_models

# With coverage
uv run pytest --cov=logic/src --cov-report=html

# Fast tests only
uv run pytest -m "not slow"
```

### 6.3 Writing Tests

```python
# logic/test/test_my_feature.py
import pytest
import torch
from logic.src.models.my_model import MyModel

class TestMyModel:
    """Tests for MyModel class."""

    @pytest.fixture
    def model(self):
        """Create a model instance for testing."""
        return MyModel(problem='vrpp', embed_dim=64)

    @pytest.fixture
    def sample_batch(self):
        """Create a sample batch for testing."""
        return {
            'loc': torch.rand(4, 20, 2),
            'waste': torch.rand(4, 20),
            'depot': torch.rand(4, 2)
        }

    def test_forward_pass_shape(self, model, sample_batch):
        """Test that forward pass returns correct shapes."""
        cost, log_p, pi = model(sample_batch, return_pi=True)

        assert cost.shape == (4,)
        assert log_p.shape == (4,)
        assert pi.shape[0] == 4

    def test_forward_pass_no_nan(self, model, sample_batch):
        """Test that forward pass produces no NaN values."""
        cost, log_p, _ = model(sample_batch)

        assert not torch.isnan(cost).any()
        assert not torch.isnan(log_p).any()

    @pytest.mark.slow
    def test_training_step(self, model, sample_batch):
        """Test a full training step."""
        optimizer = torch.optim.Adam(model.parameters())

        cost, log_p, _ = model(sample_batch)
        loss = (cost * log_p).mean()

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # Check gradients are not None
        for param in model.parameters():
            if param.requires_grad:
                assert param.grad is not None
```

### 6.4 Test Markers

| Marker                     | Usage                   |
| -------------------------- | ----------------------- |
| `@pytest.mark.slow`        | Long-running tests      |
| `@pytest.mark.fast`        | Quick unit tests        |
| `@pytest.mark.integration` | Integration tests       |
| `@pytest.mark.gpu`         | Tests requiring CUDA    |
| `@pytest.mark.train`       | Training pipeline tests |

---

## 7. Documentation Standards

### 7.1 Code Documentation

Every public module, class, and function must have:

1. **Module docstring**: At the top of each file
2. **Class docstring**: Describing purpose and usage
3. **Method docstrings**: For all public methods
4. **Type hints**: On all function signatures

### 7.2 Markdown Files

| File                 | Purpose                      |
| -------------------- | ---------------------------- |
| `README.md`          | Project overview, quickstart |
| `ARCHITECTURE.md`    | System design                |
| `CONTRIBUTING.md`    | Contribution guidelines      |
| `TUTORIAL.md`        | Detailed tutorials           |
| `TROUBLESHOOTING.md` | Common issues                |

### 7.3 Updating Documentation

When your PR changes:

- **API**: Update docstrings and relevant `.md` files
- **CLI**: Update help text and usage examples
- **Architecture**: Update `ARCHITECTURE.md`
- **Setup**: Update `DEVELOPMENT.md`

---

## 8. Architecture Guidelines

### 8.1 Layer Separation

```
GUI Layer (gui/) ──depends on──▶ Logic Layer (logic/)
                                       │
                                       ▼
                            External Dependencies
```

**Rules:**

- `logic/` must NEVER import from `gui/`
- `gui/` communicates via defined interfaces
- Shared utilities go in `logic/src/utils/`

### 8.2 Adding New Components

#### New Model

1. Create `logic/src/models/my_model.py`
2. Register in `logic/src/models/model_factory.py`
3. Add configuration in `assets/configs/train.yaml` or relevant Hydra config
4. Write tests in `logic/test/test_models.py`

#### New Policy

1. Create `logic/src/policies/my_policy.py`
2. Implement the `Policy` interface
3. Register in `logic/src/policies/adapters.py`
4. Write tests in `logic/test/test_policies.py`

#### New Problem

1. Create `logic/src/tasks/my_problem/problem_my.py`
2. Implement `BaseProblem` interface
3. Register in `logic/src/utils/setup_utils.py`
4. Write tests in `logic/test/test_problems.py`

### 8.3 Design Patterns

Follow established patterns:

- **Factory**: For model/policy instantiation
- **Strategy**: For interchangeable algorithms
- **State**: For simulation lifecycle
- **Command**: For simulation actions
- **Mediator**: For GUI communication

---

## 9. Adding New Features

### 9.1 Feature Planning

1. **Open an issue** first to discuss the feature
2. **Get approval** from maintainers
3. **Create a design document** for large features
4. **Break into smaller PRs** if possible

### 9.2 Feature Checklist

- [ ] Implementation complete
- [ ] Unit tests added
- [ ] Integration tests added (if applicable)
- [ ] Documentation updated
- [ ] CLI/GUI updated (if applicable)
- [ ] CHANGELOG entry added
- [ ] No breaking changes (or clearly documented)

### 9.3 Example: Adding a New Encoder

```python
# 1. Create the encoder (logic/src/models/subnets/my_encoder.py)
import torch
import torch.nn as nn
from typing import Optional
from ..modules import FeedForward, Normalization

class MyEncoder(nn.Module):
    """
    My custom encoder implementation.

    Args:
        embed_dim: Dimension of node embeddings.
        n_layers: Number of encoder layers.
        n_heads: Number of attention heads.
    """

    def __init__(
        self,
        embed_dim: int = 128,
        n_layers: int = 3,
        n_heads: int = 8
    ):
        super().__init__()
        self.layers = nn.ModuleList([
            MyEncoderLayer(embed_dim, n_heads)
            for _ in range(n_layers)
        ])

    def forward(
        self,
        x: torch.Tensor,
        edge_index: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node features of shape (batch, nodes, dim).
            edge_index: Optional edge indices.

        Returns:
            Encoded node features of shape (batch, nodes, dim).
        """
        for layer in self.layers:
            x = layer(x, edge_index)
        return x


# 2. Register in model_factory.py
ENCODER_REGISTRY = {
    'gat': GATEncoder,
    'gcn': GCNEncoder,
    'my_encoder': MyEncoder,  # Add here
}


# 3. Add CLI argument in train_parser.py
parser.add_argument(
    '--encoder',
    type=str,
    default='gat',
    choices=['gat', 'gcn', 'my_encoder'],  # Add choice
    help='Encoder type'
)


# 4. Write tests (logic/test/test_subnets.py)
class TestMyEncoder:
    @pytest.fixture
    def encoder(self):
        return MyEncoder(embed_dim=64, n_layers=2)

    def test_forward_shape(self, encoder):
        x = torch.rand(4, 20, 64)
        output = encoder(x)
        assert output.shape == x.shape

    def test_forward_no_nan(self, encoder):
        x = torch.rand(4, 20, 64)
        output = encoder(x)
        assert not torch.isnan(output).any()
```

---

## 10. Issue Reporting

### 10.1 Bug Reports

Include:

- **Environment**: OS, Python version, PyTorch version, CUDA version
- **Steps to reproduce**: Minimal code to reproduce
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Stack trace**: Full error message

**Template:**

```markdown
## Environment

- OS: Ubuntu 24.04
- Python: 3.9.18
- PyTorch: 2.2.2
- CUDA: 11.8
- Commit: abc1234

## Steps to Reproduce

1. Run `uv sync`
2. Run `python main.py train_lightning model=am env.num_loc=50`
3. Wait for epoch 5

## Expected Behavior

Training should complete successfully.

## Actual Behavior

Training crashes with CUDA OOM error.

## Stack Trace
```

Traceback (most recent call last):
...
torch.cuda.OutOfMemoryError: CUDA out of memory.

```

## Additional Context
- This worked on commit xyz789
- Only happens with graph_size >= 50
```

### 10.2 Feature Requests

Include:

- **Problem**: What problem does this solve?
- **Solution**: Your proposed solution
- **Alternatives**: Other solutions considered
- **Use case**: Who would benefit?

---

## 11. Code Review Guidelines

### 11.1 For Reviewers

- **Be constructive**: Focus on the code, not the person
- **Be specific**: Explain why and suggest alternatives
- **Be timely**: Review within 2-3 business days
- **Use labels**: `nit`, `suggestion`, `blocking`

### 11.2 For Authors

- **Respond to all comments**: Even if just acknowledging
- **Ask questions**: If feedback is unclear
- **Update promptly**: Keep the PR moving
- **Request re-review**: After addressing comments

### 11.3 Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are adequate
- [ ] Documentation is updated
- [ ] No obvious bugs
- [ ] Performance is acceptable
- [ ] Security considerations addressed

---

## 12. Community Standards

### 12.1 Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- **Be respectful**: Treat everyone with respect
- **Be constructive**: Offer helpful feedback
- **Be patient**: Remember everyone was a beginner once
- **Be inclusive**: Welcome diverse perspectives

### 12.2 Getting Help

- **GitHub Discussions**: For general questions
- **GitHub Issues**: For bugs and features
- **Documentation**: Check TROUBLESHOOTING.md first

### 12.3 Recognition

All contributors are recognized:

- In the CHANGELOG for their contributions
- In release notes for significant contributions
- Through GitHub's contributor insights

---

## License

By contributing to Image-Toolkit, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing to Image-Toolkit!**
