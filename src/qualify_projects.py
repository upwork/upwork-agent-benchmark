#!/usr/bin/env python
"""Script to run qualification agent on projects and log qualification statistics."""

import argparse
import asyncio
import logging

from upwork_agent_benchmark.agents.qualification import QualificationRunner


def main():
  """Main entry point."""
  # Configure logging
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
  )

  # Parse args
  parser = argparse.ArgumentParser(description='Run qualification agent on projects and log statistics')
  parser.add_argument(
    '--data_dir',
    type=str,
    required=True,
    help='Path to directory containing projects',
  )
  parser.add_argument(
    '--limit',
    type=int,
    default=None,
    help='Maximum number of projects to process',
  )
  parser.add_argument(
    '--parallelism',
    type=int,
    default=1,
    help='Number of projects to process in parallel',
  )
  parser.add_argument(
    '--llm',
    type=str,
    default=None,
    help='Language model to use (if not specified, uses the default)',
  )
  args = parser.parse_args()

  # Create and run the qualification runner
  runner = QualificationRunner(data_dir=args.data_dir, limit=args.limit, parallelism=args.parallelism, llm=args.llm)
  asyncio.run(runner.run())


if __name__ == '__main__':
  main()
