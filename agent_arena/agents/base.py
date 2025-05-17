"""Agent class to complete tasks on upwork with configurable components."""

import json
import os
from typing import Any, Dict, List, Optional

from llama_index.core.agent.workflow import AgentStream, ReActAgent
from llama_index.core.llms import LLM
from llama_index.core.tools import BaseTool
from llama_index.core.workflow import Context
from llama_index.llms.fireworks import Fireworks
from llama_index.llms.openai import OpenAI

from agent_arena.tools import input_tools

AGENT_STREAM_PREFIX = 'agent_stream'


def get_llm(llm_name: str) -> LLM:
  """Maps string name of llm to llama_index LLM object.

  Args:
      llm_name: String identifier for the LLM to use

  Returns:
      LLM: A configured LLM instance from llama_index

  Raises:
      ValueError: If the requested LLM is not supported
  """
  if llm_name == 'gpt-4o-mini':
    return OpenAI(model='gpt-4o-mini')
  if llm_name == 'gpt-4o':
    return OpenAI(model='gpt-4o')
  if llm_name == 'llama-v3p1-8b-instruct':
    return Fireworks(model='accounts/fireworks/models/llama-v3p1-8b-instruct')
  if llm_name == 'llama-v3p1-70b-instruct':
    return Fireworks(model='accounts/fireworks/models/llama-v3p1-70b-instruct')
  if llm_name == 'llama-v3p1-405b-instruct':
    return Fireworks(model='accounts/fireworks/models/llama-v3p1-405b-instruct')
  if llm_name == 'mixtral-8x22b-instruct':
    return Fireworks(model='accounts/fireworks/models/mixtral-8x22b-instruct')
  if llm_name == 'deepseek-v3':
    return Fireworks(model='accounts/fireworks/models/deepseek-v3')
  if llm_name == 'deepseek-r1':
    return Fireworks(model='accounts/fireworks/models/deepseek-r1')
  else:
    raise ValueError(f'Unsupported LLM: {llm_name}')


def load_project_json(project_dir: str) -> Dict[str, Any]:
  """Load project.json file from the project path.

  Args:
      project_dir: Directory containing project.json file

  Returns:
      Dictionary containing project data
  """
  with open(os.path.join(project_dir, 'project.json'), 'r') as f:
    project_data = json.load(f)
  return project_data


class BaseUpworkAgent:
  """Configurable agent for Upwork tasks.

  This class allows for experimentation with different LLMs,
  prompts, and tools for qualifying, submitting attempts on Upwork tasks, and evaluating submissions
  """

  def __init__(
    self,
    output_dir: Optional[str] = None,
    llm: Optional[str] = 'gpt-4o-mini',
    tools: Optional[List[BaseTool]] = None,
    prompt: Optional[str] = None,
    max_iterations: int = 3,
  ):
    """Initialize the Upwork agent with configurable components.

    Args:
        output_dir: optional location to write out the agent stream
        llm: Language model to use (defaults to gpt-4o-mini if None)
        tools: List of input tools (defaults to load_directory if None)
        prompt: Prompt to use instead of base prompt from reActAgent
        max_iterations: max iteration loops the reActAgent goes through
    """
    self.llm = get_llm(llm)
    self.tools = tools if tools is not None else [input_tools.load_directory]
    self.prompt = prompt
    self.max_iterations = max_iterations
    self.output_dir = output_dir

    # Create agent with tools as context
    self.agent = ReActAgent(
      tools=self.tools,
      llm=self.llm,
      max_iterations=self.max_iterations,
    )

  async def run(self, stream_output: bool = True) -> str:
    """Run the agent.

    Args:
        stream_output: Whether to stream agent output to console

    Returns:
        Agent response
    """
    # Create context to store the conversation history/session state
    ctx = Context(self.agent)
    handler = self.agent.run(self.prompt, ctx=ctx)

    # Stream events if requested
    async for ev in handler.stream_events():
      if isinstance(ev, AgentStream):
        if stream_output:
          print(f'{ev.delta}', end='', flush=True)
        if self.output_dir:
          with open(os.path.join(self.output_dir, f'{AGENT_STREAM_PREFIX}.txt'), 'a') as f:
            f.write(f'{ev.delta}')

    # Get final response
    response = await handler
    return response
