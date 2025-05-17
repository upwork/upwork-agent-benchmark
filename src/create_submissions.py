#!/usr/bin/env python
"""Script to run submission agent on projects and log completion statistics."""

import argparse
import asyncio
import logging

from agent_arena.agents.worker import WorkerRunner


def main():
  """Main entry point."""
  # Configure logging
  logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
  )

  # Parse args
  parser = argparse.ArgumentParser(description='Run submission agent on projects and log statistics')
  parser.add_argument(
    '--data_dir',
    type=str,
    required=True,
    help='Path to directory containing projects',
  )
  parser.add_argument(
    '--submission_dir',
    type=str,
    required=True,
    help='Path to directory where submissions will be placed',
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
  parser.add_argument(
    '--timeout',
    type=int,
    default=60,
    help='Maximum seconds to wait before timing out agent run',
  )
  args = parser.parse_args()

  # Create and run the worker runner
  runner = WorkerRunner(
    data_dir=args.data_dir,
    submission_dir=args.submission_dir,
    limit=args.limit,
    parallelism=args.parallelism,
    llm=args.llm,
    timeout_seconds=args.timeout,
  )
  asyncio.run(runner.run())


if __name__ == '__main__':
  main()
