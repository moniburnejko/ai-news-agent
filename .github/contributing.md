## contributing to AI news agent
thank you for your interest in contributing to ai news agent!

table of contents
- how to get help
- ways to contribute
- getting the code
- branching & workflow
- coding standards
- tests
- documentation
- reporting security issues
- communication & community

how to get help
- check the README and existing issues first - your question may already be answered.
- if you need help or want to discuss a non-urgent design decision, open an issue or join the discussion on the repository.

ways to contribute
- report a bug (use bug_report.md template)
- propose a feature (use feature_request.md template)
- improve documentation (typos, clarifications, examples)
- add or improve tests
- refactor code for readability and maintainability
- add ci, linting, or release automation
- provide example scripts or demos

getting the code
1. fork the repository.
2. clone your fork:  
   git clone https://github.com/<your-username>/ai-news-agent.git
3. create a branch for your change:  
   git checkout -b feat/short-description or git checkout -b fix/short-description

branching & workflow
- use descriptive branch names: feat/<short-desc>, fix/<short-desc>, docs/<short-desc>, chore/<short-desc>.
- keep changes scoped to the branch and focused on a single logical change.
- open a pull request against the `main` branch in the main repository.
- provide a clear pr description, linking related issues and describing the motivation and behavior change.
- make sure ci passes and address review feedback in a timely manner.

coding standards
- follow pep 8 for python code.
- use type hints for public functions and methods where practical.
- keep functions small and single-responsibility.
- add docstrings for modules, classes, and public functions.

tests
- add unit tests for new features and bug fixes.

documentation
- update readme for any changes that affect usage or configuration.
- add examples in the examples/ directory when introducing new features.
- keep usage examples minimal and copy-pastable.

pull requests
- link to the issue the pr resolves (if applicable) and use a descriptive title.
- include a summary of changes, rationale, and screenshots or sample outputs when appropriate.
- break very large changes into smaller prs when feasible.
- rebase or merge latest `main` to resolve conflicts prior to merging.

commit messages
- use clear, concise commit messages.
- prefer present-tense, short summary line, and (optionally) a longer description in the body.
- example: "fix: handle invalid rss items when parsing feeds"

security & sensitive information
- never commit api keys, tokens, or any other secrets to the repository.
- use environment variables or secret stores for credentials.

code of conduct
- this project follows a code of conduct. by participating, you agree to the terms in code_of_conduct.md.

thank you for helping make ai news agent better!

📅 *last updated: october 2025*  
👩‍💻 *author: Monika Burnejko*
