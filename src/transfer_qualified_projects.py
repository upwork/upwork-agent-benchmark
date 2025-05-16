"""Transfer qualified projects to new directory for the worker agent."""

import argparse
import json
import logging
import os
import shutil

from agent_arena.agents.base import AGENT_STREAM_PREFIX
from agent_arena.agents.qualification import EVAL_FILE_PREFIX


def check_criteria(eval_file_path: str, criteria_list: list[str]):
  """Check if the project meets all specified criteria based on the evaluation JSON.

  Args:
      eval_file_path: Path to the evaluation JSON file
      criteria_list: List of criteria to check, e.g. ["criterion_1", "criterion_2"]

  Returns:
      bool: True if all criteria are met, False otherwise
  """
  # If criteria list is empty, consider all projects as qualified
  if not criteria_list:
    return True

  try:
    with open(eval_file_path, 'r') as f:
      eval_data = json.load(f)

    # Check if all specified criteria are met
    for criterion in criteria_list:
      judgment_key = f'{criterion}_judgment'
      if judgment_key not in eval_data or eval_data[judgment_key] != 'YES':
        return False

    return True
  except Exception as e:
    logging.info(f'Error reading evaluation file {eval_file_path}: {e}')
    return False


def copy_project(src_project_path: str, dest_project_path: str):
  """Copy project contents to destination, excluding outputs/ and LLM eval JSON files.

  Args:
      src_project_path: Source project directory
      dest_project_path: Destination project directory
  """
  # Create destination directory if it doesn't exist
  os.makedirs(dest_project_path, exist_ok=True)

  # Walk through source directory
  for root, dirs, files in os.walk(src_project_path):
    # Skip outputs and submissions directory
    if 'outputs' in dirs:
      dirs.remove('outputs')

    # Calculate relative path from source project
    rel_path = os.path.relpath(root, src_project_path)
    dest_dir = os.path.join(dest_project_path, rel_path) if rel_path != '.' else dest_project_path

    # Create corresponding dest directory if needed
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)

    # Copy all files except LLM eval JSON files
    for file in files:
      if not file.startswith(EVAL_FILE_PREFIX) and not file.startswith(AGENT_STREAM_PREFIX):
        src_file = os.path.join(root, file)
        dst_file = os.path.join(dest_dir, file)
        shutil.copy2(src_file, dst_file)


def process_data_directory(
  data_dir: str, qualification_execution_timestamp: str, criteria_list: list[str], dest_dir: str
):
  """Process all projects in the data directory.

  Args:
      data_dir: Directory containing projects data
      eval_json_pattern: Pattern to match evaluation JSON files
      criteria_list: List of criteria to check
      dest_dir: Destination directory for qualified projects

  Returns:
      int: Number of qualified projects that were transferred
  """
  # Create the destination directory if it doesn't exist
  os.makedirs(dest_dir, exist_ok=True)

  # Counter for qualified projects
  qualified_count = 0

  # Walk through all projects
  for root, dirs, files in os.walk(data_dir):
    # Find the evaluation JSON files that match the pattern
    eval_files = [f for f in files if f == f'{EVAL_FILE_PREFIX}_{qualification_execution_timestamp}.json']

    if eval_files:
      # Use the first matching eval file to check criteria
      eval_file_path = os.path.join(root, eval_files[0])

      if check_criteria(eval_file_path, criteria_list):
        # If all criteria are met, copy the project
        # Get the relative path from data_dir to determine the project's path structure
        rel_path = os.path.relpath(root, data_dir)
        dest_project_path = os.path.join(dest_dir, rel_path)
        logging.info(f'Project qualified, copying: {rel_path}')
        copy_project(root, dest_project_path)
        qualified_count += 1

  return qualified_count


def main():
  """Main function."""
  # Configure logging
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
  )

  # Parse args
  # Parse args
  parser = argparse.ArgumentParser(description='Transfer qualified projects based on evaluation criteria.')
  parser.add_argument('--data_dir', required=True, help='Directory containing the projects data')
  parser.add_argument(
    '--qualification_execution_timestamp',
    required=True,
    help='Timestamp from the qualification run to get judgments from',
  )
  parser.add_argument(
    '--criteria', required=True, help='Comma-separated list of criteria to check, e.g. "criterion_1,criterion_2"'
  )
  parser.add_argument('--dest_dir', required=True, help='Destination directory for qualified projects')
  args = parser.parse_args()

  # Parse criteria list
  criteria_list = args.criteria.split(',')

  # Process the data directory
  qualified_count = process_data_directory(
    args.data_dir, args.qualification_execution_timestamp, criteria_list, args.dest_dir
  )
  logging.info(f'Finished transferring {qualified_count} qualified projects to {args.dest_dir}')


if __name__ == '__main__':
  main()
