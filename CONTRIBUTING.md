# Contributing to Rongle

Thank you for your interest in helping us build the future of hardware-isolated AI agents! We welcome contributions from both humans and AI agents.

## 🤝 Getting Started

1.  **Read the Docs:** Start with [docs/ONBOARDING.md](docs/ONBOARDING.md).
2.  **Fork & Clone:** Fork the repository and clone it locally.
3.  **Install Dependencies:**
    ```bash
    pip install -r rng_operator/requirements.txt
    npm install
    ```

## 🛠 Development Workflow

### Branching Strategy
We use a simplified feature branch workflow.
*   `main`: Stable, deployable code.
*   `feat/your-feature`: New features.
*   `fix/your-bug`: Bug fixes.
*   `docs/your-topic`: Documentation updates.

### Making Changes
1.  Create a new branch: `git checkout -b feat/my-awesome-feature`.
2.  Make your changes.
3.  **Run Tests:** Before committing, ensure everything passes.
    ```bash
    ./scripts/rongle test
    ```
4.  **Lint/Format:** Keep code clean.
    *   Python: `black rng_operator`
    *   JS/TS: `npm run lint` (if available)

### Submitting a PR
1.  Push your branch to your fork.
2.  Open a Pull Request against `main`.
3.  Fill out the PR template (describe changes, link issues).
4.  Wait for review!

## 🤖 AI Contributors

If you are an LLM agent attempting to modify this codebase:
1.  **MANDATORY:** Read [docs/AGENTS.md](docs/AGENTS.md).
2.  **Safety:** Never modify `rng_operator/policy_engine/guardian.py` to weaken security checks without explicit human approval.
3.  **Tests:** Always add a test case in `rng_operator/tests/` for new backend logic.

## 🐛 Reporting Bugs

Please open an Issue on GitHub with:
1.  **Steps to Reproduce.**
2.  **Expected Behavior.**
3.  **Actual Behavior.**
4.  **Logs:** Output from `scripts/rongle logs` or `/tmp/operator.log`.
5.  **Hardware:** What device are you running on? (Pi Zero, PC, Pixel, etc.)

## 📜 License

This project is licensed under the MIT License - see the `LICENSE` file for details.
