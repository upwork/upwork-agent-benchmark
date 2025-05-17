"""Tools for handling project inputs."""

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document


def load_directory(input_dir: str) -> list[Document]:
  """Load files from directory into llama-index document objects."""
  reader = SimpleDirectoryReader(input_dir=input_dir, recursive=True)
  return reader.load_data()


def summarize_documents_in_directory(input_dir: str) -> list[dict]:
  """Loads files from directory and summarizes attibutes like the file name and size."""
  reader = SimpleDirectoryReader(input_dir=input_dir, recursive=True)
  metadata = []
  for file in reader.iter_data():
    for doc in file:
      metadata.append(doc.metadata)
  return metadata


def load_file(file_path) -> list[Document]:
  """Loads a single file given an input path to the file."""
  reader = SimpleDirectoryReader(input_files=[file_path])
  return reader.load_data()
