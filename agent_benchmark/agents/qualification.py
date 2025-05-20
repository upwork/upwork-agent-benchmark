"""Implementation of agent used to complete work and submit for review."""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from llama_index.core.llms import LLM

from agent_benchmark.agents import base
from agent_benchmark.tools import input_tools, output_tools

EVAL_FILE_PREFIX = 'llm_eval'


def create_prompt(project_dir: str, execution_timestamp: str) -> str:
  """Create a prompt for the agent based on project data.

  Args:
      project_dir: Directory containing project.json file and all other attachments

  Returns:
      Formatted prompt string
  """
  # Load the project.json file
  project_data = base.load_project_json(project_dir)

  prompt = f"""
      You are an expert project evaluator. Analyze the project information, attachments, and deliverables and evaluate 
      each criteria independently of each other. Determine if the project meets the following criteria:

      1. The attachments contain the information described in the project description needed to complete the job and 
        there are no other properietary systems/logins needed beyond the attachments themselves. Do not accept examples 
        that say things like 'attached is a sample' because that means there is another source of information not 
        included in the attachments. If no attachments are given, then ensure the project can be completed on the 
        information in the project description alone.
      2. The milestone descriptions are well-defined and someone without context of the client or freelancer would be 
        able to understand what was agreed to.

      Create a json report called {EVAL_FILE_PREFIX}_{execution_timestamp}.json and put it in the project_dir with the following 
      structure:

      criterion_1_judgment: [YES/NO]
      criterion_1_reasoning: [Your detailed explanation]
      
      criterion_2_judgment: [YES/NO]
      criterion_2_reasoning: [Your detailed explanation]
      
      Finally respond with SUCCESS if you were able to complete the request successfully and FAILED if you were unable to 
      complete for any reason.

      ## Project Category
      Category: {project_data.get('category')}
      Sub Category: {project_data.get('subcategory')}
      Occupation: {project_data.get('occupation')}

      ## Project Title
      {project_data.get('job_title')}

      ## Project Description
      {project_data.get('job_description')}
      
      ## Project Path
      {project_dir}

      ## Attachments Directory
      {os.path.join(project_dir, 'inputs')}

      ## Deliverables Directory
      {os.path.join(project_dir, 'outputs')}
      """
  return prompt


class QualificationAgent(base.BaseUpworkAgent):
  """Agent for qualifying projects as good for the benchmark."""

  def __init__(
    self,
    project_dir: str,
    execution_timestamp: str,
    output_dir: Optional[str] = None,
    llm: Optional[LLM] = None,
    max_iterations: int = 3,
  ):
    """Initialize the Qualification agent.

    Args:
        project_dir: Path to the project directory
        execution_timestamp: string timestamp used to save files with unique names
        output_dir: Optional location to write out the agent stream
        llm: Language model to use (defaults to gpt-4o-mini if None)
        max_iterations: Max iteration loops the ReActAgent goes through
    """
    # Generate the prompt based on project data
    prompt = create_prompt(project_dir, execution_timestamp)

    # Initialize the base agent with the generated prompt
    super().__init__(
      output_dir=output_dir,
      llm=llm,
      tools=[input_tools.summarize_documents_in_directory, input_tools.load_file, output_tools.write_to_json],
      prompt=prompt,
      max_iterations=max_iterations,
    )


@dataclass
class ProjectResult:
  """Stores results of a project qualification attempt."""

  project_path: str
  success: bool
  processing_time: float
  criteria_judgments: Dict = None

  def __post_init__(self):
    if self.criteria_judgments is None:
      self.criteria_judgments = {}

  @property
  def project_name(self):
    """Return the project basename for readability."""
    return os.path.basename(self.project_path)


