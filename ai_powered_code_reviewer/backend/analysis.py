import ast
from collections.abc import Iterable


Issue = dict[str, int | str]


def _is_zero_literal(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is False or (
            isinstance(node.value, (int, float, complex)) and node.value == 0
        )
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float, complex))
        and node.operand.value == 0
    )


def syntax_issue(error: SyntaxError) -> Issue:
    message = error.msg or "Invalid Python syntax."
    return {
        "severity": "High",
        "title": "Python syntax error",
        "line": error.lineno or 1,
        "category": "Syntax",
        "description": f"Python could not parse this code: {message}",
        "fix": "Correct the syntax at or near this line, then run the analysis again.",
    }


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _is_mutable_default(node: ast.expr) -> bool:
    return isinstance(node, (ast.List, ast.Dict, ast.Set)) or (
        isinstance(node, ast.Call)
        and _call_name(node.func) in {"list", "dict", "set"}
        and not node.args
        and not node.keywords
    )


class _FunctionNameUsage(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bindings: dict[str, int] = {}
        self.references: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def _bind(self, name: str, line: int) -> None:
        self.bindings.setdefault(name, line)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.references.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self._bind(node.id, node.lineno)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._bind(alias.asname or alias.name.split(".", 1)[0], node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self._bind(alias.asname or alias.name, node.lineno)

    def visit_Global(self, node: ast.Global) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_nested_scope_declaration(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_nested_scope_declaration(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._bind(node.name, node.lineno)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, (node.key, node.value))

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type:
            self.visit(node.type)
        if node.name:
            self._bind(node.name, node.lineno)
        for statement in node.body:
            self.visit(statement)

    def _visit_nested_scope_declaration(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self._bind(node.name, node.lineno)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation:
                self.visit(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self.visit(node.args.kwarg.annotation)
        if node.returns:
            self.visit(node.returns)

    def _visit_comprehension(
        self,
        generators: list[ast.comprehension],
        expressions: tuple[ast.expr, ...],
    ) -> None:
        for generator in generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for expression in expressions:
            self.visit(expression)


class _LoadNames(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)


class _Analyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self._seen: set[tuple[str, int, str]] = set()

    def add_issue(
        self,
        node: ast.AST,
        *,
        severity: str,
        title: str,
        category: str,
        description: str,
        fix: str,
    ) -> None:
        line = getattr(node, "lineno", 1)
        key = (title, line, description)
        if key in self._seen:
            return
        self._seen.add(key)
        self.issues.append(
            {
                "severity": severity,
                "title": title,
                "line": line,
                "category": category,
                "description": description,
                "fix": fix,
            }
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in {"eval", "exec"}:
            self.add_issue(
                node,
                severity="High",
                title="Dynamic code execution",
                category="Security",
                description=f"`{name}()` executes code supplied as a value; untrusted input can run arbitrary Python.",
                fix="Avoid dynamic execution, or strictly validate and constrain the input before execution.",
            )
        elif name == "os.system":
            self.add_issue(
                node,
                severity="High",
                title="Shell command execution",
                category="Security",
                description="`os.system()` passes a command to a shell, so interpolated or untrusted values can enable command injection.",
                fix="Prefer a subprocess API with an argument list and avoid `shell=True`.",
            )
        elif name in {
            "subprocess.run",
            "subprocess.call",
            "subprocess.Popen",
            "subprocess.check_call",
            "subprocess.check_output",
        } and any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            self.add_issue(
                node,
                severity="High",
                title="Shell execution enabled",
                category="Security",
                description="This subprocess call enables a shell; untrusted command content may allow command injection.",
                fix="Pass the executable and arguments as a list and remove `shell=True`.",
            )
        elif name in {"pickle.load", "pickle.loads"}:
            self.add_issue(
                node,
                severity="High",
                title="Unsafe deserialization",
                category="Security",
                description="Unpickling untrusted data can execute attacker-controlled code.",
                fix="Only unpickle trusted data; use a data-only format such as JSON for untrusted input.",
            )
        elif name == "yaml.load" and not any(
            keyword.arg == "Loader"
            and _call_name(keyword.value)
            in {"SafeLoader", "CSafeLoader", "yaml.SafeLoader", "yaml.CSafeLoader"}
            for keyword in node.keywords
        ):
            self.add_issue(
                node,
                severity="High",
                title="Potentially unsafe YAML loading",
                category="Security",
                description="`yaml.load()` without a safe loader can construct arbitrary Python objects from the input.",
                fix="Use `yaml.safe_load()` or pass `yaml.SafeLoader` explicitly.",
            )

        if name == "divide" and len(node.args) > 1 and _is_zero_literal(node.args[1]):
            self.add_issue(
                node,
                severity="High",
                title="Division by zero",
                category="Bug",
                description="The second argument passed to `divide()` is the literal zero, which can raise `ZeroDivisionError`.",
                fix="Check the divisor before calling `divide()` and handle the zero case.",
            )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and _is_zero_literal(
            node.right
        ):
            self.add_issue(
                node,
                severity="High",
                title="Division by zero",
                category="Bug",
                description="The divisor is the literal zero, which raises `ZeroDivisionError` when this expression runs.",
                fix="Check the divisor before this operation and handle the zero case.",
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if (
            isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            self.add_issue(
                node,
                severity="Medium",
                title="Dictionary key may be missing",
                category="Reliability",
                description=f"Direct lookup of `{node.slice.value}` on `{node.value.id}` raises `KeyError` if the key is absent.",
                fix=f'Use `{node.value.id}.get("{node.slice.value}")` or validate the key before accessing it.',
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        for index, operator in enumerate(node.ops):
            left, right = operands[index], operands[index + 1]
            if isinstance(operator, (ast.Eq, ast.NotEq)) and (
                _is_none(left) or _is_none(right)
            ):
                self.add_issue(
                    node,
                    severity="Low",
                    title="Use identity comparison for None",
                    category="Code quality",
                    description="Equality comparison with `None` can invoke custom equality behavior and is not the standard null check.",
                    fix="Use `is None` or `is not None`.",
                )
            elif isinstance(operator, (ast.Is, ast.IsNot)) and (
                isinstance(left, ast.Constant) and left.value is not None
                or isinstance(right, ast.Constant) and right.value is not None
            ):
                self.add_issue(
                    node,
                    severity="Medium",
                    title="Identity comparison with a literal",
                    category="Bug",
                    description="Object identity is not a reliable way to compare values such as numbers, strings, or booleans.",
                    fix="Use `==` or `!=` to compare values; reserve `is` for singleton checks such as `None`.",
                )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add_issue(
                node,
                severity="Medium",
                title="Bare exception handler",
                category="Reliability",
                description="A bare `except` catches `BaseException`, including interrupts and exit signals, and can hide unrelated failures.",
                fix="Catch the specific exception types the handler can recover from.",
            )
        elif any(isinstance(statement, ast.Pass) for statement in node.body):
            self.add_issue(
                node,
                severity="Medium",
                title="Exception silently ignored",
                category="Reliability",
                description="This exception handler discards the caught failure, making errors difficult to detect and diagnose.",
                fix="Handle the exception explicitly or log it with enough context.",
            )
        self.generic_visit(node)

    def _check_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        defaults = [*node.args.defaults, *node.args.kw_defaults]
        if any(default is not None and _is_mutable_default(default) for default in defaults):
            self.add_issue(
                node,
                severity="Medium",
                title="Mutable default argument",
                category="Bug",
                description="This function creates a mutable default once, so changes can persist between calls.",
                fix="Use `None` as the default and create a new list, dictionary, or set inside the function.",
            )

        usage = _FunctionNameUsage()
        for statement in node.body:
            usage.visit(statement)

        nested_loads = _LoadNames()
        for statement in node.body:
            for child in ast.walk(statement):
                if child is not statement and isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
                ):
                    nested_loads.visit(child)
        references = usage.references | (nested_loads.names & usage.bindings.keys())
        for name, line in usage.bindings.items():
            if (
                name not in references
                and name not in usage.nonlocal_names
                and not name.startswith("_")
            ):
                self.add_issue(
                    _LineNode(line),
                    severity="Low",
                    title="Unused local variable",
                    category="Code quality",
                    description=f"`{name}` is assigned in this function but never read.",
                    fix=f"Remove `{name}` if it is unnecessary, or use it where the result is needed.",
                )

    def check_module_imports(self, tree: ast.Module) -> None:
        loaded_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".", 1)[0]
                    if name not in loaded_names and not name.startswith("_"):
                        self.add_issue(
                            _LineNode(node.lineno),
                            severity="Low",
                            title="Unused import",
                            category="Code quality",
                            description=f"`{name}` is imported but never referenced.",
                            fix=f"Remove the unused `{name}` import.",
                        )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if (
                        alias.name != "*"
                        and name not in loaded_names
                        and not name.startswith("_")
                    ):
                        self.add_issue(
                            _LineNode(node.lineno),
                            severity="Low",
                            title="Unused import",
                            category="Code quality",
                            description=f"`{name}` is imported but never referenced.",
                            fix=f"Remove the unused `{name}` import.",
                        )

    def check_unreachable_statements(self, statements: Iterable[ast.stmt]) -> None:
        terminated = False
        for statement in statements:
            if terminated:
                self.add_issue(
                    statement,
                    severity="Medium",
                    title="Unreachable statement",
                    category="Bug",
                    description="This statement follows an unconditional `return`, `raise`, `break`, or `continue` in the same block and will not run.",
                    fix="Remove the unreachable code or move it before the control-flow statement.",
                )
            if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminated = True
            elif isinstance(statement, ast.If) and statement.orelse:
                terminated = terminated or (
                    _block_terminates(statement.body)
                    and _block_terminates(statement.orelse)
                )


class _LineNode(ast.AST):
    def __init__(self, line: int) -> None:
        self.lineno = line


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _block_terminates(statements: list[ast.stmt]) -> bool:
    if not statements:
        return False
    final = statements[-1]
    return isinstance(final, (ast.Return, ast.Raise, ast.Break, ast.Continue)) or (
        isinstance(final, ast.If)
        and bool(final.orelse)
        and _block_terminates(final.body)
        and _block_terminates(final.orelse)
    )


def analyze_tree(tree: ast.Module) -> list[Issue]:
    analyzer = _Analyzer()
    analyzer.check_module_imports(tree)
    analyzer.visit(tree)

    scopes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    undocumented = [node for node in scopes if ast.get_docstring(node) is None]
    if undocumented:
        analyzer.add_issue(
            min(undocumented, key=lambda node: (node.lineno, node.col_offset)),
            severity="Low",
            title="Consider adding documentation",
            category="Maintainability",
            description="A docstring can explain the purpose, expected inputs, and output of this scope.",
            fix="Add a concise docstring inside the function, async function, or class definition.",
        )
    elif not scopes and not ast.get_docstring(tree):
        analyzer.add_issue(
            tree.body[0] if tree.body else _LineNode(1),
            severity="Low",
            title="Consider adding documentation",
            category="Maintainability",
            description="A module docstring can describe the purpose of this code.",
            fix="Add a concise module docstring at the beginning of the file.",
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            analyzer.check_unreachable_statements(node.body)
        elif isinstance(node, ast.If):
            analyzer.check_unreachable_statements(node.body)
            analyzer.check_unreachable_statements(node.orelse)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            analyzer.check_unreachable_statements(node.body)
        elif isinstance(node, ast.With):
            analyzer.check_unreachable_statements(node.body)
        elif isinstance(node, ast.Try):
            analyzer.check_unreachable_statements(node.body)
            analyzer.check_unreachable_statements(node.orelse)
            analyzer.check_unreachable_statements(node.finalbody)
        elif isinstance(node, ast.ExceptHandler):
            analyzer.check_unreachable_statements(node.body)

    return sorted(
        analyzer.issues,
        key=lambda issue: (int(issue["line"]), str(issue["title"])),
    )
