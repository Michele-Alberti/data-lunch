import mkdocs_gen_files
import re

from pathlib import Path

# Get nav dictionary from mkdocs.yml
nav = mkdocs_gen_files.Nav()

# Paths
project_root = Path(__file__).parent.parent.parent
readme_path = project_root / "README.md"
doc_getting_started_path = "getting_started.md"

# Read text
with open(readme_path, "r") as f:
    readme_text = f.read()

# Remove all text before the doc-start anchor
readme_text = re.sub(
    r'^[\s\S]*<a id="doc-start"><\/a>', r'<a id="doc-start"></a>', readme_text
)

# Hide sidebar and navigation bar
front_matter_and_title = """---
hide:
  - navigation
---

# Getting Started

"""
readme_text = front_matter_and_title + readme_text

# Create a ghost getting_started.md
with mkdocs_gen_files.open(doc_getting_started_path, "w") as f:
    f.write(readme_text)
