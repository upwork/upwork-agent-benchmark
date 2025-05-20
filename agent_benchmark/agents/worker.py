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


def create_prompt(project_path: str, submission_dir: str, execution_timestamp: str) -> str:
  """Create a prompt for the agent based on project data.

  Args:
      project_path: Path to the project directory containing project.json
      submission_dir: Directory where agent will submit work deliverables
      execution_timetamp: String timestmap of when the agent run occured

  Returns:
      Formatted prompt string
  """
  # Load the project.json file
  project_data = base.load_project_json(project_path)
  project_submission_dir = os.path.join(
    submission_dir,
    execution_timestamp,
    project_data.get('category'),
    project_data.get('project_id'),
  )

  # Format the prompt
  prompt = f"""
    You are an expert Freelancer agent that uses the information included from the client to deliver work described in 
    the Project Title, Project Description, and Milestones. Put the completed work as requested by the client in the 
    appropriate sub-directory for each milestone in the submission directory. Make sure to use the tools provided to put
    the completed work in the directory. DO NOT attempt to complete the work if you do not have the correct tools or
    capabilities to complete the work as requested by the client. DO NOT simply create a report describing the work that
    should be completed, you are being hired to actually complete the work.
    
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
    {project_path}

    ## Attachments Directory
    {os.path.join(project_path, 'inputs')}

    ## Milestones
    {'\\n\\n'.join([f'Milestone {m.get("milestone_sequence")} \\n{m.get("milestone_description")}' for m in project_data.get('milestone_data')])}

    ## Submission Directory
    {project_submission_dir}
    """
  return prompt


class WorkerAgent(base.BaseUpworkAgent):
  """Agent for handling project submissions.

  This agent uses the project data to generate a prompt and complete
  the requested work for each milestone.
  """

  def __init__(
    self,
    project_dir: str,
    execution_timestamp: str,
    submission_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    llm: Optional[LLM] = None,
    max_iterations: int = 3,
  ):
    """Initialize the submission agent.

    Args:
        project_dir: Path to the project directory
        execution_timestamp: String timestamp used to save files with unique names
        submission_dir: Directory where agent will submit work deliverables (defaults to project_dir/outputs if None)
        output_dir: Optional location to write out the agent stream
        llm: Language model to use (defaults to gpt-4o-mini if None)
        max_iterations: Max iteration loops the ReActAgent goes through
    """
    # Use project_dir/outputs as default submission directory if not specified
    if submission_dir is None:
      submission_dir = os.path.join(project_dir, 'outputs')

    # Generate the prompt based on project data
    prompt = create_prompt(project_dir, submission_dir, execution_timestamp)

    # Initialize the base agent with the generated prompt
    super().__init__(
      output_dir=output_dir,
      llm=llm,
      tools=[
        input_tools.load_directory,
        output_tools.write_to_docx,
        output_tools.write_to_pdf,
        output_tools.write_to_code_file,
        output_tools.write_to_xlsx,
        output_tools.write_to_csv,
      ],
      prompt=prompt,
      max_iterations=max_iterations,
    )


@dataclass
class WorkerResult:
  """Stores results of a project submission attempt."""

  project_path: str
  success: bool
  processing_time: float

  @property
  def project_name(self):
    """Return the project basename for readability."""
    return os.path.basename(self.project_path)


class WorkerRunner:
  """Handles the process of running submission agents on projects."""

  def __init__(
    self,
    data_dir: str,
    submission_dir: str,
    limit: Optional[int] = None,
    parallelism: int = 1,
    llm: Optional[str] = None,
    timeout_seconds: int = 120,
    max_retries: int = 3,
  ):
    self.data_dir = data_dir
    self.submission_dir = submission_dir
    self.limit = limit
    self.parallelism = parallelism
    self.llm = llm
    self.timeout_seconds = timeout_seconds
    self.max_retries = max_retries
    self.stream_output = parallelism == 1

  async def run_agent_with_timeout(self, agent: WorkerAgent) -> any:
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

  async def process_project(self, project_path: str, execution_timestamp: str) -> WorkerResult:
    """Process a single project with the submission agent."""
    start_time = time.time()
    logging.info(f'Processing project: {os.path.basename(project_path)}')

    try:
      agent = WorkerAgent(
        project_dir=project_path,
        submission_dir=self.submission_dir,
        execution_timestamp=execution_timestamp,
        llm=self.llm,
      )

      # Run the agent with timeout and retry
      response = await self.run_agent_with_timeout(agent)

      # Check if the response indicates success
      success = response.response.content == 'SUCCESS'
      status = 'SUCCESS' if success else 'FAILED'
      logging.info(f'Project {os.path.basename(project_path)} submitted with status: {status}')

      return WorkerResult(
        project_path=project_path,
        success=success,
        processing_time=time.time() - start_time,
      )
    except Exception as e:
      logging.error(f'Error processing project {project_path}: {e}')
      return WorkerResult(project_path=project_path, success=False, processing_time=time.time() - start_time)

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

  def calculate_statistics(self, results: List[WorkerResult]) -> Dict:
    """Calculate statistics from project results."""
    if not results:
      return {'error': 'No results to analyze'}

    # Start timers
    start_time = getattr(self, 'start_time', time.time())
    total_time = time.time() - start_time
    successes = [r for r in results if r.success]

    # Build statistics dictionary
    stats = {
      'total_projects': len(results),
      'parallelism': self.parallelism,
      'total_processing_time': total_time,
      'successful_submissions': len(successes),
      'failed_submissions': len(results) - len(successes),
      'success_rate': len(successes) / len(results) if results else 0,
      'average_processing_time': sum(r.processing_time for r in results) / len(results),
      'results': [
        {
          'project': r.project_name,
          'success': r.success,
          'processing_time': r.processing_time,
        }
        for r in results
      ],
    }

    return stats

  def save_statistics(self, stats: Dict) -> str:
    """Save statistics to a file."""
    summary_dir = os.path.join(self.submission_dir, 'summary')
    os.makedirs(summary_dir, exist_ok=True)
    stats_file = os.path.join(summary_dir, f'submission_stats_{self.execution_timestamp}.json')

    with open(stats_file, 'w') as f:
      json.dump(stats, f, indent=2)

    return stats_file

  def log_summary(self, stats: Dict) -> None:
    """Log summary statistics."""
    logging.info(f'Completed processing {stats["total_projects"]} projects')
    logging.info(f'Execution timestamp: {self.execution_timestamp}')
    logging.info(f'Success rate: {stats["success_rate"]:.2%}')
    logging.info(f'Total processing time: {stats["total_processing_time"]:.2f} seconds')
    logging.info(f'Average processing time: {stats["average_processing_time"]:.2f} seconds')
    logging.info(f'LLM used: {self.llm if self.llm else "default"}')

  async def run(self) -> Dict:
    """Run the submission process on all projects."""
    self.start_time = time.time()
    self.execution_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Find project directories
    all_projects = self.find_projects()
    logging.info(f'Found {len(all_projects)} projects to process')
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
    self.log_summary(stats, self.execution_timestamp)
    return stats
