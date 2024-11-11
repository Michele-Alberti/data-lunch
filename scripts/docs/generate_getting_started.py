import mkdocs_gen_files

from pathlib import Path

# Get nav dictionary from mkdocs.yml
nav = mkdocs_gen_files.Nav()

# Paths
project_root = Path(__file__).parent.parent.parent
readme_path = project_root / "README.md"
doc_getting_started_path = "getting_started.md"

# Read text
with open(readme_path, "r") as f:
    read_me_text = f.read()

# Create a ghost getting_started.md
with mkdocs_gen_files.open(doc_getting_started_path, "w") as f:
    f.write(read_me_text)
