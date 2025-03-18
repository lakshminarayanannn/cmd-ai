"""
Extraction tools for retrieving content from files and repositories.
"""

import os
import subprocess
import datetime
import requests
import pyperclip
import re
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool

from fixter.config import get_master_folder
@tool
def extract_git_content(
    git_url: str, 
    extensions: Optional[List[str]] = None, 
    clone: bool = False, 
    clipboard_only: bool = True
) -> str:
    """
    Extract content from a GitHub repository by either cloning it locally or fetching via GitHub's API.

    Args:
        git_url: The URL of the GitHub repository
        extensions: A list of file extensions to filter (e.g. [".py", ".md"])
        clone: If True, repository will be cloned locally first
        clipboard_only: If True, content will only be copied to clipboard without saving

    Returns:
        Extracted content as a string
    """
    if extensions is None:
        extensions = []

    git_url = git_url.strip().replace('"', '').replace("'", '')

    if clone:
        master = get_master_folder()
        repo_name = git_url.split('/')[-1].replace('.git', '')
        clone_dir = os.path.join(master, 'local_cloned', repo_name)
        
        subprocess.run(['git', 'clone', git_url, clone_dir], check=True)
        
        files = _get_files_from_path(clone_dir, extensions)
        if not files:
            return "No matching files found in cloned repository."

        content = _extract_content(
            files,
            output_file=None if clipboard_only else os.path.join(
                master, 'extractions', f'{repo_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            ),
            clipboard_only=clipboard_only
        )
        
        completion_message = f"""
=== REPOSITORY EXTRACTION COMPLETE ===
Repository: {git_url}
File types: {extensions if extensions else 'All files'}
Number of files found: {content.count('---- ')}
=== NO NEED TO EXTRACT AGAIN ===

"""
        return completion_message + content
    else:
        clean_url = git_url.strip()
        
        if "github.com" in clean_url:
            pattern = r"github\.com[/:]([^/]+)/([^/\",\.]+)"
            match = re.search(pattern, clean_url)
            if match:
                owner, repo = match.groups()
            else:
                parts = clean_url.split("/")
                if len(parts) >= 5:  
                    owner = parts[-2]
                    repo = parts[-1]
                else:
                    return f"Invalid GitHub URL format: {git_url}"
        else:
            parts = clean_url.split("/")
            if len(parts) >= 4:
                owner = parts[-2]
                repo = parts[-1]
            else:
                return f"Cannot extract owner/repo from URL: {git_url}"
                
        repo = repo.replace('.git', '')
        repo = re.sub(r'[^\w\-.]', '', repo)
        
        content = ""
        headers = {"User-Agent": "Fixter-Content-Extractor"}
        
        # Recursive function to fetch directory contents
        def fetch_directory_contents(path=""):
            nonlocal content
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            
            print(f"Fetching from: {api_url}")
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            items = response.json()
            
            # Handle case where response is a single file
            if not isinstance(items, list):
                items = [items]
            
            for item in items:
                if item.get('type') == 'file':
                    # Check extension filter
                    if not extensions or any(item['name'].endswith(ext) for ext in extensions):
                        download_url = item.get('download_url')
                        if download_url:
                            dl_resp = requests.get(download_url, headers=headers)
                            dl_resp.raise_for_status()
                            file_path = f"{path}/{item['name']}" if path else item['name']
                            content += f'\n---- {file_path} ----\n\n{dl_resp.text}'
                elif item.get('type') == 'dir':
                    # Recursively process subdirectory
                    subdir_path = f"{path}/{item['name']}" if path else item['name']
                    fetch_directory_contents(subdir_path)
        
        # Start fetching from root
        try:
            fetch_directory_contents()
        except requests.exceptions.RequestException as e:
            return f"Error accessing GitHub API: {str(e)}"

        if not content:
            return "No file content extracted from GitHub repository."

        pyperclip.copy(content)

        if not clipboard_only:
            master = get_master_folder()
            repo_name = f"{owner}_{repo}"
            filename = os.path.join(master, 'extractions', f'{repo_name}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as out:
                out.write(content)
        
        completion_message = f"""
=== REPOSITORY EXTRACTION COMPLETE ===
Repository: {git_url}
File types: {extensions if extensions else 'All files'}
Number of files found: {content.count('---- ')}
Extraction mode: Recursive API fetch
=== NO NEED TO EXTRACT AGAIN ===

"""
        return completion_message + "\n" + "Copied to clipboard"
@tool
def extract_content_local(directory: str, extensions: list[str] = None, clipboard_only: bool = False) -> str:
    """
    Extracts content from files in the specified directory based on the given extensions.
    
    Args:
        directory (str): Path to the directory containing files to extract.
        extensions (list[str], optional): List of file extensions to filter. Extracts all files if None.
        clipboard_only (bool, optional): If True, copies extracted content to the clipboard without saving.

    Returns:
        str: Extracted content as a single string.
    
    Example Usage:
        extract_content_local("/path/to/directory", extensions=[".txt", ".md"], clipboard_only=True)
    """
    directory = str(directory).strip().strip('"\'')
    
    directory = os.path.expanduser(directory)
    directory = os.path.abspath(directory)
    
    if not extensions:
        extensions = [".py"]
    
    if not os.path.exists(directory) or not os.path.isdir(directory):
        error_msg = f"Error: Directory '{directory}' does not exist or is not accessible."
        print(error_msg)
        return error_msg

    content = f"Extracted Content from: {directory}\n\n"
    extracted_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if not extensions or file.endswith(tuple(extensions)):
                file_path = os.path.join(root, file)
                print(f"Extracting content from: {file_path}")
                extracted_files.append(file_path)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content += f"\n---- {file_path} ----\n\n{f.read()}\n"
                except Exception as e:
                    content += f"\n---- {file_path} ----\nError reading file: {str(e)}\n"

    if not extracted_files:
        no_files_msg = f"No matching files found in '{directory}' for extensions: {extensions}"
        print(no_files_msg)
        return no_files_msg

    pyperclip.copy(content)
    print("Content copied to clipboard.")

    if not clipboard_only:
        output_dir = os.path.expanduser("~/.fixter_extractions")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"extracted_{timestamp}.txt")

        with open(output_file, 'w', encoding='utf-8') as out_file:
            out_file.write(content)
        print(f"Content saved to {output_file}")

    return "Content has been copied to clipboard" if content else "No content extracted."
def _get_files_from_path(path: str, extensions: List[str]) -> List[str]:
    """Get files from path, filtered by extensions if provided."""
    matched_files = []
    if os.path.isfile(path):
        if not extensions or any(path.endswith(ext) for ext in extensions):
            matched_files.append(path)
    else:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if not extensions or any(file_path.endswith(ext) for ext in extensions):
                    matched_files.append(file_path)
    return matched_files

def _get_directory_structure(path: str) -> str:
    """Generate a directory structure listing for a path."""
    structure = "Directory Structure:\n"
    for root, dirs, files in os.walk(path):
        level = root.replace(path, '').count(os.sep)
        indent = ' ' * 4 * level
        structure += f'{indent}{os.path.basename(root)}/\n'
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            structure += f'{subindent}{file}\n'
    return structure

def _extract_content(file_paths: List[str], output_file: Optional[str], clipboard_only: bool) -> str:
    """Extract content from file paths and optionally save to output file."""
    if not file_paths:
        return "No files to extract."
        
    content = _get_directory_structure(os.path.dirname(file_paths[0])) + "\n"
    for file in file_paths:
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content += f'\n---- {file} ----\n\n'
                content += f.read()
        except Exception as e:
            content += f'\n---- {file} ----\n\n'
            content += f"Error reading file: {str(e)}\n"
    
    pyperclip.copy(content)
    
    if not clipboard_only and output_file:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write(content)
    
    return content