"""Script to unpack a local tar file for the benchmark."""

import argparse
import os
import tarfile
import logging

def extract_tarfile(tar_path, data_dir):
    """
    Extract a local tar file to the specified data directory,
    ignoring any files that start with a period.
    
    Args:
        tar_path: Path to the local tar file
        data_dir: Directory to extract the contents to
    """
    # Create the data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
    # Extract the tar file, ignoring hidden files
    logging.info(f"Extracting {tar_path} to {data_dir}...")
    with tarfile.open(tar_path, "r") as tar:
        members = [m for m in tar.getmembers() if not os.path.basename(m.name).startswith('.')]
        logging.info(f"Skipping {len(tar.getmembers()) - len(members)} hidden files")
        tar.extractall(path=data_dir, members=members)
    
    logging.info(f"Successfully extracted to {data_dir}")

def main():
    # Configure logging
    logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Parse args
    parser = argparse.ArgumentParser(description="Extract a local tar file")
    parser.add_argument(
        "--tar_path", 
        required=True,
        help="Path to the local tar file to extract"
    )
    parser.add_argument(
        "--data_dir", 
        default="data/", 
        help="Directory to extract the contents to (default: data/)"
    )
    
    args = parser.parse_args()
    extract_tarfile(args.tar_path, args.data_dir)

if __name__ == "__main__":
    main()

