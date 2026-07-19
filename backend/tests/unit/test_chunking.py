from src.services.chunking import chunk_source_file


def test_python_chunks_by_function_boundary():
    content = """import os

def foo():
    return 1


class Bar:
    def method(self):
        return 2
"""
    chunks = chunk_source_file("widgets/module.py", content)
    symbol_names = [c.symbol_name for c in chunks if c.symbol_name]
    assert "foo" in symbol_names
    assert "Bar" in symbol_names
    # the leading `import os` should survive as a leftover chunk
    assert any("import os" in c.text for c in chunks)


def test_python_invalid_syntax_falls_back_to_flat():
    chunks = chunk_source_file("widgets/broken.py", "def foo(:\n  pass")
    assert len(chunks) >= 1
    assert chunks[0].symbol_name is None


def test_js_chunks_by_function_and_class_boundary():
    content = """const unused = 1;

function doThing() {
  return 1;
}

class Widget {
  spin() { return true; }
}
"""
    chunks = chunk_source_file("widgets/app.ts", content)
    symbol_names = [c.symbol_name for c in chunks if c.symbol_name]
    assert "doThing" in symbol_names
    assert "Widget" in symbol_names


def test_unsupported_extension_falls_back_to_flat_chunking():
    content = "\n".join(f"line {i}" for i in range(150))
    chunks = chunk_source_file("widgets/data.yaml", content)
    assert len(chunks) > 1
    assert all(c.symbol_name is None for c in chunks)


def test_empty_file_produces_no_chunks():
    assert chunk_source_file("widgets/empty.py", "") == []
