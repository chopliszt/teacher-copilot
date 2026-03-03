# Contributing to TeacherPilot

Thank you for contributing to TeacherPilot! To maintain code quality and consistency, please follow these guidelines.

## Python Coding Standards

### 🐍 Python Version & Typing
- **Python Version**: Use Python 3.13+ syntax and features
- **Type Hints**: All functions must have explicit return type annotations
- **Variable Typing**: Use type hints for function parameters and variables where appropriate

### 📝 Code Style & Readability
- **PEP 8 Compliance**: Follow [PEP 8](https://peps.python.org/pep-0008/) style guide strictly
- **List Comprehensions**: Avoid complex list comprehensions for better readability
- **Line Length**: Maximum 88 characters per line (PEP 8 recommendation)
- **Docstrings**: Use Google-style docstrings for all public functions and classes

### 🔤 Naming Conventions
- **Variables & Functions**: `snake_case` (e.g., `student_name`, `calculate_grade`)
- **Classes**: `PascalCase` (e.g., `ClassroomManager`, `StudentProfile`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_STUDENTS`, `API_TIMEOUT`)
- **Private Members**: `_single_leading_underscore` for protected, `__double_leading` for private
- **Meaningful Names**: Use descriptive, self-documenting names (avoid `x`, `data`, `temp`)

### 🧩 Code Structure
- **Function Length**: Keep functions short (ideally < 20 lines)
- **Single Responsibility**: Each function should do one thing well
- **Avoid Nesting**: Limit nesting levels (use early returns, guard clauses)
- **Error Handling**: Use specific exception types, not bare `except:`

### 🔧 Type-Specific Guidelines
- **Collections**: Use native Python types (`list`, `dict`, `set`, etc.) instead of `typing.List`, `typing.Dict`
- **Optional Types**: Use `typing.Optional` or the `|` union syntax (e.g., `str | None`)
- **Complex Types**: Use `typing` module for complex types (`Callable`, `Generator`, etc.)
- **Imports**: Group imports (standard library, third-party, local) with blank lines between
- **Relative Imports**: Use explicit relative imports for local modules
- **Future Annotations**: Use `from __future__ import annotations` for forward references

## JavaScript/TypeScript Standards (Frontend)

> **Visual Guidelines:** All UI changes must follow [`DESIGN.md`](./DESIGN.md) — the app's design language document.

### 🦄 TypeScript Requirements
- **Strict Typing**: Enable strict TypeScript compilation
- **Interface Naming**: `PascalCase` without prefix (e.g., `PriorityListProps`, `MarimbaWidgetProps`)
- **Type Aliases**: Use for unions and complex types (e.g., `type MarimbaState = 'idle' | 'listening' | ...`)
- **Zod Schemas**: All API responses are validated with Zod schemas in `lib/api/client.ts`

### 📐 Function Style
- **Prefer `function` declarations** over arrow functions for components and named functions:
  ```tsx
  // ✅ Good — clear, hoisted, readable
  function PriorityCard({ priority, rank }: PriorityCardProps) { ... }

  // ❌ Avoid — harder to scan, not hoisted
  const PriorityCard = ({ priority, rank }: PriorityCardProps) => { ... }
  ```
- Arrow functions are acceptable for **inline callbacks** (e.g., `.map()`, `.filter()`, event handlers).

### 🎨 React Specific
- **Component Naming**: `PascalCase` for components (e.g., `ClassroomCard.tsx`)
- **One component per file** for top-level components. Small helper components (like `EmptyState`, `ThinkingDots`) can live in the same file when they are only used there.
- **Hooks**: Use custom hooks with `use` prefix (e.g., `useVoice`, `useSchedule`)
- **Props**: Always type component props using interfaces, named `ComponentNameProps`
- **State Management**: Use React's `useState` + `useCallback`. No external state library needed.
- **Data Fetching**: Use `@tanstack/react-query` for all API calls. Never `fetch` directly in components.

### 🎯 Voice Actions & Skills
When adding a new Marimba "skill" (voice-triggered action), you must update **three files**:
1. **Backend prompt** (`backend/prompts/voice.py`) — teach Mistral the new action type and JSON shape
2. **Frontend schema** (`frontend/src/lib/api/client.ts`) — add the new type to `VoiceActionSchema`
3. **Frontend handler** (`frontend/src/App.tsx`) — handle the new action in `handleVoiceAction`

After adding a skill, add eval cases in `backend/tests/evals/run_voice_evals.py` and run them.

### 🖼️ Icons & Visual Elements
- **Never use emojis as UI controls** — see [`DESIGN.md`](./DESIGN.md) for details
- Use **inline SVGs** with `stroke="currentColor"`, `strokeLinecap="round"`, `strokeLinejoin="round"`
- The only allowed emoji is 🦊 (Marimba's avatar identity)

### 🔊 Audio Feedback
- Use the **Web Audio API** to generate tones for UI feedback — never load external audio files for blips and clicks
- Keep sounds subtle: short duration (80–150ms), low volume (0.08–0.15)
- **Note:** This rule is for UI sounds only. Content audio (meeting recordings, TTS playback) uses real audio files/streams.

## Git & Commit Guidelines

### 🌱 Branch Naming
- `feature/[issue-number]-description` (e.g., `feature/42-classroom-card`)
- `bugfix/[issue-number]-description` (e.g., `bugfix/17-email-triage`)
- `docs/[topic]` (e.g., `docs/api-endpoints`)

### 📝 Commit Messages
- **Format**: `[type]: short description` (e.g., `feat: implement 3 bullets algorithm`)
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- **Body**: Include detailed explanation if needed, referencing issues
- **Scope**: Optional scope in parentheses (e.g., `feat(backend): add student API`)

### 🔗 Issue Tracking
- Reference GitHub issues in commits (e.g., `Fixes #42`, `Related to #17`)
- Keep issues updated with progress

## Testing Standards

### 🧪 Testing Requirements
- **Coverage**: Aim for 80%+ test coverage
- **Unit Tests**: For all non-UI logic
- **Integration Tests**: For API endpoints and component interactions
- **E2E Tests**: For critical user flows

### 📌 Test Naming
- `test_[module]_[function]_[scenario].py` (e.g., `test_student_get_grades.py`)
- Use `describe`/`it` pattern for JavaScript tests

## Documentation

### 📚 Code Documentation
- **Public APIs**: Must have comprehensive docstrings
- **Complex Logic**: Add inline comments explaining "why", not "what"
- **TODO Comments**: Use `TODO(username): description` format

### 📖 Project Documentation
- Keep `README.md` updated with major changes
- Update `docs/` directory for significant features
- Maintain API documentation (OpenAPI/Swagger for backend)

## Development Workflow

1. **Create Issue**: For any new feature or bug
2. **Create Branch**: From latest `main` branch
3. **Implement Changes**: Following these guidelines
4. **Write Tests**: Ensure adequate coverage
5. **Update Documentation**: As needed
6. **Create PR**: With clear description and issue references
7. **Request Review**: From at least one other team member
8. **Address Feedback**: Make requested changes
9. **Merge**: Once approved

## Code Review Checklist

- [ ] Follows Python/JavaScript coding standards
- [ ] Has appropriate type hints/annotations
- [ ] Includes comprehensive tests
- [ ] Has clear, meaningful naming
- [ ] Follows single responsibility principle
- [ ] Includes proper error handling
- [ ] Has appropriate documentation
- [ ] Passes all existing tests
- [ ] Maintains or improves test coverage

## Tools & Configuration

### 🛠 Recommended Tools
- **Python**: `black`, `isort`, `mypy`, `pylint`, `pytest`
- **JavaScript**: `ESLint`, `Prettier`, `TypeScript`
- **Git**: `pre-commit` hooks for automatic formatting

### 📦 Recommended VSCode Extensions
- Python: `ms-python.python`, `ms-python.pylint`, `ms-python.black-formatter`
- TypeScript: `vscode.typescript`, `dbaeumer.vscode-eslint`
- General: `editorconfig.editorconfig`, `esbenp.prettier-vscode`

## Continuous Integration

All pull requests must pass:
- Code formatting checks
- Linting
- Type checking
- Unit tests
- Integration tests (where applicable)

By following these guidelines, we ensure TeacherPilot maintains high code quality, readability, and maintainability throughout its development lifecycle.

**Happy Coding!** 🚀