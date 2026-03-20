# Contributing to ORGA

Thank you for your interest in contributing to ORGA!

To maintain the architectural integrity of this project, we adhere to strict contribution guidelines. Please read this before opening a Pull Request.

## 🚫 The "Anti-Patch" Rule

**We do NOT accept site-specific patches.**

ORGA is a general-purpose engine. If `example.com` fails to parse, we will **not** merge a PR that adds:
- `if "example.com" in url: ...`
- A regex that only matches `example.com`'s specific footer format.
- A hardcoded override for a specific organization's category.

**Acceptable Contributions:**
- **Systemic Fixes:** "I found a bug where `NoneType` crashes the parser when `<meta>` tags are empty. Here is a fix that handles ALL empty meta tags."
- **Generic Heuristics:** "I improved the phone number regex to support E.164 formats more robustly across all sites."
- **Documentation:** Improving examples, guides, or fixing typos.

## 🛠 Development Setup

1. **Install Dependencies:**
   ```bash
   pip install -e .[dev,server]
   ```

2. **Run Tests:**
   We require 100% test passing before merging.
   ```bash
   pytest tests/
   ```

3. **Linting:**
   ```bash
   ruff check .
   ```

## 📝 Commit Messages

Please use semantic commit messages:
- `Fix: ...` for bug fixes.
- `Feat: ...` for new features.
- `Docs: ...` for documentation.
- `Refactor: ...` for code restructuring.