class QualificationRunner:
  """Handles the process of running qualification agents on projects."""

  def __init__(
    self,
    data_dir: str,
    limit: Optional[int] = None,
    parallelism: int = 1,
    llm: Optional[str] = None,
    timeout_seconds: int = 60,
    max_retries: int = 3,
  ):
    self.data_dir = data_dir
    self.limit = limit
    self.parallelism = parallelism
    self.llm = llm
    self.timeout_seconds = timeout_seconds
    self.max_retries = max_retries
    self.stream_output = parallelism == 1

  async def run_agent_with_timeout(self, agent: QualificationAgent) -> any:
    """Run the agent with a timeout and retry mechanism."""
    retry_count = 0

    while retry_count <= self.max_retries:
      try:
        return await asyncio.wait_for(agent.run(stream_output=self.stream_output), timeout=self.timeout_seconds)
      except asyncio.TimeoutError:
        retry_count += 1
        if retry_count <= self.max_retries:
          logging.warning(
            f'Agent timed out after {self.timeout_seconds} seconds. Retry {retry_count}/{self.max_retries}...'
          )
        else:
          logging.error(f'Agent failed after {self.max_retries} retries.')
          raise

  async def process_project(self, project_path: str, execution_timestamp: str) -> ProjectResult:
    """Process a single project with the qualification agent."""
    start_time = time.time()
    logging.info(f'Processing project: {os.path.basename(project_path)}')

    try:
      agent = QualificationAgent(project_dir=project_path, execution_timestamp=execution_timestamp, llm=self.llm)

      # Run the agent with timeout and retry
      response = await self.run_agent_with_timeout(agent)

      # Check if the response indicates success
      success = response.response.content == 'SUCCESS'
      status = 'SUCCESS' if success else 'FAILED'
      logging.info(f'Project {os.path.basename(project_path)} qualified with status: {status}')

      # Read the criteria judgments from json file if it exists
      criteria_judgments = {}
      eval_json_path = os.path.join(project_path, f'{EVAL_FILE_PREFIX}_{execution_timestamp}.json')
      if os.path.exists(eval_json_path):
        try:
          with open(eval_json_path, 'r') as f:
            criteria_judgments = json.load(f)
          logging.info(f'Loaded criteria judgments from {eval_json_path}')
        except Exception as e:
          logging.error(f'Error loading criteria judgments from {eval_json_path}: {e}')

      return ProjectResult(
        project_path=project_path,
        success=success,
        processing_time=time.time() - start_time,
        criteria_judgments=criteria_judgments,
      )
    except Exception as e:
      logging.error(f'Error qualifying project {project_path}: {e}')
      return ProjectResult(project_path=project_path, success=False, processing_time=time.time() - start_time)

  def find_projects(self) -> List[str]:
    """Find all project directories containing project.json."""
    projects_dir = os.path.join(self.data_dir, 'projects')
    all_projects = []

    for root, _, files in os.walk(projects_dir):
      if 'project.json' in files:
        all_projects.append(root)

    # Shuffle for better distribution
    random.shuffle(all_projects)

    # Apply limit if specified
    if self.limit:
      all_projects = all_projects[: self.limit]

    return all_projects

  def calculate_statistics(self, results: List[ProjectResult]) -> Dict:
    """Calculate statistics from project results."""
    if not results:
      return {'error': 'No results to analyze'}

    # Start timers
    start_time = getattr(self, 'start_time', time.time())
    total_time = time.time() - start_time
    successes = [r for r in results if r.success]

    # Calculate criteria statistics
    criteria_counts = {}
    criteria_passes = {}

    for result in results:
      for criterion, judgment in result.criteria_judgments.items():
        if '_judgment' in criterion:
          criteria_counts.setdefault(criterion, 0)
          criteria_passes.setdefault(criterion, 0)

          criteria_counts[criterion] += 1
          if judgment == 'YES':
            criteria_passes[criterion] += 1

    # Build statistics dictionary
    stats = {
      'total_projects': len(results),
      'parallelism': self.parallelism,
      'total_processing_time': total_time,
      'successful_qualifications': len(successes),
      'failed_qualifications': len(results) - len(successes),
      'success_rate': len(successes) / len(results) if results else 0,
      'average_processing_time': sum(r.processing_time for r in results) / len(results),
      'results': [
        {
          'project': r.project_name,
          'success': r.success,
          'processing_time': r.processing_time,
          'criteria_judgments': r.criteria_judgments,
        }
        for r in results
      ],
      'criteria_pass_rates': {
        criterion: criteria_passes[criterion] / count if count > 0 else 0
        for criterion, count in criteria_counts.items()
      },
    }

    return stats

  def save_statistics(self, stats: Dict) -> str:
    """Save statistics to a file."""
    summary_dir = os.path.join(self.data_dir, 'summary')
    os.makedirs(summary_dir, exist_ok=True)
    stats_file = os.path.join(summary_dir, f'qualification_stats_{self.execution_timestamp}.json')

    with open(stats_file, 'w') as f:
      json.dump(stats, f, indent=2)
    return stats_file

  def log_summary(self, stats: Dict) -> None:
    """Log summary statistics."""
    logging.info(f'Completed qualifying {stats["total_projects"]} projects')
    logging.info(f'Execution timestamp: {self.execution_timestamp}')
    logging.info(f'Success rate: {stats["success_rate"]:.2%}')
    logging.info(f'Total processing time: {stats["total_processing_time"]:.2f} seconds')
    logging.info(f'Average processing time: {stats["average_processing_time"]:.2f} seconds')
    logging.info(f'LLM used: {self.llm if self.llm else "default"}')

    for criterion, pass_rate in stats['criteria_pass_rates'].items():
      logging.info(f'Criterion {criterion} pass rate: {pass_rate:.2%}')

  async def run(self) -> Dict:
    """Run the qualification process on all projects."""
    self.start_time = time.time()
    self.execution_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Find project directories
    all_projects = self.find_projects()
    logging.info(f'Found {len(all_projects)} projects to qualify')
    logging.info(f'Processing with parallelism: {self.parallelism}')

    # Process projects in parallel batches
    results = []
    for i in range(0, len(all_projects), self.parallelism):
      batch = all_projects[i : i + self.parallelism]
      batch_tasks = [self.process_project(project, self.execution_timestamp) for project in batch]
      batch_results = await asyncio.gather(*batch_tasks)
      results.extend(batch_results)

    # Calculate and save statistics
    stats = self.calculate_statistics(results)
    stats_file = self.save_statistics(stats)
    logging.info(f'Statistics saved to {stats_file}')

    # Log summary
    self.log_summary(stats)
    return stats
