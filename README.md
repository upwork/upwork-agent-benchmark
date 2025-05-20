# Upwork Agent Benchmark

## Getting Started

### 1. Install software prerequisites
1. [Pyenv](https://github.com/pyenv/pyenv) for python version management
2. [Poetry](https://python-poetry.org/docs/) for python dependency management

### 2. Create and activate a virtualenv
```commandline
./scripts/venv.sh
source venv/bin/activate
```

### 3. Set env variables
```commandline
OPENAI_API_KEY=<your_openai_api_key>
FIREWORKS_API_KEY=<your_fireworks_api_key>
```

## Running the benchmark

### 1. Get the dataset
Download the dataset from <todo add link to dataset> and run the get_dataset.py script to unpack the contents in the correct location

Execute the data extraction script
```commandline
python src/create_dataset.py --tar_path=<path_to_tar_file>
```

Take note of the directory where assets are saved:
```
2025-05-16 14:37:40 - root - INFO - Extracting ~/Downloads/paper_submission.tar to data/...
```

### 2. Qualify Jobs with the qualification agent

Execute the qualify projects script, pointing to the directory where you just downloaded
data from:
```commandline
python src/qualify_projects.py --data_dir=data/raw/20250516_143205 --llm=gpt-4o-mini
```

Take note of the execution timestamp associated with this qualification run
```
2025-05-16 14:38:40 - root - INFO - Completed qualifying 12 projects
2025-05-16 14:38:40 - root - INFO - Execution timestamp: 20250516_143452
2025-05-16 14:38:40 - root - INFO - Success rate: 100.00%
2025-05-16 14:38:40 - root - INFO - Total processing time: 227.91 seconds
2025-05-16 14:38:40 - root - INFO - Average processing time: 18.99 seconds
2025-05-16 14:38:40 - root - INFO - LLM used: gpt-4o-mini
2025-05-16 14:38:40 - root - INFO - Criterion criterion_1_judgment pass rate: 63.64%
2025-05-16 14:38:40 - root - INFO - Criterion criterion_2_judgment pass rate: 36.36%
2025-05-16 14:38:40 - root - INFO - Criterion criterion_3_judgment pass rate: 72.73%
```

### 3. Transfer qualified projects to new directory
```commandline
python src/transfer_qualified_projects.py --data_dir=data/raw/20250516_143205 --dest_dir=data/qualified/20250516_143205 --qualification_execution_timestamp=20250516_143452 --criteria=criterion_1,criterion_2
```

Take note of how many projects were qualified and where they now live
```commandline
2025-05-16 14:52:32 - root - INFO - Finished transferring 7 qualified projects to data/qualified/20250516_143205
```

### 4. Submit work deliverables with the worker agent
```commandline
python src/create_submissions.py --data_dir=data/qualified/20250516_143205 --submission_dir=data/submissions/20250516_143205 --llm=gpt-4o-mini --parallelism=4
```

```commandline
2025-05-16 15:08:25 - root - INFO - Completed processing 7 projects
2025-05-16 15:08:25 - root - INFO - Execution timestamp: 20250516_150320
2025-05-16 15:08:25 - root - INFO - Success rate: 85.71%
2025-05-16 15:08:25 - root - INFO - Total processing time: 304.23 seconds
2025-05-16 15:08:25 - root - INFO - Average processing time: 43.46 seconds
2025-05-16 15:08:25 - root - INFO - LLM used: gpt-4o-mini
```
### 5. TODO: Evaluate work deliverables with the evaluation agent
