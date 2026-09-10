"""Components wrapped in a higher-order call (forwardRef, memo, ...) get Function nodes."""

from pathlib import Path

from code_review_graph.parser import CodeParser


def _parse(tmp_path: Path, name: str, source: str):
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path, CodeParser().parse_file(path)


def _functions(nodes):
    return {node.name: node for node in nodes if node.kind == "Function"}


def test_forward_ref_component_gets_a_function_node(tmp_path):
    path, (nodes, edges) = _parse(
        tmp_path,
        "Button.tsx",
        "import { forwardRef } from 'react';\n"
        "export const Button = forwardRef<HTMLButtonElement, Props>((props, ref) => (\n"
        "  <button ref={ref} {...props} />\n"
        "));\n",
    )
    functions = _functions(nodes)
    assert "Button" in functions
    assert functions["Button"].line_start == 2
    assert functions["Button"].line_end == 4
    qualified = f"{path.as_posix()}::Button"
    assert any(edge.kind == "CONTAINS" and edge.target == qualified for edge in edges)


def test_nested_and_plain_wrappers_are_unwrapped(tmp_path):
    _path, (nodes, _edges) = _parse(
        tmp_path,
        "widgets.jsx",
        "export const Card = memo(forwardRef((props, ref) => <div ref={ref} />));\n"
        "export const Store = observer(() => <span />);\n"
        "export const Page = withRouter(function Page(props) { return <main />; });\n"
        "export const Fancy = styled(Base)((props) => ({ color: props.color }));\n",
    )
    assert {"Card", "Store", "Page", "Fancy"} <= set(_functions(nodes))


def test_calls_inside_a_wrapped_component_are_attributed_to_it(tmp_path):
    path, (_nodes, edges) = _parse(
        tmp_path,
        "Input.tsx",
        "export const Input = forwardRef((props, ref) => {\n"
        "  useImperativeHandle(ref, () => ({}));\n"
        "  return <input />;\n"
        "});\n",
    )
    calls = [edge for edge in edges if edge.kind == "CALLS"]
    assert any(
        edge.source == f"{path.as_posix()}::Input" and edge.target.endswith("useImperativeHandle")
        for edge in calls
    )


def test_calls_without_a_function_argument_stay_plain_variables(tmp_path):
    _path, (nodes, _edges) = _parse(
        tmp_path,
        "setup.ts",
        "const client = createClient({ url: 'x' });\n"
        "const Title = styled.h1`color: red;`;\n"
        "const total = sum(1, 2);\n",
    )
    assert not _functions(nodes)


def test_jsx_use_of_a_wrapped_component_targets_an_existing_node(tmp_path):
    button_path, (button_nodes, _button_edges) = _parse(
        tmp_path,
        "Button.tsx",
        "import { forwardRef } from 'react';\n"
        "export const Button = forwardRef((props, ref) => <button ref={ref} {...props} />);\n",
    )
    _toolbar_path, (_toolbar_nodes, toolbar_edges) = _parse(
        tmp_path,
        "Toolbar.tsx",
        "import { Button } from './Button';\nexport const Toolbar = () => <Button>Save</Button>;\n",
    )
    calls = [edge for edge in toolbar_edges if edge.kind == "CALLS"]
    assert any(edge.target == f"{button_path.resolve().as_posix()}::Button" for edge in calls)
    assert "Button" in _functions(button_nodes)
